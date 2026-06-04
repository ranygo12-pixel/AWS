"""
Orchestrator Lambda
API Gateway 요청을 받아 Bedrock Agent를 실행하고 응답을 반환합니다.
"""

import json
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

bedrock_agent_runtime = boto3.client(
    "bedrock-agent-runtime",
    region_name=os.environ.get("AWS_REGION", "ap-northeast-2"),
)


def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        body = json.loads(event.get("body", "{}"))

        pr_url = body.get("pr_url")
        action = body.get("action", "review")

        if not pr_url:
            return respond(400, {"error": "Missing pr_url"})

        owner, repo, pr_number = parse_pr_url(pr_url)
        prompt = build_prompt(owner, repo, pr_number, action)

        agent_id = os.environ["AGENT_ID"]
        alias_id = os.environ["ALIAS_ID"]

        response = bedrock_agent_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=alias_id,
            sessionId=f"webhook-{pr_number}",
            inputText=prompt,
            enableTrace=False,
        )

        result_text = ""
        for event_chunk in response["completion"]:
            if "chunk" in event_chunk:
                result_text += event_chunk["chunk"]["bytes"].decode("utf-8")

        return respond(200, {"result": result_text, "status": "completed"})

    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        return respond(500, {"error": f"Server misconfiguration: {e}"})
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return respond(500, {"error": str(e)})


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """
    GitHub PR URL에서 owner, repo, pr_number를 추출합니다.
    예: https://github.com/owner/repo/pull/123
    """
    parts = pr_url.rstrip("/").split("/")
    pr_number = int(parts[-1])
    repo = parts[-2]
    owner = parts[-3]
    return owner, repo, pr_number


def build_prompt(owner: str, repo: str, pr_number: int, action: str = "review") -> str:
    """Agent에 전달할 프롬프트를 생성합니다."""
    return f"""
다음 GitHub Pull Request를 리뷰해주세요:

저장소: {owner}/{repo}
PR 번호: {pr_number}
작업: {action}

분석 항목:
- 코드 스타일 위반
- 보안 취약점
- 복잡도가 높은 함수
- 필요한 테스트 코드
""".strip()


def respond(status_code: int, body: dict) -> dict:
    """API Gateway 형식의 응답을 반환합니다."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }
