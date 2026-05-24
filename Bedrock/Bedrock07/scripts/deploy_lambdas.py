"""
scripts/deploy_lambdas.py
Lambda 함수 패키징 및 배포 스크립트

환경 변수 (GitHub Secrets에서 주입):
  AWS_DEFAULT_REGION   - AWS 리전 (기본: ap-northeast-2)
  LAMBDA_ROLE_ARN      - Lambda 실행 역할 ARN
  GITHUB_TOKEN         - GitHub Personal Access Token
  SLACK_WEBHOOK_URL    - Slack Incoming Webhook URL
  AGENT_ID             - Bedrock Agent ID (권한 추가용)
"""
import boto3
import botocore.exceptions
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-2")
LAMBDA_ROLE_ARN = os.environ["LAMBDA_ROLE_ARN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
AGENT_ID = os.environ.get("AGENT_ID", "")

ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]

lambda_client = boto3.client("lambda", region_name=REGION)

# 배포할 Lambda 함수 목록
LAMBDAS = [
    {
        "name": "codebuddy-github-pr",
        "source_dir": "lambdas/get_pr",
        "handler": "index.handler",
        "runtime": "python3.12",
        "timeout": 30,
        "env_vars": {"GITHUB_TOKEN": GITHUB_TOKEN},
        "pip_packages": ["PyGithub"],
        "description": "GitHub PR 정보 조회",
    },
    {
        "name": "codebuddy-github-pr-comment",
        "source_dir": "lambdas/post_comment",
        "handler": "index.handler",
        "runtime": "python3.12",
        "timeout": 30,
        "env_vars": {"GITHUB_TOKEN": GITHUB_TOKEN},
        "pip_packages": ["PyGithub"],
        "description": "GitHub PR 댓글 추가",
    },
    {
        "name": "codebuddy-slack-notifier",
        "source_dir": "lambdas/slack_notifier",
        "handler": "index.handler",
        "runtime": "python3.12",
        "timeout": 30,
        "env_vars": {"SLACK_WEBHOOK_URL": SLACK_WEBHOOK_URL},
        "pip_packages": [],          # urllib만 사용 (표준 라이브러리)
        "description": "Slack 메시지 전송",
    },
]


def build_zip(source_dir: str, pip_packages: list) -> bytes:
    """Lambda 배포 패키지(ZIP) 생성"""
    tmp = Path(f"/tmp/lambda_build_{source_dir.replace('/', '_')}")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    # 소스 파일 복사
    src = Path(source_dir)
    for f in src.glob("*.py"):
        shutil.copy(f, tmp / f.name)

    # 의존 라이브러리 설치
    if pip_packages:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *pip_packages, "-t", str(tmp)],
            stdout=subprocess.DEVNULL,
        )

    # ZIP 압축
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in tmp.rglob("*"):
            if fp.is_file():
                zf.write(fp, fp.relative_to(tmp))
    buf.seek(0)

    shutil.rmtree(tmp)
    return buf.getvalue()


def wait_for_lambda(name: str, max_wait: int = 60):
    """Lambda 함수가 Active 상태가 될 때까지 대기"""
    for _ in range(max_wait):
        resp = lambda_client.get_function_configuration(FunctionName=name)
        state = resp.get("State", "")
        last_update = resp.get("LastUpdateStatus", "Successful")
        if state == "Active" and last_update == "Successful":
            return
        time.sleep(1)
    raise TimeoutError(f"Lambda '{name}'가 Active 상태가 되지 않았습니다.")


def deploy_lambda(cfg: dict) -> str:
    """Lambda 함수 생성 또는 업데이트 후 ARN 반환"""
    name = cfg["name"]
    print(f"\n  📦 패키징: {name} ({cfg['description']})")
    zip_bytes = build_zip(cfg["source_dir"], cfg["pip_packages"])

    try:
        # 신규 생성
        resp = lambda_client.create_function(
            FunctionName=name,
            Runtime=cfg["runtime"],
            Role=LAMBDA_ROLE_ARN,
            Handler=cfg["handler"],
            Code={"ZipFile": zip_bytes},
            Environment={"Variables": cfg["env_vars"]},
            Timeout=cfg["timeout"],
            Description=cfg["description"],
        )
        arn = resp["FunctionArn"]
        print(f"  ✅ 생성 완료: {arn}")

    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] != "ResourceConflictException":
            raise
        # 기존 함수 업데이트
        lambda_client.update_function_code(FunctionName=name, ZipFile=zip_bytes)
        wait_for_lambda(name)
        lambda_client.update_function_configuration(
            FunctionName=name,
            Role=LAMBDA_ROLE_ARN,
            Environment={"Variables": cfg["env_vars"]},
            Timeout=cfg["timeout"],
        )
        wait_for_lambda(name)
        arn = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{name}"
        print(f"  ✅ 업데이트 완료: {arn}")

    return arn


def add_bedrock_permission(function_name: str, agent_id: str):
    """Bedrock Agent가 Lambda를 호출할 수 있도록 리소스 기반 정책 추가"""
    if not agent_id:
        print(f"  ⚠️  AGENT_ID 미설정 — {function_name} 권한 추가 생략")
        return

    statement_id = "AllowBedrockAgentInvoke"
    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="bedrock.amazonaws.com",
            SourceArn=f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/{agent_id}",
        )
        print(f"  ✅ Bedrock 호출 권한 추가: {function_name}")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print(f"  ⚠️  이미 권한 존재: {function_name}")
        else:
            raise


def main():
    print("=" * 55)
    print("  CodeBuddy Lambda 함수 배포")
    print("=" * 55)

    arns = {}
    for cfg in LAMBDAS:
        arn = deploy_lambda(cfg)
        arns[cfg["name"]] = arn
        add_bedrock_permission(cfg["name"], AGENT_ID)

    print("\n" + "=" * 55)
    print("배포 완료! 아래 ARN을 GitHub Secrets에 저장하세요:")
    for name, arn in arns.items():
        key = name.upper().replace("-", "_") + "_ARN"
        print(f"  {key} = {arn}")
    print("=" * 55)

    # GitHub Actions outputs 저장
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as f:
            for name, arn in arns.items():
                key = name.replace("-", "_") + "_arn"
                f.write(f"{key}={arn}\n")


if __name__ == "__main__":
    main()
