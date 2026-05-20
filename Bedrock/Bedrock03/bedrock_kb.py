import boto3
from config import Config

class BedrockKnowledgeBaseManager:
    def __init__(self):
        # 인프라 관리/동기화용 클라이언트
        self.agent_client = boto3.client(
            'bedrock-agent', 
            region_name=Config.AWS_REGION
        )
        # 질문 검색/답변 생성용 런타임 클라이언트
        self.agent_runtime_client = boto3.client(
            'bedrock-agent-runtime', 
            region_name=Config.AWS_REGION
        )

    def start_sync(self, kb_id: str, data_source_id: str) -> str:
        """S3에 새로 업로드된 문서를 Knowledge Base에 동기화(Ingestion) 시킵니다."""
        response = self.agent_client.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id
        )
        return response['ingestionJob']['ingestionJobId']

    def check_sync_status(self, kb_id: str, data_source_id: str, job_id: str) -> str:
        """동기화 작업의 진행 상태를 반환합니다. (예: IN_PROGRESS, COMPLETE, FAILED)"""
        response = self.agent_client.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            ingestionJobId=job_id
        )
        return response['ingestionJob']['status']

    def ask(self, kb_id: str, question: str) -> str:
        """지식 기반 문서에서 관련 내용을 검색(Retrieve)한 뒤, Claude를 통해 답변을 조립합니다."""
        response = self.agent_runtime_client.retrieve_and_generate(
            input={'text': question},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': kb_id,
                    'modelArn': 'global.anthropic.claude-sonnet-4-6' # 최신 Claude 3.5 Sonnet 인프라 사용
                }
            }
        )
        return response['output']['text']
        
    def retrieve_only(self, kb_id: str, question: str) -> list:
        """LLM 답변 없이, 순수하게 지식 기반 내에서 매칭되는 원본 문서 조각들과 유사도 점수만 뽑아옵니다."""
        response = self.agent_runtime_client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={'text': question}
        )
        return response['retrievalResults']
