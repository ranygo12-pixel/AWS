"""
JaredAI Jira Tool Lambda
=========================
Bedrock Agent의 create_jira_issue 도구 호출 시 실행됩니다.

역할:
- Jira Cloud REST API를 통해 신규 To-Do 티켓 생성
- 생성된 티켓 ID와 URL을 Agent에게 반환
"""

import json
import os
import logging
import urllib.request
import urllib.error
import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── 환경변수 ──────────────────────────────────────────────────────────────
JIRA_BASE_URL   = os.environ.get("JIRA_BASE_URL", "")       # 예: https://yourorg.atlassian.net
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "PROJ")
JIRA_USER_EMAIL  = os.environ.get("JIRA_USER_EMAIL", "")
JIRA_API_TOKEN   = os.environ.get("JIRA_API_TOKEN", "")     # Atlassian API 토큰


# ── 메인 핸들러 ───────────────────────────────────────────────────────────
def lambda_handler(event, context):
    """
    Bedrock Agent Action Group이 호출하는 엔트리포인트.
    Agent는 api_spec.yaml의 스키마대로 파라미터를 전달합니다.
    """
    logger.info(f"Jira Tool Lambda 호출됨: {json.dumps(event)}")

    # Bedrock Agent Action Group 이벤트 파싱
    action_group = event.get("actionGroup", "")
    api_path     = event.get("apiPath", "")
    parameters   = _extract_parameters(event)

    logger.info(f"Action: {action_group}, Path: {api_path}, Params: {parameters}")

    if api_path == "/create_jira_issue":
        result = _create_jira_issue(parameters)
    else:
        result = {"status": "error", "message": f"알 수 없는 apiPath: {api_path}"}

    # Bedrock Agent Action Group 응답 포맷
    return {
        "actionGroup": action_group,
        "apiPath": api_path,
        "httpMethod": event.get("httpMethod", "POST"),
        "httpStatusCode": 200 if result.get("status") == "success" else 500,
        "responseBody": {
            "application/json": {
                "body": json.dumps(result, ensure_ascii=False)
            }
        }
    }


# ── Jira 티켓 생성 ────────────────────────────────────────────────────────
def _create_jira_issue(params: dict) -> dict:
    """
    Jira Cloud REST API v3를 사용해 이슈를 생성합니다.
    """
    summary     = params.get("summary", "")
    description = params.get("description", "")
    github_issue_number = params.get("github_issue_number")
    github_issue_url    = params.get("github_issue_url", "")

    if not summary:
        return {"status": "error", "message": "summary 파라미터가 필요합니다."}

    # Jira ADF(Atlassian Document Format) 형식으로 description 구성
    adf_description = _build_adf_description(description, github_issue_number, github_issue_url)

    payload = {
        "fields": {
            "project":     {"key": JIRA_PROJECT_KEY},
            "summary":     summary,
            "description": adf_description,
            "issuetype":   {"name": "Task"},
            "labels":      ["JaredAI", "AI-Generated"],
        }
    }

    try:
        response_data = _jira_api_post("/rest/api/3/issue", payload)
        issue_key = response_data.get("key", "")
        issue_id  = response_data.get("id", "")
        issue_url = f"{JIRA_BASE_URL}/browse/{issue_key}"

        logger.info(f"Jira 티켓 생성 성공: {issue_key}")
        return {
            "status":        "success",
            "jira_issue_id": issue_key,
            "jira_issue_url": issue_url,
            "raw_id":        issue_id,
        }

    except JiraAPIError as e:
        logger.error(f"Jira API 오류: {e}")
        return {"status": "error", "message": str(e)}


# ── Jira ADF Description 빌더 ─────────────────────────────────────────────
def _build_adf_description(
    ai_content: str,
    github_issue_number: int | None,
    github_issue_url: str,
) -> dict:
    """
    Atlassian Document Format(ADF)으로 티켓 본문을 구성합니다.
    일반 마크다운은 Jira가 인식하지 못하므로 ADF 변환이 필요합니다.
    """
    nodes = []

    # GitHub Issue 링크 섹션
    if github_issue_number:
        nodes.append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "🔗 GitHub Issue: ", "marks": [{"type": "strong"}]},
                {
                    "type": "text",
                    "text": f"#{github_issue_number}",
                    "marks": [{"type": "link", "attrs": {"href": github_issue_url}}],
                },
            ],
        })

    # AI 생성 코드 초안 섹션
    nodes.append({
        "type": "heading",
        "attrs": {"level": 2},
        "content": [{"type": "text", "text": "🤖 JaredAI 분석 결과"}],
    })

    # 코드 블록 감지: ```python ... ``` 패턴 처리
    if "```" in ai_content:
        parts = ai_content.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # 일반 텍스트
                if part.strip():
                    nodes.append({
                        "type": "paragraph",
                        "content": [{"type": "text", "text": part.strip()}],
                    })
            else:
                # 코드 블록
                lang = "python"
                code_content = part
                if part.startswith("python\n"):
                    code_content = part[7:]
                nodes.append({
                    "type": "codeBlock",
                    "attrs": {"language": lang},
                    "content": [{"type": "text", "text": code_content.strip()}],
                })
    else:
        nodes.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": ai_content}],
        })

    # 푸터
    nodes.append({
        "type": "paragraph",
        "content": [
            {
                "type": "text",
                "text": "⚠️ 이 티켓은 JaredAI가 자동 생성했습니다. 개발자 검토 후 진행하세요.",
                "marks": [{"type": "em"}],
            }
        ],
    })

    return {"type": "doc", "version": 1, "content": nodes}


# ── Jira REST API 호출 헬퍼 ───────────────────────────────────────────────
class JiraAPIError(Exception):
    pass


def _jira_api_post(endpoint: str, payload: dict) -> dict:
    """
    Jira Cloud REST API에 POST 요청을 보냅니다.
    외부 라이브러리 없이 urllib만 사용합니다 (Lambda 경량화).
    """
    url = f"{JIRA_BASE_URL}{endpoint}"

    # Basic Auth: email:api_token을 base64 인코딩
    credentials = f"{JIRA_USER_EMAIL}:{JIRA_API_TOKEN}"
    auth_header  = base64.b64encode(credentials.encode()).decode()

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise JiraAPIError(f"Jira API HTTP {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise JiraAPIError(f"Jira API 연결 실패: {e.reason}") from e


# ── 파라미터 추출 헬퍼 (Bedrock Agent 이벤트 파싱) ────────────────────────
def _extract_parameters(event: dict) -> dict:
    """
    Bedrock Agent Action Group 이벤트에서 파라미터를 딕셔너리로 추출합니다.
    requestBody 또는 parameters 배열 두 형식을 모두 지원합니다.
    """
    # 방식 1: requestBody JSON (api_spec.yaml의 POST body)
    request_body = event.get("requestBody", {})
    if request_body:
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        properties = json_content.get("properties", {})
        return {k: v.get("value") for k, v in properties.items()}

    # 방식 2: parameters 배열 (일부 Agent 버전)
    params_list = event.get("parameters", [])
    return {p["name"]: p["value"] for p in params_list}
