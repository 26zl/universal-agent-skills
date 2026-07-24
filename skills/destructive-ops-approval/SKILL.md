---
name: destructive-ops-approval
description: Obtain explicit confirmation before irreversible or outward-facing operations such as force-pushes, history rewrites, mass deletion, data migrations, or production changes, and prefer the reversible alternative when one exists. Use when an action could destroy data, rewrite shared history, or change systems other people depend on; do not use to stall routine, easily reversible work.
license: MIT
---

# Destructive Ops Approval

Irreversible actions get a human decision first, every time.

## Rules

- Before force-pushing, rewriting shared history, deleting branches or tags others may use, mass-deleting files or records, dropping schemas, or changing production configuration, state the action, the blast radius, and the rollback plan, then wait for explicit approval.
- Approval covers one action in one context; it does not carry over to the next occasion or a wider scope.
- Prefer the reversible form when one exists: soft deletes, archives, expiring backups, feature flags, force-with-lease over force, dry run before apply.
- Take a verified backup or snapshot before an approved destructive step, and confirm the restore path works.
- Scope credentials and commands to the narrowest target that completes the task; never widen a destructive command to save a step.
- If the target's state does not match what the approval assumed, stop and re-confirm instead of proceeding.

## Boundaries

- Routine local, reversible operations need no ceremony.
- Organizational emergency procedures override this skill's pacing; follow them exactly.
