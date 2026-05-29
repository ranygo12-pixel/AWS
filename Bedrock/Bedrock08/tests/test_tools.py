"""
tests/test_tools.py
-------------------
Bing Code 각 Tool의 핵심 로직을 검증하는 pytest 테스트 모음입니다.

[테스트 전략]
  - AWS 호출이 필요한 부분(Bedrock Converse, GitHub API)은 unittest.mock 으로 대체합니다.
  - radon 기반 복잡도 계산은 실제 라이브러리를 사용해 결과 구조를 검증합니다.
  - Lambda handler 의 입출력 형식(Bedrock Agent 응답 스키마)을 end-to-end 로 확인합니다.

[실행 방법]
  pytest tests/ -v
"""

import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 경로 설정 (프로젝트 루트 기준 상대 임포트 지원)
# ---------------------------------------------------------------------------
sys.path.insert(0, ".")
sys.path.insert(0, "tools")

# boto3 가 설치되지 않은 환경(테스트 서버 등)을 위해 미리 mock 모듈을 등록합니다.
# 실제 AWS 호출 여부는 각 테스트에서 개별 MagicMock 으로 제어합니다.
if "boto3" not in sys.modules:
    _boto3_mock = types.ModuleType("boto3")
    _boto3_mock.client = MagicMock(return_value=MagicMock())
    sys.modules["boto3"] = _boto3_mock


# ===========================================================================
# 공통 헬퍼
# ===========================================================================

def _make_event(api_path: str, method: str, **params) -> dict:
    """Bedrock Agent Action Group 이벤트 객체를 생성합니다."""
    return {
        "actionGroup": "CodeAnalysisTools",
        "apiPath": api_path,
        "httpMethod": method,
        "parameters": [{"name": k, "value": str(v)} for k, v in params.items()],
    }


# ===========================================================================
# analyze_complexity
# ===========================================================================

class TestAnalyzeComplexityLogic:
    """radon 기반 복잡도 분석 핵심 로직 테스트"""

    @pytest.fixture(autouse=True)
    def _import(self):
        pytest.importorskip("radon", reason="radon 미설치 → 스킵")
        from tools.analyze_complexity import analyze_complexity_logic
        self.analyze = analyze_complexity_logic

    def test_simple_function_returns_low_complexity(self):
        """단순 함수는 복잡도 1~2 를 반환해야 합니다."""
        code = "def hello():\n    return 'hello'"
        result = self.analyze(code)
        assert result["summary"]["total_functions"] == 1
        assert result["summary"]["max_complexity"] <= 2

    def test_branchy_function_has_higher_complexity(self):
        """분기가 많은 함수는 더 높은 복잡도 값을 가져야 합니다."""
        code = """
def process(x):
    if x > 0:
        if x % 2 == 0:
            return x * 2
        else:
            return x * 3
    else:
        return 0
"""
        result = self.analyze(code)
        assert result["summary"]["max_complexity"] >= 3

    def test_response_structure(self):
        """반환 딕셔너리가 summary/details 키를 포함해야 합니다."""
        code = "def f(x):\n    return x"
        result = self.analyze(code)
        assert "summary" in result
        assert "details" in result
        summary = result["summary"]
        for key in ("total_functions", "average_complexity", "max_complexity",
                    "high_complexity_count", "high_complexity_functions"):
            assert key in summary, f"summary 에 '{key}' 키가 없습니다."

    def test_empty_code_returns_zero_functions(self):
        """빈 코드는 함수가 0개인 결과를 반환해야 합니다."""
        result = self.analyze("x = 1")
        assert result["summary"]["total_functions"] == 0

    def test_high_complexity_threshold(self):
        """복잡도 > 10 인 함수가 high_complexity_functions 에 포함돼야 합니다."""
        branches = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(12))
        code = f"def complex_func(x):\n{branches}\n    return -1"
        result = self.analyze(code)
        assert result["summary"]["high_complexity_count"] >= 1


class TestAnalyzeComplexityHandler:
    """Lambda handler 입출력 형식 테스트"""

    @pytest.fixture(autouse=True)
    def _import(self):
        pytest.importorskip("radon", reason="radon 미설치 → 스킵")
        from tools.analyze_complexity import handler
        self.handler = handler

    def test_handler_returns_200_for_valid_code(self):
        """유효한 코드 입력 시 httpStatusCode 200 을 반환해야 합니다."""
        event = _make_event("/complexity", "POST", code="def f(x):\n    return x")
        resp = self.handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200

    def test_handler_returns_500_for_empty_code(self):
        """빈 code 파라미터 시 httpStatusCode 500 을 반환해야 합니다."""
        event = _make_event("/complexity", "POST", code="")
        resp = self.handler(event, None)
        assert resp["response"]["httpStatusCode"] == 500


# ===========================================================================
# generate_unit_test
# ===========================================================================

class TestGenerateUnitTestHandler:
    """generate_unit_test Lambda handler 테스트 (Bedrock mock)"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import tools.generate_unit_test as _mod
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "def test_sample():\n    assert True"}]
                }
            }
        }
        patcher = patch.object(_mod, "_bedrock", mock_bedrock)
        patcher.start()
        self.mock_bedrock = mock_bedrock
        yield
        patcher.stop()

    def test_handler_200_with_valid_code(self):
        from tools.generate_unit_test import handler
        code = "def add(a, b):\n    return a + b"
        event = _make_event("/unittest", "POST", code=code)
        resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200
        body = resp["response"]["responseBody"]["application/json"]["body"]
        assert "test_code" in body

    def test_handler_500_for_empty_code(self):
        from tools.generate_unit_test import handler
        event = _make_event("/unittest", "POST", code="")
        resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 500

    def test_bedrock_called_with_low_temperature(self):
        """테스트 생성 시 temperature 0.2 로 Bedrock을 호출해야 합니다."""
        from tools.generate_unit_test import handler
        code = "def multiply(a, b):\n    return a * b"
        event = _make_event("/unittest", "POST", code=code)
        handler(event, None)
        call_kwargs = self.mock_bedrock.converse.call_args[1]
        assert call_kwargs["inferenceConfig"]["temperature"] == 0.2


# ===========================================================================
# suggest_refactor
# ===========================================================================

class TestSuggestRefactorHandler:
    """suggest_refactor Lambda handler 테스트 (Bedrock mock)"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import tools.suggest_refactor as _mod
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "## 문제점 분석\n개선 가능합니다."}]
                }
            }
        }
        patcher = patch.object(_mod, "_bedrock", mock_bedrock)
        patcher.start()
        self.mock_bedrock = mock_bedrock
        yield
        patcher.stop()

    def test_handler_200_default_focus(self):
        """focus 미지정 시 maintainability 로 동작해야 합니다."""
        from tools.suggest_refactor import handler
        code = "def calc(x):\n    return x * 2"
        event = _make_event("/refactor", "POST", code=code)
        resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200
        body = resp["response"]["responseBody"]["application/json"]["body"]
        assert "suggestion" in body

    def test_handler_200_with_explicit_focus(self):
        """유효한 focus 값(readability, performance, maintainability) 모두 처리해야 합니다."""
        from tools.suggest_refactor import handler
        code = "def f(x):\n    return x"
        for focus in ("readability", "performance", "maintainability"):
            event = _make_event("/refactor", "POST", code=code, focus=focus)
            resp = handler(event, None)
            assert resp["response"]["httpStatusCode"] == 200

    def test_handler_500_for_empty_code(self):
        from tools.suggest_refactor import handler
        event = _make_event("/refactor", "POST", code="")
        resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 500

    def test_invalid_focus_falls_back_to_maintainability(self):
        """잘못된 focus 는 maintainability 로 대체되어 500 이 발생하지 않아야 합니다."""
        from tools.suggest_refactor import suggest_refactor
        result = suggest_refactor("def f(): pass", focus="unknown_focus")
        assert isinstance(result, str)


# ===========================================================================
# github_pr  (GitHub API mock)
# ===========================================================================

class TestGithubPrHandler:
    """github_pr Lambda handler 테스트 (urllib mock)"""

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token-for-test")

    def _mock_github(self, pr_response: dict, files_response: list):
        responses = iter([pr_response, files_response])
        def _fake_request(path, method="GET", payload=None):
            return next(responses)
        return patch("tools.github_pr._github_request", side_effect=_fake_request)

    def test_get_pr_returns_pr_info_and_files(self):
        from tools.github_pr import handler
        fake_pr = {
            "title": "Fix bug", "state": "open",
            "user": {"login": "dev"}, "created_at": "2025-01-01T00:00:00Z", "body": "desc",
        }
        fake_files = [{
            "filename": "main.py", "status": "modified",
            "additions": 5, "deletions": 2, "patch": "def foo(): pass",
        }]
        with self._mock_github(fake_pr, fake_files):
            event = _make_event("/pr", "GET", owner="org", repo="repo", pr_number=1)
            resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200
        body = resp["response"]["responseBody"]["application/json"]["body"]
        assert "pr_info" in body
        assert body["pr_info"]["title"] == "Fix bug"

    def test_post_comment_returns_comment_url(self):
        from tools.github_pr import handler
        fake_comment = {"html_url": "https://github.com/...", "id": 42}
        with patch("tools.github_pr._github_request", return_value=fake_comment):
            event = _make_event("/pr/comment", "POST",
                                owner="org", repo="repo", pr_number=1, comment="LGTM")
            resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 200
        body = resp["response"]["responseBody"]["application/json"]["body"]
        assert body["comment_url"] == "https://github.com/..."

    def test_missing_github_token_raises_500(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from tools.github_pr import handler
        event = _make_event("/pr", "GET", owner="o", repo="r", pr_number=1)
        resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 500

    def test_unsupported_path_raises_500(self):
        from tools.github_pr import handler
        event = _make_event("/unknown", "GET", owner="o", repo="r", pr_number=1)
        with patch("tools.github_pr._get_token", return_value="tok"):
            resp = handler(event, None)
        assert resp["response"]["httpStatusCode"] == 500


# ===========================================================================
# 청크 분할 분석 (split_and_analyze)
# ===========================================================================

class TestSplitAndAnalyze:
    """500줄 이상 대형 코드의 청크 분할 로직 테스트"""

    @pytest.fixture(autouse=True)
    def _import(self):
        pytest.importorskip("radon", reason="radon 미설치 → 스킵")
        from tools.analyze_complexity import split_and_analyze
        self.split_analyze = split_and_analyze

    def test_short_code_analyzed_directly(self):
        """500줄 미만 코드는 분할 없이 직접 분석돼야 합니다."""
        code = "def f(x):\n    return x\n"
        result = self.split_analyze(code)
        assert result["summary"]["total_functions"] >= 1

    def test_large_code_splits_by_function(self):
        """500줄 초과 코드는 함수 단위로 분할 분석돼야 합니다."""
        # 함수 1개당 약 5줄 × 120개 = 600줄 이상
        funcs = "\n".join(
            f"def func_{i}(x):\n    if x > 0:\n        return x\n    else:\n        return 0\n"
            for i in range(120)
        )
        assert len(funcs.splitlines()) > 500, "테스트 데이터가 500줄 미만입니다."
        result = self.split_analyze(funcs)
        assert result["summary"]["total_functions"] == 120
