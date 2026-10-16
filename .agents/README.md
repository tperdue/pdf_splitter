# .agents Workspace Profile

This directory is the workspace-level `.agents` profile for a new Python project.
It is intentionally small, vendor-neutral, and safe to commit on day zero.

The profile provides:

- Project instructions in `agents.md`
- A general system prompt in `system-prompt.md`
- Empty, explicit JSON config files for MCP servers, model presets, settings, and UI layout
- Reusable Python skills under `skills/`
- General-purpose agent profiles under `agents/`
- A disabled recurring health-check task under `tasks/`
- A baseline memory describing the starting architecture assumptions under `memories/`

Do not store secrets, personal tokens, machine-specific paths, or live credentials in this folder.
Project-specific decisions should be added only after they are true for the project.
