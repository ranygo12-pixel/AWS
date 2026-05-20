import json
import boto3
import numpy as np
from config import Config

class BedrockManager:
    def __init__(self):
        # 런타임용 클라이언트 (모델 호출, 검색 등)
        self.runtime_client = boto3.client(
            'bedrock-runtime', 
            region_name=Config.AWS_REGION
        )
        self.agent_runtime_client = boto3.client(
            'bedrock-agent-runtime', 
            region_name=Config.AWS_REGION
        )
        # 에이전트/KB 관리용 클라이언트
        self.agent_client = boto3.client(
            'bedrock-agent', 
            region_name=Config.AWS_REGION
        )

    def get_embedding(self, text: str) -> list:
        """텍스트를 Amazon Titan v2 모델을 통해 1024차원 벡터로 변환"""
        body = json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
        response = self.runtime_client.invoke_model(
            modelId='amazon.titan-embed-text-v2:0',
            contentType='application/json',
            body=body
        )
        result = json.loads(response['body'].read())
        return result['embedding']

    @staticmethod
    def cosine_similarity(vec1: list, vec2: list) -> float:
        """두 벡터 간의 코사인 유사도 계산"""
        v1, v2 = np.array(vec1), np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def sync_knowledge_base(self, kb_id: str, data_source_id: str):
        """Knowledge Base 데이터 소스 동기화 작업 시작"""
        response = self.agent_client.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id
        )
        return response['ingestionJob']['ingestionJobId']

    def get_sync_status(self, kb_id: str, data_source_id: str, job_id: str) -> str:
        """동기화 작업 상태 확인"""
        response = self.agent_client.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            ingestionJobId=job_id
        )
        return response['ingestionJob']['status']

    def ask_knowledge_base(self, kb_id: str, question: str) -> str:
        """Knowledge Base에 질문하고 Claude를 통해 답변 생성"""
        response = self.agent_runtime_client.retrieve_and_generate(
            input={'text': question},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': kb_id,
                    'modelArn': 'global.anthropic.claude-sonnet-4-6'
                }
            }
        )
        return response['output']['text']
