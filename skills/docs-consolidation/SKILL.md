---
name: docs-consolidation
description: Keep project documentation in a small set of canonical files; extend an existing document instead of creating a new Markdown file, and merge overlapping documents rather than adding another. Use when writing, updating, or reorganizing documentation, or when a task would create a new .md file such as a summary, notes, plan, or per-feature guide; do not use to merge files a convention requires to stand alone, such as README, LICENSE, CHANGELOG, or generated references.
license: MIT
---

# Docs Consolidation

Every documentation topic gets one canonical home. A reader should find setup, usage, or design in one predictable place, not reconstruct it from a pile of overlapping Markdown files.

## Rules

- Before creating any documentation file, check whether the README or an existing document already covers the topic. Extend that document instead.
- Create a new file only when the user asks for one or the content serves a clearly distinct audience or lifecycle, such as an API reference next to a contributor guide.
- Never leave unrequested working files in the repository: summaries, notes, plans, implementation reports, and task lists belong in the conversation, not in `SUMMARY.md`, `NOTES.md`, `PLAN.md`, or similar files.
- Do not duplicate instructions across files. Link to the canonical section instead of restating it.
- When existing documents overlap, merge them into the canonical one, delete the leftovers, and update inbound links.
- Keep conventional standalone files as they are: README, LICENSE, CONTRIBUTING, CHANGELOG, SECURITY, CODE_OF_CONDUCT, and generated documentation.
- Match documentation size to the change: a small feature earns a section, not a document tree.

## Review

Before finishing, list every documentation file the change adds. Each one must be explicitly requested or justified by a distinct audience; fold anything else into an existing document and remove the extra file.
