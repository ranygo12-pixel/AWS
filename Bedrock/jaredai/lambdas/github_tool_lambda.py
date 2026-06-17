"""
JaredAI GitHub Tool Lambda
===========================
Bedrock Agent의 post_github_comment 도구 호출 시 실행됩니다.

역할:
- 원본 GitHub Issue에 AI 분석 결과와 Jira 티켓 링크를 마크다운 댓글로 등록
"""

import json
import os
import logging
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── 환경변수 ──────────────────────────────────────────────────────────────
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")       # GitHub Personal Access Token
GITHUB_REPO_OWNER = os.environ.get("GITHUB_REPO_OWNER", "") # 예: your-org
GITHUB_REPO_NAME  = os.environ.get("GITHUB_REPO_NAME", "")  # 예: your-repo


# ── 메인 핸들러 ───────────────────────────────────────────────────────────
def lambda_handler(event, context):
    logger.info(f"GitHub Tool Lambda 호출됨: {json.dumps(event)}")

    action_group = event.get("actionGroup", "")
    api_path     = event.get("apiPath", "")
    parameters   = _extract_parameters(event)

    if api_path == "/post_github_comment":
        result = _post_github_comment(parameters)
    else:
        result = {"status": "error", "message": f"알 수 없는 apiPath: {api_path}"}

    return {
        "actionGroup": action_group,
        "apiPath":     api_path,
        "httpMethod":  event.get("httpMethod", "POST"),
        "httpStatusCode": 200 if result.get("status") == "success" else 500,
        "responseBody": {
            "application/json": {
                "body": json.dumps(result, ensure_ascii=False)
            }
        }
    }


# ── GitHub 댓글 등록 ──────────────────────────────────────────────────────
def _post_github_comment(params: dict) -> dict:
    """
    GitHub REST API를 사용해 Issue에 마크다운 댓글을 등록합니다.
    """
    issue_number  = params.get("issue_number")
    comment_body  = params.get("comment_body", "")
    jira_issue_id  = params.get("jira_issue_id", "")
    jira_issue_url = params.get("jira_issue_url", "")

    if not issue_number:
        return {"status": "error", "message": "issue_number 파라미터가 필요합니다."}

    # Jira 링크가 별도로 전달된 경우 댓글에 자동 추가
    full_comment = _build_comment(comment_body, jira_issue_id, jira_issue_url)

    try:
        response_data = _github_api_post(
            endpoint=f"/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/issues/{issue_number}/comments",
            payload={"body": full_comment},
        )

        comment_id  = response_data.get("id")
        comment_url = response_data.get("html_url", "")

        logger.info(f"GitHub 댓글 등록 성공: #{issue_number} → 댓글 ID {comment_id}")
        return {
            "status":      "success",
            "comment_id":  comment_id,
            "comment_url": comment_url,
        }

    except GitHubAPIError as e:
        logger.error(f"GitHub API 오류: {e}")
        return {"status": "error", "message": str(e)}


# ── 댓글 마크다운 빌더 ────────────────────────────────────────────────────
def _build_comment(ai_content: str, jira_issue_id: str, jira_issue_url: str) -> str:
    """
    GitHub Issue 댓글에 표시될 마크다운을 구성합니다.
    Jira 링크가 없는 경우에도 graceful하게 처리합니다.
    """
    header = "## 🤖 JaredAI 분석 결과\n\n"
    header += "> 내부 코딩 가이드라인(Knowledge Base)을 기반으로 자동 생성된 코드 초안입니다.\n> 개발자 검토 후 사용하세요.\n\n"
    header += "---\n\n"

    body = ai_content if ai_content else "_AI 분석 결과를 불러올 수 없습니다._"

    footer = "\n\n---\n\n"
    if jira_issue_id and jira_issue_url:
        footer += f"📋 **생성된 Jira 티켓:** [{jira_issue_id}]({jira_issue_url})  \n"
    footer += "_🚀 Powered by JaredAI (Amazon Bedrock + Claude)_"

    return header + body + footer


# ── GitHub REST API 호출 헬퍼 ─────────────────────────────────────────────
class GitHubAPIError(Exception):
    pass


def _github_api_post(endpoint: str, payload: dict) -> dict:
    """
    GitHub REST API v3에 POST 요청을 보냅니다.
    urllib 사용으로 외부 의존성을 제거합니다.
    """
    url  = f"https://api.github.com{endpoint}"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type":  "application/json",
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent":    "JaredAI/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise GitHubAPIError(f"GitHub API HTTP {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise GitHubAPIError(f"GitHub API 연결 실패: {e.reason}") from e


# ── 파라미터 추출 헬퍼 ────────────────────────────────────────────────────
def _extract_parameters(event: dict) -> dict:
    request_body = event.get("requestBody", {})
    if request_body:
        content      = request_body.get("content", {})
        json_content = content.get("application/json", {})
        properties   = json_content.get("properties", {})
        return {k: v.get("value") for k, v in properties.items()}

    params_list = event.get("parameters", [])
    return {p["name"]: p["value"] for p in params_list}
