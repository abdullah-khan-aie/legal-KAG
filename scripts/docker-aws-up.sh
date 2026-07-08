#!/usr/bin/env bash
# Start Lodestone with Docker Compose on EC2 (or any host with instance role / AWS creds).
# App config is loaded at runtime from Secrets Manager — not flattened into LODESTONE_* env.
#
#   AWS_REGION=eu-west-2 ./scripts/docker-aws-up.sh

set -euo pipefail
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="${LODESTONE_DEPLOY_DIR:-/opt/lodestone}"
REGION="${AWS_REGION:-eu-west-2}"
SECRET_ID="${LODESTONE_SECRET_ID:-lodestone/env}"
ENV_FILE="${DEPLOY_DIR}/.env"
IMAGE="${LODESTONE_IMAGE:-lodestone-lodestone:latest}"
LOG_GROUP="${CLOUDWATCH_LOG_GROUP:-}"
if [[ -z "$LOG_GROUP" && -f "${DEPLOY_DIR}/cloudwatch_log_group" ]]; then
  LOG_GROUP="$(<"${DEPLOY_DIR}/cloudwatch_log_group")"
fi

log() { printf '[docker-aws] %s\n' "$*"; }
die() { printf '[docker-aws] ERROR: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || die "docker not installed"
docker compose version >/dev/null 2>&1 || die "docker compose plugin not installed"
aws sts get-caller-identity --region "$REGION" >/dev/null || die "AWS credentials unavailable"

mkdir -p "$DEPLOY_DIR"

log "Writing bootstrap env → $ENV_FILE (secret id: $SECRET_ID)"
cat >"$ENV_FILE" <<EOF
LODESTONE_PORT=8080
LODESTONE_IMAGE=${IMAGE}
AWS_SECRETS_MANAGER_SECRET_ID=${SECRET_ID}
AWS_SECRETS_MANAGER_REGION=${REGION}
AWS_REGION=${REGION}
INGEST_MOUNT=${INGEST_MOUNT:-/data/ingest}
EOF
if [[ -n "$LOG_GROUP" ]]; then
  printf 'CLOUDWATCH_LOG_GROUP=%s\n' "$LOG_GROUP" >>"$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

if [[ -n "${LODESTONE_ECR_URI:-}" ]]; then
  log "Pulling $LODESTONE_ECR_URI"
  aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "${LODESTONE_ECR_URI%%/*}"
  docker pull "${LODESTONE_ECR_URI}"
  export LODESTONE_IMAGE="${LODESTONE_ECR_URI}"
  sed -i "s|^LODESTONE_IMAGE=.*|LODESTONE_IMAGE=${LODESTONE_ECR_URI}|" "$ENV_FILE"
fi

cd "$ROOT"
export LODESTONE_ENV_FILE="$ENV_FILE"
export INGEST_MOUNT="${INGEST_MOUNT:-/data/ingest}"
export AWS_SECRETS_MANAGER_SECRET_ID="$SECRET_ID"
export AWS_SECRETS_MANAGER_REGION="$REGION"
export AWS_REGION="$REGION"

COMPOSE_FILES=(-f docker-compose.yml)
if [[ -n "$LOG_GROUP" ]]; then
  log "CloudWatch Logs → $LOG_GROUP"
  export CLOUDWATCH_LOG_GROUP="$LOG_GROUP"
  COMPOSE_FILES+=(-f docker-compose.aws.yml)
fi

docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" up -d --remove-orphans
docker compose ps
log "curl http://127.0.0.1:8080/docs"
