# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Every tag also carries full release notes on [GitHub Releases](https://github.com/26zl/universal-agent-skills/releases), which is where the history before v0.3.5 lives.

## [Unreleased]

### Added

- 30 review and workflow skills generated from the [AI_prompts](https://github.com/26zl/AI_prompts) collection, from `full-project-audit` to `write-tests`, each with its own settings block and safety boundaries. They are regenerated with its `scripts/export-skills.py` rather than edited here. The plugin manifests now report version 0.4.0.
- This changelog.

### Changed

- The profile's upstream pins move to the current sources: Humanizer (`blader/humanizer`) and Frontend Design (`anthropics/claude-plugins-official`) to their latest commits, the Codex Ponytail marketplace ref to the current commit, the `skills` CLI to 1.7.4, the OpenCode Ponytail plugin to 5.3.3, Context7 MCP to 4.4.4, and Playwright MCP to 0.0.83. `ecc-universal` stays at 2.1.0 because 2.2.x moves its OpenCode target into `~/.config/opencode`, which the profile's state path and the reconciler do not model yet; see `docs/plugin-stack.md`.
- The pin-freshness workflow grants `issues: write` only to the job that files the tracking issue; the workflow token itself is read-only.

### Fixed

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

[Unreleased]: https://github.com/26zl/universal-agent-skills/compare/v0.3.5...HEAD
[0.3.5]: https://github.com/26zl/universal-agent-skills/compare/v0.3.4...v0.3.5
