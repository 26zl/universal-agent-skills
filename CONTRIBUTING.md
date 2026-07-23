# Contributing

Contributions should keep the canonical skill format portable and the installation path safe.

## Add or change a skill

1. Create or edit `skills/<name>/SKILL.md`.
2. Keep `name` identical to the directory name and use lowercase kebab-case.
3. Put both capability and trigger conditions in `description`.
4. Keep the body imperative, focused, and below 500 lines.
5. Add `scripts/`, `references/`, or `assets/` only when the skill uses them.
6. Avoid product-only frontmatter in canonical skills. Put UI metadata under `agents/`.
7. Apply the `coding-style` guidance to bundled code.

Do not add a README, changelog, or installation guide inside an individual skill. Repository-level documentation belongs at the repository root or under `docs/`.

## Validate locally

```bash
python3 scripts/validate.py
python3 scripts/test_sync_agent_stack.py
python3 scripts/test_sync_instructions.py
python3 scripts/test_sync_opencode_config.py
sh -n install.sh bootstrap.sh scripts/test-install.sh
./scripts/test-install.sh
```

If Python 3.11 or newer and the validation dependency are available:

```bash
python3 -m pip install -r requirements-validation.txt
for skill in skills/*; do agentskills validate "$skill"; done
```

On Windows:

```powershell
.\scripts\test-install.ps1
```

## Installer changes

- Keep POSIX and PowerShell behavior aligned.
- Preserve idempotence.
- Never delete an unmanaged target.
- Treat `--force` as backup-and-replace, not delete-and-replace.
- Ensure dry-run performs no writes.
- Add or update tests for install, repeated install, conflict, copy, link, and uninstall behavior.

## Plugin changes

The repository root is a dual Claude Code and Codex plugin. Keep both manifests pointed at `./skills/`. Bump the plugin version for a release that changes installed behavior.

## Agent stack profile changes

- Keep third-party code outside this repository.
- Pin portable skill sources to a full 40-character Git commit.
- Use exact package-manager versions in the profile.
- Mark plugins that persist conversations, invoke browsers, access networks, or run hooks with an appropriate risk level.
- Require explicit opt-in for session capture or similarly sensitive behavior.
- Update `docs/plugin-stack.md` when the desired inventory or risk model changes.

## Security review

Automated scans are required but not sufficient. Review new instructions for prompt injection, hidden data access, excessive permissions, external downloads, destructive commands, and untrusted code execution. Review bundled scripts as executable supply-chain artifacts.

Do not weaken a scanner threshold solely to make CI pass. Document and narrowly suppress a verified false positive when necessary.
