-- Teams, employees, and employee-to-track assignments.
-- Run after projects exist. Safe to re-run (uses IF NOT EXISTS / ON CONFLICT).

CREATE TABLE IF NOT EXISTS teams (
    team_id         SERIAL        PRIMARY KEY,
    team_name       VARCHAR(100)  NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_teams_team_name ON teams (team_name);

CREATE TABLE IF NOT EXISTS employees (
    employee_id     SERIAL        PRIMARY KEY,
    employee_name   VARCHAR(200)  NOT NULL,
    team_id         INTEGER       NOT NULL REFERENCES teams (team_id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_employees_employee_name ON employees (employee_name);
CREATE INDEX IF NOT EXISTS ix_employees_team_id ON employees (team_id);

CREATE TABLE IF NOT EXISTS employee_tracks (
    employee_track_id SERIAL      PRIMARY KEY,
    employee_id       INTEGER     NOT NULL REFERENCES employees (employee_id) ON DELETE CASCADE,
    project_id        INTEGER     NOT NULL REFERENCES projects (project_id) ON DELETE RESTRICT,
    is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, project_id)
);

CREATE INDEX IF NOT EXISTS ix_employee_tracks_employee_id ON employee_tracks (employee_id);
CREATE INDEX IF NOT EXISTS ix_employee_tracks_project_id ON employee_tracks (project_id);
