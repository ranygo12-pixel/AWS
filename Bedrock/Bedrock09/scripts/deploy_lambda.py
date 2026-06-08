"""
Lambda 함수 배포 스크립트
orchestrator.py를 ZIP으로 패키징하고 AWS Lambda에 생성/업데이트합니다.

사용법:
    # 최초 배포 (함수 생성 + 환경변수 + 레이어 연결)
    python scripts/deploy_lambda.py --create

    # 코드만 업데이트
    python scripts/deploy_lambda.py --update-code

    # 환경변수만 업데이트
    python scripts/deploy_lambda.py --update-config
"""

import argparse
import io
import json
import logging
import os
import zipfile

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
FUNCTION_NAME = "codebuddy-orchestrator"
LAMBDA_SOURCE = os.path.join(os.path.dirname(__file__), "../lambda/orchestrator.py")


def build_zip() -> bytes:
    """orchestrator.py를 ZIP으로 패키징합니다."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.abspath(LAMBDA_SOURCE), "lambda_function.py")
    zip_buffer.seek(0)
    logger.info("Lambda ZIP 패키징 완료")
    return zip_buffer.read()


def get_role_arn(iam_client, role_name: str) -> str:
    """IAM 역할의 ARN을 반환합니다."""
    response = iam_client.get_role(RoleName=role_name)
    return response["Role"]["Arn"]


def create_function(lambda_client, role_arn: str, zip_bytes: bytes, layer_arn: str | None):
    """Lambda 함수를 신규 생성합니다."""
    kwargs = dict(
        FunctionName=FUNCTION_NAME,
        Runtime="python3.12",
        Role=role_arn,
        Handler="lambda_function.handler",
        Code={"ZipFile": zip_bytes},
        Description="CodeBuddy Orchestrator — Bedrock Agent PR reviewer",
        Timeout=300,
        MemorySize=1024,
        Environment={
            "Variables": {
                "AGENT_ID": os.environ.get("AGENT_ID", ""),
                "ALIAS_ID": os.environ.get("ALIAS_ID", ""),
                "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
                "SLACK_WEBHOOK_URL": os.environ.get("SLACK_WEBHOOK_URL", ""),
                "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
            }
        },
    )
    if layer_arn:
        kwargs["Layers"] = [layer_arn]

    response = lambda_client.create_function(**kwargs)
    logger.info(f"Lambda 함수 생성 완료: {response['FunctionArn']}")
    return response


def update_code(lambda_client, zip_bytes: bytes):
    """Lambda 함수 코드만 업데이트합니다."""
    response = lambda_client.update_function_code(
        FunctionName=FUNCTION_NAME,
        ZipFile=zip_bytes,
    )
    logger.info(f"코드 업데이트 완료: {response['FunctionArn']}")
    return response


def update_config(lambda_client, layer_arn: str | None):
    """Lambda 환경변수·메모리·타임아웃 설정을 업데이트합니다."""
    kwargs = dict(
        FunctionName=FUNCTION_NAME,
        MemorySize=1024,
        Timeout=300,
        Environment={
            "Variables": {
                "AGENT_ID": os.environ.get("AGENT_ID", ""),
                "ALIAS_ID": os.environ.get("ALIAS_ID", ""),
                "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
                "SLACK_WEBHOOK_URL": os.environ.get("SLACK_WEBHOOK_URL", ""),
                "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
            }
        },
    )
    if layer_arn:
        kwargs["Layers"] = [layer_arn]

    response = lambda_client.update_function_configuration(**kwargs)
    logger.info("설정 업데이트 완료")
    return response


def load_layer_arn(path: str = "layer_arn.txt") -> str | None:
    """create_layer.py가 저장한 Layer ARN을 읽습니다."""
    if os.path.exists(path):
        with open(path) as f:
            arn = f.read().strip()
            logger.info(f"Layer ARN 로드: {arn}")
            return arn
    logger.warning(f"{path} 없음 — Layer 연결 생략")
    return None


def main():
    parser = argparse.ArgumentParser(description="Lambda 배포 도구")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true", help="함수 신규 생성")
    group.add_argument("--update-code", action="store_true", help="코드만 업데이트")
    group.add_argument("--update-config", action="store_true", help="설정만 업데이트")
    parser.add_argument("--layer-arn-file", default="layer_arn.txt", help="Layer ARN 파일 경로")
    args = parser.parse_args()

    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    iam_client = boto3.client("iam", region_name=AWS_REGION)
    layer_arn = load_layer_arn(args.layer_arn_file)

    if args.create:
        role_arn = get_role_arn(iam_client, "CodeBuddyOrchestratorRole")
        zip_bytes = build_zip()
        create_function(lambda_client, role_arn, zip_bytes, layer_arn)

    elif args.update_code:
        zip_bytes = build_zip()
        update_code(lambda_client, zip_bytes)

    elif args.update_config:
        update_config(lambda_client, layer_arn)

    print("\n✅ 배포 완료")


if __name__ == "__main__":
    main()
