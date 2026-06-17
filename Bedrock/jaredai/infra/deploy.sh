#!/bin/bash
# ============================================================
# JaredAI Lambda 배포 스크립트
# 사용법: bash deploy.sh [함수명 | all]
# 예시:   bash deploy.sh all
#         bash deploy.sh orchestrator
# ============================================================

set -e  # 오류 발생 시 즉시 중단

# ── 환경변수 로드 ─────────────────────────────────────────────
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  echo "✓ .env 로드 완료"
else
  echo "❌ .env 파일이 없습니다. .env.example을 복사하고 값을 채워주세요."
  exit 1
fi

# ── 필수 환경변수 확인 ────────────────────────────────────────
REQUIRED_VARS=(AWS_REGION AWS_ACCOUNT_ID)
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var}" ]; then
    echo "❌ 환경변수 누락: $var"
    exit 1
  fi
done

# ── 설정 ─────────────────────────────────────────────────────
REGION="${AWS_REGION}"
ACCOUNT_ID="${AWS_ACCOUNT_ID}"
BUILD_DIR=".build"
TARGET="${1:-all}"

# Lambda 함수 정의: "배포명:파일명" 형식
declare -A LAMBDAS=(
  ["orchestrator"]="orchestrator_lambda"
  ["jira"]="jira_tool_lambda"
  ["github"]="github_tool_lambda"
  ["slack"]="slack_tool_lambda"
)

# ── 공통 함수 ─────────────────────────────────────────────────
build_and_deploy() {
  local name="$1"
  local filename="${LAMBDAS[$name]}"
  local func_name="jaredai-${name}"
  local zip_path="${BUILD_DIR}/${name}.zip"

  echo ""
  echo "📦 [${name}] 패키징 중..."

  # 임시 빌드 디렉토리 생성
  local tmp_dir="${BUILD_DIR}/tmp_${name}"
  rm -rf "$tmp_dir" && mkdir -p "$tmp_dir"

  # Lambda 소스 복사
  cp "lambdas/${filename}.py" "${tmp_dir}/lambda_function.py"

  # 외부 의존성 없음 (urllib 사용으로 경량화)
  # 필요 시 pip install -r requirements.txt -t "$tmp_dir" 활성화

  # ZIP 패키징
  cd "$tmp_dir"
  zip -r "../../${zip_path}" . -x "*.pyc" "__pycache__/*" > /dev/null
  cd - > /dev/null

  echo "   ✓ 패키징 완료: ${zip_path}"

  # Lambda 함수 존재 여부 확인
  if aws lambda get-function --function-name "$func_name" --region "$REGION" > /dev/null 2>&1; then
    # 이미 존재하면 코드 업데이트
    echo "   🔄 Lambda 코드 업데이트 중..."
    aws lambda update-function-code \
      --function-name "$func_name" \
      --zip-file "fileb://${zip_path}" \
      --region "$REGION" \
      --output json > /dev/null

    # 환경변수 업데이트
    update_env_vars "$func_name"

  else
    # 신규 생성
    echo "   🆕 Lambda 함수 신규 생성 중..."
    local role_arn="arn:aws:iam::${ACCOUNT_ID}:role/JaredAILambdaRole"

    aws lambda create-function \
      --function-name "$func_name" \
      --runtime python3.12 \
      --role "$role_arn" \
      --handler "lambda_function.lambda_handler" \
      --zip-file "fileb://${zip_path}" \
      --timeout 30 \
      --memory-size 256 \
      --region "$REGION" \
      --output json > /dev/null

    update_env_vars "$func_name"
  fi

  # 배포 안정화 대기
  aws lambda wait function-updated \
    --function-name "$func_name" \
    --region "$REGION"

  echo "   ✅ [${func_name}] 배포 완료"
}

update_env_vars() {
  local func_name="$1"
  local ENV_VARS=""

  # 확인용 코드 (디버깅 시 사용)
  echo "DEBUG: func_name is $func_name"
  echo "DEBUG: ENV_VARS is '$ENV_VARS'"

  case "$func_name" in
    *orchestrator*)
      ENV_VARS="AWS_REGION=ap-northeast-2"
      ;;
    *jira*)
      # 줄 바꿈 없이 한 줄로 작성
      ENV_VARS="JIRA_BASE_URL=${JIRA_INSTANCE_URL},JIRA_API_TOKEN=${JIRA_API_TOKEN}"
      ;;
    *github*)
      ENV_VARS="GITHUB_TOKEN=${JARED_GITHUB_PAT}"
      ;;
    *slack*)
      ENV_VARS="SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}"
      ;;
  esac

  echo "DEBUG: 최종 ENV_VARS 값은 '$ENV_VARS' 입니다."
  
  if [ -n "$ENV_VARS" ]; then
    echo "    🔄 환경변수 업데이트 중: $ENV_VARS"
    aws lambda update-function-configuration \
      --function-name "$func_name" \
      --environment "Variables={$ENV_VARS}" \
      --region "$REGION" \
      --output json > /dev/null
    echo "    ✓ 환경변수 업데이트 완료"
  fi
}

# ── 메인 실행 ─────────────────────────────────────────────────
mkdir -p "$BUILD_DIR"

echo "======================================================"
echo "🚀 JaredAI Lambda 배포 시작 (대상: ${TARGET})"
echo "   Region   : ${REGION}"
echo "   Account  : ${ACCOUNT_ID}"
echo "======================================================"

if [ "$TARGET" == "all" ]; then
  for name in "${!LAMBDAS[@]}"; do
    build_and_deploy "$name"
  done
elif [ -n "${LAMBDAS[$TARGET]}" ]; then
  build_and_deploy "$TARGET"
else
  echo "❌ 알 수 없는 함수명: ${TARGET}"
  echo "   사용 가능: all, orchestrator, jira, github, slack"
  exit 1
fi

# 빌드 임시 파일 정리
rm -rf "${BUILD_DIR}/tmp_"*

echo ""
echo "======================================================"
echo "✅ 모든 배포 완료!"
echo ""
echo "다음 단계:"
echo "  1. python infra/bedrock_agent_setup.py  ← Agent + KB 설정"
echo "  2. GitHub Webhook URL 설정              ← API Gateway URL"
echo "======================================================"
