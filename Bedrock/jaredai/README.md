# 🚀 JaredAI

> **GitHub Issue 기반 AI 코드 초안 생성 및 Jira / GitHub / Slack 자동 연동 에이전트**

미드 *실리콘밸리*에서 애자일과 스프린트를 도입했던 Jared에서 착안한 프로젝트입니다.
개발자가 GitHub Issue를 등록하면, AI가 사내 코딩 가이드라인과 보안 정책을 검색(RAG)해
코드 초안을 작성하고, Jira 티켓 생성 → GitHub 댓글 등록 → Slack 알림까지 자동으로 처리합니다.

---

## 📐 아키텍처

```
GitHub Issue 등록
      │ (Webhook)
      ▼
API Gateway ──▶ orchestrator_lambda  ──▶ Bedrock Agent (Claude)
                                              │
                                              ├─ Knowledge Base 검색 (RAG)
                                              │   ├─ coding_standards.md
                                              │   └─ security_policy.md
                                              │
                                              ├─ Tool: create_jira_issue      ──▶ jira_tool_lambda
                                              ├─ Tool: post_github_comment    ──▶ github_tool_lambda
                                              └─ Tool: send_slack_notification──▶ slack_tool_lambda
```

**처리 흐름 (5단계)**

1. 개발자가 GitHub Issue에 기능 요구사항 작성
2. GitHub Webhook → API Gateway → Orchestrator Lambda 트리거
3. Bedrock Agent가 Knowledge Base를 검색해 가이드라인 기반 코드 초안 생성
4. Agent가 Jira 티켓 생성 + GitHub 댓글 등록 (Tool 자율 실행)
5. Slack으로 개발팀에 완료 알림 전송

---

## 📁 파일 구조

```
jaredai/
├── lambdas/
│   ├── orchestrator_lambda.py     # Webhook 수신 + Bedrock Agent 호출
│   ├── jira_tool_lambda.py        # Jira 티켓 생성 Tool
│   ├── github_tool_lambda.py      # GitHub 댓글 등록 Tool
│   └── slack_tool_lambda.py       # Slack 알림 Tool
│
├── tools/
│   └── api_spec.yaml              # Bedrock Agent OpenAPI 스키마
│
├── knowledge_base/
│   ├── coding_standards.md        # PEP8 기반 내부 코딩 표준
│   └── security_policy.md         # OWASP 기반 보안 정책
│
├── infra/
│   ├── deploy.sh                  # Lambda 패키징 + 배포 스크립트
│   └── bedrock_agent_setup.py     # Agent + KB 초기 설정 스크립트
│
├── .env.example                   # 환경변수 템플릿
├── requirements.txt
└── README.md
```

---

## ✅ 사전 준비

| 항목 | 필요한 것 |
|---|---|
| AWS | CLI 자격증명, Bedrock 모델 액세스(Claude), Lambda 실행 IAM Role |
| GitHub | Personal Access Token (`repo` 권한), Webhook Secret |
| Jira Cloud | Atlassian API 토큰, 프로젝트 Key |
| Slack | Bot Token (`xoxb-...`), 알림받을 채널 |
| 로컬 | Python 3.12+, AWS CLI, `zip` 명령어 |

---

## ⚡ 빠른 시작 (하루 완성용)

### 1. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 AWS, GitHub, Jira, Slack 값 채우기
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. Lambda 배포

```bash
bash infra/deploy.sh all
```

개별 배포도 가능합니다.

```bash
bash infra/deploy.sh orchestrator
bash infra/deploy.sh jira
bash infra/deploy.sh github
bash infra/deploy.sh slack
```

### 4. Knowledge Base 문서 업로드

```bash
aws s3 cp knowledge_base/ s3://${S3_BUCKET_NAME}/knowledge_base/ --recursive
```

### 5. Bedrock Agent + Knowledge Base 설정

```bash
python infra/bedrock_agent_setup.py
```

실행 완료 후 출력되는 `BEDROCK_AGENT_ID`, `BEDROCK_AGENT_ALIAS` 값을 `.env`에 추가하고,
`orchestrator` Lambda를 다시 배포합니다.

```bash
bash infra/deploy.sh orchestrator
```

### 6. GitHub Webhook 등록

GitHub Repository → **Settings → Webhooks → Add webhook**

| 필드 | 값 |
|---|---|
| Payload URL | API Gateway 엔드포인트 URL |
| Content type | `application/json` |
| Secret | `.env`의 `GITHUB_WEBHOOK_SECRET`과 동일한 값 |
| Events | **Issues** 만 체크 |

---

## 🧪 테스트

GitHub Issue를 새로 작성하면 자동으로 흐름이 시작됩니다.

```markdown
제목: [Feature] 회원가입 시 비밀번호 유효성 규칙 강화
내용: 비밀번호는 8자 이상, 대소문자 및 특수문자가 포함되어야 합니다.
      내부 보안 규정을 참고하여 파이썬으로 안전한 검증 함수 초안을 짜주세요.
```

**예상 결과**

- ✅ GitHub Issue에 AI 코드 초안 + Jira 링크 댓글 등록
- ✅ Jira 프로젝트 보드에 `[AI 제안] ...` To-Do 티켓 생성
- ✅ Slack 채널에 완료 알림 (GitHub/Jira 링크 버튼 포함)

CloudWatch Logs에서 각 Lambda 실행 로그를 확인할 수 있습니다.

```bash
aws logs tail /aws/lambda/jaredai-orchestrator --follow
```

---

## 🔧 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| Webhook이 403 응답 | `GITHUB_WEBHOOK_SECRET`이 GitHub 설정과 다름 |
| Agent가 Tool을 호출하지 않음 | `api_spec.yaml`의 `operationId`와 Lambda 분기 로직(`apiPath`) 불일치 확인 |
| Jira 티켓 생성 실패 | API 토큰 만료 또는 `JIRA_PROJECT_KEY` 오타 |
| KB 검색 결과가 비어있음 | `start_ingestion_job` 완료 전 호출 — 인덱싱은 수 분 소요 |
| Slack 메시지 미전송 | Bot이 해당 채널에 초대되지 않음 (`/invite @JaredAI`) |

---

## 📌 향후 개선 아이디어

- Orchestrator를 비동기로 분리해 Issue에 "분석 중..." 즉시 응답 추가
- Jira/Slack 실패 시 재시도(DLQ) 로직 추가
- PR 생성까지 자동화 (코드 초안 → 브랜치 → PR)

---

## 🤖 기술 스택

`Amazon Bedrock (Claude Sonnet)` · `AWS Lambda` · `API Gateway` · `Knowledge Base (RAG)` · `GitHub REST API` · `Jira Cloud REST API` · `Slack Web API`
