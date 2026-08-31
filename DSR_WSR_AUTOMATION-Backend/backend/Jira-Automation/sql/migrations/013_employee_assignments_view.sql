-- pgAdmin-friendly view of employee track assignments.
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
