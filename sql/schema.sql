-- Reference schema (managed by Alembic migrations)
-- Run: alembic upgrade head

CREATE TABLE IF NOT EXISTS projects (
    project_id      SERIAL        PRIMARY KEY,
    project_key     VARCHAR(50)   NOT NULL UNIQUE,
    project_name    VARCHAR(200)  NOT NULL,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_projects_project_key ON projects (project_key);

CREATE TABLE IF NOT EXISTS story_statuses (
    status_id       SERIAL        PRIMARY KEY,
    status_name     VARCHAR(100)  NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS ix_story_statuses_status_name ON story_statuses (status_name);

CREATE TABLE IF NOT EXISTS sprints (
    sprint_id           SERIAL        PRIMARY KEY,
    sprint_name         VARCHAR(200)  NOT NULL UNIQUE,
    sprint_status       VARCHAR(50)   NOT NULL DEFAULT 'inprogress',
    sprint_start_date   DATE,
    sprint_end_date     DATE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
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
    status_id           INTEGER       NOT NULL REFERENCES story_statuses (status_id) ON DELETE RESTRICT,
    assignee            VARCHAR(200),
    reporter            VARCHAR(200),
    issue_type          VARCHAR(100),
    priority            VARCHAR(50),
    completion          NUMERIC(5, 2),
    created_date        DATE,
    updated_date        DATE,
    resolved_date       DATE,
    snapshot_date       DATE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_jira_stories_project_id ON jira_stories (project_id);
CREATE INDEX IF NOT EXISTS ix_jira_stories_sprint_id  ON jira_stories (sprint_id);
CREATE INDEX IF NOT EXISTS ix_jira_stories_assignee   ON jira_stories (assignee);
CREATE INDEX IF NOT EXISTS ix_jira_stories_status_id  ON jira_stories (status_id);

COMMENT ON TABLE projects IS 'Lookup table: one row per Jira project_key';
COMMENT ON TABLE sprints IS 'Lookup table: one row per unique sprint name';
COMMENT ON TABLE jira_stories IS 'Jira story details from Rovo AI for DSR/WSR reporting';
