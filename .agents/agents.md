---
kind: agents
---

# Project Guidelines

## Baseline

- Treat this repository as a day-zero Python project until the code proves otherwise.
- Prefer a `src/` layout for importable packages and a top-level `tests/` directory for tests.
- Keep the initial architecture shallow. Add subpackages only when there is a real domain boundary.
- Use clear module names in `snake_case`; avoid abbreviations that hide intent.
- Expose public package APIs deliberately with `__all__` when a module is meant for import by consumers.

## Build And Tooling

- Prefer `pyproject.toml` as the source of truth for package metadata and tool configuration.
- Use a local virtual environment for development.
- Keep runtime dependencies separate from development and test dependencies.
- Add commands to the project README as soon as they exist.
- When a command is missing, infer cautiously from `pyproject.toml`, lockfiles, and existing scripts before inventing one.

## Testing

- Add focused pytest tests for new behavior.
- Keep tests deterministic and independent of network access unless explicitly marked as integration tests.
- Prefer fixtures and factories over shared mutable test state.
- Run the narrowest useful test first, then broaden when touching shared code.

## Style And Maintenance

- Prefer typed, straightforward Python over clever dynamic behavior.
- Keep files cohesive and split them when unrelated reasons to change appear.
- Write comments only where they explain intent, tradeoffs, or non-obvious constraints.
- Preserve user changes in the working tree. Do not revert unrelated edits.

## Documentation

- Keep `README.md` current with setup, test, and run instructions once those workflows exist.
- Record durable architectural decisions in project docs or `.agents/memories/` after they become true.
- Avoid documenting speculative frameworks, services, databases, or deployment targets on day zero.
