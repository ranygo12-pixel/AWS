"""
agent/bedrock_agent.py
----------------------
Amazon Bedrock Agent 설정(Action Group 등록) 및 PR 분석 실행 스크립트입니다.

[실행 흐름]
  1. setup_action_group()  → Agent에 Tool(OpenAPI 스키마) 등록 + prepare
  2. run_pr_analysis()     → Agent에 자연어 프롬프트 전송 → 결과 스트리밍 출력

[Agent 자동 실행 순서 (단일 프롬프트)]
  get_github_pr       → PR 코드 획득
  analyze_complexity  → 복잡도 측정
  suggest_refactor    → 고복잡도 함수 리팩토링 제안
  generate_unit_test  → 해당 함수 테스트 자동 생성
  post_pr_comment     → 분석 결과 PR 댓글 통합 등록

[환경변수]
  BEDROCK_AGENT_ID      : Bedrock Agent ID
  BEDROCK_AGENT_ALIAS   : Bedrock Agent Alias ID
  BEDROCK_ACTION_GROUP  : Action Group ID (update 시 필요)
  UNIFIED_LAMBDA_ARN    : 모든 Tool을 처리하는 Lambda ARN
  AWS_REGION            : AWS 리전 (기본값: ap-northeast-2)
"""

import json
import logging
import os
import sys
import uuid

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

REGION = os.environ.get("AWS_REGION", "ap-northeast-2")


# ---------------------------------------------------------------------------
# OpenAPI 스키마
# ---------------------------------------------------------------------------
# Bedrock Agent는 OpenAPI 3.0 형식의 스키마로 Tool 명세를 받습니다.
# 각 path 가 하나의 Tool 에 해당하며, operationId 가 Tool 식별자입니다.

OPENAPI_SCHEMA: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Bing Code Tools", "version": "1.0.0"},
    "paths": {
        # ── Tool 1: GitHub PR 조회 ────────────────────────────────────────
        "/pr": {
            "get": {
                "operationId": "get_github_pr",
                "summary": "Get GitHub Pull Request details",
                "description": (
                    "Retrieves detailed information about a specific GitHub Pull Request. "
                    "Use this when the user asks about PR details, wants to review a PR, "
                    "or needs to analyze code changes in a pull request."
                ),
                "parameters": [
                    {
                        "name": "owner",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The GitHub repository owner/organization name",
                    },
                    {
                        "name": "repo",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The GitHub repository name",
                    },
                    {
                        "name": "pr_number",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "The Pull Request number to retrieve",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "PR details retrieved successfully",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        # ── Tool 2: PR 댓글 등록 ─────────────────────────────────────────
        "/pr/comment": {
            "post": {
                "operationId": "post_pr_comment",
                "summary": "Add a comment to a Pull Request",
                "description": (
                    "Adds a comment to a specific GitHub Pull Request. "
                    "Use this to post analysis results (complexity, refactoring, tests) "
                    "as a PR review comment."
                ),
                "parameters": [
                    {
                        "name": "owner",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Repository owner/organization",
                    },
                    {
                        "name": "repo",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Repository name",
                    },
                    {
                        "name": "pr_number",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "Pull Request number",
                    },
                    {
                        "name": "comment",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The comment text to post (Markdown supported)",
                    },
                ],
                "responses": {
                    "200": {"description": "Comment added successfully"}
                },
            }
        },
        # ── Tool 3: 코드 복잡도 분석 ─────────────────────────────────────
        "/complexity": {
            "post": {
                "operationId": "analyze_complexity",
                "summary": "Analyze code cyclomatic complexity",
                "description": (
                    "Analyzes Python code and returns cyclomatic complexity scores. "
                    "Use this to identify overly complex functions that need refactoring. "
                    "Returns summary (avg, max, high-complexity list) and per-function details."
                ),
                "parameters": [
                    {
                        "name": "code",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The Python source code to analyze",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Complexity analysis results",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "summary": {"type": "object"},
                                        "details": {"type": "array"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        # ── Tool 4: 단위 테스트 자동 생성 ───────────────────────────────
        "/unittest": {
            "post": {
                "operationId": "generate_unit_test",
                "summary": "Generate pytest unit tests for a Python function",
                "description": (
                    "Automatically generates comprehensive pytest unit test code "
                    "for a given Python function. Includes normal cases, boundary values, "
                    "and exception handling tests."
                ),
                "parameters": [
                    {
                        "name": "code",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The Python function code to generate tests for",
                    },
                    {
                        "name": "function_name",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Specific function name to focus on (optional)",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Generated test code",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        # ── Tool 5: 리팩토링 제안 ────────────────────────────────────────
        "/refactor": {
            "post": {
                "operationId": "suggest_refactor",
                "summary": "Suggest code refactoring improvements",
                "description": (
                    "Analyzes Python code and provides refactoring suggestions "
                    "with improved code examples. Focus can be set to readability, "
                    "performance, or maintainability."
                ),
                "parameters": [
                    {
                        "name": "code",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The Python code to refactor",
                    },
                    {
                        "name": "focus",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "enum": ["readability", "performance", "maintainability"],
                        },
                        "description": "Refactoring focus area (default: maintainability)",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Refactoring suggestion",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
    },
}


# ---------------------------------------------------------------------------
# Action Group 등록 / 업데이트
# ---------------------------------------------------------------------------

def setup_action_group(
    agent_id: str,
    action_group_id: str,
    lambda_arn: str,
) -> None:
    """
    Bedrock Agent에 Bing Code Action Group(Tool 5종)을 등록하고 prepare 합니다.

    이미 존재하는 Action Group을 update_agent_action_group 으로 갱신합니다.
    변경 후 반드시 prepare_agent 를 호출해야 Agent가 새 스키마를 인식합니다.
    """
    client = boto3.client("bedrock-agent", region_name=REGION)

    logger.info("Action Group 업데이트 중 (agentId=%s) ...", agent_id)
    client.update_agent_action_group(
        agentId=agent_id,
        agentVersion="DRAFT",
        actionGroupId=action_group_id,
        actionGroupName="CodeAnalysisTools",
        actionGroupExecutor={"lambda": lambda_arn},
        apiSchema={"payload": json.dumps(OPENAPI_SCHEMA)},
        actionGroupState="ENABLED",
    )

    logger.info("prepare_agent 호출 중 ...")
    client.prepare_agent(agentId=agent_id)
    logger.info("✅ Action Group 등록 완료.")


# ---------------------------------------------------------------------------
# PR 분석 실행
# ---------------------------------------------------------------------------

def run_pr_analysis(
    agent_id: str,
    alias_id: str,
    owner: str,
    repo: str,
    pr_number: int,
) -> str:
    """
    Agent에 PR 전체 분석 프롬프트를 전송하고 스트리밍 결과를 반환합니다.

    단일 자연어 프롬프트로 Agent가 아래 순서를 자율적으로 실행합니다:
      1. get_github_pr        → PR 코드 획득
      2. analyze_complexity   → 복잡도 측정
      3. suggest_refactor     → 리팩토링 제안
      4. generate_unit_test   → 테스트 생성
      5. post_pr_comment      → PR 댓글 등록
    """
    runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)

    prompt = f"""
다음 GitHub PR을 시니어 개발자 관점에서 자동 분석해주세요.

저장소: {owner}/{repo}
PR 번호: #{pr_number}

[수행 단계]
1. get_github_pr 를 호출해 PR 변경 코드를 가져오세요.
2. analyze_complexity 로 복잡도가 높은 함수(복잡도 > 10)를 찾아주세요.
3. suggest_refactor 로 복잡도 상위 함수의 리팩토링 방안을 제안하세요.
4. generate_unit_test 로 해당 함수의 pytest 테스트 코드를 생성하세요.
5. post_pr_comment 로 아래 형식의 댓글을 PR에 등록하세요.

[PR 댓글 형식]
## 🤖 Bing Code 자동 분석 결과

### 📊 복잡도 분석
| 함수명 | 복잡도 | 등급 | 권장 조치 |
|--------|--------|------|-----------|
| ...    | ...    | ...  | ...       |

### 🔧 리팩토링 제안
{{리팩토링 제안 내용}}

### ✅ 생성된 단위 테스트
```python
{{테스트 코드}}
```
"""

    session_id = f"pr-analysis-{pr_number}-{uuid.uuid4().hex[:8]}"
    logger.info("Agent 호출 시작 (sessionId=%s)", session_id)

    response = runtime.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id,
        inputText=prompt,
        enableTrace=True,
    )

    full_output: list[str] = []
    for event in response["completion"]:
        if "chunk" in event:
            chunk_text = event["chunk"]["bytes"].decode("utf-8")
            full_output.append(chunk_text)
            print(chunk_text, end="", flush=True)
        if "trace" in event:
            trace = event["trace"].get("trace", {})
            if "orchestrationTrace" in trace:
                orch = trace["orchestrationTrace"]
                if "invocationInput" in orch:
                    inv = orch["invocationInput"].get("actionGroupInvocationInput", {})
                    logger.debug("Tool 호출: %s %s", inv.get("actionGroupName"), inv.get("apiPath"))

    print()  # 개행
    return "".join(full_output)


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bing Code PR 자동 분석")
    subparsers = parser.add_subparsers(dest="command")

    # setup 서브커맨드
    setup_p = subparsers.add_parser("setup", help="Action Group 등록")
    setup_p.add_argument("--agent-id",        required=True)
    setup_p.add_argument("--action-group-id", required=True)
    setup_p.add_argument("--lambda-arn",      required=True)

    # analyze 서브커맨드
    analyze_p = subparsers.add_parser("analyze", help="PR 분석 실행")
    analyze_p.add_argument("--agent-id",   required=True)
    analyze_p.add_argument("--alias-id",   required=True)
    analyze_p.add_argument("--owner",      required=True)
    analyze_p.add_argument("--repo",       required=True)
    analyze_p.add_argument("--pr-number",  required=True, type=int)

    args = parser.parse_args()

    if args.command == "setup":
        setup_action_group(args.agent_id, args.action_group_id, args.lambda_arn)
    elif args.command == "analyze":
        run_pr_analysis(
            args.agent_id, args.alias_id,
            args.owner, args.repo, args.pr_number,
        )
    else:
        parser.print_help()
        sys.exit(1)
