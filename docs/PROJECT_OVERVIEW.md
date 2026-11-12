# Jira Automation — Project Overview

This project builds **status report PowerPoint decks** for H-E-B delivery work from Jira story data.

It is **not** a React or web UI app. It is a **Python automation pipeline**: data goes into a database, scripts turn that data into slide content, and a PowerPoint template is filled and saved.

Two report types are supported:

| Report | What it is | Typical use |
|--------|------------|-------------|
| **WSR** (Weekly Status Report) | Delivery status deck with Highlights and Key Activities per project | Weekly cadence |
| **MSR** (Monthly Status Report) | Monthly cadence deck with cover, accomplishments, and delivery metrics | Monthly cadence |

Both read from the **same PostgreSQL database**. They use **different templates and code paths**.

---

## What you get today

- **Data import** from Rovo AI JSON into PostgreSQL
- **Weekly WSR** PowerPoint generation from a G10X template
- **Monthly MSR** PowerPoint generation from a monthly cadence template
- **AI story titles** (optional) for cleaner slide bullets
- **AI accomplishments** summaries for MSR (optional)
- **Format evaluation** of WSR decks (PASS/FAIL style checks)
- **Visual / layout correction** loop for WSR (optional, uses vision models)
- **Docker / AWS-friendly** database setup

---

## Big picture — how the system is put together

There is no frontend screen and no REST API layer in this repo. The “app” is scripts + Python packages talking to a database and PowerPoint files.

```text
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────────┐
│  Rovo / Jira    │      │   PostgreSQL     │      │  PowerPoint templates   │
│  JSON export    │─────▶│                  │◀────▶│  (WSR + MSR masters)    │
└─────────────────┘      │  projects        │      └─────────────────────────┘
                         │  sprints         │
                         │  jira_stories    │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
           ┌────────────────┐          ┌────────────────┐
           │  WSR pipeline  │          │  MSR pipeline  │
           │  (weekly)      │          │  (monthly)     │
           └───────┬────────┘          └───────┬────────┘
                   │                           │
                   ▼                           ▼
           HEB_Delivery_Status.pptx     HEB_Monthly_Cadence_….pptx
```

### Main pieces (think of them as layers)

| Layer | Role | Where it lives |
|-------|------|----------------|
| **Scripts** | Entry points you run from the command line | `scripts/` |
| **Data models** | Tables for projects, sprints, stories | `app/models/` + `sql/` |
| **Repositories / DB access** | Read and write story data | `app/repositories/`, `monthly_report/db.py` |
| **Services** | Business logic (content build, titles, format checks) | `app/services/` |
| **WSR engine** | Fills the weekly PowerPoint template | `app/wsr_engine/` |
| **Monthly report package** | Builds the monthly cadence deck | `monthly_report/` |
| **Vision / validation** | Optional layout review and correction | `app/vision/`, `app/pipeline/`, `app/validation/` |
| **Templates** | Master `.pptx` files to clone and fill | `templates/`, `templates/monthly/` |
| **Output** | Generated JSON, previews, and decks | `output/` |

Optional AI (Azure OpenAI / configured LLM) is used for:

- Shorter story titles on WSR slides
- Accomplishments wording on MSR slides
- Vision-based layout review on WSR decks

---

## Shared data foundation

Everything starts with imported Jira-like data.

```text
Rovo AI JSON  →  import script  →  PostgreSQL
```

**Tables (simple view):**

- **projects** — one row per service / track (e.g. Cost, Location)
- **sprints** — sprint name, dates, status
- **jira_stories** — story key, status, summary, optional AI title, links to project + sprint

```text
projects ──◀── jira_stories ──▶── sprints
```

Import command (high level):

```powershell
python scripts/seed_from_rovo.py "path\to\rovo-response.json"
```

Once data is in the database, both WSR and MSR can run without re-importing (until you want fresher data).

---

## WSR — Weekly Status Report

### What the deck contains

- Cover slide with the report date window
- Index of projects that have content
- One or more **Delivery status** slides per project
  - **Highlights** (e.g. released / in progress / completed style bullets)
  - **Key Activities**
- Continuation slides when content overflows
- Empty projects are dropped from the deck and index

### End-to-end flow

```text
1. Choose report dates (start + end)
2. Read matching stories / sprints from PostgreSQL
3. Build slide content JSON (+ human-readable preview)
4. Copy G10X WSR template
5. Fill Highlights / Key Activities, update cover + index
6. Save PowerPoint
7. (Optional) Evaluate format
8. (Optional) Run visual layout correction
```

```text
PostgreSQL
    │
    ▼
Content builder  ──▶  ppt_content.json
    │                 ppt_content_preview.txt
    ▼
WSR engine / deck builder
    │
    ▼
HEB_Delivery_Status.pptx
    │
    ├──▶ Format evaluation (optional)
    └──▶ Vision correction loop (optional)
```

### Main WSR components

| Component | What it does |
|-----------|--------------|
| `scripts/generate_ppt_content.py` | Main “run the weekly report” command |
| Content builder (`app/services/ppt_content_builder.py`) | Selects stories for the date window and groups them into slide content |
| Title generator | Optionally creates short AI titles for bullets |
| WSR engine (`app/wsr_engine/`) | Matches projects to template slides, fills text, handles overflow / continuation, updates index and logos |
| Format evaluator | Checks spacing, fonts, layout rules |
| Hybrid validation loop | Inspects rendered slides and tries to fix layout issues |

### Typical command

```powershell
python scripts/generate_ppt_content.py --start-date 2026-04-16 --end-date 2026-06-15
```

Outputs usually land under `output/`:

- `ppt_content.json` — structured slide text
- `ppt_content_preview.txt` — easy-to-read check
- `HEB_Delivery_Status.pptx` — the weekly deck

### WSR features in brief

- Sprint selection based on overlap with the report window
- Project-ordered delivery slides from the G10X template
- Highlights + Key Activities filled from story statuses
- Continuation slides for long content
- Cover date + week date placeholders updated
- Index rebuilt for projects that remain
- Optional AI titles
- Optional PASS/FAIL format evaluation
- Optional vision-based layout correction

---

## MSR — Monthly Status Report

### What the deck contains

One deck per run, filtered by **track / project name(s)**:

1. **Cover** — meeting date, period, track name
2. Per selected project:
   - **Accomplishments** (AI summary of completed / notable work, when enabled)
   - **Delivery Updates** — sprint snapshot tables and status chart metrics
3. Closing slide (e.g. Thank you)

The monthly pipeline is **independent** of the weekly WSR engine. It lives in `monthly_report/` and uses templates under `templates/monthly/`.

### End-to-end flow

```text
1. Choose report period (start + end) and track name(s)
2. Load projects / sprints / stories for that period from PostgreSQL
3. Filter to the requested track(s)
4. Compute sprint metrics (counts by status)
5. (Optional) Summarize accomplishments with an LLM
6. Clone monthly template and fill cover + project slides
7. Save PowerPoint under output/monthly/
```

```text
PostgreSQL
    │
    ▼
monthly_report data + metrics
    │
    ├──▶ Accomplishments summarizer (optional AI)
    │
    ▼
Deck builder (cover → accomplishments → delivery → close)
    │
    ▼
HEB_Monthly_Cadence_YYYY-MM-DD.pptx
```

### Main MSR components

| Component | What it does |
|-----------|--------------|
| `scripts/generate_monthly_report.py` | Main “run the monthly report” command |
| `monthly_report/data.py` | Finds projects and sprints in the period |
| `monthly_report/track_filter.py` | Matches `--track-name` to projects |
| `monthly_report/metrics.py` | Builds sprint counts for Delivery Updates |
| `monthly_report/stories.py` | Loads stories used for accomplishments |
| `monthly_report/accomplishments_summarizer.py` | AI write-up for Accomplishments slides |
| `monthly_report/cover_slide.py` | Fills cover placeholders |
| `monthly_report/delivery_slide.py` | Fills sprint tables / charts |
| `monthly_report/deck.py` | Assembles the full monthly deck |

### Typical command

```powershell
python scripts/generate_monthly_report.py --start-date 2026-10-01 --end-date 2026-10-31 --track-name COST
```

Useful options:

- `--track-name` — required to build a deck; repeat or comma-separate for multiple tracks
- `--dry-run` — print sprint metrics only; do not write a PowerPoint
- `--no-accomplishments` — skip AI accomplishments slides

### MSR features in brief

- Period-based reporting (explicit start/end, or legacy calendar month from meeting date)
- Track / project filtering
- Sprint metrics tables and delivery status visuals
- Optional AI accomplishments narrative
- Token-based filling so template formatting is preserved
- Dry-run mode for a quick data check before generating the file

---

## Side-by-side: WSR vs MSR

| | WSR (Weekly) | MSR (Monthly) |
|--|--------------|---------------|
| **Purpose** | Weekly delivery narrative | Monthly cadence / metrics view |
| **Input** | Same DB stories + sprints | Same DB stories + sprints |
| **Selection** | Date window; projects with content | Date window + required track name(s) |
| **Slide focus** | Highlights + Key Activities | Accomplishments + Delivery metrics |
| **Code home** | `app/` + WSR engine | `monthly_report/` |
| **Template** | `templates/` WSR G10X | `templates/monthly/` |
| **Main script** | `generate_ppt_content.py` | `generate_monthly_report.py` |
| **Extra quality tools** | Format eval + vision correction | (not the same WSR eval loop) |

---

## Optional quality tools (mainly WSR)

After a weekly deck is built, you can:

1. **Evaluate** — read-only check against spacing / layout rules  
   `python scripts/evaluate_ppt_format.py --ppt output/HEB_Delivery_Status.pptx --mode deterministic`

2. **Correct** — inspect and adjust layout with geometry + vision  
   `python scripts/run_hybrid_validation_loop.py --ppt output/HEB_Delivery_Status.pptx`

These are separate from the default “build the deck” path.

---

## Mental model for a new reader

1. **Import once** (or refresh) Jira/Rovo data into PostgreSQL.
2. **WSR** answers: “What happened this week across services?” → narrative bullets on delivery slides.
3. **MSR** answers: “How did this track look for the month?” → cover + accomplishments + sprint metrics.
4. Both are **template-driven**: the design lives in PowerPoint masters; the code fills the content.
5. AI is optional polish (titles, accomplishments, visual review), not required for the basic data → deck path.

For setup commands, environment variables, and troubleshooting, see the root [README.md](../README.md).
