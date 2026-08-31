# GitLab deploy trigger — smoke test file

Use this file to verify **GitHub push → GitHub Action → GitLab pipeline → VM deploy**.

## How to test

1. Edit the line below (change the timestamp or add a word).
2. Commit and push to **`master`** or **`main`** on GitHub.
3. Confirm each step succeeds.

| Step | Where to check | Expected |
|------|----------------|----------|
| 1 | GitHub → **Actions** → *Trigger GitLab Deploy* | Green checkmark |
| 2 | GitLab → **Build → Pipelines** | New pipeline within ~1 min |
| 3 | GitLab job **deploy_production** | Passed |
| 4 | VM | `curl http://127.0.0.1:8000/health` → OK |

## Last test push

```
status: e2e-test-1
updated: 32-08-2026
note: Change this block, commit, push, then verify pipeline + this file on VM via git log.
```

## Quick VM check (after pipeline passes)

SSH into the VM and run:

```bash
cd ~/DSR-WSR-AUTOMATION   # or your clone path
git log -1 --oneline TRIGGER_TEST.md
grep "updated:" TRIGGER_TEST.md
curl -s http://127.0.0.1:8000/health
```

If `git log` shows your commit and health returns OK, the trigger chain worked.

## Manual trigger (without GitHub)

From laptop or Cloud Shell:

```bash
export GITLAB_PROJECT_ID="YOUR_NUMERIC_PROJECT_ID"
export GITLAB_TRIGGER_TOKEN="YOUR_PIPELINE_TRIGGER_TOKEN"
export GIT_REF="master"
bash scripts/test-gitlab-trigger.sh
```

Then watch GitLab → Pipelines.
