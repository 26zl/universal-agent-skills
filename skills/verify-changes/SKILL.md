---
name: verify-changes
description: Verify code or configuration changes with focused tests, static checks, and diff inspection before reporting completion. Use after implementing or modifying a repository; do not use for read-only explanations or when no files changed.
license: MIT
---

# Verify Changes

Verify the actual change at the narrowest useful scope, then expand checks in proportion to risk.

## Workflow

1. Inspect the final diff and list the behaviors that changed.
2. Identify the repository's documented validation commands before inventing new ones.
3. Run the smallest focused test that exercises each changed behavior.
4. Run the relevant formatter, linter, type checker, build, or broader test suite when the change can affect adjacent code.
5. Inspect generated files and user-visible output when automated assertions cannot cover layout or behavior.
6. Re-read the diff for accidental edits, debug output, secrets, stale comments, and missing tests.
7. Report which checks ran, their outcomes, and any check that could not run.

## Rules

- Do not claim success without fresh evidence from the current working tree.
- Do not hide failing checks because they appear unrelated. Distinguish pre-existing failures only when evidence supports that conclusion.
- Do not broaden the change merely to make unrelated checks pass.
- Never expose credentials or sensitive output in logs or the final report.
- Treat skipped checks as residual risk, not as passing checks.

## Completion evidence

Provide a concise summary containing:

- focused checks and their results;
- broader checks and their results, when applicable;
- manual inspection performed, when applicable;
- remaining limitations or unverified behavior.
