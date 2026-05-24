"""
Lambda 함수: Slack 채널에 메시지 전송
- Bedrock Agent Action Group에서 호출됨
- Slack Incoming Webhook을 사용하여 메시지 전송
"""
import json
import os
import logging
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Bedrock Agent가 전달한 파라미터 추출
        parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}

        channel = parameters.get("channel")
        message = parameters.get("message")

        # 필수 파라미터 검증
        if not channel or not message:
            raise ValueError("Missing required parameters: channel, message")

        # Slack Webhook URL (Lambda 환경 변수)
        webhook_url = os.environ["SLACK_WEBHOOK_URL"]

        # Slack 메시지 페이로드 구성
        payload = {"text": message, "channel": channel}
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Slack Webhook 호출 (외부 라이브러리 없이 urllib 사용)
        req = urllib.request.Request(
            webhook_url,
            data=payload_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req) as response:
            resp_body = response.read().decode("utf-8")
            logger.info(f"Slack response: {resp_body}")

        response_body = {
            "success": True,
            "message": f"Slack message sent to {channel}",
        }

        return _build_success_response(event, response_body)

    except urllib.error.HTTPError as e:
        error_msg = f"Slack Webhook HTTP error: {e.code} {e.reason}"
        logger.error(error_msg)
        return _build_error_response(event, error_msg, 400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return _build_error_response(event, str(e), 500)


def _build_success_response(event, response_body):
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "httpStatusCode": 200,
            "responseBody": {"application/json": {"body": response_body}},
        },
    }


def _build_error_response(event, error_msg, status_code):
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "httpStatusCode": status_code,
            "responseBody": {"application/json": {"body": {"error": error_msg}}},
        },
    }
