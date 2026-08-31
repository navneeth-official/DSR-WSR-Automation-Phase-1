"""
Apply employees / employee_tracks migration without Alembic CLI or psql.

Usage (from backend/Jira-Automation):
    python scripts/apply_employees_migration.py
    python scripts/apply_employees_migration.py --seed-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import engine

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_012 = REPO_ROOT / "sql" / "migrations" / "012_add_employees.sql"
MIGRATION_013 = REPO_ROOT / "sql" / "migrations" / "013_employee_assignments_view.sql"

TEAM_SEED_SQL = """
INSERT INTO teams (team_name) VALUES
    ('HEB'),
    ('Trader Joe'),
    ('IVC'),
    ('TFG'),
    ('Underarmour')
ON CONFLICT (team_name) DO NOTHING
"""

EMPLOYEE_SEED_SQL = """
INSERT INTO employees (employee_name, team_id)
SELECT v.employee_name, t.team_id
FROM (
    VALUES
        ('Rishi'),
        ('Noble'),
        ('Vineed')
) AS v(employee_name)
CROSS JOIN teams t
WHERE t.team_name = 'HEB'
  AND NOT EXISTS (
      SELECT 1
      FROM employees e
      WHERE e.employee_name = v.employee_name
        AND e.team_id = t.team_id
  )
"""

EMPLOYEE_TRACKS_SEED_SQL = """
INSERT INTO employee_tracks (employee_id, project_id, is_active)
SELECT e.employee_id, p.project_id, v.is_active
FROM (
    VALUES
        ('Rishi',  'COST', TRUE),
        ('Noble',  'SUP',  TRUE),
        ('Noble',  'LOC',  FALSE),
        ('Vineed', 'SUP',  TRUE)
) AS v(employee_name, project_key, is_active)
JOIN employees e ON e.employee_name = v.employee_name
JOIN teams t ON t.team_id = e.team_id AND t.team_name = 'HEB'
JOIN projects p ON p.project_key = v.project_key
ON CONFLICT (employee_id, project_id) DO UPDATE
    SET is_active = EXCLUDED.is_active
"""


def _table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :name
                )
                """
            ),
            {"name": table_name},
        ).scalar()
    )


def _run_sql_file(conn, path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Migration file not found: {path}")
    sql = path.read_text(encoding="utf-8")
    # Strip line comments; execute as one script (PostgreSQL accepts multi-statement).
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    cleaned = "\n".join(lines).strip()
    if cleaned:
        conn.execute(text(cleaned))


def apply_schema(conn) -> None:
    if _table_exists(conn, "employees"):
        print("employees table already exists — skipping DDL.")
        return

    print("Applying 012_add_employees.sql …")
    _run_sql_file(conn, MIGRATION_012)
    print("Applying 013_employee_assignments_view.sql …")
    _run_sql_file(conn, MIGRATION_013)

    if _table_exists(conn, "alembic_version"):
        conn.execute(
            text(
                "UPDATE alembic_version SET version_num = '012_employee_assignments_view'"
            )
        )


def seed_reference_data(conn) -> None:
    print("Seeding teams …")
    conn.execute(text(TEAM_SEED_SQL))
    print("Seeding employees …")
    conn.execute(text(EMPLOYEE_SEED_SQL))
    print("Seeding employee_tracks …")
    conn.execute(text(EMPLOYEE_TRACKS_SEED_SQL))


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply employee tables migration via SQLAlchemy")
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Only run reference seed SQL (tables must already exist)",
    )
    args = parser.parse_args()

    with engine.begin() as conn:
        if not args.seed_only:
            apply_schema(conn)
        if not _table_exists(conn, "employees"):
            raise RuntimeError(
                "employees table still missing after migration. Check database connection in .env"
            )
        seed_reference_data(conn)

    print("Employee migration complete.")
    print("Next: python scripts/seed_employees.py  (optional extra seed)")


if __name__ == "__main__":
    main()
