"""
IAM 역할 생성 스크립트
Orchestrator Lambda에 필요한 IAM 역할과 정책을 생성하고 연결합니다.

사용법:
    python scripts/setup_iam.py
"""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
ROLE_NAME = "CodeBuddyOrchestratorRole"
INLINE_POLICY_NAME = "CodeBuddyBedrockLogsPolicy"

# Lambda가 역할을 수임할 수 있도록 하는 신뢰 정책
TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

# Bedrock Agent 호출 + CloudWatch 로그 권한 (최소 권한 원칙)
INLINE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "bedrock:InvokeAgent",
            "Resource": f"arn:aws:bedrock:{AWS_REGION}:*:agent/*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            "Resource": "*",
        },
    ],
}


def create_role(iam_client) -> str:
    """IAM 역할을 생성하고 ARN을 반환합니다."""
    try:
        response = iam_client.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Description="CodeBuddy Orchestrator Lambda execution role",
        )
        role_arn = response["Role"]["Arn"]
        logger.info(f"IAM 역할 생성: {role_arn}")
        return role_arn
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            response = iam_client.get_role(RoleName=ROLE_NAME)
            role_arn = response["Role"]["Arn"]
            logger.info(f"기존 IAM 역할 사용: {role_arn}")
            return role_arn
        raise


def attach_policies(iam_client):
    """관리형 정책과 인라인 정책을 역할에 연결합니다."""
    # AWS 관리형 기본 실행 정책 연결
    managed_policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    iam_client.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=managed_policy_arn)
    logger.info(f"관리형 정책 연결 완료: {managed_policy_arn}")

    # 인라인 정책 추가 (Bedrock + CloudWatch)
    iam_client.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=INLINE_POLICY_NAME,
        PolicyDocument=json.dumps(INLINE_POLICY),
    )
    logger.info(f"인라인 정책 추가 완료: {INLINE_POLICY_NAME}")


def main():
    iam_client = boto3.client("iam", region_name=AWS_REGION)

    role_arn = create_role(iam_client)
    attach_policies(iam_client)

    print(f"\n✅ IAM 역할 준비 완료")
    print(f"   Role ARN : {role_arn}")
    print(f"   다음 단계: scripts/deploy_lambda.py --create 로 Lambda를 배포하세요.")


if __name__ == "__main__":
    main()
