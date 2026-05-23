"""
utils/aws_client.py
───────────────────
Boto3 클라이언트를 생성하는 팩토리 함수 모음.
모든 모듈이 이 함수를 통해 클라이언트를 얻으므로
리전 설정이 한 곳에 집중됩니다.
"""

import boto3
from config.settings import AWS_REGION


def get_bedrock_agent_client():
    """bedrock-agent 컨트롤 플레인 클라이언트 (Agent 생성/관리)"""
    return boto3.client("bedrock-agent", region_name=AWS_REGION)


def get_bedrock_agent_runtime_client():
    """bedrock-agent-runtime 클라이언트 (Agent 호출)"""
    return boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)
