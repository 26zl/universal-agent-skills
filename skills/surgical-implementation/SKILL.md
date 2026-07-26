---
name: surgical-implementation
description: Make the smallest justified code or configuration change, surface material assumptions, avoid unrelated cleanup, fix rather than silently skip defects found along the way, and define verifiable success criteria. Use when implementing features, fixes, refactors, or configuration changes in an existing repository; do not use for read-only analysis or broad rewrites the user explicitly requested.
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
- Do not fold an unrelated defect into the requested patch, and do not leave it unfixed either.
- Expand scope only when the requested behavior cannot be implemented safely without it; explain the dependency first.

## Defects found outside the request

A defect stays in scope even when it predates the task, came from another session, or sits in code nobody asked about. Silently skipping it is not allowed.

1. Name the defect, the evidence for it, and the risk of leaving it in place.
2. Fix it as its own change, kept out of the requested patch so both stay reviewable.
3. Ask first when the fix is destructive, outward-facing, or needs a materially different design.
4. Verify the fix on its own terms and report it separately from the requested work.

Style differences, unfamiliar patterns, and code that is merely improvable are not defects. A defect is behavior that is wrong, unsafe, or contradicts a documented contract.

## Completion evidence

- the success condition and focused checks performed;
- any necessary scope expansion and why it was unavoidable;
- any defect found outside the request, and whether it was fixed or is waiting for approval;
- remaining uncertainty or checks that could not run.
