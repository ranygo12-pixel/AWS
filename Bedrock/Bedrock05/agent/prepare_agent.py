"""
agent/prepare_agent.py
──────────────────────
Agent를 PREPARED 상태로 만들고 Alias를 생성합니다.

주요 함수
---------
prepare_agent(agent_id)             → None
create_alias(agent_id, alias_name)  → alias_id: str
"""

from __future__ import annotations

import time

from utils.aws_client import get_bedrock_agent_client

_PREPARE_TIMEOUT_SEC = 120
_POLL_INTERVAL_SEC = 2


def prepare_agent(agent_id: str) -> None:
    """
    Agent를 Prepare 상태로 전환합니다.
    PREPARED 상태가 될 때까지 폴링하며 대기합니다.

    Parameters
    ----------
    agent_id : str
        대상 Agent의 ID
    """
    client = get_bedrock_agent_client()

    prepare_resp = client.prepare_agent(agentId=agent_id)
    print(f"⏳ Prepare 요청 완료 — 현재 상태: {prepare_resp['agentStatus']}")

    elapsed = 0
    while elapsed < _PREPARE_TIMEOUT_SEC:
        agent_info = client.get_agent(agentId=agent_id)
        status: str = agent_info["agent"]["agentStatus"]

        if status == "PREPARED":
            print(f"✅ Agent가 PREPARED 상태가 되었습니다! (소요 시간: {elapsed}초)")
            return

        if status == "FAILED":
            reasons = agent_info["agent"].get("failureReasons", [])
            raise RuntimeError(f"❌ Prepare 실패: {reasons}")

        print(f"   ... 대기 중 ({elapsed}s) — 현재 상태: {status}")
        time.sleep(_POLL_INTERVAL_SEC)
        elapsed += _POLL_INTERVAL_SEC

    raise TimeoutError(f"❌ {_PREPARE_TIMEOUT_SEC}초 내에 PREPARED 상태에 도달하지 못했습니다.")


def create_alias(agent_id: str, alias_name: str = "dev") -> str:
    """
    Agent Alias를 생성하고 alias_id를 반환합니다.

    Parameters
    ----------
    agent_id   : str   대상 Agent ID
    alias_name : str   Alias 이름 (기본값: "dev")

    Returns
    -------
    alias_id : str
    """
    client = get_bedrock_agent_client()

    response = client.create_agent_alias(
        agentId=agent_id,
        agentAliasName=alias_name,
        description=f"{alias_name} 환경용 Alias",
    )

    alias_id: str = response["agentAlias"]["agentAliasId"]
    print(f"✅ Agent Alias 생성 완료!")
    print(f"   Alias 이름: {alias_name}")
    print(f"   Alias ID  : {alias_id}")
    return alias_id
