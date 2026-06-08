# GitHub PR 자동 리뷰 Agent

AWS Bedrock Agent를 Lambda + API Gateway로 서버리스 배포하여  
GitHub Pull Request를 자동으로 리뷰하는 프로젝트입니다.

## 아키텍처

```
GitHub Webhook (PR 오픈)
        │
        ▼
  API Gateway  POST /review
        │
        ▼
 Orchestrator Lambda
  ├── PR URL 파싱
  ├── Bedrock Agent 호출
  └── 응답 반환
        │
   ┌────┴────┐
   ▼         ▼
Bedrock    CloudWatch
 Agent      Logs
```

## 프로젝트 구조

```
codebud
├── lambda/
│   └── orchestrator.py        # Lambda 핸들러 (Bedrock Agent 호출)
├── scripts/
│   ├── setup_iam.py           # IAM 역할 및 정책 생성
│   ├── create_layer.py        # Lambda Layer 패키징 및 업로드
│   ├── deploy_lambda.py       # Lambda 함수 생성 / 코드·설정 업데이트
│   └── setup_api_gateway.py   # API Gateway 생성, CORS, API Key 설정
├── iam/
│   └── lambda_policy.json     # IAM 인라인 정책 (참고용)
├── .env.example               # 환경 변수 템플릿
├── .gitignore
├── requirements.txt
└── README.md
```

## 사전 준비

- Python 3.12+
- AWS CLI 설정 완료 (`aws configure`)
- Amazon Bedrock Agent 생성 완료 (Agent ID, Alias ID 확보)
- GitHub Personal Access Token (repo 권한)

## 설치

```bash
git clone https://github.com/your-org/codebuddy.git
cd codebuddy

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env 파일을 열어 각 값을 채워주세요
```

## 배포 순서

환경 변수를 로드한 뒤 아래 순서대로 스크립트를 실행합니다.

```bash
# .env 로드 (bash)
export $(grep -v '^#' .env | xargs)

# 1. IAM 역할 생성
python scripts/setup_iam.py

# 2. Lambda Layer 생성 (radon, PyGithub, requests)
python scripts/create_layer.py
#   → layer_arn.txt 생성됨

# 3. Lambda 함수 배포
python scripts/deploy_lambda.py --create

# 4. API Gateway 생성 및 연결
python scripts/setup_api_gateway.py
#   → api_outputs.json 생성됨 (엔드포인트 URL, API Key)
```

## 코드 업데이트

```bash
# Lambda 코드만 재배포
python scripts/deploy_lambda.py --update-code

# 환경변수·메모리·타임아웃 설정만 변경
python scripts/deploy_lambda.py --update-config
```

## 테스트

`api_outputs.json`에서 엔드포인트와 API Key를 확인한 후:

```bash
curl -X POST https://<api-id>.execute-api.ap-northeast-2.amazonaws.com/prod/review \
  -H "Content-Type: application/json" \
  -H "x-api-key: <your-api-key>" \
  -d '{"pr_url": "https://github.com/owner/repo/pull/1", "action": "review"}'
```

성공 응답 예시:

```json
{
  "result": "## PR 리뷰 결과\n\n...",
  "status": "completed"
}
```

## Lambda 설정

| 항목 | 값 | 이유 |
|---|---|---|
| 메모리 | 1024 MB | Bedrock Agent 호출 + 코드 분석 |
| 타임아웃 | 300초 | LLM 응답 대기 (최대 30초+) |
| 런타임 | Python 3.12 | |

## 환경 변수

| 변수명 | 설명 |
|---|---|
| `AGENT_ID` | Bedrock Agent ID |
| `ALIAS_ID` | Bedrock Agent Alias ID |
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| `LOG_LEVEL` | 로그 수준 (기본: INFO) |

> **보안 권장사항**: 민감 정보는 AWS Secrets Manager에 저장하고  
> Lambda에서 `boto3`로 런타임에 읽어오는 방식을 권장합니다.

## GitHub Webhook 연결

1. GitHub 저장소 > Settings > Webhooks > Add webhook
2. **Payload URL**: `https://<api-id>.execute-api.ap-northeast-2.amazonaws.com/prod/review`
3. **Content type**: `application/json`
4. **Events**: `Pull requests` 선택

## 라이선스

MIT
