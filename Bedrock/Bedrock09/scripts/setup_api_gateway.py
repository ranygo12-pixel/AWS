"""
API Gateway 생성 및 설정 스크립트
REST API → /review POST 엔드포인트 → Lambda 프록시 통합 → 배포까지 수행합니다.

사용법:
    python scripts/setup_api_gateway.py
"""

import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
FUNCTION_NAME = "codebuddy-orchestrator"
API_NAME = "CodeBuddyAPI"
STAGE_NAME = "prod"


def get_account_id() -> str:
    sts = boto3.client("sts", region_name=AWS_REGION)
    return sts.get_caller_identity()["Account"]


def get_lambda_arn(lambda_client, function_name: str) -> str:
    response = lambda_client.get_function(FunctionName=function_name)
    return response["Configuration"]["FunctionArn"]


def create_rest_api(apigw_client) -> str:
    """REST API를 생성하고 API ID를 반환합니다."""
    response = apigw_client.create_rest_api(
        name=API_NAME,
        description="CodeBuddy Agent Webhook API",
        endpointConfiguration={"types": ["REGIONAL"]},
    )
    api_id = response["id"]
    logger.info(f"REST API 생성 완료: {api_id}")
    return api_id


def get_root_resource_id(apigw_client, api_id: str) -> str:
    resources = apigw_client.get_resources(restApiId=api_id)
    return next(r for r in resources["items"] if r["path"] == "/")["id"]


def create_review_resource(apigw_client, api_id: str, root_id: str) -> str:
    """/review 리소스를 생성하고 리소스 ID를 반환합니다."""
    resource = apigw_client.create_resource(
        restApiId=api_id,
        parentId=root_id,
        pathPart="review",
    )
    resource_id = resource["id"]
    logger.info(f"/review 리소스 생성 완료: {resource_id}")
    return resource_id


def setup_post_method(apigw_client, api_id: str, resource_id: str):
    """POST 메서드를 생성하고 API Key 인증을 적용합니다."""
    apigw_client.put_method(
        restApiId=api_id,
        resourceId=resource_id,
        httpMethod="POST",
        authorizationType="NONE",
        apiKeyRequired=True,  # API Key 필수
    )
    logger.info("POST 메서드 생성 완료 (API Key 인증 활성화)")


def setup_lambda_integration(
    apigw_client, api_id: str, resource_id: str, lambda_arn: str, account_id: str
):
    """Lambda 프록시 통합을 설정합니다."""
    uri = (
        f"arn:aws:apigateway:{AWS_REGION}:lambda:path/2015-03-31"
        f"/functions/{lambda_arn}/invocations"
    )
    apigw_client.put_integration(
        restApiId=api_id,
        resourceId=resource_id,
        httpMethod="POST",
        type="AWS_PROXY",
        integrationHttpMethod="POST",
        uri=uri,
    )
    logger.info("Lambda 프록시 통합 설정 완료")

    # API Gateway가 Lambda를 호출할 수 있도록 권한 부여
    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    try:
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="AllowAPIGatewayInvoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{AWS_REGION}:{account_id}:{api_id}/*/*",
        )
        logger.info("Lambda 호출 권한 부여 완료")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            logger.info("Lambda 호출 권한 이미 존재 — 스킵")
        else:
            raise


def setup_cors(apigw_client, api_id: str, resource_id: str):
    """OPTIONS 메서드를 추가하여 CORS를 활성화합니다."""
    apigw_client.put_method(
        restApiId=api_id,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        authorizationType="NONE",
        apiKeyRequired=False,
    )
    apigw_client.put_integration(
        restApiId=api_id,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        type="MOCK",
        requestTemplates={"application/json": '{"statusCode": 200}'},
    )
    apigw_client.put_integration_response(
        restApiId=api_id,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        statusCode="200",
        responseParameters={
            "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Api-Key'",
            "method.response.header.Access-Control-Allow-Methods": "'POST,OPTIONS'",
            "method.response.header.Access-Control-Allow-Origin": "'*'",
        },
    )
    apigw_client.put_method_response(
        restApiId=api_id,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        statusCode="200",
        responseParameters={
            "method.response.header.Access-Control-Allow-Headers": False,
            "method.response.header.Access-Control-Allow-Methods": False,
            "method.response.header.Access-Control-Allow-Origin": False,
        },
    )
    logger.info("CORS(OPTIONS) 설정 완료")


def deploy_api(apigw_client, api_id: str) -> str:
    """API를 prod 스테이지로 배포하고 엔드포인트 URL을 반환합니다."""
    apigw_client.create_deployment(restApiId=api_id, stageName=STAGE_NAME)
    endpoint = (
        f"https://{api_id}.execute-api.{AWS_REGION}.amazonaws.com/{STAGE_NAME}/review"
    )
    logger.info(f"API 배포 완료: {endpoint}")
    return endpoint


def create_api_key(apigw_client, api_id: str) -> tuple[str, str]:
    """API Key와 Usage Plan을 생성하고 연결합니다."""
    key = apigw_client.create_api_key(
        name="CodeBuddyKey",
        description="CodeBuddy webhook API key",
        enabled=True,
    )
    key_id = key["id"]
    key_value = key["value"]

    plan = apigw_client.create_usage_plan(
        name="CodeBuddyPlan",
        description="Rate limiting: 1000 req/day, 50 req/sec burst",
        apiStages=[{"apiId": api_id, "stage": STAGE_NAME}],
        throttle={"rateLimit": 10, "burstLimit": 50},
        quota={"limit": 1000, "period": "DAY"},
    )
    apigw_client.create_usage_plan_key(
        usagePlanId=plan["id"],
        keyId=key_id,
        keyType="API_KEY",
    )
    logger.info(f"API Key 생성 및 Usage Plan 연결 완료")
    return key_id, key_value


def save_outputs(endpoint: str, api_key_value: str):
    """생성된 엔드포인트와 API Key를 파일로 저장합니다."""
    outputs = {"endpoint": endpoint, "api_key": api_key_value}
    with open("api_outputs.json", "w") as f:
        json.dump(outputs, f, indent=2)
    logger.info("api_outputs.json 저장 완료 (.gitignore에 포함됨)")


def main():
    apigw_client = boto3.client("apigateway", region_name=AWS_REGION)
    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    account_id = get_account_id()
    lambda_arn = get_lambda_arn(lambda_client, FUNCTION_NAME)

    api_id = create_rest_api(apigw_client)
    root_id = get_root_resource_id(apigw_client, api_id)
    resource_id = create_review_resource(apigw_client, api_id, root_id)

    setup_post_method(apigw_client, api_id, resource_id)
    setup_lambda_integration(apigw_client, api_id, resource_id, lambda_arn, account_id)
    setup_cors(apigw_client, api_id, resource_id)

    # 배포 전 잠시 대기 (통합 설정 반영)
    time.sleep(2)
    endpoint = deploy_api(apigw_client, api_id)
    _, api_key_value = create_api_key(apigw_client, api_id)

    save_outputs(endpoint, api_key_value)

    print(f"\n✅ API Gateway 배포 완료")
    print(f"   엔드포인트 : {endpoint}")
    print(f"   API Key    : {api_key_value}")
    print(f"\n   테스트 명령:")
    print(f'   curl -X POST {endpoint} \\')
    print(f'     -H "Content-Type: application/json" \\')
    print(f'     -H "x-api-key: {api_key_value}" \\')
    print(f'     -d \'{{"pr_url": "https://github.com/owner/repo/pull/1", "action": "review"}}\'')


if __name__ == "__main__":
    main()
