"""
knowledge_base/associate_kb.py
──────────────────────────────
Agent에 Knowledge Base를 연결합니다.

주요 함수
---------
associate_knowledge_base(agent_id, kb_id)  → None
"""

from __future__ import annotations

from utils.aws_client import get_bedrock_agent_client


def associate_knowledge_base(
    agent_id: str,
    kb_id: str,
    description: str = "코드 스타일 및 보안 규칙",
) -> None:
    """
    DRAFT 버전의 Agent에 Knowledge Base를 연결합니다.
    이미 연결된 경우 AWS API가 오류를 반환할 수 있으므로
    ConflictException을 무시하도록 처리합니다.

    Parameters
    ----------
    agent_id    : str   대상 Agent ID
    kb_id       : str   연결할 Knowledge Base ID
    description : str   KB 설명 (Agent가 참고 목적 이해에 사용)
    """
    if not kb_id:
        print("⚠️  KNOWLEDGE_BASE_ID가 설정되지 않아 KB 연결을 건너뜁니다.")
        return

    client = get_bedrock_agent_client()

    try:
        client.associate_agent_knowledge_base(
            agentId=agent_id,
            agentVersion="DRAFT",
            knowledgeBaseId=kb_id,
            description=description,
            knowledgeBaseState="ENABLED",
        )
        print(f"✅ Knowledge Base 연결 완료: {kb_id}")
    except client.exceptions.ConflictException:
        print(f"ℹ️  Knowledge Base '{kb_id}'는 이미 연결되어 있습니다.")
    except Exception as e:
        print(f"❌ Knowledge Base 연결 오류: {e}")
        raise
