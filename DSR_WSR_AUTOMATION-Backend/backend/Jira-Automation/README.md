# Jira Automation — WSR PowerPoint Pipeline

Python tooling that stores Jira story data in PostgreSQL and builds **H-E-B Weekly Status Report (WSR)** PowerPoint decks from the G10X template.

> **Full project guide** (frontend + API + deployment + PowerPoint COM): see the repository root [README.md](../../README.md).

## How it works

```
Rovo AI JSON  →  PostgreSQL  →  ppt_content.json  →  HEB_Delivery_Status.pptx
     (import)      (stories,        (slide text)         (G10X layout)
                    sprints)
```

1. **Import** — Story data from Rovo AI is loaded into `projects`, `sprints`, and `jira_stories`.
2. **Content build** — For a WSR date range you specify, the app selects qualifying sprints (overlap with the report window), groups stories by service/sprint, and writes `output/ppt_content.json`.
3. **Deck build** — `update_delivery_status.py` copies the G10X template, fills Highlights / Key Activities, removes slides with no content, reflows the Index, and saves the `.pptx`.
4. **Evaluation** (optional) — A separate step checks the deck against G10X spacing and layout rules (PASS/FAIL per slide).
5. **Visual correction** (optional) — A separate command uses geometry + vision models to inspect and correct layout issues.

**Key paths**

| Path | Purpose |
|------|---------|
| `templates/G10X H-E-B WSR Sustainment 05 June 2026 .pptx` | G10X master template |
| `output/ppt_content.json` | Generated slide content |
| `output/ppt_content_preview.txt` | Human-readable preview |
| `output/HEB_Delivery_Status.pptx` | Built deck (default) |

## Prerequisites

- **Python 3.11+**
- **PostgreSQL** (local, Docker, or AWS RDS)
- **Azure OpenAI** (optional) — for AI story titles and vision-based layout review

---

## One-time setup

### 1. Clone and install

```powershell
cd Jira-Automation

py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment

```powershell
copy .env.example .env
```

Edit `.env` with your database credentials:

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/dsr_wsr_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=dsr_wsr_db
```

> If the password contains `@`, URL-encode it in `DATABASE_URL` (e.g. `@` → `%40`).

For AI titles and vision evaluation, also set:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_MODEL=gpt-4o-mini
AZURE_OPENAI_VISION_MODEL=gpt-4o
```

### 3. Create database and tables

```powershell
python scripts/init_db.py
python -m alembic upgrade head
```

### 4. Import Jira / Rovo data

```powershell
python scripts/seed_from_rovo.py "path\to\rovo-response.json"
```

Re-running the import **upserts** rows by `jira_key`. Verify with:

```powershell
python scripts/check_schema.py
```

**Docker alternative** — see `.env.docker.example` and `docker compose --env-file .env.docker up -d`. Remote/AWS setup: [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md).

---

## Running — Automation (build the deck)

All commands assume the virtual environment is active and you are in the `Jira-Automation` folder.

### Full pipeline (recommended)

Reads PostgreSQL for the WSR date range, writes JSON + preview, and builds the PowerPoint:

```powershell
python scripts/generate_ppt_content.py --start-date 2026-04-16 --end-date 2026-06-15
```

**Outputs:** `output/ppt_content.json`, `output/ppt_content_preview.txt`, `output/HEB_Delivery_Status.pptx`

### JSON only (no PowerPoint)

```powershell
python scripts/generate_ppt_content.py --start-date 2026-04-16 --end-date 2026-06-15 --json-only
```

### Build PowerPoint from existing JSON

If `ppt_content.json` already exists:

```powershell
python scripts/update_delivery_status.py --content output/ppt_content.json --output output/HEB_Delivery_Status.pptx
```

### Useful automation flags

| Flag | Purpose |
|------|---------|
| `--save-titles` | Persist AI-generated story titles to the database |
| `--regenerate-titles` | Force regeneration of titles via GPT |
| `--ppt-output path.pptx` | Custom output deck path |
| `--json-only` | Skip `.pptx` build |

**WSR sprint selection** — Sprints whose duration **overlaps** the report range are included. Sprint dates shown on slides come from the `sprints` table (not clipped to the WSR window). Projects with no content are omitted from the deck and Index slide.

---

## Running — Evaluation (format check)

Evaluation is **read-only** — it reports PASS/FAIL per slide; it does not modify the deck.

### Deterministic rules only (no API)

```powershell
python scripts/evaluate_ppt_format.py --ppt output/HEB_Delivery_Status.pptx --mode deterministic
```

### Full evaluation (rules + AI rulebook)

```powershell
python scripts/evaluate_ppt_format.py --ppt output/HEB_Delivery_Status.pptx --mode full
```

### Include visual / vision review in evaluation

```powershell
python scripts/evaluate_ppt_format.py --ppt output/HEB_Delivery_Status.pptx --mode full --vision
```

Vision review flags: oversized HL box for sparse content, excessive HL–KA tab gap, overlap/clipping. It does **not** flag small KA tabs or empty space below KA on `(Contd…)` slides.

**Reports** (saved by default under `output/`):

- `HEB_Delivery_Status.format_eval.json`
- `HEB_Delivery_Status.format_eval.txt`

| Mode | What it checks |
|------|----------------|
| `deterministic` | Spacing, overlap, fonts, utilization — no API |
| `ai` | AI rulebook review |
| `vision` | Visual review via rendered slide images |
| `full` | Deterministic + AI (`--vision` adds visual layer) |

---

## Running — Visual model correction (separate step)

Use this **after** the deck is built when you want automated layout inspection and correction (geometry + qualitative vision). This is **not** part of the default build.

```powershell
python scripts/run_hybrid_validation_loop.py --ppt output/HEB_Delivery_Status.pptx
```

Rebuild from JSON and correct in one run:

```powershell
python scripts/run_hybrid_validation_loop.py --content output/ppt_content.json --output output/HEB_Delivery_Status_corrected.pptx
```

| Flag | Purpose |
|------|---------|
| `--max-iterations 3` | Max correction loops (default: 3) |
| `--keep-images` | Keep rendered slide PNGs |
| `--geometry-only` | Geometry inspection only (no vision API) |
| `--legacy-vision-measurement` | Legacy pixel-measurement loop |

Requires `AZURE_OPENAI_*` in `.env` for vision steps. Close the `.pptx` in PowerPoint before running if you get a file-lock error.

> **Note:** You can also trigger validation from the generate script with `--vision-validate`, but the dedicated command above is the recommended way to run visual correction on an existing deck.

---

## Database schema (summary)

| Table | Purpose |
|-------|---------|
| `projects` | One row per Jira project |
| `sprints` | Sprint name, start/end dates, status |
| `jira_stories` | Story details; FK to project and sprint |

Full reference: `sql/schema.sql` · ER diagram: `sql/erd.md`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Connection refused | Ensure PostgreSQL is running; check `.env` |
| Database does not exist | `python scripts/init_db.py` |
| Missing columns | `python -m alembic upgrade head` |
| PermissionError on `.pptx` | Close PowerPoint or use a different `--output` path |
| No stories for date range | Widen `--start-date` / `--end-date` or re-import Rovo data |
| Vision / AI errors | Verify `AZURE_OPENAI_*` in `.env` |

## What not to commit

- `.env` (credentials)
- `.venv/`
- Local sample Rovo files with real data

## License

Internal H-E-B training project.
