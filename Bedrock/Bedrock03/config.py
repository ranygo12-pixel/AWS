import os
from dotenv import load_dotenv

# .env 파일이 있으면 로드합니다.
load_dotenv()

class Config:
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'ap-northeast-2')
    
    # 지식 기반(KB) 설정
    KB_ID = os.getenv('KB_ID')
    DATA_SOURCE_ID = os.getenv('DATA_SOURCE_ID')
    BUCKET_NAME = "codebuddy-kb-docs"
