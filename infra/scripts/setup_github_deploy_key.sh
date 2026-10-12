#!/usr/bin/env bash
# Create a GitHub deploy key and store the private key in Secrets Manager.
# You add the PUBLIC key in GitHub (repo → Settings → Deploy keys).
#
#   aws sso login --profile sandbox
#   AWS_PROFILE=sandbox ./infra/scripts/setup_github_deploy_key.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEY_DIR="${ROOT}/.deploy-keys"
KEY_FILE="${KEY_DIR}/github-deploy"
REGION="${AWS_REGION:-eu-west-2}"
PROFILE="${AWS_PROFILE:-sandbox}"
SECRET_ID="${GITHUB_DEPLOY_KEY_SECRET_ID:/github-deploy-key}"

aws_cli() { aws --profile "$PROFILE" --region "$REGION" "$@"; }
log() { printf '[github-deploy-key] %s\n' "$*"; }
die() { printf '[github-deploy-key] ERROR: %s\n' "$*" >&2; exit 1; }

aws_cli sts get-caller-identity >/dev/null || die "Not logged in. Run: aws sso login --profile $PROFILE"

mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

if [[ ! -f "$KEY_FILE" ]]; then
  log "Generating ed25519 key → $KEY_FILE"
  ssh-keygen -t ed25519 -f "$KEY_FILE" -N "" -C "ec2-deploy"
else
  log "Using existing key → $KEY_FILE"
fi

PRIVATE_KEY="$(cat "$KEY_FILE")"
PUBLIC_KEY="$(cat "${KEY_FILE}.pub")"

if aws_cli secretsmanager describe-secret --secret-id "$SECRET_ID" >/dev/null 2>&1; then
  aws_cli secretsmanager put-secret-value --secret-id "$SECRET_ID" --secret-string "$PRIVATE_KEY" >/dev/null
  log "Updated Secrets Manager secret: $SECRET_ID"
else
  aws_cli secretsmanager create-secret \
    --name "$SECRET_ID" \
    --description "GitHub deploy key (private) for App EC2 git clone" \
    --secret-string "$PRIVATE_KEY" >/dev/null
  log "Created Secrets Manager secret: $SECRET_ID"
fi

log ""
log "=== Add this PUBLIC key in GitHub ==="
log "Repo → Settings → Deploy keys → Add deploy key"
log "Title: ec2-deploy   Allow write access: OFF (read-only)"
log ""
cat "${KEY_FILE}.pub"
log ""
log "Then set in terraform.tfvars:"
log "  github_deploy_key_secret_id = \"$SECRET_ID\""
log "  git_repo_url = \"git@github.com:YOUR_ORG/legal-kag.git\""
log "  deploy_with_docker = false"
log ""
log "Then: cd infra/terraform/environments && terraform apply"
