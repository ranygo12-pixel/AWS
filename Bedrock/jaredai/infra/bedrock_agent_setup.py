"""
JaredAI Bedrock Agent Setup Script
====================================
최초 1회 실행으로 Bedrock Agent + Knowledge Base를 구성합니다.

실행 방법:
    python bedrock_agent_setup.py

사전 조건:
    - AWS CLI 자격증명 설정 완료
    - .env 파일에 환경변수 설정
    - S3 버킷에 knowledge_base/ 문서 업로드 완료
    - Lambda 함수들 배포 완료 (deploy.sh 실행 후)
"""

import boto3
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

# ── 설정값 ────────────────────────────────────────────────────────────────
AWS_REGION       = os.environ.get("AWS_REGION", "us-east-1")
AWS_ACCOUNT_ID   = os.environ.get("AWS_ACCOUNT_ID", "")
S3_BUCKET_NAME   = os.environ.get("S3_BUCKET_NAME", "")            # KB 문서 버킷
BEDROCK_IAM_ROLE = os.environ.get("BEDROCK_AGENT_ROLE_ARN", "")    # Bedrock Agent 실행 역할

JIRA_LAMBDA_ARN   = os.environ.get("JIRA_LAMBDA_ARN", "")
GITHUB_LAMBDA_ARN = os.environ.get("GITHUB_LAMBDA_ARN", "")
SLACK_LAMBDA_ARN  = os.environ.get("SLACK_LAMBDA_ARN", "")

# Bedrock 클라이언트
bedrock_agent = boto3.client("bedrock-agent", region_name=AWS_REGION)
s3            = boto3.client("s3", region_name=AWS_REGION)


# ── Bedrock Agent 지시 프롬프트 ───────────────────────────────────────────
AGENT_INSTRUCTION = """
당신은 JaredAI입니다. GitHub Issue 내용을 분석하여 개발팀의 생산성을 높이는 AI 에이전트입니다.
미드 실리콘밸리의 Jared처럼, 개발 프로세스를 체계적으로 정리하고 자동화하는 것이 목표입니다.

## 핵심 역할
1. GitHub Issue의 요구사항을 분석하여 내부 코딩 가이드라인에 맞는 파이썬 코드 초안을 생성합니다.
2. Knowledge Base를 반드시 검색하여 PEP8 규칙, 보안 정책, 내부 라이브러리 활용법을 준수합니다.
3. 코드 초안 완성 후 Jira 티켓 생성 → GitHub 댓글 등록 → Slack 알림 순서로 도구를 실행합니다.

## 코드 생성 원칙
- PEP8 준수: snake_case 함수명, 영문 변수명, 79자 이하 라인
- 타입 힌트 필수: def validate_password(password: str) -> dict:
- Docstring 필수: 함수 목적, 파라미터, 반환값 명시
- 보안: 하드코딩 금지, SQL 파라미터 바인딩, bcrypt 해싱 사용
- 예외처리: 구체적인 except 절, 사용자에게 내부 오류 미노출

## 절대 하지 말아야 할 것
- Knowledge Base 검색 없이 코드 생성 금지 (할루시네이션 방지)
- 도구 실행 순서 변경 금지
- 민감 정보(API 키, 비밀번호 등) 코드에 하드코딩 금지
""".strip()


def setup_all():
    """전체 JaredAI 인프라를 순서대로 설정합니다."""
    print("=" * 60)
    print("🚀 JaredAI Bedrock Agent 설정 시작")
    print("=" * 60)

    # 1단계: Knowledge Base 생성
    kb_id = create_knowledge_base()

    # 2단계: Knowledge Base에 S3 데이터 소스 연결
    ds_id = create_data_source(kb_id)

    # 3단계: Knowledge Base 인덱싱 시작
    start_ingestion(kb_id, ds_id)

    # 4단계: Bedrock Agent 생성
    agent_id = create_bedrock_agent()

    # 5단계: Action Group 연결 (3개 Lambda Tool)
    create_action_groups(agent_id)

    # 6단계: Agent에 Knowledge Base 연결
    associate_knowledge_base(agent_id, kb_id)

    # 7단계: Agent 준비(Prepare) 및 Alias 생성
    alias_id = prepare_and_alias(agent_id)

    print("\n" + "=" * 60)
    print("✅ JaredAI 설정 완료!")
    print(f"   Agent ID    : {agent_id}")
    print(f"   Agent Alias : {alias_id}")
    print(f"   KB ID       : {kb_id}")
    print("\n.env 파일에 아래 값을 추가하세요:")
    print(f"   BEDROCK_AGENT_ID={agent_id}")
    print(f"   BEDROCK_AGENT_ALIAS={alias_id}")
    print("=" * 60)


# ── 1단계: Knowledge Base 생성 ────────────────────────────────────────────
def create_knowledge_base() -> str:
    print("\n[1/7] Knowledge Base 생성 중...")

    response = bedrock_agent.create_knowledge_base(
        name="jaredai-coding-standards-kb",
        description="JaredAI용 내부 코딩 표준 및 보안 정책 Knowledge Base",
        roleArn=BEDROCK_IAM_ROLE,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": (
                    f"arn:aws:bedrock:{AWS_REGION}::foundation-model/"
                    "amazon.titan-embed-text-v1"
                )
            },
        },
        storageConfiguration={
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": os.environ.get("OPENSEARCH_COLLECTION_ARN", ""),
                "vectorIndexName": "jaredai-kb-index",
                "fieldMapping": {
                    "vectorField":    "embedding",
                    "textField":      "text",
                    "metadataField":  "metadata",
                },
            },
        },
    )

    kb_id = response["knowledgeBase"]["knowledgeBaseId"]
    print(f"   ✓ Knowledge Base 생성: {kb_id}")
    return kb_id


# ── 2단계: S3 데이터 소스 연결 ────────────────────────────────────────────
def create_data_source(kb_id: str) -> str:
    print("\n[2/7] S3 데이터 소스 연결 중...")

    response = bedrock_agent.create_data_source(
        knowledgeBaseId=kb_id,
        name="jaredai-s3-docs",
        description="내부 코딩 표준 및 보안 정책 문서 (S3)",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{S3_BUCKET_NAME}",
                "inclusionPrefixes": ["knowledge_base/"],
            },
        },
        vectorIngestionConfiguration={
            "chunkingConfiguration": {
                "chunkingStrategy": "FIXED_SIZE",
                "fixedSizeChunkingConfiguration": {
                    "maxTokens":       512,
                    "overlapPercentage": 20,
                },
            }
        },
    )

    ds_id = response["dataSource"]["dataSourceId"]
    print(f"   ✓ 데이터 소스 생성: {ds_id}")
    return ds_id


# ── 3단계: 인덱싱 시작 ────────────────────────────────────────────────────
def start_ingestion(kb_id: str, ds_id: str):
    print("\n[3/7] Knowledge Base 인덱싱 시작...")

    response = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
    )
    job_id = response["ingestionJob"]["ingestionJobId"]
    print(f"   ✓ 인덱싱 작업 시작: {job_id}")
    print("   ⏳ 인덱싱은 백그라운드에서 진행됩니다. 완료까지 수 분 소요.")


# ── 4단계: Bedrock Agent 생성 ─────────────────────────────────────────────
def create_bedrock_agent() -> str:
    print("\n[4/7] Bedrock Agent 생성 중...")

    response = bedrock_agent.create_agent(
        agentName="JaredAI-Agent",
        description="GitHub Issue 기반 AI 코드 초안 생성 및 Jira/GitHub/Slack 자동 연동 에이전트",
        instruction=AGENT_INSTRUCTION,
        foundationModel=f"anthropic.claude-sonnet-4-5",
        agentResourceRoleArn=BEDROCK_IAM_ROLE,
        idleSessionTTLInSeconds=600,
    )

    agent_id = response["agent"]["agentId"]
    print(f"   ✓ Agent 생성: {agent_id}")
    time.sleep(5)  # Agent 생성 안정화 대기
    return agent_id


# ── 5단계: Action Group 생성 (Tool Lambda 연결) ───────────────────────────
def create_action_groups(agent_id: str):
    print("\n[5/7] Action Groups 생성 중...")

    # api_spec.yaml 읽기
    spec_path = os.path.join(os.path.dirname(__file__), "../tools/api_spec.yaml")
    with open(spec_path, "r", encoding="utf-8") as f:
        api_spec_content = f.read()

    # Jira + GitHub + Slack을 단일 Action Group으로 묶음
    # (각 Lambda가 apiPath로 분기 처리)
    lambda_arns = [JIRA_LAMBDA_ARN, GITHUB_LAMBDA_ARN, SLACK_LAMBDA_ARN]

    for i, lambda_arn in enumerate(lambda_arns):
        if not lambda_arn:
            print(f"   ⚠ Lambda ARN {i+1} 미설정 - 건너뜀")
            continue

        tool_names = ["Jira", "GitHub", "Slack"]
        response = bedrock_agent.create_agent_action_group(
            agentId=agent_id,
            agentVersion="DRAFT",
            actionGroupName=f"JaredAI-{tool_names[i]}-Tool",
            description=f"{tool_names[i]} 연동 도구",
            actionGroupExecutor={"lambda": lambda_arn},
            apiSchema={
                "payload": api_spec_content,
            },
        )
        ag_id = response["agentActionGroup"]["actionGroupId"]
        print(f"   ✓ {tool_names[i]} Action Group: {ag_id}")
        time.sleep(2)


# ── 6단계: Knowledge Base 연결 ────────────────────────────────────────────
def associate_knowledge_base(agent_id: str, kb_id: str):
    print("\n[6/7] Knowledge Base 연결 중...")

    bedrock_agent.associate_agent_knowledge_base(
        agentId=agent_id,
        agentVersion="DRAFT",
        knowledgeBaseId=kb_id,
        description="내부 코딩 표준 및 보안 정책 검색",
        knowledgeBaseState="ENABLED",
    )
    print(f"   ✓ KB {kb_id} → Agent {agent_id} 연결 완료")


# ── 7단계: Prepare + Alias 생성 ───────────────────────────────────────────
def prepare_and_alias(agent_id: str) -> str:
    print("\n[7/7] Agent Prepare 및 Alias 생성 중...")

    # Prepare (변경사항 적용)
    bedrock_agent.prepare_agent(agentId=agent_id)
    print("   ✓ Agent Prepare 완료")
    time.sleep(10)  # Prepare 완료 대기

    # Alias 생성
    response = bedrock_agent.create_agent_alias(
        agentId=agent_id,
        agentAliasName="production",
        description="JaredAI 운영 환경 Alias",
        routingConfiguration=[
            {"agentVersion": "1"},
        ],
    )
    alias_id = response["agentAlias"]["agentAliasId"]
    print(f"   ✓ Alias 생성: {alias_id}")
    return alias_id


if __name__ == "__main__":
    setup_all()
