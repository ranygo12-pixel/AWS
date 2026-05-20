import time
from config import Config
# 💡 s3 업로드를 안 하므로 s3 관련 import도 필요 없어집니다!
from titan_embedding import BedrockEmbeddingManager
from cosine_similarity import cosine_similarity
from knowledge_base import BedrockKnowledgeBaseManager

def main():
    # 1. 초기화 (S3 매니저 제거)
    embedding_mgr = BedrockEmbeddingManager()
    kb_mgr = BedrockKnowledgeBaseManager()
    
    print("🚀 AWS Bedrock RAG 서비스 가동...\n")

    # 2. 임베딩 및 유사도 테스트
    code1 = "def calculate_total(items): return sum(items)"
    code2 = "def get_sum(prices): return sum(prices)"
    
    emb1 = embedding_mgr.get_embedding(code1)
    emb2 = embedding_mgr.get_embedding(code2)
    
    similarity = cosine_similarity(emb1, emb2)
    print(f"🔬 코드 스니펫 유사도: {similarity:.4f}\n")

    # ❌ [삭제됨] 로컬 파일 준비 및 S3 업로드 파트가 통째로 사라져서 깔끔해졌습니다.
    # 이제 데이터 업로드는 upload_data.py가 전담합니다.

    # 3. Knowledge Base 동기화 및 서비스 런타임
    if Config.KB_ID and Config.DATA_SOURCE_ID:
        print("🔄 Knowledge Base 데이터 동기화 요청 중...")
        job_id = kb_mgr.start_sync(Config.KB_ID, Config.DATA_SOURCE_ID)
        
        while True:
            status = kb_mgr.check_sync_status(Config.KB_ID, Config.DATA_SOURCE_ID, job_id)
            print(f"⏳ 현재 동기화 상태: {status}")
            if status in ['COMPLETE', 'FAILED', 'ABORTED']:
                break
            time.sleep(10)
            
        # 4. 질문 테스트
        if status == 'COMPLETE':
            print("\n🤖 지식 기반 QA 테스트 시작...")
            question = "파이썬 변수명 규칙은 무엇인가요?"
            answer = kb_mgr.ask(Config.KB_ID, question)
            print(f"Q: {question}\nA: {answer}")
    else:
        print("\nℹ️ .env 파일에 KB_ID와 DATA_SOURCE_ID를 설정하면 동기화 및 QA 테스트가 활성화됩니다.")

if __name__ == "__main__":
    main()
