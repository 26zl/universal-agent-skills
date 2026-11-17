# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Every tag also carries full release notes on [GitHub Releases](https://github.com/26zl/universal-agent-skills/releases), which is where the history before v0.3.5 lives.

## [Unreleased]

## [0.4.0] - 2026-11-17

Adds 30 review and workflow skills kept in sync with AI_prompts, installs only the core skills by default, keeps the agent stack to plugins that load on demand and add something new, and tightens the guard and the CI supply chain.

### Added

- 30 review and workflow skills generated from the [AI_prompts](https://github.com/26zl/AI_prompts) collection, from `full-project-audit` to `write-tests`, each with its own settings block and safety boundaries. They are regenerated with its `scripts/export-skills.py` rather than edited here.
- `ai-prompts.lock`, written by the export, records the AI_prompts commit and the generated skills. The new `AI_prompts sync` workflow fails when the generated files differ from what that commit exports, and opens a tracking issue each week when AI_prompts has changes that are not exported yet. The export also keeps the generated skills' `defaultPrompt` lines in `.codex-plugin/plugin.json` in step and removes skills whose prompt was deleted.
- `--all-skills` for `install.sh` and `bootstrap.sh`, and `-AllSkills` for `install.ps1` and `bootstrap.ps1`.
- `--version` for `install.sh`, `bootstrap.sh`, and the Python CLIs, and `-Version` for `install.ps1` and `bootstrap.ps1`. `-WhatIf` is an alias of `-DryRun` in PowerShell.
- A documented release process in CONTRIBUTING.md, and this changelog.

### Changed

- The profile's upstream pins move to the current sources: Humanizer (`blader/humanizer`) and Frontend Design (`anthropics/claude-plugins-official`) to their latest commits, the `skills` CLI to 1.7.4, Context7 MCP to 4.4.4, and Playwright MCP to 0.0.83.
- The pin-freshness workflow grants `issues: write` only to the job that files the tracking issue; the workflow token itself is read-only.
- The installers install the 11 core skills by default. The 30 generated review and workflow skills are added with `--all-skills` or by name with `--skill`, typically per project with `--scope project`.
- The SkillSpector scan matrices are built from `skills/` and the profile's portable skills, so a new skill is scanned without editing the workflow.
- `sync_agent_stack.py` skips a client whose profile section declares nothing, so a missing CLI for that client no longer fails `--apply` or `--check` for that component.
- `install.sh` and `bootstrap.sh` exit with status 2 for invalid usage and 1 for failed operations. The PowerShell scripts run under `Set-StrictMode -Version 3.0`.
- The Cisco Skill Scanner and SkillSpector run in CI from hash-locked uv projects under `.github/scanners/`, which replace the top-level-only pins in `requirements-cisco.txt` and `requirements-security.txt`; Dependabot updates them through its `uv` ecosystem.
- Shell scripts follow `shfmt` with the style in `.editorconfig`, and CI checks it.
- The Windows bootstrap in the README downloads and shows the script in one step and runs it in a second, so it can be read before it runs.
- When a call is blocked, the guard points to the documented placement of a `uas-allow` comment: on its own line directly above the quoted violation.

### Removed

- Ponytail, ECC, Superpowers, and `claude-mem` leave the default agent stack profile for every agent that declared them. Each injects hidden context into every session, prompt, or tool call, or makes its own background model calls, regardless of the task. The reconciler leaves existing installations alone; `docs/plugin-stack.md` lists the removal commands.
- `code-simplifier`, Skill Creator, Firecrawl, and the Karpathy Guidelines (the Claude plugin and the pinned skill for Codex and OpenCode) leave the profile because each duplicates Claude Code's `/simplify`, Claude's own skill creator, the built-in web tools and Context7, or this repository's `surgical-implementation`.
- The `nativeInstallers` profile section, the reconciler's `native` component, and the ECC ledger handling in `sync_opencode_config.py`, which existed only for ECC's OpenCode installer.

### Fixed

- `sync_instructions.py` writes the OpenCode rules to `$XDG_CONFIG_HOME/opencode/AGENTS.md` when `XDG_CONFIG_HOME` is set, which is where OpenCode reads them. A block written earlier to `~/.config/opencode/AGENTS.md` stays there; remove it by hand on such a machine.
- `sync_hooks.py --apply` keeps non-ASCII text in `~/.claude/settings.json` as written instead of rewriting it as `\uXXXX` escapes.
- Thirteen Codex default prompts, in the plugin manifest and in each skill's `agents/openai.yaml`, read as broken sentences, for example "Use $api-design-review to rEST, GraphQL, …"; their short descriptions are now verb phrases.
- An interrupted `bootstrap.sh` clone exits with the signal's status (130 or 143) after removing its staging directory, instead of carrying on and failing with a misleading `mv` error.
- The guard's root-and-home delete rule also catches `rm -rf -- /`, `sudo rm -rf --no-preserve-root /`, `rm -rf '/'`, `rm -rf "$HOME"`, `rm -rf "$HOME"/*`, `rm -rf ${HOME}/`, `rm -rf ~/`, `rm -rf ~; …`, and `rm --recursive --force /`, which it let through before.
- The managed guard hook is recognised by a unique marker instead of any command that mentions `hooks/guard.py`, so `--apply` and `--uninstall` leave a user's own guard hooks alone (#26).
- SkillSpector SARIF locations are rewritten onto the scanned skill path before upload, so code-scanning alerts point at the real files (#26).
- `supply-chain-pinning` requires an immutable URL and a pinned checksum or signature before a downloaded install script is reviewed and run, and the external-skill scan and its SARIF upload keep running after a local finding (#19).

## [0.3.5] - 2026-07-30

Adds an enforcement layer so the always-on rules hold during a session instead of only being advised.

### Added

- `hooks/guard.py` blocks a tool call that would write a secret value, add AI attribution to a commit or pull request, run a destructive Git or SQL operation, or pipe a remote script into an interpreter. Claude Code loads it from `hooks/hooks.json` for plugin installs and from `scripts/sync_hooks.py` for direct installs; OpenCode loads it through `hooks/opencode-guard.js`, which maps tool names onto the same rules.
- An approved destructive command is re-run prefixed with `UAS_ALLOW=1`; documentation and tests quote a violation with a `uas-allow` comment on its own line directly above it.
- A code of conduct, issue and pull request templates, and CODEOWNERS. CI gained lint and format gates and runs the guard tests on Linux, macOS, and Windows.

### Changed

- The managed instruction block carries the hard rules from `secret-hygiene`, `no-ai-traces`, `data-minimization`, and `destructive-ops-approval` alongside the comment rules; `python3 scripts/sync_instructions.py --apply` without `--agent` covers all four clients.
- `sync_agent_stack.py` isolates each component, so a missing or unresponsive CLI is reported as skipped instead of ending the audit; `--apply` still refuses a partial reconciliation and `--check` treats an unevaluated component as unconfirmed. Subprocesses no longer inherit the caller's stdin and each one has a timeout.
- The documented bootstrap downloads the script, shows it, and runs it from disk instead of piping remote code into a shell.

### Fixed

- `XDG_CONFIG_HOME` no longer overrides a redirected `UAS_HOME`, so an audit or test run stays inside the home it was pointed at.

Older releases: see [GitHub Releases](https://github.com/26zl/universal-agent-skills/releases).

[Unreleased]: https://github.com/26zl/universal-agent-skills/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/26zl/universal-agent-skills/compare/v0.3.5...v0.4.0
[0.3.5]: https://github.com/26zl/universal-agent-skills/compare/v0.3.4...v0.3.5
