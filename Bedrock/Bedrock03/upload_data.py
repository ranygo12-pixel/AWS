# upload_data.py
import os
from config import Config
from s3_utils import S3Manager

def initialize_rag_data():
    s3 = S3Manager()
    data_dir = "./data"
    
    print("📂 S3 데이터 가이드라인 업로드 시작...")
    
    # 예시: data 폴더 안에 있는 파일들을 깔끔하게 읽어서 업로드
    files_to_upload = {
        "pep8.txt": "style-guides/pep8.txt",
        "owasp-top10.txt": "security/owasp-top10.txt"
    }
    
    for filename, s3_key in files_to_upload.items():
        file_path = os.path.join(data_dir, filename)
        
        if os.path.exists(file_path):
            print(f"📤 {filename} -> S3://{Config.BUCKET_NAME}/{s3_key} 업로드 중...")
            s3.upload_file_with_metadata(file_path, s3_key, {"status": "deployed"})
        else:
            print(f"❌ 오류: {file_path} 파일이 data 폴더에 없습니다.")

if __name__ == "__main__":
    initialize_rag_data()
