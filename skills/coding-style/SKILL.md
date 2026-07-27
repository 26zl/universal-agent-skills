---
name: coding-style
description: Keep code comments and docstrings concise, neutral, human-authored in tone, and written in English unless another language is required. Use when writing, refactoring, or reviewing code where comments, identifiers, or docstrings may be added or changed; do not use to shorten required public API documentation, safety notes, or legal notices.
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
- Do not narrate the change itself: no before/after wording, "previously," "now," "used to," or "fixed" — state the current invariant, not the diff that produced it.
- Do not add tutorial paragraphs throughout implementation code.
- Delete stale, redundant, speculative, or copied comments when touching nearby code.
- Preserve required API documentation, public contracts, safety warnings, citations, and legal notices.
- Match the repository's established documentation convention when it is stricter than this skill.

## Language

- Write code in English: identifiers, comments, docstrings, commit messages, and test names.
- Keep English even when the conversation, issue, or specification is in another language.
- Switch only when the user asks for another language, or when the repository already uses one consistently.
- Never mix languages inside one identifier or one comment.
- Keep user-facing strings, translations, and localized content in whatever language the product requires.

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

State the current invariant, not the change that produced it:

```py
# Built-in marketplaces (openai-*) are listed without a source.
if name not in managed:
    continue
```

Avoid narrating the fix history:

```py
# Before the fix this raised "inventory malformed"; now the built-in is skipped.
if name not in managed:
    continue
```

## Review

Before finishing, inspect new and edited comments. Shorten or remove any comment that sounds conversational, narrates the implementation, repeats the code, describes the change history, or reveals use of an AI assistant. Rewrite any identifier or comment left in the conversation's language instead of the repository's.
