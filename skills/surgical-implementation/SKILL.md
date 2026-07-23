---
name: surgical-implementation
description: Make the smallest justified code or configuration change, surface material assumptions, avoid unrelated cleanup, and define verifiable success criteria. Use when implementing features, fixes, refactors, or configuration changes in an existing repository; do not use for read-only analysis or broad rewrites the user explicitly requested.
license: MIT
---

# Surgical Implementation

Keep every changed line traceable to the requested outcome. Match the repository before introducing a new convention.

## Workflow

1. Read the relevant code, local instructions, and nearby tests before choosing an approach.
2. State only assumptions that could materially change the implementation. Ask when guessing would create meaningful risk.
3. Define a short success condition that can be checked after the change.
4. Choose the smallest design that satisfies the request and existing contracts.
5. Modify only the required files. Match local naming, structure, error handling, and style.
6. Remove imports or helpers made obsolete by this change. Leave pre-existing cleanup alone unless requested.
7. Run focused checks against the success condition, then inspect the final diff for unrelated edits.

## Guardrails

- Do not add speculative features, abstraction layers, configuration, or fallback behavior.
- Do not silently choose among materially different interpretations.
- Do not refactor adjacent code merely because it could be cleaner.
- Do not rewrite comments or formatting outside the changed behavior.
- Report unrelated defects separately instead of folding them into the patch.
- Expand scope only when the requested behavior cannot be implemented safely without it; explain the dependency first.

## Completion evidence

- the success condition and focused checks performed;
- any necessary scope expansion and why it was unavoidable;
- remaining uncertainty or checks that could not run.
