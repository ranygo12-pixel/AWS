"""
Lambda 함수: GitHub Pull Request 정보 조회
- Bedrock Agent Action Group에서 호출됨
- PyGithub를 사용하여 PR 상세 정보 반환
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

        # 필수 파라미터 검증
        if not all([owner, repo_name, pr_number]):
            raise ValueError("Missing required parameters: owner, repo, pr_number")

        # GitHub API 호출
        g = Github(os.environ["GITHUB_TOKEN"])
        repo = g.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(int(pr_number))

        response_body = {
            "title": pr.title,
            "body": pr.body or "",
            "state": pr.state,
            "author": pr.user.login,
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "changed_files": pr.changed_files,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "diff_url": pr.diff_url,
        }

        return _build_success_response(event, response_body)

    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        return _build_error_response(
            event, f"GitHub API error: {e.data.get('message', str(e))}", 404
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
