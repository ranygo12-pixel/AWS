# 🚀 AWS RAG Reviewer (aws_rag_reviewer)

Amazon Bedrock Knowledge Base와 Claude 3.5 Sonnet을 활용하여 소스 코드의 **PEP8 스타일 규칙 위반** 및 **보안 취약점(OWASP Top 10 등)**을 자동으로 검사하고 리포트를 생성하는 대규모 프로젝트 코드 리뷰 도구입니다.

---

## 📂 프로젝트 구조

```text
├── main.py                    # 전체 프로젝트를 테스트/실행하는 메인 엔트리포인트
├── aws_rag_reviewer/          # 핵심 로직이 내장된 패키지 폴더
│   ├── __init__.py            # 외부 노출 인터페이스 통합 정의
│   ├── config.py              # AWS 자격 증명 검증 및 리전 설정
│   ├── reviewer.py            # Bedrock API 호출 및 스타일/보안/다국어 리뷰 로직
│   └── project_scanner.py     # 디렉토리 내 전체 파일 탐색 및 MD 리포트 생성
├──
└── README.md                  # 본 사용 설명서 파일
