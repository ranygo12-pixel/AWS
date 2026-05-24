"""
Lambda 함수: GitHub Pull Request에 댓글 추가
- Bedrock Agent Action Group에서 호출됨
- PyGithub를 사용하여 PR에 이슈 댓글 생성
"""
import json
import os
import logging
from github import Github, GithubException

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Bedrock Agent가 전달한 파라미터 추출
        parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}

        owner = parameters.get("owner")
        repo_name = parameters.get("repo")
        pr_number = parameters.get("pr_number")
        comment = parameters.get("comment")

        # 필수 파라미터 검증
        if not all([owner, repo_name, pr_number, comment]):
            raise ValueError("Missing required parameters: owner, repo, pr_number, comment")

        # GitHub API 호출
        g = Github(os.environ["GITHUB_TOKEN"])
        repo = g.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(int(pr_number))
        created_comment = pr.create_issue_comment(comment)

        response_body = {
            "success": True,
            "message": f"Comment added to PR #{pr_number}",
            "comment_id": created_comment.id,
            "comment_url": created_comment.html_url,
            "pr_url": pr.html_url,
        }

        return _build_success_response(event, response_body)

    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        return _build_error_response(
            event, f"GitHub API error: {e.data.get('message', str(e))}", 400
        )
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
