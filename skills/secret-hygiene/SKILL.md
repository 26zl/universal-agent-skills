---
name: secret-hygiene
description: Never write, echo, or commit secret values such as API keys, tokens, passwords, or private keys; reference them through environment variables or a secret manager, and report discovered secrets without reproducing the value. Use when writing code, tests, configuration, documentation, logs, or shell commands that touch credentials; do not use to weaken cryptographic material handling that the product itself must perform.
license: MIT
---

# Secret Hygiene

A secret that enters code, output, or history must be treated as leaked.

## Rules

- Never hardcode API keys, tokens, passwords, connection strings, or private keys in code, tests, fixtures, configuration, or documentation examples; reference environment variables or the project's secret manager and document the variable name only.
- Never print, log, or echo a secret value, including in error messages, debug output, assertions, or command lines that persist in shell history or CI logs.
- Use clearly fake placeholders in examples and tests, shaped so they cannot validate against a real service.
- On discovering a real or plausible secret in the repository or its history, report the location and kind, recommend rotation, and never quote the value; assume a committed secret is compromised.
- Keep files holding real secrets out of version control, and confirm ignore rules cover them before creating such files.
- Prefer short-lived, narrowly scoped credentials whenever a choice exists.

## Boundaries

- Do not delete or rewrite committed secrets unprompted; rotation and history cleanup are decisions for the owner.
- Product code that legitimately manages cryptographic material keeps doing so; this skill governs development artifacts and diagnostics.
