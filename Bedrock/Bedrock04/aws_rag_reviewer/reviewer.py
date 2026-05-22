"""
aws_rag_reviewer: Amazon Bedrock 기반 코드 분석 및 리뷰 핵심 로직 모듈
"""
import boto3

def style_check(code, kb_id):
    """지식 기반(Knowledge Base)을 활용한 PEP8 및 일반 스타일 검사"""
    client = boto3.client('bedrock-agent-runtime')
    prompt = f"""
    당신은 코드 스타일 검사기입니다. 다음 코드에서 PEP8 또는 일반적인 스타일 규칙을 위반한 부분을 찾아주세요.
    형식은 반드시 아래 형식을 지켜주세요:
    [라인번호] 위반 유형: 설명

    코드:
    {code}
    """
    response = client.retrieve_and_generate(
        input={'text': prompt},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': kb_id,
                'modelArn': 'global.anthropic.claude-sonnet-4-6'
            }
        }
    )
    return response['output']['text']

def check_security(code, kb_id):
    """KB 검색 후 Bedrock Runtime(Claude)을 활용한 보안 취약점 심층 분석"""
    agent_client = boto3.client('bedrock-agent-runtime')
    runtime_client = boto3.client('bedrock-runtime')

    retrieve_response = agent_client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={'text': 'OWASP security vulnerabilities SQL Injection hardcoded credentials'}
    )
    context = "\n".join([r['content']['text'] for r in retrieve_response.get('retrievalResults', [])])

    prompt = f"""아래 보안 가이드를 참고하여 코드의 보안 취약점을 분석해주세요.

보안 가이드:
{context}

분석할 코드:
{code}

각 항목을 위치 / 유형 / 심각도 / 개선 방법 형식으로 작성해주세요.
"""
    
    response = runtime_client.converse(
        modelId='global.anthropic.claude-sonnet-4-6',
        messages=[{"role": "user", "content": [{"text": prompt}]}]
    )
    return response['output']['message']['content'][0]['text']

def generate_security_report_json(code, kb_id):
    """보안 취약점 결과를 정형화된 JSON 스트링으로 받아옵니다."""
    client = boto3.client('bedrock-agent-runtime')
    prompt = f"""
    다음 코드의 보안 취약점을 분석하고 JSON 형식으로 보고서를 작성해주세요.

    형식:
    {{
        "vulnerabilities": [
            {{
                "line": 라인번호,
                "type": "취약점 유형",
                "severity": "CRITICAL/HIGH/MEDIUM/LOW",
                "description": "설명",
                "suggestion": "수정 제안"
            }}
        ],
        "summary": "전체 평가"
    }}

    코드:
    {code}
    """
    response = client.retrieve_and_generate(
        input={'text': prompt},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': kb_id,
                'modelArn': 'global.anthropic.claude-sonnet-4-6'
            }
        }
    )
    return response['output']['text']

def check_multilang(code, language, kb_id):
    """언어별 스타일 가이드 기준 검사"""
    client = boto3.client('bedrock-agent-runtime')
    prompt = f"""
    {language} 코드 스타일 가이드에 따라 다음 코드를 검사해주세요.
    언어: {language}
    코드:
    {code}
    """
    response = client.retrieve_and_generate(
        input={'text': prompt},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': kb_id,
                'modelArn': 'global.anthropic.claude-sonnet-4-6'
            }
        }
    )
    return response['output']['text']

def semantic_search_query(question, kb_id, topk=5):
    """검색 옵션을 SEMANTIC 유형으로 강제하여 튜닝 검색을 진행합니다."""
    client = boto3.client('bedrock-agent-runtime')
    response = client.retrieve_and_generate(
        input={'text': question},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': kb_id,
                'modelArn': 'global.anthropic.claude-sonnet-4-6',
                'retrievalConfiguration': {
                    'vectorSearchConfiguration': {
                        'numberOfResults': topk,
                        'overrideSearchType': 'SEMANTIC'
                    }
                }
            }
        }
    )
    return response['output']['text']
