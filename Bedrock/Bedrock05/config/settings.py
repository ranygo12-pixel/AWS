"""
config/settings.py
──────────────────
환경 변수를 로드하고 프로젝트 전역 설정을 제공합니다.
.env 파일 또는 시스템 환경 변수에서 값을 읽습니다.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── AWS 기본 설정 ──────────────────────────────────────────────────────────────
AWS_REGION: str = os.getenv("AWS_REGION", "ap-northeast-2")
AWS_ACCOUNT_ID: str = os.getenv("AWS_ACCOUNT_ID", "")

# ── Agent 설정 ─────────────────────────────────────────────────────────────────
AGENT_NAME: str = os.getenv("AGENT_NAME", "CodeBuddy-Reviewer")
AGENT_DESCRIPTION: str = os.getenv("AGENT_DESCRIPTION", "코드 리뷰 및 보안 분석 에이전트")
FOUNDATION_MODEL: str = os.getenv("FOUNDATION_MODEL", "global.anthropic.claude-sonnet-4-6")
AGENT_ROLE_ARN: str = os.getenv(
    "AGENT_ROLE_ARN",
    f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/AmazonBedrockAgentServiceRole",
)

# ── Knowledge Base ─────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_ID: str = os.getenv("KNOWLEDGE_BASE_ID", "")

# ── 저장된 Agent / Alias ID ────────────────────────────────────────────────────
AGENT_ID: str = os.getenv("AGENT_ID", "")
AGENT_ALIAS_ID: str = os.getenv("AGENT_ALIAS_ID", "")

# ── Agent Instruction ──────────────────────────────────────────────────────────
AGENT_INSTRUCTION: str = """\
당신은 시니어 개발자이자 코드 리뷰 전문가입니다.

## 역할
- Python, JavaScript, Java 코드 리뷰를 수행합니다.
- 버그, 보안 취약점, 스타일 위반을 찾습니다.

## 행동 규칙
1. 코드를 받으면 반드시 Knowledge Base를 참고하여 검사합니다.
2. 발견된 문제는 심각도(높음/중간/낮음)와 함께 보고합니다.
3. 수정 제안은 구체적인 코드 예시를 포함합니다.

## 출력 형식
🔴 높은 심각도
[라인번호] 문제: 설명

수정 제안: 코드 예시

🟡 중간 심각도
...

🔵 낮은 심각도
...

## 제약사항
- 모르는 내용은 "정보 부족"이라고 답변합니다.
- 보안 취약점은 반드시 보고합니다.
"""
