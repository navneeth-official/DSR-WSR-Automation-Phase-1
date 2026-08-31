-- Optional reference rows for HEB DSR/WSR projects.
-- Run AFTER: alembic upgrade head
-- Safe to re-run: uses project_key ON CONFLICT DO UPDATE.

INSERT INTO projects (project_key, project_name) VALUES
    ('LOC',  'LOCO'),
    ('COST', 'Cost Core Service'),
    ('GSS',  'GSS'),
    ('WNF',  'Wentforth'),
    ('PHRM', 'Pharamacy'),
    ('SUP',  'Supplier QA'),
    ('SPUR', 'SPUR'),
    ('PRC',  'Pricing')
ON CONFLICT (project_key) DO UPDATE
    SET project_name = EXCLUDED.project_name;

-- Sprint names come from Rovo per project. Examples of real sprint name formats:
--   Nacogdoches - 248
--   Q2.13FY26 Eridanus
--   Q2.14 FY26 Fornax
--
-- Sprints are created automatically on import via seed_from_rovo.py
-- (one sprint_id per unique sprint_name).

INSERT INTO teams (team_name) VALUES
    ('HEB'),
    ('Trader Joe'),
    ('IVC'),
    ('TFG'),
    ('Underarmour')
ON CONFLICT (team_name) DO NOTHING;

-- Optional employee seed for HEB (safe to re-run).
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
  );

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
    SET is_active = EXCLUDED.is_active;
