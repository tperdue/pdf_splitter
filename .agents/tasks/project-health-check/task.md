---
enabled: false
id: project-health-check
intervalMinutes: 1440
kind: task
name: Project Health Check
runOnStartup: false
---

Review the current Python project for day-zero hygiene:

- Confirm setup, test, lint, and run commands are documented when they exist.
- Check whether `pyproject.toml`, `src/`, `tests/`, and README content remain aligned.
- Report stale instructions, missing verification steps, or confusing structure.
- Stay quiet if there is no actionable change to report.
