#!/usr/bin/env bash
# Deploy the API Monitoring Platform to AWS (dev-sized stack).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"
AWS_REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

echo "==> Checking prerequisites"
require_cmd aws
require_cmd docker
require_cmd npm
require_cmd node

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials not configured. Run: aws configure" >&2
  exit 1
fi

export AWS_REGION
export CDK_DEFAULT_REGION="${AWS_REGION}"
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

echo "==> Installing CDK dependencies"
(cd "${INFRA_DIR}" && npm install)

echo "==> Synthesizing CloudFormation (pre-flight)"
(cd "${INFRA_DIR}" && npx cdk synth -c "imageTag=${IMAGE_TAG}" -c "corsOrigins=${CORS_ORIGINS}" >/dev/null)

echo "==> Deploying infrastructure"
(cd "${INFRA_DIR}" && npx cdk deploy --all --require-approval never \
  -c "imageTag=${IMAGE_TAG}" \
  -c "corsOrigins=${CORS_ORIGINS}")

ECR_URI="$(aws cloudformation describe-stacks \
  --stack-name RateLimiterDev \
  --query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri'].OutputValue" \
  --output text \
  --region "${AWS_REGION}")"

API_URL="$(aws cloudformation describe-stacks \
  --stack-name RateLimiterDev \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text \
  --region "${AWS_REGION}")"

echo "==> Building and pushing backend image to ${ECR_URI}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_URI%/*}"
docker build -t "${ECR_URI}:${IMAGE_TAG}" "${ROOT_DIR}/backend"
docker push "${ECR_URI}:${IMAGE_TAG}"

echo "==> Forcing ECS services to pull the new image"
CLUSTER_ARN="$(aws ecs list-clusters --region "${AWS_REGION}" --query "clusterArns[?contains(@, 'RateLimiterDev')]" --output text)"
for SERVICE in ApiService WorkerService SchedulerService; do
  SERVICE_ARN="$(aws ecs list-services --cluster "${CLUSTER_ARN}" --region "${AWS_REGION}" \
    --query "serviceArns[?contains(@, '${SERVICE}')]" --output text || true)"
  if [ -n "${SERVICE_ARN}" ]; then
    aws ecs update-service --cluster "${CLUSTER_ARN}" --service "${SERVICE_ARN}" \
      --force-new-deployment --region "${AWS_REGION}" >/dev/null
  fi
done

echo "==> Running database migrations (one-off ECS task)"
# Migration task uses the API task definition with an overridden command.
TASK_DEF="$(aws ecs list-task-definitions --region "${AWS_REGION}" \
  --sort DESC --max-items 20 --query "taskDefinitionArns[?contains(@, 'ApiServiceTaskDef')]" --output text | head -n1)"
SUBNETS="$(aws ec2 describe-subnets --region "${AWS_REGION}" \
  --filters "Name=tag:aws:cloudformation:stack-name,Values=RateLimiterDev" "Name=tag:Name,Values=*private*" \
  --query "Subnets[].SubnetId" --output text | tr '\t' ',')"
SG="$(aws ec2 describe-security-groups --region "${AWS_REGION}" \
  --filters "Name=tag:aws:cloudformation:stack-name,Values=RateLimiterDev" \
  --query "SecurityGroups[?contains(GroupName, 'ApiService')].GroupId | [0]" --output text)"

RUN_TASK="$(aws ecs run-task --region "${AWS_REGION}" \
  --cluster "${CLUSTER_ARN}" \
  --task-definition "${TASK_DEF}" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SG}],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"web","command":["alembic","upgrade","head"]}]}' \
  --query "tasks[0].taskArn" --output text)"

echo "Migration task: ${RUN_TASK}"
aws ecs wait tasks-stopped --cluster "${CLUSTER_ARN}" --tasks "${RUN_TASK}" --region "${AWS_REGION}"

EXIT_CODE="$(aws ecs describe-tasks --cluster "${CLUSTER_ARN}" --tasks "${RUN_TASK}" --region "${AWS_REGION}" \
  --query "tasks[0].containers[0].exitCode" --output text)"
if [ "${EXIT_CODE}" != "0" ]; then
  echo "Migration failed with exit code ${EXIT_CODE}" >&2
  exit 1
fi

echo ""
echo "Deployment complete."
echo "  API URL:     ${API_URL}"
echo "  Health:      ${API_URL}/health/ready"
echo "  Metrics:     ${API_URL}/metrics"
echo ""
echo "Next steps:"
echo "  1. Deploy frontend to Amplify with NEXT_PUBLIC_API_URL=${API_URL}"
echo "  2. Re-deploy with CORS_ORIGINS set to your frontend URL:"
echo "     CORS_ORIGINS=https://your-app.amplifyapp.com ./scripts/deploy-aws.sh"
echo "  3. Smoke test: ./scripts/smoke-test.sh ${API_URL}"
