"""
Tool: github_pr
---------------
GitHub Pull Request 정보를 조회하고 분석 결과를 PR 댓글로 등록합니다.

[제공 기능]
  get_pr      : PR 번호로 파일 목록·변경 코드(diff) 조회
  post_comment: 분석 결과를 PR 댓글로 등록

[인증]
  GITHUB_TOKEN 환경변수에서 Personal Access Token을 읽습니다.
  GitHub Actions 환경에서는 secrets.GITHUB_TOKEN 을 사용하세요.

[Lambda 이벤트 형식] (Amazon Bedrock Agent Action Group)
  GET  /pr         → get_github_pr
    파라미터: owner, repo, pr_number
  POST /pr/comment → post_pr_comment
    파라미터: owner, repo, pr_number, comment
"""

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GITHUB_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# GitHub API 헬퍼
# ---------------------------------------------------------------------------

def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "GITHUB_TOKEN 환경변수가 설정되지 않았습니다. "
            "GitHub Secrets 또는 Lambda 환경변수를 확인하세요."
        )
    return token


def _github_request(
    path: str,
    method: str = "GET",
    payload: dict | None = None,
) -> dict:
    """
    GitHub REST API를 호출합니다.

    urllib 를 사용해 외부 의존성 없이 구현합니다.
    응답 코드가 2xx 가 아니면 RuntimeError를 발생시킵니다.
    """
    url = f"{GITHUB_API}{path}"
    token = _get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }

    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        raise RuntimeError(
            f"GitHub API 오류 [{exc.code}]: {body}"
        ) from exc


# ---------------------------------------------------------------------------
# PR 조회
# ---------------------------------------------------------------------------

def get_pr(owner: str, repo: str, pr_number: int) -> dict:
    """
    PR 기본 정보·변경 파일 목록·파일별 패치(diff)를 조회합니다.

    반환 구조:
      {
        "pr_info":  { title, state, user, created_at, body },
        "files":    [{ filename, status, additions, deletions, patch }, ...],
        "raw_code": "파일별 패치(diff) 전체 텍스트"
      }
    """
    pr_info_raw = _github_request(f"/repos/{owner}/{repo}/pulls/{pr_number}")
    files_raw = _github_request(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")

    pr_info = {
        "title": pr_info_raw.get("title"),
        "state": pr_info_raw.get("state"),
        "user": pr_info_raw.get("user", {}).get("login"),
        "created_at": pr_info_raw.get("created_at"),
        "body": pr_info_raw.get("body"),
    }

    files = [
        {
            "filename": f.get("filename"),
            "status": f.get("status"),
            "additions": f.get("additions"),
            "deletions": f.get("deletions"),
            "patch": f.get("patch", ""),   # diff 텍스트
        }
        for f in files_raw
    ]

    # 분석 Tool에 전달하기 편하도록 패치 전체를 하나의 문자열로 합칩니다.
    raw_code = "\n\n".join(
        f"# --- {f['filename']} ---\n{f['patch']}"
        for f in files
        if f["patch"]
    )

    return {"pr_info": pr_info, "files": files, "raw_code": raw_code}


# ---------------------------------------------------------------------------
# PR 댓글 등록
# ---------------------------------------------------------------------------

def post_comment(owner: str, repo: str, pr_number: int, comment: str) -> dict:
    """
    PR에 댓글을 등록하고 생성된 댓글 URL을 반환합니다.

    Agent Instruction 에 따라 분석 결과를 아래 형식으로 등록합니다.
      ## 🤖 Bing Code 자동 분석 결과
      ### 📊 복잡도 분석 ...
      ### 🔧 리팩토링 제안 ...
      ### ✅ 단위 테스트 ...
    """
    payload = {"body": comment}
    result = _github_request(
        f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
        method="POST",
        payload=payload,
    )
    return {"comment_url": result.get("html_url"), "comment_id": result.get("id")}


# ---------------------------------------------------------------------------
# 응답 헬퍼
# ---------------------------------------------------------------------------

def _build_response(event: dict, status_code: int, body: dict) -> dict:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "httpStatusCode": status_code,
            "responseBody": {
                "application/json": {"body": body}
            },
        },
    }


# ---------------------------------------------------------------------------
# Lambda 핸들러
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:  # noqa: ANN001
    """
    Bedrock Agent Action Group 진입점.

    apiPath 에 따라 기능을 분기합니다.
      GET  /pr         → get_pr
      POST /pr/comment → post_comment
    """
    logger.info("github_pr 이벤트 수신: %s", json.dumps(event))
    api_path = event.get("apiPath", "")
    http_method = event.get("httpMethod", "GET").upper()

    try:
        params = {p["name"]: p["value"] for p in event.get("parameters", [])}
        owner = params.get("owner", "").strip()
        repo = params.get("repo", "").strip()
        pr_number_raw = params.get("pr_number", "0")
        pr_number = int(pr_number_raw)

        if not owner or not repo or pr_number <= 0:
            raise ValueError("owner, repo, pr_number 는 필수 파라미터입니다.")

        if api_path == "/pr" and http_method == "GET":
            body = get_pr(owner, repo, pr_number)

        elif api_path == "/pr/comment" and http_method == "POST":
            comment = params.get("comment", "").strip()
            if not comment:
                raise ValueError("'comment' 파라미터가 비어 있습니다.")
            body = post_comment(owner, repo, pr_number, comment)

        else:
            raise ValueError(f"지원하지 않는 apiPath/httpMethod: {api_path} {http_method}")

        return _build_response(event, 200, body)

    except Exception as exc:  # noqa: BLE001
        logger.error("github_pr 오류: %s", exc)
        return _build_response(event, 500, {"error": str(exc)})
