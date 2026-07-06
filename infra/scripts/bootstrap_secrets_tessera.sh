#!/usr/bin/env bash
# Push .env → Secrets Manager as flat JSON for Lodestone (LODESTONE_* / Bedrock on EC2).
#
#   aws sso login --profile sandbox
#   AWS_PROFILE=sandbox AWS_REGION=eu-west-2 ./infra/scripts/bootstrap_secrets_lodestone.sh
#
# Prod: LODESTONE_SECRET_ID=lodestone/prod/env ./infra/scripts/bootstrap_secrets_lodestone.sh

set -euo pipefail
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGION="${AWS_REGION:-eu-west-2}"
PROFILE="${AWS_PROFILE:-sandbox}"
SECRET_ID="${LODESTONE_SECRET_ID:-lodestone/env}"

aws_cli() { aws --profile "$PROFILE" --region "$REGION" "$@"; }
log() { printf '[secrets] %s\n' "$*"; }
die() { printf '[secrets] ERROR: %s\n' "$*" >&2; exit 1; }

aws_cli sts get-caller-identity >/dev/null || die "Not logged in. Run: aws sso login --profile $PROFILE"
[[ -f "${ROOT}/.env" ]] || die "Missing ${ROOT}/.env"

JSON="$(python3 - "$ROOT/.env" <<'PY'
import json, sys
from pathlib import Path

vals = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k, v = k.strip(), v.strip()
    if k:
        vals[k] = v

required = ("LODESTONE_NEO4J_PASSWORD",)
missing = [k for k in required if not vals.get(k)]
if missing:
    raise SystemExit(f"missing required keys in .env: {', '.join(missing)}")

print(json.dumps(vals, indent=2))
PY
)" || die "Failed to parse .env"

if aws_cli secretsmanager describe-secret --secret-id "$SECRET_ID" >/dev/null 2>&1; then
  aws_cli secretsmanager put-secret-value --secret-id "$SECRET_ID" --secret-string "$JSON" >/dev/null
  log "Updated: $SECRET_ID"
else
  aws_cli secretsmanager create-secret \
    --name "$SECRET_ID" \
    --description "Lodestone runtime env (LODESTONE_* flat JSON)" \
    --secret-string "$JSON" >/dev/null
  log "Created: $SECRET_ID"
fi

log "Keys: $(python3 -c 'import json,sys; print(", ".join(sorted(json.load(sys.stdin))))' <<<"$JSON")"
