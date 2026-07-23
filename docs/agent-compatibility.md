# Agent compatibility

Verified against public documentation on 2026-07-22.

## Open Agent Skills format

The [Agent Skills specification](https://agentskills.io/specification) defines a skill as a directory with `SKILL.md`. Required frontmatter is `name` and `description`; optional resources commonly live in `scripts/`, `references/`, and `assets/`.

This repository uses only portable frontmatter in canonical skills. Codex-specific UI metadata is isolated under each skill's `agents/openai.yaml`.

## Codex

Codex reads repository skills from `.agents/skills` and user skills from `~/.agents/skills`. It follows symbolic links. Native plugins use `.codex-plugin/plugin.json`, can bundle a root `skills/` directory, and can be listed through `.agents/plugins/marketplace.json`.

Sources: [OpenAI build skills](https://learn.chatgpt.com/docs/build-skills), [OpenAI build plugins](https://learn.chatgpt.com/docs/build-plugins).

## Claude Code

Claude Code reads project skills from `.claude/skills` and personal skills from `~/.claude/skills`. Current versions follow skill-directory symbolic links. Native plugins use `.claude-plugin/plugin.json`; marketplace metadata can point to the repository root with `"source": "./"`.

Sources: [Claude Code skills](https://code.claude.com/docs/en/slash-commands), [Claude Code plugins](https://code.claude.com/docs/en/plugins), [Claude plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces).

## OpenCode

OpenCode reads project skills from `.opencode/skills`, `.claude/skills`, and `.agents/skills`. It reads corresponding global locations under `~/.config/opencode/skills`, `~/.claude/skills`, and `~/.agents/skills`.

Global rules live in `~/.config/opencode/AGENTS.md`. The stack profile installs Ponytail through OpenCode's own version-pinned npm-plugin command and ECC through its native OpenCode target.

Sources: [OpenCode Agent Skills](https://opencode.ai/docs/skills), [OpenCode rules](https://opencode.ai/docs/rules).

## GitHub Copilot

GitHub Copilot discovers project skills from `.github/skills`, `.agents/skills`, and `.claude/skills`; Copilot CLI also discovers personal skills from `~/.copilot/skills` and `~/.agents/skills`. This repository deliberately shares the Codex `~/.agents/skills` installation instead of writing duplicate Copilot copies.

Repository-wide editor instructions live in `.github/copilot-instructions.md`. Copilot CLI additionally reads personal instructions from `~/.copilot/copilot-instructions.md` and supports plugins and MCP servers. VS Code Agent Mode consumes skills and repository instructions, but it does not provide byte-for-byte compatibility with every Claude Code hook or command.

Sources: [GitHub Copilot Agent Skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills), [custom-instruction support](https://docs.github.com/en/copilot/reference/custom-instructions-support), [Copilot plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins).

## Other agents

The `universal` adapter installs to `.agents/skills`, a common Agent Skills target. Support and precedence vary by client. Add a row to `adapters/agents.tsv` only after verifying both its global and project discovery paths from current primary documentation.
