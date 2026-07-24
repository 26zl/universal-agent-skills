---
name: supply-chain-pinning
description: Add dependencies deliberately by justifying each new one, pinning versions or commits, respecting lockfiles, and never executing unpinned remote code. Use when adding or updating packages, container images, GitHub Actions, install scripts, or vendored code; do not use to block upgrades the user explicitly requested.
license: MIT
---

# Supply Chain Pinning

Every dependency is code you now ship; adopt it deliberately or not at all.

## Rules

- Before adding a dependency, state what it is needed for and why the standard library or an existing dependency does not cover it.
- Pin what you adopt: exact versions in manifests where the ecosystem supports it, full commit hashes for Git sources and GitHub Actions, digests for container images.
- Never pipe remote scripts into a shell and never fetch install code from a mutable reference; when a script install is unavoidable, download, review, and execute it from disk.
- Respect lockfiles: change them through the ecosystem's own tool, never by hand, and never delete one to make an install pass.
- Read what changed before adopting an update; a major version bump or a maintainer change is a review event, not a routine edit.
- Prefer maintained dependencies with compatible licenses over unmaintained or trivially replaceable packages.

## Boundaries

- Explicitly requested upgrades proceed; this skill shapes how they happen, not whether.
- Ecosystems without real pinning support get the strictest available constraint plus a note about the residual risk.
