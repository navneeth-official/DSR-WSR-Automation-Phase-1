-- Application users for signup/signin (password stored as bcrypt hash).
CREATE TABLE IF NOT EXISTS users (
    user_id         SERIAL        PRIMARY KEY,
    username        VARCHAR(100)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,
    team_id         INTEGER       NOT NULL REFERENCES teams (team_id) ON DELETE RESTRICT,
    is_pmo          BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_users_team_id ON users (team_id);

COMMENT ON TABLE users IS 'App login accounts; password_hash is bcrypt; team_id maps to teams';
