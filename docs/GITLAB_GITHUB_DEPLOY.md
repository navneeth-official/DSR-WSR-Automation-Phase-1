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
4. **Settings → CI/CD → Variables**:
   - `DEPLOY_REPO_ROOT` = absolute path to your clone on the VM (e.g. `/home/g10xtestid/DSR-WSR-AUTOMATION`)
   - `DEPLOY_ENVIRONMENT_URL` = `http://YOUR_VM_STATIC_IP` (optional)
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
- **Passwordless sudo** for the deploy script (see below).

```bash
chmod +x scripts/deploy-vm.sh
```

#### Sudo for GitLab Runner (required)

The job runs as `gitlab-runner`. `deploy-vm.sh` first does `sudo -u g10xtestid`, then as `g10xtestid` runs `sudo systemctl`, `sudo cp`, etc. Both need NOPASSWD rules.

On the VM, create `/etc/sudoers.d/gitlab-runner-deploy`:

```bash
sudo visudo -f /etc/sudoers.d/gitlab-runner-deploy
```

Paste (replace `g10xtestid` if you use a different `DEPLOY_USER`):

```sudoers
# GitLab shell runner → re-exec deploy script as app owner
gitlab-runner ALL=(g10xtestid) NOPASSWD: ALL

# App owner → restart API, publish static files to nginx
g10xtestid ALL=(ALL) NOPASSWD: /usr/bin/systemctl, /bin/systemctl, /usr/bin/mkdir, /bin/mkdir, /usr/bin/cp, /bin/cp, /usr/bin/chown, /bin/chown, /usr/bin/rm, /bin/rm
```

Save, then validate:

```bash
sudo visudo -c
sudo -u gitlab-runner sudo -u g10xtestid whoami   # should print: g10xtestid
sudo -u g10xtestid sudo systemctl status dsr-wsr-api --no-pager
```

**Alternative:** run the shell runner as `g10xtestid` — in `/etc/gitlab-runner/config.toml` add `user = "g10xtestid"` under your runner, then `sudo gitlab-runner restart`. You still need the second sudoers line for `g10xtestid`.

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
export GITLAB_PROJECT_ID="YOUR_PROJECT_ID"
export GITLAB_TRIGGER_TOKEN="YOUR_TRIGGER_TOKEN"
export GIT_REF="master"
bash scripts/test-gitlab-trigger.sh
```

## End-to-end smoke test (push)

1. Edit `TRIGGER_TEST.md` (change the `updated:` line).
2. Commit and push to GitHub `master`/`main`.
3. Verify GitHub Action, GitLab pipeline, and on VM: `git log -1 TRIGGER_TEST.md`.

## Troubleshooting

### `scripts/deploy-vm.sh: No such file or directory`

The shell runner uses `GIT_STRATEGY: none` (no GitLab checkout). The job must run the script from your **permanent VM clone**, not the runner build folder.

On the VM, find the clone path:

```bash
sudo -u g10xtestid bash -lc 'find ~ -name deploy-vm.sh 2>/dev/null'
```

Set that directory's parent repo root as **`DEPLOY_REPO_ROOT`** in GitLab → Settings → CI/CD → Variables, then re-run the pipeline.

Example: if the script is at `/home/g10xtestid/DSR-WSR-AUTOMATION/scripts/deploy-vm.sh`, set:

`DEPLOY_REPO_ROOT` = `/home/g10xtestid/DSR-WSR-AUTOMATION`

Ensure the clone contains the latest code (including `scripts/deploy-vm.sh`):

```bash
cd /home/g10xtestid/DSR-WSR-AUTOMATION
git pull origin master
chmod +x scripts/deploy-vm.sh
```

### `sudo: a password is required`

GitLab Runner jobs run as `gitlab-runner`. The deploy script calls `sudo -u g10xtestid` and later `sudo systemctl` / `sudo cp` — all must be passwordless.

Follow **Sudo for GitLab Runner** in section 3 above, then retry the pipeline.

Quick test on the VM:

```bash
sudo -u gitlab-runner sudo -u g10xtestid whoami
sudo -u g10xtestid sudo systemctl status dsr-wsr-api --no-pager
```

Both commands must succeed without prompting for a password.

## Notes

- `.env` and Google OAuth files stay on the VM only (gitignored); deploy does not remove them.
- If the VM clone lives under a extra folder (e.g. `DSR-WSR-Automation-Phase-1`), clone this repo root **inside** that folder or adjust paths in `deploy-vm.sh`.
- Slide previews on Linux: install LibreOffice and set `PPT_RENDER_BACKEND=libreoffice` when that backend is merged.
