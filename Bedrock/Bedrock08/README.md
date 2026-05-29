# 🤖 Bing Code — GitHub PR 자동 리뷰 Agent

> **AWS Generative AI 실무 8장 실습**  
> Amazon Bedrock Agent + Claude Sonnet 으로 구현하는 AI 페어 프로그래머

---

## 📌 프로젝트 개요

Bing Code는 GitHub PR이 열릴 때마다 **Amazon Bedrock Agent**가 자동으로 코드를 분석해  
복잡도·리팩토링 제안·단위 테스트를 생성하고 PR 댓글로 등록하는 시스템입니다.

원본 강의는 **Google Colab + Boto3** 환경을 기준으로 하지만,  
이 저장소는 **GitHub Actions** 워크플로우로 변환해 실제 CI/CD 파이프라인에서 실행합니다.

```
PR 오픈 / 커밋 푸시
       │
       ▼
GitHub Actions 트리거
       │
       ├─ 1. pytest 단위 테스트 실행
       │
       └─ 2. Bedrock Agent 호출
              │
              ├─ get_github_pr       → PR 변경 코드 조회
              ├─ analyze_complexity  → 복잡도 측정 (radon)
              ├─ suggest_refactor    → 리팩토링 제안 (Claude)
              ├─ generate_unit_test  → pytest 테스트 생성 (Claude)
              └─ post_pr_comment     → PR 댓글 등록
```

---

## 🗂️ 프로젝트 구조

```
Bedrock08/
│
├── tools/                         # Bedrock Agent Tool (Lambda 함수)
│   ├── analyze_complexity.py      # 코드 복잡도 분석 (radon)
│   ├── generate_unit_test.py      # pytest 단위 테스트 자동 생성
│   ├── suggest_refactor.py        # 리팩토링 제안
│   └── github_pr.py               # GitHub PR 조회 / 댓글 등록
│
├── agent/
│   └── bedrock_agent.py           # Action Group 등록 + PR 분석 실행
│
├── tests/
│   └── test_tools.py              # pytest 단위 테스트 (mock 기반)
│
├── .github/workflows/
│   └── pr_analysis.yml            # GitHub Actions 워크플로우
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🔧 구현된 Tool 목록

| Tool | 파일 | 역할 | 핵심 기술 |
|------|------|------|-----------|
| `analyze_complexity` | `tools/analyze_complexity.py` | Cyclomatic Complexity 측정 | radon `cc_visit` |
| `generate_unit_test` | `tools/generate_unit_test.py` | pytest 테스트 자동 생성 | Bedrock Converse API |
| `suggest_refactor`   | `tools/suggest_refactor.py`   | 리팩토링 제안 (3가지 focus) | Bedrock Converse API |
| `get_github_pr`      | `tools/github_pr.py`          | PR 변경 코드 조회 | GitHub REST API |
| `post_pr_comment`    | `tools/github_pr.py`          | PR 댓글 등록 | GitHub REST API |

---

## 💡 핵심 학습 개념

### 1. Cyclomatic Complexity (순환 복잡도)

코드의 분기 수(`if`, `for`, `while`, `case`)를 측정한 지표입니다.  
값이 높을수록 유지보수가 어렵고 버그 발생 가능성이 높아집니다.

| 복잡도 | 등급 | 평가 | 권장 조치 |
|--------|------|------|-----------|
| 1 ~ 5  | A    | ✅ 양호 | 유지 |
| 6 ~ 10 | B    | 🟡 보통 | 주의 |
| 11 ~ 20 | C   | 🟠 복잡 | 리팩토링 고려 |
| 21 +   | D    | 🔴 위험 | 즉시 리팩토링 |

radon 라이브러리로 측정합니다:

```python
from radon.complexity import cc_visit, cc_rank

result = cc_visit(code)
for item in result:
    print(f"{item.name}: 복잡도 {item.complexity} ({cc_rank(item.complexity)}등급)")
```

### 2. Bedrock Agent Action Group

Agent는 **OpenAPI 3.0 스키마**로 Tool 명세를 받습니다.  
자연어 프롬프트를 받으면 어떤 Tool을 어떤 순서로 호출할지 Agent가 자율적으로 결정합니다.

```
사용자 프롬프트 → Bedrock Agent (Claude Sonnet)
                        │
                        ├─ Tool 선택 & 파라미터 추출
                        │
                        ├─ Lambda 호출 (Action Group)
                        │
                        └─ 결과 취합 → 자연어 응답
```

### 3. 청크 분할 분석

1000줄이 넘는 대형 파일은 Python AST로 함수를 추출한 뒤 함수 단위로 분할 분석합니다.  
토큰 제한(200K)을 피하고 분석 시간과 비용을 절감합니다.

```python
import ast

tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        chunk = ast.unparse(node)   # 함수 하나씩 추출
        analyze(chunk)              # 개별 분석
```

### 4. 리팩토링 focus 옵션

`suggest_refactor` Tool은 목적에 따라 분석 관점을 지정할 수 있습니다.

| focus | 중점 사항 |
|-------|-----------|
| `readability`      | 직관적 변수명, 함수 분할, 핵심 주석 추가 |
| `performance`      | 불필요한 루프 제거, Set/Dict 등 최적 자료구조 활용 |
| `maintainability`  | 디자인 패턴 적용, 관심사 분리(SoC), 결합도 감소 |

---

## 🚀 사용 방법

### 사전 준비

1. **AWS 리소스 생성**
   - Amazon Bedrock Agent (Claude Sonnet 4.6 모델)
   - Lambda 함수 (tools/ 코드 배포)
   - IAM Role: Bedrock Agent → Lambda 호출 권한

2. **GitHub Secrets 등록**  
   저장소 Settings → Secrets and variables → Actions

   | Secret 이름 | 설명 |
   |-------------|------|
   | `AWS_ACCESS_KEY_ID` | Bedrock + Lambda 접근 IAM 액세스 키 |
   | `AWS_SECRET_ACCESS_KEY` | 위 키의 시크릿 |
   | `BEDROCK_AGENT_ID` | Bedrock Agent ID |
   | `BEDROCK_AGENT_ALIAS` | Bedrock Agent Alias ID |
   | `BEDROCK_ACTION_GROUP` | Action Group ID (setup 시 필요) |
   | `UNIFIED_LAMBDA_ARN` | Tool Lambda 함수 ARN |

   > `GITHUB_TOKEN` 은 Actions에서 자동 제공되므로 별도 설정이 필요 없습니다.

### Action Group 초기 등록

저장소 Actions 탭 → **Bing Code PR Analysis** → **Run workflow** 실행  
(main 브랜치에서 workflow_dispatch 트리거 시 `setup-agent` Job이 실행됩니다)

또는 로컬에서 직접 실행:

```bash
python agent/bedrock_agent.py setup \
  --agent-id        <AGENT_ID>        \
  --action-group-id <ACTION_GROUP_ID> \
  --lambda-arn      <LAMBDA_ARN>
```

### PR 분석 실행

PR을 열거나 커밋을 푸시하면 자동으로 분석이 시작됩니다.  
수동 실행이 필요하다면:

```bash
python agent/bedrock_agent.py analyze \
  --agent-id  <AGENT_ID>  \
  --alias-id  <ALIAS_ID>  \
  --owner     <GITHUB_ORG> \
  --repo      <REPO_NAME>  \
  --pr-number 123
```

### 로컬 테스트 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 전체 테스트 (AWS/GitHub 호출 없이 mock으로 실행)
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=tools --cov-report=term-missing
```

---

## 🔄 GitHub Actions 워크플로우 흐름

```yaml
on:
  pull_request:          # PR 오픈 또는 새 커밋 푸시 시 자동 실행
    types: [opened, synchronize]

jobs:
  test:                  # Job 1: pytest 단위 테스트
  analyze:               # Job 2: Bedrock Agent PR 분석 (test 통과 후 실행)
  setup-agent:           # Job 3: Action Group 스키마 업데이트 (수동 실행 전용)
```

PR에 달리는 댓글 예시:

```markdown
## 🤖 Bing Code 자동 분석 결과

### 📊 복잡도 분석
| 함수명       | 복잡도 | 등급 | 권장 조치       |
|--------------|--------|------|-----------------|
| process_data | 8      | B    | 보통, 리팩토링 고려 |
| calculate    | 15     | C    | 복잡, 분할 필요   |

### 🔧 리팩토링 제안
...

### ✅ 생성된 단위 테스트
```python
def test_process_data_empty_list():
    ...
```
```

---

## 📚 참고

- [Amazon Bedrock Agent 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [radon 라이브러리](https://radon.readthedocs.io/)
- [GitHub REST API](https://docs.github.com/en/rest)
- 원본 강의: AWS Generative AI 실무 8장 (Google Colab 환경 기준)
