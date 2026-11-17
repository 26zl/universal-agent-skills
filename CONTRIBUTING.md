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
8. Add a new skill to `defaultPrompt` in `.codex-plugin/plugin.json`; validation fails while a skill is missing there. The exporter does this for generated skills.

## Skills generated from AI_prompts

The skills listed in `ai-prompts.lock` come from [AI_prompts](https://github.com/26zl/AI_prompts). Change them there, merge, and then run the export from an AI_prompts checkout at the merged commit:

```bash
scripts/export-skills.py <path-to-this-checkout>
```

The export rewrites those skills and their `defaultPrompt` lines in `.codex-plugin/plugin.json`, removes skills whose prompt was deleted, and records the commit and the generated skills in `ai-prompts.lock`. The `AI_prompts sync` workflow fails while the lock names uncommitted AI_prompts changes or the files differ from what that commit exports. The installers treat every skill that is not in the lock as a core skill.

Do not add a README, changelog, or installation guide inside an individual skill. Repository-level documentation belongs at the repository root or under `docs/`.

## Validate locally

```bash
python3 scripts/validate.py
python3 scripts/test_sync_agent_stack.py
python3 scripts/test_sync_instructions.py
python3 scripts/test_sync_opencode_config.py
python3 scripts/test_check_pin_freshness.py
python3 scripts/test_hooks.py
ruff check --select E4,E7,E9,F .
ruff format --check .
node --check hooks/opencode-guard.js
sh -n install.sh bootstrap.sh scripts/test-install.sh
shellcheck install.sh bootstrap.sh scripts/test-install.sh
shfmt -d install.sh bootstrap.sh scripts/test-install.sh
./scripts/test-install.sh
```

`shfmt` reads its style from `.editorconfig`, so run it without formatting flags.

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

## Release

The README and the Codex marketplace point at a release tag, so the version changes only in the commit that is tagged right after it merges:

1. Set the new version in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, the `ref` in `.agents/plugins/marketplace.json`, and every pinned `vX.Y.Z` in `README.md`. `python3 scripts/validate.py` fails when the manifests and the marketplace ref disagree.
2. Move the `[Unreleased]` entries in `CHANGELOG.md` under a dated `[X.Y.Z]` heading and update the compare links at the bottom.
3. Merge to `main` with CI green, then tag that commit and publish the notes:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
awk '/^## \[X.Y.Z\]/ { found = 1; next } /^## \[/ { found = 0 } found' CHANGELOG.md > release-notes.md
gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes-file release-notes.md
rm release-notes.md
```

The tag push reruns the workflows, and `validate.py` then also checks that the tag matches the manifest version.

## Agent stack profile changes

- Keep third-party code outside this repository.
- Pin portable skill sources to a full 40-character Git commit.
- Use exact package-manager versions in the profile.
- Mark plugins that persist conversations, invoke browsers, access networks, or run hooks with an appropriate risk level.
- Require explicit opt-in for session capture or similarly sensitive behavior.
- Do not declare plugins that inject context through session, prompt, or tool-call hooks; see the selection rule in `docs/plugin-stack.md`.
- Update `docs/plugin-stack.md` when the desired inventory or risk model changes.

## CI scanner environments

The Cisco Skill Scanner and SkillSpector run from the uv projects under `ci/scanners/`, whose `uv.lock` files pin every dependency with hashes. Dependabot updates them. To change one by hand, edit the version or commit in that directory's `pyproject.toml` and relock it with the uv version that `.github/workflows/security.yml` pins:

```bash
uvx uv@0.13.6 lock --project ci/scanners/cisco-skill-scanner
```

## Security review

Automated scans are required but not sufficient. Review new instructions for prompt injection, hidden data access, excessive permissions, external downloads, destructive commands, and untrusted code execution. Review bundled scripts as executable supply-chain artifacts.

Do not weaken a scanner threshold solely to make CI pass. Document and narrowly suppress a verified false positive when necessary.
