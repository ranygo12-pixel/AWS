"""
JaredAI Orchestrator Lambda
============================
GitHub Webhook → API Gateway → 이 Lambda → Bedrock Agent 호출

역할:
1. GitHub Webhook 서명(HMAC-SHA256) 검증
2. Issue 이벤트 필터링 (opened / reopened만 처리)
3. Bedrock Agent 호출 및 결과 반환
"""

import json
import hmac
import hashlib
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── 환경변수 (Lambda 콘솔 또는 Secrets Manager에서 주입) ──────────────────
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
BEDROCK_AGENT_ID      = os.environ.get("BEDROCK_AGENT_ID", "")
BEDROCK_AGENT_ALIAS   = os.environ.get("BEDROCK_AGENT_ALIAS", "TSTALIASID")
AWS_REGION            = os.environ.get("AWS_REGION", "us-east-1")

bedrock_agent_runtime = boto3.client(
    "bedrock-agent-runtime", region_name=AWS_REGION
)


# ── 메인 핸들러 ───────────────────────────────────────────────────────────
def lambda_handler(event, context):
    logger.info("JaredAI Orchestrator 시작")

    # 1. GitHub Webhook 서명 검증
    if not _verify_github_signature(event):
        logger.warning("서명 검증 실패 - 요청 거부")
        return _response(403, {"error": "Invalid signature"})

    # 2. 요청 바디 파싱
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    # 3. Issue 이벤트만 처리 (PR, 댓글 등 제외)
    github_event = event.get("headers", {}).get("X-GitHub-Event", "")
    if github_event != "issues":
        logger.info(f"무시된 이벤트: {github_event}")
        return _response(200, {"message": f"Ignored event: {github_event}"})

    action = body.get("action", "")
    if action not in ("opened", "reopened"):
        logger.info(f"무시된 액션: {action}")
        return _response(200, {"message": f"Ignored action: {action}"})

    # 4. Issue 정보 추출
    issue = body.get("issue", {})
    repo  = body.get("repository", {})

    issue_number = issue.get("number")
    issue_title  = issue.get("title", "")
    issue_body   = issue.get("body", "")
    issue_url    = issue.get("html_url", "")
    repo_owner   = repo.get("owner", {}).get("login", "")
    repo_name    = repo.get("name", "")

    logger.info(f"처리 중인 Issue: #{issue_number} - {issue_title}")

    # 5. Bedrock Agent에게 전달할 프롬프트 구성
    agent_prompt = _build_agent_prompt(
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body,
        issue_url=issue_url,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )

    # 6. Bedrock Agent 호출
    try:
        agent_response = _invoke_bedrock_agent(
            session_id=f"jaredai-{repo_name}-issue-{issue_number}",
            prompt=agent_prompt,
        )
        logger.info("Bedrock Agent 호출 성공")
        return _response(200, {
            "message": "JaredAI 처리 완료",
            "issue_number": issue_number,
            "agent_response": agent_response,
        })

    except Exception as e:
        logger.error(f"Bedrock Agent 호출 실패: {e}")
        return _response(500, {"error": "Bedrock Agent 호출 실패", "detail": str(e)})


# ── GitHub HMAC-SHA256 서명 검증 ──────────────────────────────────────────
def _verify_github_signature(event: dict) -> bool:
    """
    GitHub이 보낸 X-Hub-Signature-256 헤더를 검증합니다.
    환경변수 GITHUB_WEBHOOK_SECRET이 없으면 개발 편의상 통과합니다.
    """
    if not GITHUB_WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET 미설정 - 서명 검증 건너뜀 (개발 환경)")
        return True

    headers   = event.get("headers", {})
    signature = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256", "")
    raw_body  = event.get("body", "")

    if not signature:
        return False

    expected = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


# ── Bedrock Agent 프롬프트 구성 ───────────────────────────────────────────
def _build_agent_prompt(
    issue_number: int,
    issue_title: str,
    issue_body: str,
    issue_url: str,
    repo_owner: str,
    repo_name: str,
) -> str:
    """
    Bedrock Agent에게 전달할 지시 프롬프트를 구성합니다.
    Knowledge Base(RAG) 검색을 유도하고 Tool 사용 순서를 명시합니다.
    """
    return f"""
당신은 JaredAI입니다. GitHub Issue를 분석하여 코드 초안을 생성하고,
Jira 티켓 등록 → GitHub 댓글 등록 → Slack 알림 순서로 작업을 완료하세요.

## GitHub Issue 정보
- 저장소: {repo_owner}/{repo_name}
- Issue 번호: #{issue_number}
- Issue URL: {issue_url}
- 제목: {issue_title}
- 내용:
{issue_body}

## 수행할 작업 (순서 엄수)
1. Knowledge Base에서 관련 코딩 가이드라인과 보안 정책을 검색하세요.
2. 검색 결과를 바탕으로 요구사항을 분석하고 파이썬 코드 초안을 작성하세요.
   - PEP8 준수, 타입 힌트 포함, docstring 필수
   - 보안 취약점(SQL Injection, 하드코딩 등) 없을 것
3. create_jira_issue 도구를 호출하여 Jira 티켓을 생성하세요.
   - 제목: "[AI 제안] {issue_title}"
   - 본문: 코드 초안 + 구현 가이드라인 포함
4. post_github_comment 도구를 호출하여 #{issue_number} Issue에 댓글을 등록하세요.
   - 코드 초안과 Jira 티켓 링크 포함 (마크다운 형식)
5. send_slack_notification 도구를 호출하여 개발팀에 완료 알림을 보내세요.

모든 작업을 순서대로 완료한 뒤 처리 결과를 요약하여 보고하세요.
""".strip()


# ── Bedrock Agent 호출 ────────────────────────────────────────────────────
def _invoke_bedrock_agent(session_id: str, prompt: str) -> str:
    """
    Bedrock Agent Runtime을 호출하고 스트리밍 응답을 취합하여 반환합니다.
    """
    response = bedrock_agent_runtime.invoke_agent(
        agentId=BEDROCK_AGENT_ID,
        agentAliasId=BEDROCK_AGENT_ALIAS,
        sessionId=session_id,
        inputText=prompt,
    )

    # 스트리밍 이벤트 취합
    result_text = ""
    for event in response.get("completion", []):
        chunk = event.get("chunk", {})
        if "bytes" in chunk:
            result_text += chunk["bytes"].decode("utf-8")

    return result_text


# ── 공통 응답 헬퍼 ────────────────────────────────────────────────────────
def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }
