"""
scripts/setup_iam.py
IAM 역할 생성 스크립트
- Lambda 실행 역할 생성
- Bedrock Agent 실행 역할 생성
"""
import boto3
import json
import sys
import botocore.exceptions

REGION = "ap-northeast-2"

iam = boto3.client("iam")
sts = boto3.client("sts")

ACCOUNT_ID = sts.get_caller_identity()["Account"]

# ── Lambda 실행 역할 ──────────────────────────────────────────────────
LAMBDA_ROLE_NAME = "CodeBuddy-Lambda-Role"

LAMBDA_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

# ── Bedrock Agent 실행 역할 ───────────────────────────────────────────
AGENT_ROLE_NAME = "CodeBuddy-BedrockAgent-Role"

AGENT_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "bedrock.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

AGENT_INLINE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel"],
            "Resource": f"arn:aws:bedrock:{REGION}::foundation-model/*",
        },
        {
            "Effect": "Allow",
            "Action": ["lambda:InvokeFunction"],
            "Resource": f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:codebuddy-*",
        },
    ],
}


def create_or_get_role(role_name: str, trust_policy: dict) -> str:
    """역할 생성 또는 기존 역할 ARN 반환"""
    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
        )
        print(f"  ✅ 역할 생성: {role_name}")
        return role["Role"]["Arn"]
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"
            print(f"  ⚠️  기존 역할 사용: {role_name}")
            return arn
        raise


def setup_lambda_role() -> str:
    print("\n[1/2] Lambda 실행 역할 설정 중...")
    arn = create_or_get_role(LAMBDA_ROLE_NAME, LAMBDA_TRUST_POLICY)

    # CloudWatch Logs 권한 부착
    iam.attach_role_policy(
        RoleName=LAMBDA_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    print(f"  ✅ Lambda 역할 ARN: {arn}")
    return arn


def setup_agent_role() -> str:
    print("\n[2/2] Bedrock Agent 실행 역할 설정 중...")
    arn = create_or_get_role(AGENT_ROLE_NAME, AGENT_TRUST_POLICY)

    # 인라인 정책 추가
    iam.put_role_policy(
        RoleName=AGENT_ROLE_NAME,
        PolicyName="CodeBuddy-AgentPolicy",
        PolicyDocument=json.dumps(AGENT_INLINE_POLICY),
    )
    print(f"  ✅ Agent 역할 ARN: {arn}")
    return arn


def main():
    print("=" * 50)
    print("  CodeBuddy IAM 역할 설정")
    print("=" * 50)

    lambda_role_arn = setup_lambda_role()
    agent_role_arn = setup_agent_role()

    print("\n" + "=" * 50)
    print("설정 완료! 아래 값을 GitHub Secrets에 저장하세요:")
    print(f"  LAMBDA_ROLE_ARN  = {lambda_role_arn}")
    print(f"  AGENT_ROLE_ARN   = {agent_role_arn}")
    print("=" * 50)


if __name__ == "__main__":
    main()
