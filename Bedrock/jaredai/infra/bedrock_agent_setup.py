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

    print("IAM 역할 전파를 위해 15초간 대기합니다...")
    time.sleep(15)

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


# ── 1단계: Knowledge Base 생성 또는 기존 리소스 연동 ────────────────────────────────────────────
def create_knowledge_base() -> str:
    print("\n[1/7] Knowledge Base 확인 및 생성 프로세스 시작...")

    # 💡 콘솔에 구성된 실제 Knowledge Base 이름과 정확히 일치시킵니다.
    KB_NAME = "bedrock-knowledge-base-hgzg8n" 

    # 1. 🔍 이미 존재하는지 먼저 목록을 조회해 봅니다.
    try:
        paginator = bedrock_agent.get_paginator('list_knowledge_bases')
        for page in paginator.paginate():
            for kb in page.get('knowledgeBaseSummaries', []):
                if kb['name'] == KB_NAME:
                    # 동일한 이름이 이미 있다면 생성하지 않고 기존 ID를 리턴합니다.
                    existing_kb_id = kb['knowledgeBaseId']
                    print(f"   ℹ️  이미 존재하는 Knowledge Base를 발견했습니다. (이름: {KB_NAME}, ID: {existing_kb_id})")
                    print("   ✓ 기존 리소스를 연동하여 다음 단계를 진행합니다.")
                    return existing_kb_id
    except Exception as e:
        print(f"   ⚠️  기존 KB 목록을 조회하는 중 오류 발생(무시하고 생성을 시도합니다): {e}")

    # 2. ✨ 목록에 없다면 새로 생성을 시도합니다.
    print(f"   🆕  {KB_NAME} 리소스가 없으므로 새로 생성을 시도합니다...")
    try:
        response = bedrock_agent.create_knowledge_base(
            name=KB_NAME, 
            description="JaredAI용 내부 코딩 표준 및 보안 정책 Knowledge Base",
            roleArn=BEDROCK_IAM_ROLE,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": (
                        f"arn:aws:bedrock:{AWS_REGION}::foundation-model/"
                        "amazon.titan-embed-text-v2:0"
                    )
                },
            },
            storageConfiguration={
                "type": "OPENSEARCH_SERVERLESS",
                "opensearchServerlessConfiguration": {
                    "collectionArn": os.environ.get("OPENSEARCH_COLLECTION_ARN", ""),
                    # 💡 실제 콘솔 내 인덱스 및 필드 정보와 완벽히 일치화 완료
                    "vectorIndexName": "bedrock-knowledge-base-default-index", 
                    "fieldMapping": {
                        "vectorField":    "bedrock-knowledge-base-default-vector",
                        "textField":      "AMAZON_BEDROCK_TEXT_CHUNK",
                        "metadataField":  "AMAZON_BEDROCK_METADATA",
                    },
                },
            },
        )
        kb_id = response["knowledgeBase"]["knowledgeBaseId"]
        print(f"   ✓ Knowledge Base 새로 생성 완료: {kb_id}")
        return kb_id

    except bedrock_agent.exceptions.ConflictException:
        # 혹시 모를 레이스 컨디션 충돌에 대비한 이중 안전장치
        print(f"   ℹ️  생성 중 충돌 발생: {KB_NAME}이 이미 존재하므로 ID를 다시 조회합니다.")
        pages = bedrock_agent.get_paginator('list_knowledge_bases').paginate()
        for page in pages:
            for kb in page.get('knowledgeBaseSummaries', []):
                if kb['name'] == KB_NAME:
                    return kb['knowledgeBaseId']
        raise
        
# ── 2단계: Data Source 생성 또는 기존 리소스 연동 ────────────────────────────────────────────
def create_data_source(kb_id: str) -> str:
    print("\n[2/7] Data Source 확인 및 생성 프로세스 시작...")

    DATA_SOURCE_NAME = "jaredai-kb-926442180845"

    # 1. 기존 리소스 조회 로직 (생략 - 기존 코드 그대로 유지)
    try:
        paginator = bedrock_agent.get_paginator('list_data_sources')
        for page in paginator.paginate(knowledgeBaseId=kb_id):
            for ds in page.get('dataSourceSummaries', []):
                if ds['name'] == DATA_SOURCE_NAME:
                    existing_ds_id = ds['dataSourceId']
                    print(f"   ℹ️  이미 존재하는 Data Source를 발견했습니다. (이름: {DATA_SOURCE_NAME}, ID: {existing_ds_id})")
                    print("   ✓ 기존 Data Source 리소스를 연동하여 다음 단계를 진행합니다.")
                    return existing_ds_id
    except Exception as e:
        pass

    # 2. ✨ 신규 생성 시 파라미터 이름 수정 부분
    print(f"   🆕  {DATA_SOURCE_NAME} 리소스가 없으므로 새로 생성을 시도합니다...")
    try:
        response = bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name=DATA_SOURCE_NAME,
            description="JaredAI용 S3 문서 소스 연동",
            dataSourceConfiguration={
                "type": "S3",
                # 🚨 여기를 s3DataSourceConfiguration에서 s3Configuration으로 수정했습니다!
                "s3Configuration": { 
                    "bucketArn": f"arn:aws:s3:::{S3_BUCKET_NAME}",
                }
            }
        )
        ds_id = response["dataSource"]["dataSourceId"]
        print(f"   ✓ Data Source 새로 생성 완료: {ds_id}")
        return ds_id

    except bedrock_agent.exceptions.ConflictException:
        # 기존 ID 조회 백업 로직 (생략 - 기존 코드 그대로 유지)
        pages = bedrock_agent.get_paginator('list_data_sources').paginate(knowledgeBaseId=kb_id)
        for page in pages:
            for ds in page.get('dataSourceSummaries', []):
                if ds['name'] == DATA_SOURCE_NAME:
                    return ds['dataSourceId']
        raise

# ── 3단계: 인덱싱 시작 ────────────────────────────────────────────────────
def start_ingestion(kb_id: str, ds_id: str):
    print("\n[3/7] Knowledge Base 인덱싱 시작...")

    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
        )
        job_id = response["ingestionJob"]["ingestionJobId"]
        print(f"   ✓ 인덱싱 작업 시작: {job_id}")
        print("   ⏳ 인덱싱은 백그라운드에서 진행됩니다. 완료까지 수 분 소요.")
    except Exception as e:
        # 인덱싱이 이미 실행 중이거나 백그라운드 작업일 경우 멈추지 않도록 예외 처리만 수행
        print(f"   ℹ️  인덱싱 작업 요청 결과: {e} (다음 단계로 진행합니다.)")


# ── 4단계: Bedrock Agent 생성 ─────────────────────────────────────────────
def create_bedrock_agent() -> str:
    print("\n[4/7] Bedrock Agent 생성 중...")

    AGENT_NAME = "JaredAI-Agent"

    # 1. 🔍 동일한 이름의 Agent가 이미 있는지 싹 훑어봅니다.
    try:
        paginator = bedrock_agent.get_paginator('list_agents')
        for page in paginator.paginate():
            for agent in page.get('agentSummaries', []):
                if agent['agentName'] == AGENT_NAME:
                    existing_agent_id = agent['agentId']
                    print(f"   ℹ️  이미 존재하는 Agent를 발견했습니다. (이름: {AGENT_NAME}, ID: {existing_agent_id})")
                    print("   ✓ 기존 Agent 리소스를 연동하여 다음 단계를 진행합니다.")
                    return existing_agent_id
    except Exception as e:
        print(f"   ⚠️  기존 Agent 목록 조회 중 에러 발생: {e}")

    # 2. ✨ 없을 경우 신규 생성 실행
    print(f"   🆕  {AGENT_NAME} 리소스가 없으므로 새로 생성을 시도합니다...")
    try:
        response = bedrock_agent.create_agent(
            agentName=AGENT_NAME,
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
    except bedrock_agent.exceptions.ConflictException:
        print(f"   ℹ️  생성 중 충돌 발생: {AGENT_NAME}이 이미 존재하므로 ID를 재조회합니다.")
        pages = bedrock_agent.get_paginator('list_agents').paginate()
        for page in pages:
            for agent in page.get('agentSummaries', []):
                if agent['agentName'] == AGENT_NAME:
                    return agent['agentId']
        raise


# ── 5단계: Action Group 생성 (통합 단일 액션 그룹 구조로 개편) ───────────────────────────
def create_action_groups(agent_id: str):
    print("\n[5/7] Action Groups 생성 중...")

    # api_spec.yaml 읽기 (Jira, GitHub, Slack 경로가 모두 정의된 통합 명세서)
    spec_path = os.path.join(os.path.dirname(__file__), "../tools/api_spec.yaml")
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            api_spec_content = f.read().replace('\xa0', ' ')
    except Exception as e:
        print(f"   ❌ api_spec.yaml 파일을 읽을 수 없습니다: {e}")
        return

    # 💡 근본 해결: 3개의 기능을 찢지 않고 'JaredAI-Unified-Tool' 하나로 통합 바인딩합니다.
    TARGET_AG_NAME = "JaredAI-Unified-Tool"

    # 🔍 기존에 이미 해당 통합 액션 그룹이 붙어있는지 조회
    try:
        paginator = bedrock_agent.get_paginator('list_agent_action_groups')
        for page in paginator.paginate(agentId=agent_id, agentVersion="DRAFT"):
            for ag in page.get('actionGroupSummaries', []):
                if ag['actionGroupName'] == TARGET_AG_NAME:
                    print(f"   ℹ️  이미 존재하는 통합 Action Group 발견: {TARGET_AG_NAME} (건너뜀)")
                    return
    except Exception as e:
        print(f"   ❌ 통합 Action Group 생성 중 에러 발생: {e}")
        # ve 객체가 있을 경우 response 내부를 한꺼번에 다 출력해 봅니다.
        if hasattr(e, 'response'):
            import pprint
            print("\n🔍 [AWS 내부 에러 구조 원본]")
            pprint.pprint(e.response)
        raise

    # 현재 설정된 람다 중 주축이 되는 함수 하나를 대표 Executor로 지정하거나, 
    # Bedrock 에이전트 라우팅 가이드에 맞춰 람다를 연결합니다.
    # (일반적으로 단일 OpenAPI Spec은 단일 라우팅 엔드포인트 람다를 가지는 것이 표준입니다.)
    # 여기서는 가장 먼저 실행되는 JIRA_LAMBDA_ARN을 대표로 지정하거나 공통 람다 엔드포인트를 사용합니다.
    PRIMARY_LAMBDA_ARN = JIRA_LAMBDA_ARN if JIRA_LAMBDA_ARN else GITHUB_LAMBDA_ARN

    if not PRIMARY_LAMBDA_ARN:
        print("   ❌ 액션 그룹을 생성할 람다 ARN이 존재하지 않습니다.")
        return

    try:
        response = bedrock_agent.create_agent_action_group(
            agentId=agent_id,
            agentVersion="DRAFT",
            actionGroupName=TARGET_AG_NAME,
            description="Jira, GitHub, Slack 연동 통합 도구 세트",
            actionGroupExecutor={"lambda": PRIMARY_LAMBDA_ARN}, # 👈 이 람다가 내부에서 Event['apiPath']를 보고 분기하도록 설계하는 것이 Bedrock의 정석 아키텍처입니다.
            apiSchema={
                "payload": api_spec_content,
            },
        )
        ag_id = response["agentActionGroup"]["actionGroupId"]
        print(f"   ✓ 통합 Action Group 생성 성공: {ag_id}")
    except bedrock_agent.exceptions.ConflictException:
        print(f"   ℹ️  {TARGET_AG_NAME}이 이미 존재하므로 다음 단계로 진행합니다.")
    except Exception as e:
        print(f"   ❌ 통합 Action Group 생성 중 에러 발생: {e}")
        raise

# ── 6단계: Knowledge Base 연결 ────────────────────────────────────────────
def associate_knowledge_base(agent_id: str, kb_id: str):
    print("\n[6/7] Knowledge Base 연결 중...")

    # 🔍 Agent에 이미 이 KB가 붙어있는지 확인합니다.
    try:
        paginator = bedrock_agent.get_paginator('list_agent_knowledge_bases')
        for page in paginator.paginate(agentId=agent_id, agentVersion="DRAFT"):
            for kb in page.get('knowledgeBaseSummaries', []):
                if kb['knowledgeBaseId'] == kb_id:
                    print(f"   ℹ️  KB {kb_id}가 이미 Agent에 연동되어 있습니다. (건너뜀)")
                    return
    except Exception as e:
        pass

    try:
        bedrock_agent.associate_agent_knowledge_base(
            agentId=agent_id,
            agentVersion="DRAFT",
            knowledgeBaseId=kb_id,
            description="내부 코딩 표준 및 보안 정책 검색",
            knowledgeBaseState="ENABLED",
        )
        print(f"   ✓ KB {kb_id} → Agent {agent_id} 연결 완료")
    except bedrock_agent.exceptions.ConflictException:
        print(f"   ℹ️  KB 연동 충돌(이미 연동됨)로 다음 단계 진행합니다.")


# ── 7단계: Prepare + Alias 생성 ───────────────────────────────────────────
def prepare_and_alias(agent_id: str) -> str:
    print("\n[7/7] Agent Prepare 및 Alias 생성 중...")

    TARGET_ALIAS_NAME = "production"

    # Prepare (변경사항 적용)
    bedrock_agent.prepare_agent(agentId=agent_id)
    print("   ✓ Agent Prepare 완료")
    time.sleep(10)  # Prepare 완료 대기

    # 🔍 기존에 동일한 이름의 Alias가 존재하는지 체크합니다.
    try:
        paginator = bedrock_agent.get_paginator('list_agent_aliases')
        for page in paginator.paginate(agentId=agent_id):
            for alias in page.get('agentAliasSummaries', []):
                if alias['agentAliasName'] == TARGET_ALIAS_NAME:
                    existing_alias_id = alias['agentAliasId']
                    print(f"   ℹ️  이미 존재하는 Alias 발견: {TARGET_ALIAS_NAME} (ID: {existing_alias_id})")
                    return existing_alias_id
    except Exception as e:
        print(f"   ⚠️  Alias 목록 조회 중 에러 발생: {e}")

    # Alias 생성
    try:
        response = bedrock_agent.create_agent_alias(
            agentId=agent_id,
            agentAliasName=TARGET_ALIAS_NAME,
            description="JaredAI 운영 환경 Alias",
            routingConfiguration=[
                {"agentVersion": "1"},
            ],
        )
        alias_id = response["agentAlias"]["agentAliasId"]
        print(f"   ✓ Alias 생성: {alias_id}")
        return alias_id
    except bedrock_agent.exceptions.ConflictException:
        print(f"   ℹ️  Alias 충돌 발생으로 다시 한 번 목록을 검색하여 리턴합니다.")
        pages = bedrock_agent.get_paginator('list_agent_aliases').paginate(agentId=agent_id)
        for page in pages:
            for alias in page.get('agentAliasSummaries', []):
                if alias['agentAliasName'] == TARGET_ALIAS_NAME:
                    return alias['agentAliasId']
        raise


if __name__ == "__main__":
    setup_all()
