"""
agent/create_agent.py
─────────────────────
Bedrock Agent를 생성하거나 기존 Agent를 업데이트합니다.

주요 함수
---------
get_or_create_agent() → agent_id: str
    - 동일한 이름의 Agent가 있으면 설정을 업데이트하고 ID를 반환합니다.
    - 없으면 새로 생성하고 ID를 반환합니다.
"""

from __future__ import annotations

from config.settings import (
    AGENT_DESCRIPTION,
    AGENT_INSTRUCTION,
    AGENT_NAME,
    AGENT_ROLE_ARN,
    FOUNDATION_MODEL,
)
from utils.aws_client import get_bedrock_agent_client


def _find_existing_agent(client, agent_name: str) -> str | None:
    """이름이 일치하는 Agent의 ID를 반환합니다. 없으면 None."""
    paginator = client.get_paginator("list_agents")
    for page in paginator.paginate():
        for summary in page.get("agentSummaries", []):
            if summary["agentName"] == agent_name:
                return summary["agentId"]
    return None


def _create_agent(client) -> str:
    """새 Agent를 생성하고 ID를 반환합니다."""
    response = client.create_agent(
        agentName=AGENT_NAME,
        agentResourceRoleArn=AGENT_ROLE_ARN,
        instruction=AGENT_INSTRUCTION,
        foundationModel=FOUNDATION_MODEL,
        description=AGENT_DESCRIPTION,
    )
    agent_id: str = response["agent"]["agentId"]
    print(f"✅ Agent '{AGENT_NAME}' 생성 완료 — ID: {agent_id}")
    return agent_id


def _update_agent(client, agent_id: str) -> None:
    """기존 Agent의 설정을 업데이트합니다."""
    client.update_agent(
        agentId=agent_id,
        agentName=AGENT_NAME,
        agentResourceRoleArn=AGENT_ROLE_ARN,
        instruction=AGENT_INSTRUCTION,
        foundationModel=FOUNDATION_MODEL,
        description=AGENT_DESCRIPTION,
    )
    print(f"✅ Agent '{AGENT_NAME}' (ID: {agent_id}) 업데이트 완료")


def get_or_create_agent() -> str:
    """Agent를 가져오거나 생성한 뒤 agent_id를 반환합니다."""
    client = get_bedrock_agent_client()

    try:
        agent_id = _find_existing_agent(client, AGENT_NAME)

        if agent_id:
            print(f"🔍 기존 Agent 발견: '{AGENT_NAME}' (ID: {agent_id})")
            _update_agent(client, agent_id)
        else:
            print(f"🆕 Agent '{AGENT_NAME}' 미발견 — 새로 생성합니다.")
            agent_id = _create_agent(client)

        return agent_id

    except Exception as e:
        print(f"❌ Agent 생성/업데이트 오류: {e}")
        if "AccessDeniedException" in str(e):
            print(
                "HINT: IAM Role에 'bedrock:InvokeModel' 등 필요한 권한이 있는지 확인하세요. "
                f"(Role: {AGENT_ROLE_ARN})"
            )
        raise
