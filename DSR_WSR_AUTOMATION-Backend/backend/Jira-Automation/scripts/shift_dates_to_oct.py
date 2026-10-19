"""
Demo date-shift script
======================
Shifts story & sprint dates from Jun/Jul/Aug 2026 → Sep/Oct 2026
so the WSR demo shows current-period data.

Mapping applied:
  2026-06-xx  →  2026-09-xx  (snap_date, story dates)
  2026-07-xx  →  2026-10-xx  (snap_date, story dates, sprint dates)
  2026-08-xx  →  2026-10-xx  (snap_date, story dates, sprint dates)
  2026-05-xx  →  2026-09-xx  (story dates only — created/updated/resolved)
  2026-03-xx  →  2026-09-xx  (story dates only)
  2026-04-xx  →  2026-09-xx  (story dates only)

Run with:
  $env:PYTHONPATH = "."; python scripts/shift_dates_to_oct.py
"""

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Helper: shift one date column in one table using a CASE expression
def shift_date_col(table, col):
    db.execute(text(f"""
        UPDATE {table}
        SET {col} =
          CASE
            WHEN DATE_TRUNC('month', {col}) = '2026-03-01'::date THEN {col} + INTERVAL '6 months'
            WHEN DATE_TRUNC('month', {col}) = '2026-04-01'::date THEN {col} + INTERVAL '5 months'
            WHEN DATE_TRUNC('month', {col}) = '2026-05-01'::date THEN {col} + INTERVAL '4 months'
            WHEN DATE_TRUNC('month', {col}) = '2026-06-01'::date THEN {col} + INTERVAL '3 months'
            WHEN DATE_TRUNC('month', {col}) = '2026-07-01'::date THEN {col} + INTERVAL '3 months'
            WHEN DATE_TRUNC('month', {col}) = '2026-08-01'::date THEN {col} + INTERVAL '2 months'
            ELSE {col}
          END
        WHERE DATE_TRUNC('month', {col}) IN (
            '2026-03-01'::date,
            '2026-04-01'::date,
            '2026-05-01'::date,
            '2026-06-01'::date,
            '2026-07-01'::date,
            '2026-08-01'::date
        )
    """))
    print(f"  shifted {table}.{col}")

print("=== Shifting jira_stories dates ===")
for col in ('snapshot_date', 'created_date', 'updated_date', 'resolved_date'):
    shift_date_col('jira_stories', col)

print()
print("=== Shifting sprints dates ===")
for col in ('sprint_start_date', 'sprint_end_date'):
    shift_date_col('sprints', col)

db.commit()
print()
print("=== Done! Verifying new distribution ===")

dist = db.execute(text("""
    SELECT DATE_TRUNC('month', snapshot_date)::date AS month, COUNT(*) AS cnt
    FROM jira_stories
    GROUP BY 1
    ORDER BY 1
"""))
print("snapshot_date distribution:")
for row in dist:
    print(f"  {row[0]}  -> {row[1]} rows")

sprint_dist = db.execute(text("""
    SELECT DATE_TRUNC('month', sprint_start_date)::date AS month, COUNT(*) AS cnt
    FROM sprints
    GROUP BY 1
    ORDER BY 1
"""))
print()
print("sprint_start_date distribution:")
for row in sprint_dist:
    print(f"  {row[0]}  -> {row[1]} rows")

db.close()
print()
print("All done!")
