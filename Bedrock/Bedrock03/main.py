import time
from config import Config
from s3_utils import S3Manager

# 💡 기능별로 분리한 파일에서 필요한 클래스와 함수를 정확하게 불러옵니다.
# (만약 파일명을 bedrock_embedding, vector_math, bedrock_kb로 하셨다면 그 이름으로 변경하시면 됩니다!)
from titan_embedding import BedrockEmbeddingManager
from cosine_similarity import cosine_similarity
from knowledge_base import BedrockKnowledgeBaseManager

def main():
    # 1. 초기화 (기존 bedrock 하나에서 역할별 매니저로 깔끔하게 분리)
    embedding_mgr = BedrockEmbeddingManager()
    kb_mgr = BedrockKnowledgeBaseManager()
    s3 = S3Manager()
    
    print("🚀 AWS Bedrock RAG 프로세스 시작...")

    # 2. 임베딩 및 유사도 테스트
    code1 = "def calculate_total(items): return sum(items)"
    code2 = "def get_sum(prices): return sum(prices)"
    
    # 분리된 임베딩 모듈 호출
    emb1 = embedding_mgr.get_embedding(code1)
    emb2 = embedding_mgr.get_embedding(code2)
    
    # 분리된 수학 유틸리티 함수 호출
    similarity = cosine_similarity(emb1, emb2)
    print(f"🔬 코드 스니펫 유사도: {similarity:.4f}")

    # 3. S3 문서 업로드 샘플 (기존 주석 처리된 코드 및 변수명 100% 보존)
    # s3.create_bucket(Config.BUCKET_NAME)
    # s3.upload_file_with_metadata('pep8.txt', 'style-guides/python/pep8.txt', {'language': 'python'})

    # 4. Knowledge Base 동기화 (ID가 .env에 등록되어 있다면 실행)
    if Config.KB_ID and Config.DATA_SOURCE_ID:
        print("\n🔄 Knowledge Base 데이터 동기화 요청 중...")
        # 분리된 KB 모듈의 동기화 시작 기능 호출
        job_id = kb_mgr.start_sync(Config.KB_ID, Config.DATA_SOURCE_ID)
        
        while True:
            # 분리된 KB 모듈의 상태 확인 기능 호출
            status = kb_mgr.check_sync_status(Config.KB_ID, Config.DATA_SOURCE_ID, job_id)
            print(f"⏳ 현재 동기화 상태: {status}")
            if status in ['COMPLETE', 'FAILED', 'ABORTED']:
                break
            time.sleep(10)  # 기존의 10초 대기 로직 유지
            
        # 5. 질문 테스트
        if status == 'COMPLETE':
            print("\n🤖 지식 기반 QA 테스트 시작...")
            question = "파이썬 변수명 규칙은 무엇인가요?"
            # 분리된 KB 모듈의 질문(ask) 기능 호출
            answer = kb_mgr.ask(Config.KB_ID, question)
            print(f"Q: {question}\nA: {answer}")
    else:
        print("\nℹ️ .env 파일에 KB_ID와 DATA_SOURCE_ID를 설정하면 동기화 및 QA 테스트가 활성화됩니다.")

if __name__ == "__main__":
    main()
