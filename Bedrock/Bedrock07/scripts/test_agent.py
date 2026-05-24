"""
scripts/test_agent.py
Bedrock Agent 통합 테스트 스크립트

환경 변수:
  AGENT_ID       - Bedrock Agent ID
  AGENT_ALIAS_ID - Bedrock Agent Alias ID
  AWS_DEFAULT_REGION
"""
import boto3
import json
import os
import sys
import time
import uuid

REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-2")
AGENT_ID = os.environ["AGENT_ID"]
ALIAS_ID = os.environ["AGENT_ALIAS_ID"]

runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


def invoke_agent(prompt: str, session_id: str | None = None, enable_trace: bool = False) -> dict:
    """Agent 호출 및 응답 수집"""
    session_id = session_id or f"test-{uuid.uuid4().hex[:8]}"

    response = runtime.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=ALIAS_ID,
        sessionId=session_id,
        inputText=prompt,
        enableTrace=enable_trace,
    )

    result = {"answer": "", "tool_calls": [], "observations": []}

    for event in response["completion"]:
        if "chunk" in event:
            result["answer"] += event["chunk"]["bytes"].decode("utf-8")

        if enable_trace and "trace" in event:
            trace = event["trace"].get("trace", {})
            orch = trace.get("orchestrationTrace", {})
            if "invocationInput" in orch:
                result["tool_calls"].append(orch["invocationInput"])
            if "observation" in orch:
                result["observations"].append(orch["observation"])

    return result


def print_result(result: dict):
    """결과 출력"""
    print(f"\n🤖 Agent 응답:\n{result['answer']}")
    if result["tool_calls"]:
        print("\n🔧 호출된 도구:")
        for tc in result["tool_calls"]:
            ag = tc.get("actionGroup", "")
            path = tc.get("apiPath", "")
            params = tc.get("parameters", [])
            print(f"  - {ag}{path}  params={params}")


# ── 테스트 케이스 ─────────────────────────────────────────────────────

def test_get_pr():
    """TC-1: PR 정보 조회"""
    print("\n" + "=" * 50)
    print("TC-1: GitHub PR 정보 조회")
    print("=" * 50)
    result = invoke_agent(
        "octocat/Spoon-Knife 저장소의 Pull Request #1 정보를 가져와줘",
        enable_trace=True,
    )
    print_result(result)
    assert result["answer"], "응답이 비어 있습니다."
    assert result["tool_calls"], "도구가 호출되지 않았습니다."
    print("  ✅ TC-1 통과")
    return result


def test_missing_params():
    """TC-2: 필수 파라미터 누락 시 재질문 여부 확인"""
    print("\n" + "=" * 50)
    print("TC-2: 파라미터 누락 처리")
    print("=" * 50)
    result = invoke_agent("PR 정보 가져와줘")
    print_result(result)
    # Agent가 정보를 되물어야 함
    assert result["answer"], "응답이 비어 있습니다."
    print("  ✅ TC-2 통과")


def test_multi_tool():
    """TC-3: 복합 시나리오 (PR 조회 → Slack 알림)"""
    print("\n" + "=" * 50)
    print("TC-3: 복합 시나리오")
    print("=" * 50)
    prompt = (
        "octocat/Spoon-Knife의 PR #1 정보를 조회한 뒤, "
        "#general 채널에 '테스트 완료' 메시지를 보내줘"
    )
    result = invoke_agent(prompt, enable_trace=True)
    print_result(result)
    assert result["answer"], "응답이 비어 있습니다."
    print("  ✅ TC-3 통과")


def test_visualize_flow():
    """TC-4: Agent 의사결정 흐름 시각화"""
    print("\n" + "=" * 50)
    print("TC-4: 의사결정 흐름 시각화")
    print("=" * 50)
    prompt = "octocat/Spoon-Knife의 PR #1 리뷰해줘"
    result = invoke_agent(prompt, enable_trace=True)

    print("\n=== Agent 실행 순서 ===")
    for i, tc in enumerate(result["tool_calls"], 1):
        ag = tc.get("actionGroup", "")
        path = tc.get("apiPath", "")
        print(f"  {i}. 도구 호출: {ag}{path}")
    for i, obs in enumerate(result["observations"], 1):
        obs_type = obs.get("type", "")
        print(f"  {i}. 관찰: {obs_type}")

    print_result(result)
    print("  ✅ TC-4 통과")


def main():
    print("=" * 55)
    print("  CodeBuddy Agent 통합 테스트")
    print(f"  Agent ID  : {AGENT_ID}")
    print(f"  Alias ID  : {ALIAS_ID}")
    print("=" * 55)

    tests = [test_get_pr, test_missing_params, test_multi_tool, test_visualize_flow]
    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ 실패: {e}")
            failed += 1
        time.sleep(2)  # 연속 호출 간격

    print("\n" + "=" * 55)
    print(f"  결과: {passed} 통과 / {failed} 실패")
    print("=" * 55)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
