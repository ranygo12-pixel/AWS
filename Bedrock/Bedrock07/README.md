# CodeBuddy — GitHub PR 코드 리뷰 AI 어시스턴트

AWS Bedrock Agent + Lambda + GitHub API + Slack을 연동한 코드 리뷰 자동화 프로젝트입니다.

---

## 📁 프로젝트 구조

```
codebuddy/
├── .github/workflows/
│   ├── 1_setup_iam.yml          # IAM 역할 생성 (최초 1회)
│   ├── 2_deploy_lambdas.yml     # Lambda 함수 배포 (코드 변경 시 자동)
│   └── 3_setup_agent.yml        # Bedrock Agent 설정 + 통합 테스트
├── lambdas/
│   ├── get_pr/index.py          # GitHub PR 정보 조회 Lambda
│   ├── post_comment/index.py    # GitHub PR 댓글 추가 Lambda
│   └── slack_notifier/index.py  # Slack 메시지 전송 Lambda
├── agent/
│   ├── schemas/
│   │   ├── github_pr_schema.json      # get_github_pr OpenAPI 스키마
│   │   ├── github_comment_schema.json # post_pr_comment OpenAPI 스키마
│   │   └── slack_schema.json          # send_slack_message OpenAPI 스키마
│   └── instructions.txt         # Bedrock Agent 지침
├── scripts/
│   ├── setup_iam.py             # IAM 역할 생성 스크립트
│   ├── deploy_lambdas.py        # Lambda 배포 스크립트
│   ├── setup_agent.py           # Bedrock Agent 설정 스크립트
│   └── test_agent.py            # 통합 테스트 스크립트
├── requirements.txt
└── README.md
```

---

## 🚀 배포 순서

### 1단계 — GitHub Secrets 등록 (필수 선행)

저장소 → **Settings → Secrets and variables → Actions** 에서 아래 값을 등록합니다.

| Secret 이름 | 설명 |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS IAM 사용자 Access Key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM 사용자 Secret Key |
| `AWS_DEFAULT_REGION` | AWS 리전 (예: `ap-northeast-2`) |
| `GH_TOKEN` | GitHub Personal Access Token (repo 권한 필요) |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |

> ⚠️ GitHub Actions 내장 `GITHUB_TOKEN`과 이름 충돌을 피하기 위해 GitHub PAT는 **`GH_TOKEN`** 으로 등록합니다.

---

### 2단계 — IAM 역할 생성 (최초 1회)

Actions 탭 → **"1️⃣ IAM 역할 설정"** → **Run workflow**

완료 후 Job Summary에 출력된 ARN을 추가로 등록합니다.

| Secret 이름 | 설명 |
|---|---|
| `LAMBDA_ROLE_ARN` | Lambda 실행 IAM 역할 ARN |
| `AGENT_ROLE_ARN` | Bedrock Agent 실행 IAM 역할 ARN |

---

### 3단계 — Lambda 배포

`main` 브랜치에 푸시하거나 Actions 탭에서 **"2️⃣ Lambda 함수 배포"** 를 수동 실행합니다.

완료 후 아래 Secrets를 추가 등록합니다.

| Secret 이름 | 설명 |
|---|---|
| `CODEBUDDY_GITHUB_PR_ARN` | get_pr Lambda ARN |
| `CODEBUDDY_GITHUB_PR_COMMENT_ARN` | post_comment Lambda ARN |
| `CODEBUDDY_SLACK_NOTIFIER_ARN` | slack_notifier Lambda ARN |

---

### 4단계 — Agent 설정 및 테스트

Actions 탭 → **"3️⃣ Agent 설정 및 테스트"** → **Run workflow**

완료 후 Job Summary에 출력된 값을 등록합니다.

| Secret 이름 | 설명 |
|---|---|
| `AGENT_ID` | Bedrock Agent ID |
| `AGENT_ALIAS_ID` | Bedrock Agent Alias ID |

이후 `main` 브랜치 푸시 시 Lambda 재배포 → Agent 재설정 → 테스트가 **자동으로 순서대로 실행**됩니다.

---

## 🛠️ 로컬 실행

```bash
# 의존 패키지 설치
pip install -r requirements.txt

# AWS 자격증명 설정 (프로필 또는 환경 변수)
export AWS_DEFAULT_REGION=ap-northeast-2
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# 각 스크립트 개별 실행
python scripts/setup_iam.py
python scripts/deploy_lambdas.py
python scripts/setup_agent.py
python scripts/test_agent.py
```

---

## 💬 Agent 사용 예시

| 요청 | 동작 |
|---|---|
| `octocat/Spoon-Knife의 PR #1 정보 가져와줘` | get_github_pr 호출 |
| `PR #1에 'LGTM!' 댓글 남겨줘` | post_pr_comment 호출 |
| `#code-review 채널에 '리뷰 완료' 보내줘` | send_slack_message 호출 |
| `PR #1 리뷰하고 결과를 Slack으로 알려줘` | 세 도구 순차 호출 |

---

## 🔒 보안 주의사항

- `GH_TOKEN`, `SLACK_WEBHOOK_URL` 등 민감 정보는 절대 코드에 직접 포함하지 마세요.
- Lambda 환경 변수는 AWS Secrets Manager로 교체하는 것을 권장합니다.
- IAM 역할은 최소 권한 원칙을 준수합니다 (`codebuddy-*` 함수만 호출 가능).
