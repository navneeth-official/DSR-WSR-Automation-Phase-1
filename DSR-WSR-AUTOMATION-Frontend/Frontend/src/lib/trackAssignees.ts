export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function formatActivityDatePhrase(
  start: string,
  end: string,
): { preposition: "on" | "between"; phrase: string } {
  if (start && end && start === end) {
    return { preposition: "on", phrase: start };
  }
  return { preposition: "between", phrase: `${start} and ${end}` };
}

export function buildRovoRequestText(params: {
  assignees: string[];
  activityStart: string;
  activityEnd: string;
  snapshotDate: string;
}): string {
  const names = params.assignees.filter((a) => a.trim());
  const assigneeLines =
    names.length > 0
      ? names.map((n) => `* ${n}`).join("\n")
      : "* (select assignees above)";
  const activity = formatActivityDatePhrase(params.activityStart, params.activityEnd);

  return `Retrieve all Jira issues assigned to:

${assigneeLines}

Include issues where any of the following occurred ${activity.preposition} ${activity.phrase}:

* Issue created
* Issue updated
* Status transitioned
* Assignee changed
* Sprint changed
* Issue resolved

For each issue return the following fields exactly as shown:

\`\`\`json
{
  "project_key": "",
  "project_name": "",
  "sprint_name": "",
  "sprint_start_date": "",
  "sprint_end_date": "",
  "jira_key": "",
  "summary": "",
  "description": "",
  "issue_type": "",
  "priority": "",
  "assignee": "",
  "reporter": "",
  "status": "",
  "story_points": 0,
  "created_date": "",
  "updated_date": "",
  "resolved_date": "",
  "snapshot_date": ""
}
\`\`\`

Rules:

1. Return one JSON object per Jira issue.
2. Include active and closed sprint information when available.
3. Include completed and incomplete issues.
4. Use null for unavailable values.
5. Set snapshot_date to today's date.
6. Return only issues modified ${activity.preposition} ${activity.phrase}.
7. Output must be valid JSON.`;
}
