import time
from config import Config
from bedrock_utils import BedrockManager
from s3_utils import S3Manager

def main():
    # 1. 초기화
    bedrock = BedrockManager()
    s3 = S3Manager()
    
    print("🚀 AWS Bedrock RAG 프로세스 시작...")

    # 2. 임베딩 및 유사도 테스트
    code1 = "def calculate_total(items): return sum(items)"
    code2 = "def get_sum(prices): return sum(prices)"
    
    emb1 = bedrock.get_embedding(code1)
    emb2 = bedrock.get_embedding(code2)
    
    similarity = bedrock.cosine_similarity(emb1, emb2)
    print(f"🔬 코드 스니펫 유사도: {similarity:.4f}")

    # 3. S3 문서 업로드 샘플 (로컬에 파일이 있다는 가정)
    # s3.create_bucket(Config.BUCKET_NAME)
    # s3.upload_file_with_metadata('pep8.txt', 'style-guides/python/pep8.txt', {'language': 'python'})

    # 4. Knowledge Base 동기화 (ID가 .env에 등록되어 있다면 실행)
    if Config.KB_ID and Config.DATA_SOURCE_ID:
        print("\n🔄 Knowledge Base 데이터 동기화 요청 중...")
        job_id = bedrock.sync_knowledge_base(Config.KB_ID, Config.DATA_SOURCE_ID)
        
        while True:
            status = bedrock.get_sync_status(Config.KB_ID, Config.DATA_SOURCE_ID, job_id)
            print(f"⏳ 현재 동기화 상태: {status}")
            if status in ['COMPLETE', 'FAILED', 'ABORTED']:
                break
            time.sleep(10)
            
        # 5. 질문 테스트
        if status == 'COMPLETE':
            print("\n🤖 지식 기반 QA 테스트 시작...")
            question = "파이썬 변수명 규칙은 무엇인가요?"
            answer = bedrock.ask_knowledge_base(Config.KB_ID, question)
            print(f"Q: {question}\nA: {answer}")
    else:
        print("\nℹ️ .env 파일에 KB_ID와 DATA_SOURCE_ID를 설정하면 동기화 및 QA 테스트가 활성화됩니다.")

if __name__ == "__main__":
    main()
