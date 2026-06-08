"""
Lambda Layer 생성 스크립트
공통 라이브러리(radon, PyGithub, requests)를 패키징하여 AWS Lambda Layer로 업로드합니다.

사용법:
    python scripts/create_layer.py
    python scripts/create_layer.py --packages radon PyGithub requests --name my-layer
"""

import argparse
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")

DEFAULT_PACKAGES = ["radon", "PyGithub", "requests"]
DEFAULT_LAYER_NAME = "codebuddy-deps"


def create_layer_zip(packages: list[str]) -> io.BytesIO:
    """패키지를 설치하고 ZIP 파일을 생성합니다."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger.info(f"패키지 설치 중: {packages}")
        for pkg in packages:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-t", tmpdir, "--quiet"]
            )

        # 불필요한 캐시/메타 파일 제거
        for root, dirs, _ in os.walk(tmpdir):
            for d in dirs[:]:
                full_path = os.path.join(root, d)
                if d == "__pycache__" or d.endswith(".dist-info"):
                    shutil.rmtree(full_path)

        # ZIP 생성
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    full_path = os.path.join(root, f)
                    arcname = os.path.relpath(full_path, tmpdir)
                    zf.write(full_path, arcname)
        zip_buffer.seek(0)
        logger.info("ZIP 생성 완료")
        return zip_buffer


def publish_layer(layer_name: str, packages: list[str], zip_buffer: io.BytesIO) -> str:
    """ZIP을 AWS Lambda Layer로 업로드합니다."""
    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    response = lambda_client.publish_layer_version(
        LayerName=layer_name,
        Content={"ZipFile": zip_buffer.read()},
        CompatibleRuntimes=["python3.12"],
        Description=f"Layer for {', '.join(packages)}",
    )
    layer_arn = response["LayerVersionArn"]
    logger.info(f"Layer 업로드 완료: {layer_arn}")
    return layer_arn


def save_layer_arn(layer_arn: str, output_path: str = "layer_arn.txt") -> None:
    """Layer ARN을 파일로 저장합니다 (Lambda 연결 시 참조용)."""
    with open(output_path, "w") as f:
        f.write(layer_arn)
    logger.info(f"Layer ARN 저장됨: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Lambda Layer 생성 및 업로드")
    parser.add_argument(
        "--packages", nargs="+", default=DEFAULT_PACKAGES, help="설치할 패키지 목록"
    )
    parser.add_argument("--name", default=DEFAULT_LAYER_NAME, help="Layer 이름")
    parser.add_argument("--output", default="layer_arn.txt", help="ARN 저장 파일 경로")
    args = parser.parse_args()

    zip_buffer = create_layer_zip(args.packages)
    layer_arn = publish_layer(args.name, args.packages, zip_buffer)
    save_layer_arn(layer_arn, args.output)

    print(f"\n✅ Layer ARN: {layer_arn}")
    print(f"   다음 단계: scripts/deploy_lambda.py 에서 이 ARN을 Lambda에 연결하세요.")


if __name__ == "__main__":
    main()
