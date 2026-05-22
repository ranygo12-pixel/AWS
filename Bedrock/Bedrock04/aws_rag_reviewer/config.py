"""
aws_rag_reviewer: 환경 설정 및 AWS 자격 증명 관리 모듈
"""
import os
import sys

def init_aws_credentials():
    """
    AWS 자격 증명 및 필수 환경 변수를 로드합니다.
    우선순위: 로컬 환경 변수 > Colab Secrets (존재할 경우)
    """
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        try:
            from google.colab import userdata
            os.environ["AWS_ACCESS_KEY_ID"] = userdata.get('AWS_ACCESS_KEY_ID')
            os.environ["AWS_SECRET_ACCESS_KEY"] = userdata.get('AWS_SECRET_ACCESS_KEY')
            os.environ["KB_ID"] = userdata.get('KB_ID')
            print("✅ Colab Secrets로부터 AWS 자격 증명 로드 완료!")
        except ImportError:
            pass

    if not os.environ.get("AWS_DEFAULT_REGION"):
        os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-2"

    kb_id = os.environ.get("KB_ID")
    if not kb_id:
        print("❌ 에러: 환경 변수 'KB_ID'가 설정되지 않았습니다.", file=sys.stderr)
        print("힌트: export KB_ID='your-knowledge-base-id'를 실행하세요.", file=sys.stderr)
        sys.exit(1)
        
    return kb_id
