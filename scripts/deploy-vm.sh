#!/usr/bin/env bash
# Deploy DSR-WSR backend + frontend on the GCP VM (shell runner, no Docker).
#
# Prerequisites on VM: Postgres, nginx, systemd dsr-wsr-api, Node 20, Python venv,
# .env + credentials (gitignored), git remote with deploy key.
#
# Override via environment:
#   DEPLOY_USER   — user that owns the clone (default: g10xtestid)
#   DEPLOY_BRANCH — branch to deploy (default: CI_COMMIT_REF_NAME or master)

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-g10xtestid}"

# GitLab shell runner runs as gitlab-runner; re-exec as the app owner.
if [ "$(whoami)" != "$DEPLOY_USER" ]; then
  exec sudo -u "$DEPLOY_USER" env \
    DEPLOY_USER="$DEPLOY_USER" \
    DEPLOY_BRANCH="${DEPLOY_BRANCH:-${CI_COMMIT_REF_NAME:-master}}" \
    CI_COMMIT_REF_NAME="${CI_COMMIT_REF_NAME:-}" \
    bash "$0" "$@"
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$REPO_ROOT/DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation"
FRONTEND="$REPO_ROOT/DSR-WSR-AUTOMATION-Frontend/Frontend"
WEB_ROOT="/var/www/dsr-wsr"
BRANCH="${DEPLOY_BRANCH:-${CI_COMMIT_REF_NAME:-master}}"

echo "==> Deploy from $REPO_ROOT (branch: $BRANCH)"

cd "$REPO_ROOT"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# Backend
cd "$BACKEND"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m alembic upgrade head
deactivate
sudo systemctl restart dsr-wsr-api

# Frontend (react/react-dom are peer deps — ensure present before build)
cd "$FRONTEND"
npm install react@18.3.1 react-dom@18.3.1
npm install
npm run build

sudo mkdir -p "$WEB_ROOT"
sudo rm -rf "${WEB_ROOT:?}"/*
sudo cp -r dist/* "$WEB_ROOT"/
sudo chown -R www-data:www-data "$WEB_ROOT"
sudo systemctl reload nginx

curl -sf http://127.0.0.1:8000/health
echo ""
echo "Deploy OK — branch $BRANCH"
