# CodeBuddy Reviewer — AWS Bedrock Agent

코드 리뷰 및 보안 분석을 위한 AWS Bedrock Agent 프로젝트입니다.

## 프로젝트 구조

```

├── config/
│   └── settings.py          # 환경 변수 및 설정값
├── agent/
│   ├── create_agent.py      # Agent 생성/업데이트
│   ├── prepare_agent.py     # Agent Prepare & Alias 생성
│   └── invoke_agent.py      # Agent 호출 (일반 / 트레이스)
├── knowledge_base/
│   └── associate_kb.py      # Knowledge Base 연결
├── utils/
│   └── aws_client.py        # Boto3 클라이언트 팩토리
├── main.py                  # 전체 흐름 실행 진입점
├── requirements.txt
└── .env.example
```

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 AWS 설정값 입력
```

## 사용법

### 1. Agent 전체 셋업 (생성 → KB 연결 → Prepare → Alias)
```bash
python main.py --setup
```

### 2. 코드 리뷰 요청
```bash
python main.py --review "path/to/your_code.py"
```

### 3. 직접 프롬프트 입력
```bash
python main.py --prompt "안녕? 너는 어떤 역할을 하는 Agent야?"
```

### 4. 트레이스(디버그) 모드로 호출
```bash
python main.py --prompt "Python 변수명 규칙은?" --trace
```

## 환경 변수 (.env)

| 변수명 | 설명 |
|---|---|
| `AWS_REGION` | AWS 리전 (예: ap-northeast-2) |
| `AWS_ACCOUNT_ID` | AWS 계정 ID |
| `AGENT_NAME` | Agent 이름 |
| `FOUNDATION_MODEL` | 사용할 FM ID |
| `KNOWLEDGE_BASE_ID` | 연결할 KB ID (선택) |
