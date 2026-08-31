#!/usr/bin/env bash
# Manually trigger a GitLab pipeline (same API call as the GitHub Action).
#
# Usage:
#   export GITLAB_PROJECT_ID="12345678"
#   export GITLAB_TRIGGER_TOKEN="your-trigger-token"
#   export GIT_REF="master"   # optional, default master
#   bash scripts/test-gitlab-trigger.sh
#
# Get token: GitLab → Settings → CI/CD → Pipeline triggers
# Get project ID: GitLab → Settings → General

set -euo pipefail

GITLAB_PROJECT_ID="${GITLAB_PROJECT_ID:-}"
GITLAB_TRIGGER_TOKEN="${GITLAB_TRIGGER_TOKEN:-}"
GIT_REF="${GIT_REF:-master}"
GITLAB_HOST="${GITLAB_HOST:-https://gitlab.com}"

if [ -z "$GITLAB_PROJECT_ID" ] || [ -z "$GITLAB_TRIGGER_TOKEN" ]; then
  echo "ERROR: Set GITLAB_PROJECT_ID and GITLAB_TRIGGER_TOKEN" >&2
  echo "  export GITLAB_PROJECT_ID=\"12345678\"" >&2
  echo "  export GITLAB_TRIGGER_TOKEN=\"your-token\"" >&2
  exit 1
fi

URL="${GITLAB_HOST}/api/v4/projects/${GITLAB_PROJECT_ID}/trigger/pipeline"
echo "Triggering GitLab pipeline..."
echo "  Project ID: $GITLAB_PROJECT_ID"
echo "  Ref:        $GIT_REF"
echo "  URL:        $URL"

RESPONSE="$(curl --fail --show-error -sS -X POST \
  --form "token=${GITLAB_TRIGGER_TOKEN}" \
  --form "ref=${GIT_REF}" \
  "$URL")"

echo ""
echo "Success. GitLab response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""
echo "Next: GitLab → Build → Pipelines → confirm job deploy_production runs."
