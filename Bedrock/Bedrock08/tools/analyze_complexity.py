"""
Tool: analyze_complexity
------------------------
Python 코드의 Cyclomatic Complexity(순환 복잡도)를 분석합니다.

[Cyclomatic Complexity 등급 기준]
  A (1~5)   : 양호       → 유지
  B (6~10)  : 보통       → 주의
  C (11~20) : 복잡       → 리팩토링 고려
  D (21+)   : 매우 복잡  → 즉시 리팩토링

[radon 라이브러리]
  - cc_visit : 코드 내 모든 함수/메서드의 복잡도 블록을 반환
  - cc_rank  : 복잡도 점수를 A~F 등급 문자로 변환

[Lambda 이벤트 형식] (Amazon Bedrock Agent Action Group)
  event["parameters"] = [{"name": "code", "value": "<소스코드>"}]
"""

import ast
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
# 복잡도 분석 핵심 로직
# ---------------------------------------------------------------------------

def analyze_complexity_logic(code: str) -> dict:
    """
    radon cc_visit 으로 순환 복잡도를 측정하고 요약·상세 정보를 반환합니다.

    반환 구조:
      {
        "summary": {
          "total_functions": int,
          "average_complexity": float,
          "max_complexity": int,
          "high_complexity_count": int,       # complexity > 10
          "high_complexity_functions": [...]
        },
        "details": [
          {
            "name": str,
            "complexity": int,
            "rank": str,           # A~F
            "start_line": int,
            "end_line": int
          }, ...
        ]
      }
    """
    try:
        from radon.complexity import cc_visit, cc_rank
    except ImportError as exc:
        raise RuntimeError(
            "radon 라이브러리가 설치되지 않았습니다. "
            "`pip install radon` 을 실행하세요."
        ) from exc

    blocks = cc_visit(code)
    results = []
    high_complexity = []

    for block in blocks:
        complexity = block.complexity
        rank = cc_rank(complexity)
        item = {
            "name": block.name,
            "complexity": complexity,
            "rank": rank,
            "start_line": block.lineno,
            "end_line": block.endline,
        }
        results.append(item)
        if complexity > 10:
            high_complexity.append(item)

    summary = {
        "total_functions": len(results),
        "average_complexity": (
            round(sum(c["complexity"] for c in results) / len(results), 2)
            if results else 0.0
        ),
        "max_complexity": max((c["complexity"] for c in results), default=0),
        "high_complexity_count": len(high_complexity),
        "high_complexity_functions": high_complexity,
    }

    return {"summary": summary, "details": results}


def split_and_analyze(code: str) -> dict:
    """
    1000줄을 초과하는 대형 파일은 Python AST로 함수를 추출한 뒤
    함수 단위로 분할 분석하고 결과를 집계합니다.

    청크 분할 기준:
      - 소스 라인 수가 500 이하 → 그대로 전체 분석
      - 소스 라인 수가 500 초과 → AST 기반 함수 단위 분할
    """
    lines = code.splitlines()
    if len(lines) <= 500:
        return analyze_complexity_logic(code)

    logger.info("코드 길이 %d 줄 → 함수 단위 청크 분할 분석을 시작합니다.", len(lines))

    tree = ast.parse(code)
    chunks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunks.append({
                "name": node.name,
                "code": ast.unparse(node),
                "lineno": node.lineno,
            })

    if not chunks:
        # 함수가 없으면 전체를 통째로 분석
        return analyze_complexity_logic(code)

    all_details: list[dict] = []
    for chunk in chunks:
        try:
            result = analyze_complexity_logic(chunk["code"])
            all_details.extend(result["details"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("함수 '%s' 분석 실패: %s", chunk["name"], exc)

    high_complexity = [d for d in all_details if d["complexity"] > 10]
    summary = {
        "total_functions": len(all_details),
        "average_complexity": (
            round(sum(d["complexity"] for d in all_details) / len(all_details), 2)
            if all_details else 0.0
        ),
        "max_complexity": max((d["complexity"] for d in all_details), default=0),
        "high_complexity_count": len(high_complexity),
        "high_complexity_functions": high_complexity,
    }
    return {"summary": summary, "details": all_details}


# ---------------------------------------------------------------------------
# Lambda 핸들러
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:  # noqa: ANN001
    """
    Bedrock Agent Action Group 진입점.

    파라미터:
      - code (필수): 분석할 Python 소스 코드 문자열
    """
    logger.info("analyze_complexity 이벤트 수신: %s", json.dumps(event))

    try:
        params = {p["name"]: p["value"] for p in event.get("parameters", [])}
        code = params.get("code", "").strip()
        if not code:
            raise ValueError("'code' 파라미터가 비어 있습니다.")

        response_body = split_and_analyze(code)
        return _build_response(event, 200, response_body)

    except Exception as exc:  # noqa: BLE001
        logger.error("analyze_complexity 오류: %s", exc)
        return _build_response(event, 500, {"error": str(exc)})
