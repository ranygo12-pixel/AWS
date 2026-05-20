import boto3
from config import Config

class S3Manager:
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=Config.AWS_REGION)

    def create_bucket(self, bucket_name: str):
        """S3 버킷 생성 (서울 리전 기준 고정)"""
        try:
            self.s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': Config.AWS_REGION}
            )
            print(f"✅ S3 버킷 생성 완료: {bucket_name}")
        except self.s3_client.exceptions.BucketAlreadyOwnedByYou:
            print(f"ℹ️ 이미 소유한 버킷입니다: {bucket_name}")

    def upload_file_with_metadata(self, file_path: str, key: str, metadata: dict):
        """메타데이터를 포함하여 S3에 파일 업로드"""
        with open(file_path, 'rb') as f:
            self.s3_client.put_object(
                Bucket=Config.BUCKET_NAME,
                Key=key,
                Body=f.read(),
                Metadata=metadata
            )
        print(f"📤 업로드 완료: {key} (Metadata: {metadata})")
