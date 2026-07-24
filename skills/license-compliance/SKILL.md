---
name: license-compliance
description: Check the license before copying or vendoring third-party code, preserve required notices and attribution, and flag copyleft or unknown licenses before they enter the codebase. Use when copying code from other projects, adding dependencies, vendoring files, or maintaining attribution documents; do not use as legal advice beyond flagging conflicts for review.
license: MIT
---

# License Compliance

Code without a compatible license is code you cannot ship.

## Rules

- Identify the license before copying, vendoring, or adapting third-party code; no license means no permission, and such code stays out.
- Preserve copyright headers, license files, and notice content the license requires; vendored code keeps its license text beside it.
- Flag copyleft licenses such as GPL, AGPL, and SSPL before they enter a proprietary or differently licensed codebase, and leave the adoption decision to the owner.
- Confirm a new dependency's license is compatible with the project's declared license before adding it.
- Keep attribution documents accurate when dependencies change.
- Snippets taken from documentation, answers, or examples follow the same rules as any other third-party code.

## Boundaries

- Flag and describe conflicts; final licensing judgments belong to the project owner or counsel.
- Never strip license headers, even during cleanups that remove other comments.
