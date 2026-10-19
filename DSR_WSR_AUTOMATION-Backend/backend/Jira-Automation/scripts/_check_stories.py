from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Check columns in jira_stories
cols = db.execute(text("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'jira_stories' AND table_schema = 'public'
    ORDER BY ordinal_position
"""))
print("Columns:")
for row in cols:
    print(f"  {row[0]:30s}  {row[1]}")

print()

# Date distribution
dist = db.execute(text("""
    SELECT
        DATE_TRUNC('month', snapshot_date)::date AS month,
        COUNT(*) AS cnt
    FROM jira_stories
    GROUP BY 1
    ORDER BY 1
"""))
print("Snapshot date distribution:")
for row in dist:
    print(f"  {row[0]}  -> {row[1]} rows")

db.close()
