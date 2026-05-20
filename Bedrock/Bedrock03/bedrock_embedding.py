import json
import boto3
from config import Config

class BedrockEmbeddingManager:
    def __init__(self):
        # 모델 호출용 런타임 클라이언트
        self.runtime_client = boto3.client(
            'bedrock-runtime', 
            region_name=Config.AWS_REGION
        )
        # 기본 사용할 임베딩 모델 ID
        self.model_id = 'amazon.titan-embed-text-v2:0'

    def get_embedding(self, text: str, dimensions: int = 1024) -> list:
        """
        텍스트를 임베딩 모델을 통해 고차원 벡터로 변환합니다.
        dimensions: 256, 512, 1024 중 선택 가능 (Titan v2 기준)
        """
        body = json.dumps({
            "inputText": text,
            "dimensions": dimensions,
            "normalize": True
        })
        
        response = self.runtime_client.invoke_model(
            modelId=self.model_id,
            contentType='application/json',
            body=body
        )
        
        result = json.loads(response['body'].read())
        return result['embedding']
