"""
main.py
───────
CodeBuddy Reviewer — 실행 진입점

사용법
------
# 전체 셋업 (Agent 생성 → KB 연결 → Prepare → Alias 생성)
python main.py --setup

# 코드 파일을 읽어 리뷰 요청
python main.py --review path/to/code.py

# 직접 프롬프트 입력
python main.py --prompt "안녕? 너는 어떤 역할을 하는 Agent야?"

# 트레이스(디버그) 모드
python main.py --prompt "Python 변수명 규칙은?" --trace
"""

from __future__ import annotations

import argparse
import os
import sys

# ── 패키지 루트를 sys.path에 추가 ───────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from agent.create_agent import get_or_create_agent
from agent.invoke_agent import inspect_agent_thinking, invoke_agent
from agent.prepare_agent import create_alias, prepare_agent
from config.settings import AGENT_ALIAS_ID, AGENT_ID, KNOWLEDGE_BASE_ID
from knowledge_base.associate_kb import associate_knowledge_base


# ── .env 파일 업데이트 헬퍼 ────────────────────────────────────────────────────
def _update_env_file(key: str, value: str, env_path: str = ".env") -> None:
    """
    .env 파일에서 특정 키의 값을 업데이트합니다.
    키가 없으면 줄을 추가합니다.
    """
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write(f"{key}={value}\n")
        return

    with open(env_path, "r") as f:
        lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break

    if not updated:
        lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)

    print(f"📝 .env 파일 업데이트: {key}={value}")


# ── 셋업 플로우 ────────────────────────────────────────────────────────────────
def run_setup() -> tuple[str, str]:
    """
    Agent 전체 셋업을 순서대로 실행합니다.

    순서: 생성/업데이트 → KB 연결 → Prepare → Alias 생성

    Returns
    -------
    (agent_id, alias_id)
    """
    print("=" * 55)
    print("  CodeBuddy Reviewer — Agent 셋업 시작")
    print("=" * 55)

    # 1. Agent 생성 또는 업데이트
    agent_id = get_or_create_agent()

    # 2. Knowledge Base 연결 (KB ID가 있는 경우)
    associate_knowledge_base(agent_id, KNOWLEDGE_BASE_ID)

    # 3. Prepare
    prepare_agent(agent_id)

    # 4. Alias 생성
    alias_id = create_alias(agent_id, alias_name="dev")

    # 5. .env에 ID 저장
    _update_env_file("AGENT_ID", agent_id)
    _update_env_file("AGENT_ALIAS_ID", alias_id)

    print("\n🎉 셋업 완료!")
    print(f"   AGENT_ID     : {agent_id}")
    print(f"   AGENT_ALIAS_ID: {alias_id}")
    return agent_id, alias_id


# ── 리뷰 플로우 ────────────────────────────────────────────────────────────────
def run_review(file_path: str, agent_id: str, alias_id: str) -> None:
    """파일을 읽어 Agent에게 코드 리뷰를 요청합니다."""
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    ext = os.path.splitext(file_path)[1].lstrip(".")
    lang_map = {"py": "python", "js": "javascript", "java": "java"}
    lang = lang_map.get(ext, ext)

    prompt = (
        f"다음 {lang} 코드를 리뷰해주세요:\n\n"
        f"```{lang}\n{code}\n```\n\n"
        "버그, 보안 취약점, 스타일 문제를 찾아주세요."
    )

    print(f"\n📄 파일: {file_path} ({len(code)} chars)")
    print("🤖 CodeBuddy Agent 코드 리뷰 결과:\n")
    result = invoke_agent(agent_id, alias_id, prompt, session_id="code-review-session")
    print(result)


# ── 프롬프트 플로우 ────────────────────────────────────────────────────────────
def run_prompt(prompt: str, agent_id: str, alias_id: str, trace: bool = False) -> None:
    """직접 입력한 프롬프트로 Agent를 호출합니다."""
    print("🤖 Agent 응답:\n")
    if trace:
        inspect_agent_thinking(agent_id, alias_id, prompt)
    else:
        result = invoke_agent(agent_id, alias_id, prompt)
        print(result)


# ── CLI ────────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CodeBuddy Reviewer — AWS Bedrock Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--setup", action="store_true", help="Agent 전체 셋업 실행")
    parser.add_argument("--review", metavar="FILE", help="코드 파일 리뷰 요청")
    parser.add_argument("--prompt", metavar="TEXT", help="직접 프롬프트 입력")
    parser.add_argument(
        "--trace", action="store_true", help="트레이스(디버그) 모드 활성화"
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    # --review / --prompt 는 AGENT_ID, AGENT_ALIAS_ID가 필요합니다.
    agent_id = AGENT_ID
    alias_id = AGENT_ALIAS_ID

    if not agent_id or not alias_id:
        print(
            "❌ AGENT_ID 또는 AGENT_ALIAS_ID가 설정되지 않았습니다.\n"
            "   먼저 'python main.py --setup'을 실행하거나 .env에 값을 입력하세요."
        )
        sys.exit(1)

    if args.review:
        run_review(args.review, agent_id, alias_id)
    elif args.prompt:
        run_prompt(args.prompt, agent_id, alias_id, trace=args.trace)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
