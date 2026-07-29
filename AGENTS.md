# Repository guidance

- Keep canonical skills under `skills/<name>/SKILL.md`; do not maintain divergent agent-specific copies.
- Keep installer behavior idempotent and refuse unmanaged conflicts unless `--force` is explicit.
- Prefer self-explanatory code. Add comments only for non-obvious intent, invariants, constraints, workarounds, security boundaries, or surprising tradeoffs.
- Keep comments factual, neutral, and normally one sentence. Never narrate prompts, AI use, the user-agent collaboration, debugging history, or obvious code behavior.
- Keep external stack reconciliation dry-run by default, preserve unlisted plugins, and require explicit opt-in for persistent session capture.
- Keep the `hooks/guard.py` rules high-precision; a false positive that blocks ordinary work gets the whole hook disabled.
- Keep guard rules in `hooks/guard.py` only; `hooks/opencode-guard.js` maps OpenCode tool names onto the same payload and must not reimplement a rule.
- Quote a guard violation in docs or tests with a `uas-allow` comment on its own line directly above it, never by splitting the literal into concatenated fragments.
- Keep the guard's shell wrapper as `guard || exit 0; interpreter script`; the `&& … || exit 0` form turns the blocking exit code 2 into 0 and silently disables every rule.
- Run `python3 scripts/validate.py`, `python3 scripts/test_sync_agent_stack.py`, `python3 scripts/test_sync_instructions.py`, `python3 scripts/test_sync_opencode_config.py`, `python3 scripts/test_check_pin_freshness.py`, `python3 scripts/test_hooks.py`, and the installer tests after relevant changes.
- Update both POSIX and PowerShell implementations when changing installer behavior.
