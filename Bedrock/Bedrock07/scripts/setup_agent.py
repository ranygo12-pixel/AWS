"""
scripts/setup_agent.py
Bedrock Agent 및 Action Group 설정 스크립트

환경 변수 (GitHub Secrets에서 주입):
  AWS_DEFAULT_REGION              - AWS 리전
  AGENT_ROLE_ARN                  - Bedrock Agent 실행 역할 ARN
  CODEBUDDY_GITHUB_PR_ARN         - get_pr Lambda ARN
  CODEBUDDY_GITHUB_PR_COMMENT_ARN - post_comment Lambda ARN
  CODEBUDDY_SLACK_NOTIFIER_ARN    - slack_notifier Lambda ARN
  AGENT_ID        (선택)          - 기존 Agent 재사용 시
  AGENT_ALIAS_ID  (선택)          - 기존 Alias 재사용 시
"""
import boto3
import botocore.exceptions
import json
import os
import time
from pathlib import Path

REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-2")
AGENT_ROLE_ARN = os.environ["AGENT_ROLE_ARN"]
FOUNDATION_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"

PR_LAMBDA_ARN = os.environ["CODEBUDDY_GITHUB_PR_ARN"]
COMMENT_LAMBDA_ARN = os.environ["CODEBUDDY_GITHUB_PR_COMMENT_ARN"]
SLACK_LAMBDA_ARN = os.environ["CODEBUDDY_SLACK_NOTIFIER_ARN"]

EXISTING_AGENT_ID = os.environ.get("AGENT_ID", "")
EXISTING_ALIAS_ID = os.environ.get("AGENT_ALIAS_ID", "")

bedrock_agent = boto3.client("bedrock-agent", region_name=REGION)

SCHEMA_DIR = Path("agent/schemas")
INSTRUCTION_FILE = Path("agent/instructions.txt")

# Action Group 정의 (schema 파일 + Lambda ARN 매핑)
ACTION_GROUPS = [
    {
        "name": "GitHubPRViewer",
        "schema_file": "github_pr_schema.json",
        "lambda_arn": PR_LAMBDA_ARN,
        "description": "GitHub PR 정보 조회 도구",
    },
    {
        "name": "GitHubPRCommenter",
        "schema_file": "github_comment_schema.json",
        "lambda_arn": COMMENT_LAMBDA_ARN,
        "description": "GitHub PR 댓글 추가 도구",
    },
    {
        "name": "SlackNotifier",
        "schema_file": "slack_schema.json",
        "lambda_arn": SLACK_LAMBDA_ARN,
        "description": "Slack 메시지 전송 도구",
    },
]


def wait_for_agent(agent_id: str, target_status: str = "NOT_PREPARED", max_wait: int = 120):
    """Agent가 목표 상태가 될 때까지 대기"""
    terminal = {"PREPARED", "FAILED", "NOT_PREPARED"}
    for i in range(max_wait):
        info = bedrock_agent.get_agent(agentId=agent_id)["agent"]
        status = info["agentStatus"]
        if status == target_status or (target_status == "PREPARED" and status == "PREPARED"):
            print(f"  ✅ Agent 상태: {status} ({i+1}초)")
            return status
        if status == "FAILED":
            raise RuntimeError(f"Agent 상태 FAILED: {info}")
        time.sleep(1)
    raise TimeoutError(f"Agent가 {target_status} 상태가 되지 않았습니다.")


def create_or_get_agent() -> str:
    """Agent 생성 또는 기존 Agent ID 반환"""
    if EXISTING_AGENT_ID:
        print(f"  ⚠️  기존 Agent 사용: {EXISTING_AGENT_ID}")
        return EXISTING_AGENT_ID

    instruction = INSTRUCTION_FILE.read_text(encoding="utf-8")

    resp = bedrock_agent.create_agent(
        agentName="CodeBuddy",
        agentResourceRoleArn=AGENT_ROLE_ARN,
        foundationModel=FOUNDATION_MODEL,
        instruction=instruction,
        description="GitHub PR 코드 리뷰 및 Slack 알림 AI 어시스턴트",
    )
    agent_id = resp["agent"]["agentId"]
    print(f"  ✅ Agent 생성: {agent_id}")
    wait_for_agent(agent_id, "NOT_PREPARED")
    return agent_id


def list_action_groups(agent_id: str) -> dict:
    """현재 Action Group 목록 조회 {name: id}"""
    resp = bedrock_agent.list_agent_action_groups(agentId=agent_id, agentVersion="DRAFT")
    return {ag["actionGroupName"]: ag["actionGroupId"] for ag in resp.get("agentActionGroupSummaries", [])}


def upsert_action_group(agent_id: str, cfg: dict, existing: dict):
    """Action Group 생성 또는 업데이트"""
    schema_payload = (SCHEMA_DIR / cfg["schema_file"]).read_text(encoding="utf-8")
    name = cfg["name"]

    common_kwargs = dict(
        agentId=agent_id,
        agentVersion="DRAFT",
        actionGroupName=name,
        actionGroupExecutor={"lambda": cfg["lambda_arn"]},
        apiSchema={"payload": schema_payload},
        actionGroupState="ENABLED",
        description=cfg["description"],
    )

    if name in existing:
        bedrock_agent.update_agent_action_group(
            actionGroupId=existing[name], **common_kwargs
        )
        print(f"  ✅ Action Group 업데이트: {name}")
    else:
        bedrock_agent.create_agent_action_group(**common_kwargs)
        print(f"  ✅ Action Group 생성: {name}")


def prepare_agent(agent_id: str):
    """Agent Prepare 실행"""
    print("\n[3] Agent Prepare 중...")
    bedrock_agent.prepare_agent(agentId=agent_id)
    wait_for_agent(agent_id, "PREPARED")


def create_or_update_alias(agent_id: str) -> str:
    """Agent Alias 생성 또는 업데이트"""
    if EXISTING_ALIAS_ID:
        bedrock_agent.update_agent_alias(
            agentId=agent_id,
            agentAliasId=EXISTING_ALIAS_ID,
            agentAliasName="dev",
            description="Updated by GitHub Actions",
        )
        print(f"  ✅ Alias 업데이트: {EXISTING_ALIAS_ID}")
        return EXISTING_ALIAS_ID

    resp = bedrock_agent.create_agent_alias(
        agentId=agent_id,
        agentAliasName="dev",
        description="Created by GitHub Actions",
    )
    alias_id = resp["agentAlias"]["agentAliasId"]
    print(f"  ✅ Alias 생성: {alias_id}")
    return alias_id


def main():
    print("=" * 55)
    print("  CodeBuddy Bedrock Agent 설정")
    print("=" * 55)

    # 1. Agent 생성/조회
    print("\n[1] Agent 생성/조회 중...")
    agent_id = create_or_get_agent()

    # 2. Action Groups 설정
    print("\n[2] Action Groups 설정 중...")
    existing = list_action_groups(agent_id)
    for cfg in ACTION_GROUPS:
        upsert_action_group(agent_id, cfg, existing)

    # 3. Prepare
    prepare_agent(agent_id)

    # 4. Alias
    print("\n[4] Alias 설정 중...")
    alias_id = create_or_update_alias(agent_id)

    print("\n" + "=" * 55)
    print("설정 완료! 아래 값을 GitHub Secrets에 저장하세요:")
    print(f"  AGENT_ID       = {agent_id}")
    print(f"  AGENT_ALIAS_ID = {alias_id}")
    print("=" * 55)

    # GitHub Actions outputs 저장
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"agent_id={agent_id}\n")
            f.write(f"alias_id={alias_id}\n")


if __name__ == "__main__":
    main()
