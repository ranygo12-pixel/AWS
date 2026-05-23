"""
agent/invoke_agent.py
─────────────────────
Bedrock Agent를 호출하는 함수 모음.

주요 함수
---------
invoke_agent(agent_id, alias_id, prompt, session_id)
    → 응답 전체 문자열 반환 (스트리밍을 내부에서 조립)

invoke_agent_with_trace(agent_id, alias_id, prompt, session_id)
    → 트레이스(Agent 생각 과정)를 출력하며 응답 반환

inspect_agent_thinking(agent_id, alias_id, prompt, session_id)
    → 전처리/오케스트레이션 트레이스를 단계별로 출력
"""

from __future__ import annotations

from utils.aws_client import get_bedrock_agent_runtime_client


def _decode_stream(completion_stream) -> str:
    """스트리밍 이벤트를 하나의 문자열로 조립합니다."""
    parts: list[str] = []
    for event in completion_stream:
        if "chunk" in event:
            parts.append(event["chunk"]["bytes"].decode("utf-8"))
    return "".join(parts)


def invoke_agent(
    agent_id: str,
    alias_id: str,
    prompt: str,
    session_id: str = "default-session",
) -> str:
    """
    Agent를 호출하고 응답 문자열을 반환합니다.

    Parameters
    ----------
    agent_id   : str
    alias_id   : str
    prompt     : str   사용자 입력 텍스트
    session_id : str   대화 세션 ID (다중 턴 유지에 사용)

    Returns
    -------
    str  Agent의 전체 응답
    """
    client = get_bedrock_agent_runtime_client()

    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id,
        inputText=prompt,
        enableTrace=False,
    )
    return _decode_stream(response["completion"])


def invoke_agent_with_trace(
    agent_id: str,
    alias_id: str,
    prompt: str,
    session_id: str = "trace-session",
) -> str:
    """
    트레이스를 출력하면서 Agent를 호출합니다.
    디버깅·개발 환경에서 Agent의 추론 과정을 확인할 때 사용합니다.

    Returns
    -------
    str  Agent의 전체 응답
    """
    client = get_bedrock_agent_runtime_client()

    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id,
        inputText=prompt,
        enableTrace=True,
    )

    full_response = ""
    for event in response["completion"]:
        if "trace" in event:
            print("🔍 Agent 생각:", event["trace"])
        elif "chunk" in event:
            chunk = event["chunk"]["bytes"].decode("utf-8")
            full_response += chunk

    return full_response


def inspect_agent_thinking(
    agent_id: str,
    alias_id: str,
    prompt: str,
    session_id: str = "inspect-session",
) -> str:
    """
    전처리(preProcessing) 및 오케스트레이션(orchestration) 트레이스를
    단계별로 보기 좋게 출력합니다.

    Returns
    -------
    str  Agent의 전체 응답
    """
    client = get_bedrock_agent_runtime_client()

    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id,
        inputText=prompt,
        enableTrace=True,
    )

    full_response = ""
    for event in response["completion"]:
        if "trace" in event:
            trace_info = event["trace"].get("trace", {})

            if "preProcessingTrace" in trace_info:
                pre = trace_info["preProcessingTrace"]
                print("📝 [전처리] 사용자 입력 해석:")
                print(f"   {pre.get('rationale', 'N/A')}")

            if "orchestrationTrace" in trace_info:
                orch = trace_info["orchestrationTrace"]
                print("\n🧠 [계획 수립] Agent의 생각:")
                print(f"   {orch.get('rationale', 'N/A')}")

        elif "chunk" in event:
            chunk = event["chunk"]["bytes"].decode("utf-8")
            full_response += chunk

    print("\n💬 [최종 응답]:")
    print(full_response)
    return full_response
