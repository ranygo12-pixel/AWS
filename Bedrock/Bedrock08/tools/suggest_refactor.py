"""
Tool: suggest_refactor
----------------------
Python 코드를 분석해 더 나은 구조·성능·유지보수성을 위한 리팩토링을 제안합니다.

[리팩토링이란]
  동작(기능)을 변경하지 않고 코드 구조를 개선하는 작업으로,
  가독성 향상, 유지보수 용이, 성능 개선을 목표로 합니다.

[focus 파라미터]
  ┌──────────────────┬────────────────────────────────────────────────────────┐
  │ 값               │ 중점 사항                                              │
  ├──────────────────┼────────────────────────────────────────────────────────┤
  │ readability      │ 직관적 변수/함수명, 거대 함수 분할, 핵심 주석 추가    │
  │ performance      │ 불필요한 루프 제거, 최적 자료구조(Set/Dict) 활용       │
  │ maintainability  │ 디자인 패턴 적용, 관심사 분리(SoC), 결합도 감소       │
  └──────────────────┴────────────────────────────────────────────────────────┘

[출력 형식]
  1. 문제점 분석 (현재 코드의 단점)
  2. 개선된 코드 (실제 동작이 동일한 리팩토링 결과)
  3. 변경 이유 (장점 설명)

[구현 방식]
  Lambda 내부에서 Bedrock Converse API로 Claude Sonnet을 호출합니다.
  temperature=0.3 으로 창의적이되 일관된 제안을 유도합니다.

[Lambda 이벤트 형식] (Amazon Bedrock Agent Action Group)
  event["parameters"] = [
      {"name": "code",  "value": "<소스코드>"},
      {"name": "focus", "value": "readability|performance|maintainability"}  # 선택
  ]
"""

import json
import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_bedrock = boto3.client("bedrock-runtime", region_name="ap-northeast-2")
MODEL_ID = "global.anthropic.claude-sonnet-4-6"

# 허용된 focus 값
VALID_FOCUS = {"readability", "performance", "maintainability"}


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

_FOCUS_HINTS = {
    "readability": (
        "직관적인 변수명/함수명 변경, 거대한 함수를 쪼개는 단위 분할, "
        "가독성을 높이는 핵심 주석 추가에 집중하세요."
    ),
    "performance": (
        "중복되거나 불필요한 루프 제거, 시간 복잡도를 낮추기 위한 "
        "최적의 자료구조(Set, Dict 등) 활용에 집중하세요."
    ),
    "maintainability": (
        "변경과 확장에 유리하도록 적절한 디자인 패턴 적용, "
        "모듈 간 결합도를 낮추는 관심사 분리(SoC)에 집중하세요."
    ),
}


def _build_prompt(code: str, focus: str) -> str:
    """
    리팩토링 제안 프롬프트를 조립합니다.

    focus 값에 따라 Claude가 어떤 관점에서 코드를 검토할지 힌트를 제공합니다.
    개선된 코드는 원본과 동일한 동작을 보장해야 한다는 제약을 명시합니다.
    """
    focus_hint = _FOCUS_HINTS.get(focus, _FOCUS_HINTS["maintainability"])

    return f"""당신은 10년 경력의 시니어 Python 개발자입니다.
다음 코드를 리팩토링하여 더 나은 구조를 제안해주세요.

[원본 코드]
```python
{code}
```

[리팩토링 목표: {focus}]
{focus_hint}

[제안 형식 - 반드시 아래 구조를 따르세요]

## 문제점 분석
현재 코드의 단점을 구체적으로 나열하세요.

## 개선된 코드
```python
# 리팩토링된 코드 전체
```

## 변경 이유
각 변경 사항이 왜 더 나은지 간결하게 설명하세요.

[제약]
- 개선된 코드는 원본과 동일한 동작(입출력)을 보장해야 합니다.
- 불필요한 의존성을 추가하지 마세요.
"""


# ---------------------------------------------------------------------------
# 리팩토링 제안 핵심 로직
# ---------------------------------------------------------------------------

def suggest_refactor(code: str, focus: str = "maintainability") -> str:
    """
    Bedrock Converse API를 호출해 리팩토링 제안 텍스트를 반환합니다.

    Args:
        code:  리팩토링 대상 Python 소스 코드
        focus: 리팩토링 관점 (readability / performance / maintainability)

    Returns:
        Markdown 형식의 리팩토링 제안 문자열
    """
    if focus not in VALID_FOCUS:
        logger.warning("알 수 없는 focus '%s' → maintainability 로 대체합니다.", focus)
        focus = "maintainability"

    prompt = _build_prompt(code, focus)

    response = _bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={
            "temperature": 0.3,   # 약간의 창의성 허용
            "maxTokens": 3000,
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
      - code  (필수): 리팩토링할 Python 소스 코드
      - focus (선택): readability | performance | maintainability (기본값: maintainability)
    """
    logger.info("suggest_refactor 이벤트 수신: %s", json.dumps(event))

    try:
        params = {p["name"]: p["value"] for p in event.get("parameters", [])}
        code = params.get("code", "").strip()
        if not code:
            raise ValueError("'code' 파라미터가 비어 있습니다.")

        focus = params.get("focus", "maintainability").strip().lower()

        suggestion = suggest_refactor(code, focus)
        return _build_response(event, 200, {"suggestion": suggestion})

    except Exception as exc:  # noqa: BLE001
        logger.error("suggest_refactor 오류: %s", exc)
        return _build_response(event, 500, {"error": str(exc)})
