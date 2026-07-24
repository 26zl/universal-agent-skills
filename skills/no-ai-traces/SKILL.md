---
name: no-ai-traces
description: Keep delivered work free of AI self-reference, with no Co-Authored-By trailers or generated-with footers in commits and pull requests, and no comments, documentation, or changelog entries that narrate AI involvement, prompts, or the editing session. Use when writing commits, merge or squash messages, pull requests, release notes, changelogs, code comments, or documentation; do not use to bypass a policy that explicitly requires AI disclosure.
license: MIT
---

# No AI Traces

Delivered work records the accountable human author and describes the change, never the tool or session that produced it.

## Rules

- Never add a Co-Authored-By, Signed-off-by, or similar trailer naming an AI assistant, agent, model, or tool.
- Never append generated-with footers, robot signatures, tool names, or promotional links to commit messages, merge or squash messages, pull request titles or bodies, changelogs, or release notes.
- Never write code comments, docstrings, documentation, or ticket updates that narrate prompts, AI involvement, the editing session (including before/after or fix-history narration such as "previously… now…"), or a conversation with an assistant.
- Never change the configured Git author or committer identity.
- Preserve trailers and attribution that credit humans; only machine self-reference is removed or withheld.
- Do not introduce new attribution or narration while amending, rebasing, squashing, or rewording existing content.
- Keep AI mentions that are part of the product itself, its documented subject matter, or required third-party notices.

## Boundaries

- An explicit user, repository, or organizational requirement to disclose AI use wins; disclose in the mandated form instead of applying this skill.
- Never remove attribution or sign-off lines that a policy, license, or developer certificate of origin requires.
- This skill governs text about tooling only; it never hides which changes were made or misrepresents review status.
