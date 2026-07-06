#!/usr/bin/env bash
# Pre-flight before terraform apply.
#
#   ./infra/scripts/check_terraform_prereqs.sh

set -euo pipefail
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION

PROFILE="${AWS_PROFILE:-sandbox}"
REGION="${AWS_REGION:-eu-west-2}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TF_DIR="$ROOT/infra/terraform/environments"

aws_cli() { aws --profile "$PROFILE" --region "$REGION" "$@"; }
ok() { printf '  PASS  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; printf '        %s\n' "$2"; }
skip() { printf '  SKIP  %s\n' "$1"; }

echo "Terraform pre-flight profile=$PROFILE region=$REGION"
echo ""

aws_cli sts get-caller-identity || { echo "Run: aws sso login --profile $PROFILE"; exit 1; }
echo ""

BLOCKED=0
OUT=$(aws_cli ec2 run-instances --image-id ami-0add4e75149fe4c81 --instance-type t3.micro --dry-run 2>&1) || true
if echo "$OUT" | grep -q DryRunOperation; then ok "ec2:RunInstances"; else fail "ec2:RunInstances" "$OUT"; BLOCKED=1; fi

command -v terraform >/dev/null && ok "terraform installed" || { fail "terraform" "not found"; BLOCKED=1; }
[[ -d "$TF_DIR" ]] && ok "terraform dir: $TF_DIR" || { fail "terraform dir" "missing $TF_DIR"; BLOCKED=1; }

if [[ -f "$TF_DIR/terraform.tfvars" ]]; then
  ok "terraform.tfvars exists"
else
  skip "copy $TF_DIR/terraform.tfvars.example → terraform.tfvars"
fi

echo ""
if [[ $BLOCKED -eq 0 ]]; then
  echo "Ready: cd $TF_DIR && terraform init && terraform plan"
else
  exit 1
fi
