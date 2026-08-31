-- App auto-creates projects without team_id; allow NULL until teams are wired in code.
ALTER TABLE projects ALTER COLUMN team_id DROP NOT NULL;
