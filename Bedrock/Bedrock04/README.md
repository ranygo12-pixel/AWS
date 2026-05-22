# 🚀 AWS RAG Reviewer (aws_rag_reviewer)

Amazon Bedrock Knowledge Base와 Claude 3.5 Sonnet(v4.6)을 결합하여, 소스 코드의 PEP8 스타일 규칙 위반 및 보안 취약점(OWASP Top 10, SQL Injection, 하드코딩된 자격 증명 등)을 자동 스캔하고 종합 마크다운 리포트를 생성하는 대규모 프로젝트 코드 리뷰 자동화 솔루션입니다.

## 📌 1. 주요 기능 (Core Features)
* RetrieveAndGenerate API 기반 자동화: Bedrock Agent Runtime을 활용하여 한 번의 API 호출로 지식 가이드 검색(Retrieve)과 리뷰 생성(Generate)을 동시에 수행합니다.
* 보안 취약점 심층 분석 (Two-Step Hybrid): bedrock-agent-runtime으로 보안 가이드 문서를 검색한 뒤, 검색된 콘텍스트를 bedrock-runtime(Claude 3.5 Sonnet 정식 대화형 API)에 주입하여 취약점 위치, 유형, 심각도, 개선 방안을 정밀 타격합니다.
* 정형화된 JSON 리포트 구조화: 프론트엔드나 CI/CD 파이프라인에서 즉시 파싱할 수 있도록 취약점 결과를 표준화된 JSON 포맷 스트링으로 추출합니다.
* 대규모 프로젝트 디렉토리 일괄 스캔: 지정한 루트 디렉토리 내의 모든 .py 파일을 탐색하며, 가상환경(.venv, venv)이나 시스템 폴더(__pycache__, .git)는 자동으로 필터링 및 제외합니다.
* 종합 마크다운 리포트 생성: 검사된 모든 파일의 라인 수, 스타일 검사 결과, 보안 취약점 결과를 하나로 묶은 project_review_report.md 리포트를 자동 빌드합니다.
---
## 🛠️ 2. 사전 준비 사항 (Prerequisites)
1. Amazon Bedrock 모델 활성화 (Model Access): AWS Bedrock 콘솔의 Model access 메뉴에서 Claude 3.5 Sonnet (global.anthropic.claude-sonnet-4-6) 모델이 활성화(Granted)되어 있어야 합니다.
2. Knowledge Base (지식 기반) 구축: 코드 스타일 가이드(PEP8 표준) 및 보안 가이드라인(OWASP 규정) 문서가 S3에 업로드되고 Bedrock Knowledge Base에 동기화(Sync)되어 있어야 합니다. 텍스트 임베딩 모델로는 Titan Embeddings v2가 권장됩니다.
3. AWS 리전 인프라: 본 패키지는 기본적으로 ap-northeast-2 (서울 리전)의 Bedrock 엔드포인트를 바라보도록 설계되어 있습니다.
---
## 🚀 3. 시작하기 (Quick Start)
환경 변수 설정: 보안을 위해 AWS Access Key와 Knowledge Base ID는 코드에 박아두지 않고 환경 변수를 통해 주입받습니다. git의 경우, secret 에 저장합니다.

* Linux / macOS 터미널 환경 환경 변수 주입 명령어
```
export AWS_ACCESS_KEY_ID="당신의_AWS_액세스_키"
export AWS_SECRET_ACCESS_KEY="당신의_AWS_시크릿_키"
export AWS_DEFAULT_REGION="ap-northeast-2"
export KB_ID="당신의_지식_기반_ID"
```

* Windows PowerShell 환경 변수 주입 명령어
```
$env:AWS_ACCESS_KEY_ID="당신의_AWS_액세스_키"
$env:AWS_SECRET_ACCESS_KEY="당신의_AWS_시크릿_키"
$env:AWS_DEFAULT_REGION="ap-northeast-2"
$env:KB_ID="당신의_지식_기반_ID"
```
* Google Colab 가동 시: 좌측 열쇠 아이콘(Secrets)에 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, KB_ID를 각각 Key로 등록하고 값(Value)을 입력하면, config.py가 이를 인지하여 자동으로 환경 변수에 병합합니다.

의존성 패키지 설치 및 실행 방법:
pip install boto3
python main.py

실행이 완료되면 다음 두 개의 산출물이 저장소 루트에 생성됩니다:
1. security_report.json: 단일 샘플 코드 분석용 정형 데이터 보고서
2. project_review_report.md: 디렉토리 전수 스캔 마크다운 보고서

---

## 📂 프로젝트 구조

```text
├── main.py                    # 전체 프로젝트를 테스트/실행하는 메인 엔트리포인트
├── aws_rag_reviewer/          # 핵심 로직이 내장된 패키지 폴더
│   ├── __init__.py            # 외부 노출 인터페이스 통합 정의
│   ├── config.py              # AWS 자격 증명 검증 및 리전 설정
│   ├── reviewer.py            # Bedrock API 호출 및 스타일/보안/다국어 리뷰 로직
│   └── project_scanner.py     # 디렉토리 내 전체 파일 탐색 및 MD 리포트 생성
├── Bedrock04.ipynb
└── README.md                  # 본 사용 설명서 파일
