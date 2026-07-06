#!/usr/bin/env bash
# Move Terraform state from legacy repo-root terraform/ to infra/terraform/environments/.
#
#   ./infra/scripts/migrate_legacy_terraform_state.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LEGACY="$ROOT/terraform"
ENV_DIR="$ROOT/infra/terraform/environments"

if [[ ! -d "$LEGACY" ]]; then
  echo "No legacy $LEGACY — nothing to migrate."
  exit 0
fi

mkdir -p "$ENV_DIR"

for f in terraform.tfstate terraform.tfstate.backup terraform.tfvars; do
  if [[ -f "$LEGACY/$f" ]] && [[ ! -f "$ENV_DIR/$f" ]]; then
    cp -v "$LEGACY/$f" "$ENV_DIR/$f"
  fi
done

if [[ -f "$LEGACY/.terraform.lock.hcl" ]] && [[ ! -f "$ENV_DIR/.terraform.lock.hcl" ]]; then
  cp -v "$LEGACY/.terraform.lock.hcl" "$ENV_DIR/.terraform.lock.hcl"
fi

echo ""
echo "Next: cd infra/terraform/environments && terraform init && terraform plan"
