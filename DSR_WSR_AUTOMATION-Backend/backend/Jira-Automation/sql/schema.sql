-- Reference schema (managed by Alembic migrations)
-- Run: alembic upgrade head

CREATE TABLE IF NOT EXISTS projects (
    project_id      SERIAL        PRIMARY KEY,
    project_key     VARCHAR(50)   NOT NULL UNIQUE,
    project_name    VARCHAR(200)  NOT NULL,
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_projects_project_key ON projects (project_key);

CREATE TABLE IF NOT EXISTS sprints (
    sprint_id           SERIAL        PRIMARY KEY,
    project_id          INTEGER       NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE,
    sprint_name         VARCHAR(200)  NOT NULL,
    sprint_status       VARCHAR(50)   NOT NULL DEFAULT 'inprogress',
    sprint_start_date   DATE,
    sprint_end_date     DATE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sprints_project_name UNIQUE (project_id, sprint_name)
);

CREATE INDEX IF NOT EXISTS ix_sprints_sprint_name ON sprints (sprint_name);
CREATE INDEX IF NOT EXISTS ix_sprints_sprint_status ON sprints (sprint_status);

CREATE TABLE IF NOT EXISTS jira_stories (
    jira_key            VARCHAR(50)   PRIMARY KEY,
    project_id          INTEGER       NOT NULL REFERENCES projects (project_id) ON DELETE RESTRICT,
    sprint_id           INTEGER       REFERENCES sprints (sprint_id) ON DELETE SET NULL,
    title               VARCHAR(500),
    summary             VARCHAR(500)  NOT NULL,
    description         TEXT,
    story_points        NUMERIC(5, 2),
    status              VARCHAR(100)  NOT NULL,
    assignee            VARCHAR(200),
    reporter            VARCHAR(200),
    issue_type          VARCHAR(100),
    priority            VARCHAR(50),
    completion          NUMERIC(5, 2),
    created_date        DATE,
    updated_date        DATE,
    resolved_date       DATE,
    comment             TEXT,
    snapshot_date       DATE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_jira_stories_project_id ON jira_stories (project_id);
CREATE INDEX IF NOT EXISTS ix_jira_stories_sprint_id  ON jira_stories (sprint_id);
CREATE INDEX IF NOT EXISTS ix_jira_stories_assignee   ON jira_stories (assignee);
CREATE INDEX IF NOT EXISTS ix_jira_stories_status     ON jira_stories (status);

COMMENT ON TABLE projects IS 'Lookup table: one row per Jira project_key';
COMMENT ON TABLE sprints IS 'Lookup table: one row per unique sprint name';
COMMENT ON TABLE jira_stories IS 'Jira story details from Rovo AI for DSR/WSR reporting';

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

COMMENT ON TABLE employees IS 'People working under a team/account';
COMMENT ON TABLE employee_tracks IS 'Maps employees to tracks (projects) with active/inactive flag';

CREATE OR REPLACE VIEW employee_assignments AS
SELECT
    e.employee_id,
    e.employee_name,
    e.team_id,
    t.team_name,
    et.project_id,
    et.project_id AS track_id,
    p.project_key,
    p.project_name,
    et.is_active,
    et.employee_track_id,
    et.created_at,
    et.updated_at
FROM employees e
JOIN teams t ON t.team_id = e.team_id
JOIN employee_tracks et ON et.employee_id = e.employee_id
JOIN projects p ON p.project_id = et.project_id;

COMMENT ON VIEW employee_assignments IS
    'Readable join of employees + tracks + active flag (use this in pgAdmin)';
