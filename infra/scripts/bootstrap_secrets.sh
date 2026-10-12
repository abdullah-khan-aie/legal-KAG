#!/usr/bin/env bash
# Push .env → Secrets Manager as flat JSON (* keys).
# The app loads these at runtime via AWS_SECRETS_MANAGER_SECRET_ID (no .env fallback).
# Neo4j keys are preserved from the existing secret (AWS Bolt URI + password).
#
#   aws sso login --profile sandbox
#   AWS_PROFILE=sandbox AWS_REGION=eu-west-2 ./infra/scripts/bootstrap_secrets.sh

set -euo pipefail
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGION="${AWS_REGION:-eu-west-2}"
PROFILE="${AWS_PROFILE:-sandbox}"
SECRET_ID="${SECRET_ID:/env}"

aws_cli() { aws --profile "$PROFILE" --region "$REGION" "$@"; }
log() { printf '[secrets] %s\n' "$*"; }
die() { printf '[secrets] ERROR: %s\n' "$*" >&2; exit 1; }

aws_cli sts get-caller-identity >/dev/null || die "Not logged in. Run: aws sso login --profile $PROFILE"
[[ -f "${ROOT}/.env" ]] || die "Missing ${ROOT}/.env"

EXISTING_JSON="$(
  if aws_cli secretsmanager describe-secret --secret-id "$SECRET_ID" >/dev/null 2>&1; then
    aws_cli secretsmanager get-secret-value --secret-id "$SECRET_ID" --query SecretString --output text
  else
    echo "{}"
  fi
)"

JSON="$(python3 - "$ROOT/.env" "$EXISTING_JSON" <<'PY'
import json, sys
from pathlib import Path

env_path, existing_raw = sys.argv[1], sys.argv[2]
existing = json.loads(existing_raw or "{}")

vals: dict[str, str] = {}
for line in Path(env_path).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k, v = k.strip(), v.strip()
    if k.startswith(""):
        vals[k] = v

if not vals.get("NEO4J_PASSWORD") and not (
    existing.get("NEO4J_PASSWORD") or existing.get("NEO4J_PASSWORD")
):
    raise SystemExit("missing NEO4J_PASSWORD in .env or existing secret")

# Keep deployed Neo4j connection details from the existing secret.
neo4j_uri = existing.get("NEO4J_URI") or existing.get("NEO4J_URI") or vals.get("NEO4J_URI")
if not neo4j_uri:
    neo4j_uri = "bolt://10.20.1.145:7687"  # deployed Neo4j private IP (VPC)
neo4j_user = existing.get("NEO4J_USERNAME") or existing.get("NEO4J_USER") or "neo4j"
neo4j_password = existing.get("NEO4J_PASSWORD") or existing.get("NEO4J_PASSWORD")
neo4j_database = existing.get("NEO4J_DATABASE") or vals.get("NEO4J_DATABASE") or "neo4j"

if neo4j_uri:
    vals["NEO4J_URI"] = neo4j_uri
if neo4j_user:
    vals["NEO4J_USER"] = neo4j_user
if neo4j_password:
    vals["NEO4J_PASSWORD"] = neo4j_password
vals["NEO4J_DATABASE"] = neo4j_database

# Deployment default for ingest folder (not in local .env).
vals.setdefault("SCAN_DIR", "/data/ingest")
vals.setdefault("EMBED_INPUT_TYPE", "search_document")
vals.setdefault("NAMESPACE", "app")
vals.setdefault("LOG_LEVEL", "INFO")
vals.setdefault("LOG_FORMAT", "console")
vals.setdefault("MAX_CONCURRENCY", "1")
vals.setdefault("MODEL_EXECUTE_NUM", "1")
vals.setdefault("NEO4J_DATABASE", "neo4j")

required = [
    "SCHEMA_PATH",
    "BEDROCK_REGION",
    "LLM_MODEL",
    "EMBED_REGION",
    "EMBED_MODEL",
    "EMBED_INPUT_TYPE",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
    "NAMESPACE",
    "SCAN_DIR",
    "MAX_CONCURRENCY",
    "MODEL_EXECUTE_NUM",
    "LOG_LEVEL",
    "LOG_FORMAT",
]
missing = [k for k in required if not vals.get(k)]
if missing:
    raise SystemExit("missing required secret keys: " + ", ".join(missing))

# Never store local AWS profile / keys in Secrets Manager.
for k in list(vals):
    if k.startswith("AWS_ACCESS_KEY") or k in (
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_CREDENTIAL_EXPIRATION",
        "AWS_PROFILE",
    ):
        del vals[k]

print(json.dumps(dict(sorted(vals.items())), indent=2))
PY
)" || die "Failed to build secret JSON"

if aws_cli secretsmanager describe-secret --secret-id "$SECRET_ID" >/dev/null 2>&1; then
  aws_cli secretsmanager put-secret-value --secret-id "$SECRET_ID" --secret-string "$JSON" >/dev/null
  log "Updated: $SECRET_ID (replaced — old Azure/Langfuse/INGEST_* keys removed)"
else
  aws_cli secretsmanager create-secret \
    --name "$SECRET_ID" \
    --description "App runtime env (* flat JSON)" \
    --secret-string "$JSON" >/dev/null
  log "Created: $SECRET_ID"
fi

REMOVED="$(python3 - "$EXISTING_JSON" "$JSON" <<'PY'
import json, sys
old = set(json.loads(sys.argv[1] or "{}"))
new = set(json.loads(sys.argv[2]))
print(", ".join(sorted(old - new)) or "(none)")
PY
)"

log "Keys now: $(python3 -c 'import json,sys; print(", ".join(sorted(json.load(sys.stdin))))' <<<"$JSON")"
log "Removed: $REMOVED"
