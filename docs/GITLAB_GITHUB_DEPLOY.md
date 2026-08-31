# GitHub → GitLab CI → GCP VM Deploy

No Docker. Push to GitHub triggers GitLab; a **shell runner on the VM** runs `scripts/deploy-vm.sh`.

## Files in this repo

| File | Purpose |
|------|---------|
| `.gitlab-ci.yml` | GitLab pipeline (deploy job, runner tag `dsr-wsr-vm`) |
| `scripts/deploy-vm.sh` | Pull, backend restart, frontend build, nginx |
| `.github/workflows/trigger-gitlab.yml` | POST to GitLab pipeline trigger API on push |

## One-time setup

### 1. GitLab

1. Create project on [gitlab.com](https://gitlab.com).
2. Push this repo to GitLab (`git push gitlab master`) so GitLab has `.gitlab-ci.yml`.
3. **Settings → CI/CD → Pipeline triggers** → Add trigger → copy token.
4. **Settings → CI/CD → Variables** (optional):
   - `DEPLOY_ENVIRONMENT_URL` = `http://YOUR_VM_STATIC_IP`
   - `DEPLOY_USER` = VM Linux user (default in YAML: `g10xtestid`)

### 2. GitHub secrets

**Settings → Secrets and variables → Actions**

| Secret | Value |
|--------|--------|
| `GITLAB_TRIGGER_TOKEN` | Pipeline trigger token |
| `GITLAB_PROJECT_ID` | Numeric GitLab project ID |

### 3. GCP VM

- Bootstrap app (Postgres, `.env`, systemd `dsr-wsr-api`, nginx, Node 20).
- Clone repo (same layout as this monorepo root).
- Install GitLab Runner (**shell** executor, tag `dsr-wsr-vm`).
- GitHub deploy key on VM for `git pull`.
- `sudo visudo` — allow `gitlab-runner` to run deploy as `DEPLOY_USER` and restart services.

```bash
chmod +x scripts/deploy-vm.sh
```

Runner register example:

```bash
sudo gitlab-runner register
# URL: https://gitlab.com/
# Executor: shell
# Tags: dsr-wsr-vm
```

### 4. systemd service paths

Ensure `/etc/systemd/system/dsr-wsr-api.service` uses:

- `WorkingDirectory=.../DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation`
- `ExecStart=.../Jira-Automation/.venv/bin/uvicorn ...`

## Flow

```text
git push GitHub (master/main)
  → GitHub Action curl GitLab trigger API
  → GitLab pipeline deploy_production
  → scripts/deploy-vm.sh on VM
```

## Manual test

```bash
curl --fail -X POST \
  --form "token=YOUR_TRIGGER_TOKEN" \
  --form "ref=master" \
  "https://gitlab.com/api/v4/projects/YOUR_PROJECT_ID/trigger/pipeline"
```

## Notes

- `.env` and Google OAuth files stay on the VM only (gitignored); deploy does not remove them.
- If the VM clone lives under a extra folder (e.g. `DSR-WSR-Automation-Phase-1`), clone this repo root **inside** that folder or adjust paths in `deploy-vm.sh`.
- Slide previews on Linux: install LibreOffice and set `PPT_RENDER_BACKEND=libreoffice` when that backend is merged.
