```
jaredai/
│
├── lambdas/                          ← 핵심 코드 (총 4개)
│   ├── orchestrator_lambda.py        ★ 1순위 - Webhook 받아서 Bedrock 호출
│   ├── jira_tool_lambda.py           ★ 신규 - Jira 티켓 생성
│   ├── github_tool_lambda.py         ★ 재활용 가능 - GitHub 댓글 등록
│   └── slack_tool_lambda.py          ★ 재활용 가능 - Slack 알림
│
├── tools/
│   └── api_spec.yaml                 ★ Bedrock Agent OpenAPI 스키마 (핵심!)
│
├── knowledge_base/                   ← 이전 과제에서 쓴 문서 그대로 활용
│   ├── coding_standards.md           (PEP8 가이드라인 - 이미 있음)
│   └── security_policy.md            (보안 정책 - 이미 있음)
│
├── infra/
│   ├── deploy.sh                     Lambda zip + 배포 자동화
│   └── bedrock_agent_setup.py        Agent + KB 최초 세팅 스크립트
│
├── .env.example                      환경변수 템플릿
├── requirements.txt
└── README.md
```
