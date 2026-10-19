from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Check sprint columns
cols = db.execute(text("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'sprints' AND table_schema = 'public'
    ORDER BY ordinal_position
"""))
print("Sprint columns:")
for row in cols:
    print(f"  {row[0]:30s}  {row[1]}")

print()
sprints = db.execute(text("SELECT * FROM sprints ORDER BY sprint_id LIMIT 10"))
print("Sprints sample:")
for row in sprints:
    print(f"  {row}")

print()
# Distribution of story dates by field
for field in ('created_date', 'updated_date', 'resolved_date'):
    dist = db.execute(text(f"""
        SELECT DATE_TRUNC('month', {field})::date AS month, COUNT(*) AS cnt
        FROM jira_stories
        WHERE {field} IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """))
    print(f"{field} distribution:")
    for row in dist:
        print(f"  {row[0]}  -> {row[1]} rows")
    print()

db.close()
