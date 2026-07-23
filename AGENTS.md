# Repository guidance

- Keep canonical skills under `skills/<name>/SKILL.md`; do not maintain divergent agent-specific copies.
- Keep installer behavior idempotent and refuse unmanaged conflicts unless `--force` is explicit.
- Prefer self-explanatory code. Add comments only for non-obvious intent, invariants, constraints, workarounds, security boundaries, or surprising tradeoffs.
- Keep comments factual, neutral, and normally one sentence. Never narrate prompts, AI use, the user-agent collaboration, debugging history, or obvious code behavior.
- Keep external stack reconciliation dry-run by default, preserve unlisted plugins, and require explicit opt-in for persistent session capture.
- Run `python3 scripts/validate.py`, `python3 scripts/test_sync_agent_stack.py`, `python3 scripts/test_sync_instructions.py`, `python3 scripts/test_sync_opencode_config.py`, `python3 scripts/test_check_pin_freshness.py`, and the installer tests after relevant changes.
- Update both POSIX and PowerShell implementations when changing installer behavior.
