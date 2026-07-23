---
name: simplify-code
description: Simplify recently changed or user-selected code while preserving observable behavior, public APIs, tests, and required safeguards. Use when asked to simplify, clean up, refactor for clarity, reduce nesting, remove duplication, or review an implementation for unnecessary complexity.
license: MIT
---

# Simplify code

1. Read the target code, nearby tests, and repository guidance before editing.
2. Preserve observable behavior, public interfaces, error handling, security boundaries, and required compatibility unless the user explicitly requests a change.
3. Prefer direct control flow, clear names, existing abstractions, and fewer moving parts.
4. Remove dead code, redundant wrappers, needless indirection, duplicate branches, and comments that only restate the code.
5. Keep comments only for non-obvious intent, constraints, invariants, workarounds, or tradeoffs. Write them in a short, neutral voice without process narration.
6. Avoid broad rewrites, speculative abstractions, dependency changes, and unrelated formatting.
7. Run focused tests or checks that demonstrate behavior was preserved. Report any unverified area plainly.
