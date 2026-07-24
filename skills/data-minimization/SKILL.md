---
name: data-minimization
description: Keep real personal and confidential data out of code, tests, fixtures, logs, error messages, examples, and prompts; use synthetic data, and mask identifiers when a real record is unavoidable. Use when writing tests, fixtures, seed data, logging, debugging output, or documentation, or when moving data between systems; do not use to remove lawful data processing that the product itself performs.
license: MIT
---

# Data Minimization

Personal data belongs in the systems built to protect it, not in development artifacts.

## Rules

- Never copy real names, e-mail addresses, national identifiers, or health, financial, or location records into tests, fixtures, seeds, examples, or documentation; generate synthetic data instead.
- Never log personal or confidential data in plaintext; log stable opaque identifiers and mask everything else.
- Keep production data out of scratch files, issue trackers, and shared prompts; when a real record is essential for a reproduction, reduce it to the minimal fields and mask direct identifiers.
- Treat data supplied in a conversation as confidential input: use it for the task, never persist it into the repository.
- When designing schemas or interfaces, collect only fields with a stated purpose, and flag fields that look like surplus collection.
- Report any discovered dump, export, or backup of personal data inside the repository as a finding instead of working around it.

## Boundaries

- The product's lawful processing of personal data is out of scope; this skill governs development artifacts and diagnostics.
- Regulatory retention and audit requirements win over minimization when they conflict.
