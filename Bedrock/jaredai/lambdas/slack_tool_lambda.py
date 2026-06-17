"""
JaredAI Slack Tool Lambda
==========================
Bedrock Agent의 send_slack_notification 도구 호출 시 실행됩니다.

역할:
- 모든 연동(Jira, GitHub) 완료 후 개발팀 Slack 채널에 요약 알림 전송
- Slack Block Kit 형식으로 가독성 높은 메시지 구성
"""

import json
import os
import logging
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── 환경변수 ──────────────────────────────────────────────────────────────
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")    # xoxb-... 형식
SLACK_CHANNEL   = os.environ.get("SLACK_CHANNEL", "#dev-team")  # 예: #dev-jaredai


# ── 메인 핸들러 ───────────────────────────────────────────────────────────
def lambda_handler(event, context):
    logger.info(f"Slack Tool Lambda 호출됨: {json.dumps(event)}")

    action_group = event.get("actionGroup", "")
    api_path     = event.get("apiPath", "")
    parameters   = _extract_parameters(event)

    if api_path == "/send_slack_notification":
        result = _send_slack_notification(parameters)
    else:
        result = {"status": "error", "message": f"알 수 없는 apiPath: {api_path}"}

    return {
        "actionGroup":    action_group,
        "apiPath":        api_path,
        "httpMethod":     event.get("httpMethod", "POST"),
        "httpStatusCode": 200 if result.get("status") == "success" else 500,
        "responseBody": {
            "application/json": {
                "body": json.dumps(result, ensure_ascii=False)
            }
        }
    }


# ── Slack 알림 전송 ───────────────────────────────────────────────────────
def _send_slack_notification(params: dict) -> dict:
    """
    Slack Web API chat.postMessage를 사용해 Block Kit 메시지를 전송합니다.
    """
    github_issue_number = params.get("github_issue_number", "?")
    github_issue_title  = params.get("github_issue_title", "제목 없음")
    github_issue_url    = params.get("github_issue_url", "")
    jira_issue_id       = params.get("jira_issue_id", "")
    jira_issue_url      = params.get("jira_issue_url", "")
    summary             = params.get("summary", "AI 분석 및 Jira 이관이 완료되었습니다.")

    blocks = _build_slack_blocks(
        github_issue_number=github_issue_number,
        github_issue_title=github_issue_title,
        github_issue_url=github_issue_url,
        jira_issue_id=jira_issue_id,
        jira_issue_url=jira_issue_url,
        summary=summary,
    )

    payload = {
        "channel":   SLACK_CHANNEL,
        "text":      f"🚀 [JaredAI] GitHub Issue #{github_issue_number} 분석 완료",
        "blocks":    blocks,
        "unfurl_links": False,
    }

    try:
        response_data = _slack_api_post("/api/chat.postMessage", payload)

        if not response_data.get("ok"):
            error_msg = response_data.get("error", "알 수 없는 Slack 오류")
            logger.error(f"Slack API 오류: {error_msg}")
            return {"status": "error", "message": error_msg}

        message_ts = response_data.get("ts", "")
        logger.info(f"Slack 알림 전송 성공: ts={message_ts}")
        return {"status": "success", "message_ts": message_ts}

    except SlackAPIError as e:
        logger.error(f"Slack 연결 오류: {e}")
        return {"status": "error", "message": str(e)}


# ── Slack Block Kit 메시지 빌더 ───────────────────────────────────────────
def _build_slack_blocks(
    github_issue_number: int | str,
    github_issue_title: str,
    github_issue_url: str,
    jira_issue_id: str,
    jira_issue_url: str,
    summary: str,
) -> list:
    """
    Slack Block Kit 형식으로 풍부한 알림 메시지를 구성합니다.
    """
    github_link = (
        f"<{github_issue_url}|#{github_issue_number} {github_issue_title}>"
        if github_issue_url
        else f"#{github_issue_number} {github_issue_title}"
    )
    jira_link = (
        f"<{jira_issue_url}|{jira_issue_id}>"
        if jira_issue_url and jira_issue_id
        else jira_issue_id or "생성 실패"
    )

    return [
        # 헤더
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚀 JaredAI — 신규 이슈 AI 분석 완료",
                "emoji": True,
            },
        },
        {"type": "divider"},

        # 핵심 정보 섹션
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*GitHub Issue*\n{github_link}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Jira 티켓*\n{jira_link}  _(상태: To-Do)_",
                },
            ],
        },

        # AI 요약
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📝 AI 분석 요약*\n{summary}",
            },
        },
        {"type": "divider"},

        # CTA 버튼
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "GitHub Issue 보기", "emoji": True},
                    "url":   github_issue_url or "#",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Jira 티켓 보기", "emoji": True},
                    "url":   jira_issue_url or "#",
                },
            ],
        },

        # 푸터
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_🤖 Powered by JaredAI (Amazon Bedrock + Claude Sonnet) — 개발자 검토를 시작해주세요._",
                }
            ],
        },
    ]


# ── Slack Web API 호출 헬퍼 ───────────────────────────────────────────────
class SlackAPIError(Exception):
    pass


def _slack_api_post(endpoint: str, payload: dict) -> dict:
    """
    Slack Web API에 POST 요청을 보냅니다.
    """
    url  = f"https://slack.com{endpoint}"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type":  "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise SlackAPIError(f"Slack API HTTP {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise SlackAPIError(f"Slack API 연결 실패: {e.reason}") from e


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
