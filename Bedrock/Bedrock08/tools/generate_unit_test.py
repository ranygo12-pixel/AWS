"""
Tool: generate_unit_test
------------------------
주어진 Python 함수 코드를 분석해 pytest 단위 테스트 코드를 자동 생성합니다.

[생성 포함 항목]
  - 정상 입력 테스트
  - 경계값 테스트 (0, None, 빈 리스트 등)
  - 예외 상황 테스트 (잘못된 입력 타입 등)
  - pytest 스타일 (assert, pytest.raises)
  - 함수명 규칙: test_<원본함수명>_<시나리오>

[구현 방식]
  Lambda 함수 내부에서 Amazon Bedrock Converse API를 호출하여
  Claude Sonnet 모델이 완성도 높은 테스트 코드를 생성합니다.
  temperature=0.2 로 낮게 설정해 일관된 출력을 유도합니다.

[Lambda 이벤트 형식] (Amazon Bedrock Agent Action Group)
  event["parameters"] = [
      {"name": "code",          "value": "<소스코드>"},
      {"name": "function_name", "value": "<함수명>"}  # 선택
  ]
"""

import json
import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock Runtime 클라이언트 (Lambda 컨테이너 재사용을 위해 모듈 레벨 초기화)
_bedrock = boto3.client("bedrock-runtime", region_name="ap-northeast-2")

# 사용할 모델 ID
MODEL_ID = "global.anthropic.claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# 응답 헬퍼
# ---------------------------------------------------------------------------

def _build_response(event: dict, status_code: int, body: dict) -> dict:
    """Bedrock Agent Action Group 표준 응답 구조를 생성합니다."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "apiPath": event.get("apiPath"),
            "httpMethod": event.get("httpMethod"),
            "httpStatusCode": status_code,
            "responseBody": {
                "application/json": {"body": body}
            },
        },
    }


# ---------------------------------------------------------------------------
# 프롬프트 설계
# ---------------------------------------------------------------------------

def _build_prompt(code: str, function_name: str | None) -> str:
    """
    테스트 생성 프롬프트를 조립합니다.

    구체적인 요구사항을 명시할수록 Claude가 더 높은 품질의 테스트를 생성합니다.
    테스트 코드만 출력하도록 지시해 후처리 복잡도를 줄입니다.
    """
    target_hint = (
        f"특히 `{function_name}` 함수에 집중하세요.\n" if function_name else ""
    )

    return f"""당신은 숙련된 테스트 엔지니어입니다.
다음 Python 함수에 대한 pytest 단위 테스트 코드를 작성해주세요.
{target_hint}
[함수 코드]
```python
{code}
```

[요구사항]
1. 정상 입력 테스트: 대표적인 유효한 입력으로 올바른 출력이 나오는지 검증
2. 경계값 테스트: 0, None, 빈 리스트, 최솟값/최댓값 등 경계 케이스 검증
3. 예외 상황 테스트: 잘못된 타입이나 범위 초과 입력 시 적절한 예외가 발생하는지 검증
4. pytest 스타일 사용 (assert 구문, pytest.raises 컨텍스트 매니저)
5. 테스트 함수명 규칙: `test_<원본함수명>_<시나리오>` 형식 (예: test_process_data_empty_list)
6. 각 테스트 함수에 한 줄 docstring으로 시나리오 설명 추가

[출력 규칙]
- pytest 테스트 코드만 출력하세요 (설명 문장 없이).
- 코드 블록 마커(```) 없이 순수 Python 코드만 작성하세요.
"""


# ---------------------------------------------------------------------------
# 테스트 생성 핵심 로직
# ---------------------------------------------------------------------------

def generate_tests(code: str, function_name: str | None = None) -> str:
    """
    Bedrock Converse API를 호출해 pytest 테스트 코드를 생성하고 반환합니다.

    Args:
        code: 테스트 대상 Python 소스 코드
        function_name: 집중 분석할 특정 함수명 (None이면 전체 대상)

    Returns:
        생성된 pytest 테스트 코드 문자열
    """
    prompt = _build_prompt(code, function_name)

    response = _bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={
            "temperature": 0.2,   # 낮은 temperature → 일관된 코드 출력
            "maxTokens": 2000,
        },
    )

    return response["output"]["message"]["content"][0]["text"]


# ---------------------------------------------------------------------------
# Lambda 핸들러
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:  # noqa: ANN001
    """
    Bedrock Agent Action Group 진입점.

    파라미터:
      - code          (필수): 테스트를 생성할 Python 소스 코드
      - function_name (선택): 집중 테스트할 함수명
    """
    logger.info("generate_unit_test 이벤트 수신: %s", json.dumps(event))

    try:
        params = {p["name"]: p["value"] for p in event.get("parameters", [])}
        code = params.get("code", "").strip()
        if not code:
            raise ValueError("'code' 파라미터가 비어 있습니다.")

        function_name = params.get("function_name") or None

        test_code = generate_tests(code, function_name)
        return _build_response(event, 200, {"test_code": test_code})

    except Exception as exc:  # noqa: BLE001
        logger.error("generate_unit_test 오류: %s", exc)
        return _build_response(event, 500, {"error": str(exc)})
