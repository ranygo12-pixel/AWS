# AWS Bedrock 기반 RAG 및 Knowledge Base 구축 실습

이 저장소는 Amazon Bedrock과 인프라 자동화 도구를 활용하여 검색 증강 생성(RAG, Retrieval-Augmented Generation) 시스템을 이해하고, 효율적인 지식 기반(Knowledge Base)을 설계 및 구축하는 실습 코드를 담고 있습니다.

---

## 📌 프로젝트 개요

* **목적**: 대규모 언어 모델(LLM)의 할루시네이션(Hallucination) 문제를 해결하고, 최신 기업 내부 데이터에 기반한 답변을 제공하는 RAG 아키텍처 실습
* **핵심 기술**: Amazon Bedrock, Vector Databases (OpenSearch, Pinecone 등), 데이터 전처리 파이프라인
* **실습 환경**: Google Colab / AWS 환경 (AWS CLI, SDK 기반 제어)

---
## 🛠️ 실습 내용 및 아키텍처


**1. AWS CLI 및 개발 환경 설정 (`Bedrock03.ipynb`)**
* **AWS CLI v2 설치 및 업데이트**: 최신 AWS CLI를 환경에 맞춰 자동 구성하는 쉘 스크립트 실행
* **인증 및 프로필 관리**: Bedrock API 호출을 위한 자격 증명(Credentials) 및 리전(Region) 설정

**2. RAG (Retrieval-Augmented Generation) 핵심 메커니즘**
* **Data Ingestion**: 문서 데이터 수집 및 텍스트 청킹(Chunking) 전략 수립
* **Embedding**: 고성능 Embedding 모델을 활용한 텍스트의 벡터화 변환
* **Vector Store 저장**: 유사도 검색(Similarity Search) 최적화를 위한 지식 기반 구축
---


## 📁 폴더 및 파일 구조

```text
├── README.md
└── Bedrock/
    ├── Bedrock03.ipynb       # AWS CLI 구성 및 Bedrock RAG 실습 노트북
    ├── data/                 # 💡 실제 문서 데이터를 모아두는 폴더
    │   ├── pep8.txt
    │   └── owasp-top10.txt
    ├── .env                  # 로컬 테스트용 환경 변수 파일 (Git 제외 대상)
    ├── .gitignore            # Git에 올리지 않을 파일 설정 (.env, __pycache__ 등)
    ├── requirements.txt      # 설치가 필요한 라이브러리 목록
    ├── config.py             # AWS 및 환경 변수 설정 로드
    ├── bedrock_embedding.py  # 1. 텍스트를 벡터로 변환하는 기능
    ├── vector_math.py        # 2. 벡터 간 유사도를 계산하는 수학 함수
    ├── bedrock_kb.py         # 3. Knowledge Base 동기화 및 Retrieval/QA 기능
    ├── s3_utils.py           # S3 버킷 생성 및 메타데이터 업로드 함수 모음
    └── main.py               # 전체 프로세스를 실행하는 메인 스크립트
