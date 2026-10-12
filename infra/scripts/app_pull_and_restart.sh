#!/usr/bin/env bash
# Pull latest origin/feat/kag-rag-engine on the app EC2 and restart uvicorn.
#
# Run via SSM on the app instance (or locally if repo is already on the box):
#   AWS_PROFILE=sandbox AWS_REGION=eu-west-2 ./scripts/app_pull_and_restart.sh
#
# Optional overrides:
#   APP_GIT_REF=feat/kag-rag-engine
#   APP_DIR=/opt/app

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/app}"
GIT_REF="${APP_GIT_REF:-feat/kag-rag-engine}"
SERVICE="${APP_SERVICE:-app.service}"

[[ -d "$APP_DIR/.git" ]] || { echo "No git repo at $APP_DIR" >&2; exit 1; }

cd "$APP_DIR"
git fetch origin "$GIT_REF" --depth 1
git checkout -B "$GIT_REF" "FETCH_HEAD"
uv sync --frozen 2>/dev/null || uv sync
systemctl restart "$SERVICE"
systemctl --no-pager status "$SERVICE"
