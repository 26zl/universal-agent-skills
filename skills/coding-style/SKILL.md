---
name: coding-style
description: Keep code comments and docstrings concise, neutral, and human-authored in tone. Use when writing, refactoring, or reviewing code where comments may be added or changed; do not use to shorten required public API documentation, safety notes, or legal notices.
license: MIT
---

# Coding Style

Write code that explains itself through names, structure, and small functions. Treat comments as a last-mile explanation for information the code cannot express clearly.

## Comment rules

- Add a comment only for non-obvious intent, invariants, constraints, workarounds, security boundaries, or surprising tradeoffs.
- Keep comments short, factual, and neutral. Prefer one sentence or a compact phrase.
- Explain why a surprising choice is necessary. Do not narrate what an obvious line already does.
- Avoid first-person or conversational phrasing such as “I added,” “we need,” “here we,” or “this is where.”
- Avoid commentary about the editing process, the prompt, the agent, or who generated the code.
- Do not add tutorial paragraphs throughout implementation code.
- Delete stale, redundant, speculative, or copied comments when touching nearby code.
- Preserve required API documentation, public contracts, safety warnings, citations, and legal notices.
- Match the repository's established documentation convention when it is stricter than this skill.

## Examples

Prefer:

```ts
// Keep the old key for clients that cache signed URLs.
const cacheKey = previousKey ?? currentKey;
```

Avoid:

```ts
// Here we use the previous key because I want to make sure that clients that
// may have cached a signed URL do not suddenly stop working after this change.
const cacheKey = previousKey ?? currentKey;
```

Omit comments that only restate the code:

```ts
retryCount += 1;
```

## Review

Before finishing, inspect new and edited comments. Shorten or remove any comment that sounds conversational, narrates the implementation, repeats the code, or reveals use of an AI assistant.
