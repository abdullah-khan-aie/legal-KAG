#!/usr/bin/env bash
# Build and push the Lodestone image to ECR (run from laptop after terraform creates the repo).
#
#   AWS_PROFILE=sandbox AWS_REGION=eu-west-2 ./scripts/docker-build-push-ecr.sh
#
# Optional: LODESTONE_ECR_REPO=123456789012.dkr.ecr.eu-west-2.amazonaws.com/lodestone-poc-lodestone

set -euo pipefail
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Build context: default to this repo, but override to build from a clean
# checkout (e.g. an origin/main git worktree) so the image is exactly the
# online branch code, not the local working copy.
CONTEXT="${LODESTONE_BUILD_CONTEXT:-$ROOT}"
REGION="${AWS_REGION:-eu-west-2}"
PROFILE="${AWS_PROFILE:-sandbox}"
TAG="${LODESTONE_IMAGE_TAG:-latest}"
REPO="${LODESTONE_ECR_REPO:-}"

aws_cli() { aws --profile "$PROFILE" --region "$REGION" "$@"; }

if [[ -z "$REPO" ]]; then
  REPO="$(aws_cli ecr describe-repositories --query 'repositories[?contains(repositoryName, `lodestone`)].repositoryUri' --output text | head -1)"
fi
[[ -n "$REPO" ]] || { echo "Set LODESTONE_ECR_REPO or create ECR via terraform (lodestone_ecr_enabled=true)"; exit 1; }

IMAGE="${REPO}:${TAG}"
# EC2 (t3.large) is x86_64; build for linux/amd64 even from an arm64 Mac.
PLATFORM="${LODESTONE_PLATFORM:-linux/amd64}"
log() { printf '[ecr] %s\n' "$*"; }

log "Logging in to ECR"
aws_cli ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"

log "Building + pushing $IMAGE ($PLATFORM) from context: $CONTEXT"
docker buildx build --platform "$PLATFORM" -t "$IMAGE" --push "$CONTEXT"

log "Done. On EC2 set: export LODESTONE_ECR_URI=$IMAGE && ./scripts/docker-aws-up.sh"
