import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app.database import engine

with engine.connect() as c:
    for q, label in [
        ("SELECT j.jira_key, j.snapshot_date, s.status_name AS status, j.assignee FROM jira_stories j JOIN story_statuses s ON s.status_id = j.status_id WHERE j.jira_key LIKE '%990%' OR j.jira_key IN ('LOC-2812','COST-5502') ORDER BY j.jira_key, j.snapshot_date", "history rows"),
        ("SELECT sprint_id, sprint_name, project_id FROM sprints WHERE sprint_name ILIKE '%PRC%' OR sprint_name ILIKE '%SPUR%' ORDER BY sprint_id LIMIT 10", "sprints"),
        ("SELECT project_id, project_key FROM projects WHERE project_key IN ('PRC','SPUR','LOC','COST')", "projects"),
    ]:
        print(f"\n{label}:")
        for row in c.execute(text(q)):
            print(row)
