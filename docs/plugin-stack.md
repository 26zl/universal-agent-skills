# Personal plugin stack

Reviewed on 2026-07-22; pins re-reviewed on 2026-10-31; inventory reduced on 2026-11-17. The profile is declarative configuration, not proof that third-party code is safe.

## Selection rule

A plugin belongs in the profile only when it loads on demand: a skill, an agent, or an MCP server that the model calls when a task needs it. A plugin that injects context through session-start, prompt-submit, subagent-start, or per-tool-call hooks, or that makes its own model calls in the background, spends tokens and steers every turn whether or not the task needs it, and competes with the managed instruction block and the repository's own skills. Such plugins are not declared.

A plugin also has to add something the agent does not already have. One that repeats a built-in capability or a skill in this repository puts a second, competing description in front of the model for the same task, so it is left out as well.

## Desired Claude Code plugins

| Plugin | Marketplace | Current role | Risk note |
| --- | --- | --- | --- |
| `context7` | `claude-plugins-official` | Current library documentation | Networked MCP server |
| `frontend-design` | `claude-plugins-official` | Frontend design guidance | Instruction workflow |
| `playwright` | `claude-plugins-official` | Browser testing | Browser-control MCP server |
| `humanizer` | `humanizer` | Natural prose rewriting | Instruction-only skill/plugin |

Claude's built-in `computer-use` capability is outside plugin management. External plugin updates occur only with `--update`.

## Removed plugins

These plugins were removed from the profile on 2026-11-17 because each adds hidden context or work to every session regardless of the task:

| Plugin | Agents it was declared for | What it adds to every session |
| --- | --- | --- |
| Ponytail (`DietrichGebert/ponytail`) | Claude Code, Codex, Copilot CLI, OpenCode | Session-start, prompt-submit, and subagent-start hooks that inject its ruleset and a generated codebase map as hidden context, a nudge to configure its status line, and a per-task cost ledger under `~/.config/ponytail/` |
| ECC (`affaan-m/ECC`, npm `ecc-universal`) | Claude Code, OpenCode | A 2,805-file package of skills, agents, commands, hooks, and MCP configuration; its OpenCode target replaces OpenCode's own `opencode.json`, default agent, and permission block |
| Superpowers (`obra/superpowers`) | Claude Code, Codex | A bootstrap skill that requires a skill invocation before any response, including clarifying questions, and states that its skills override the default system prompt |
| `claude-mem` (`thedotmack/claude-mem`) | Claude Code | Hooks on session start, every prompt, every tool call, and stop that feed a background worker, which summarizes the session with additional model calls and stores it persistently |

These were removed on the same day because they duplicate something the agent or this repository already provides:

| Plugin | Agents it was declared for | Duplicates |
| --- | --- | --- |
| `code-simplifier` (official) | Claude Code | Claude Code's built-in `/simplify` and the repository's `simplify-code` skill |
| `skill-creator` (official) | Claude Code | The `anthropic-skills:skill-creator` skill that ships with Claude |
| Firecrawl (official) | Claude Code | The built-in WebSearch and WebFetch tools and Context7; its three skills trigger on any request for current information or a supplied URL and send it to a third-party service |
| Karpathy Guidelines (`multica-ai/andrej-karpathy-skills`) | Claude Code as a plugin, Codex and OpenCode as a pinned skill | The repository's `surgical-implementation` skill, which was distilled from it |

The reconciler never removes plugins, so a machine that applied an earlier profile keeps them until they are removed by hand. Review any stored data first, then run the commands for whatever `claude plugin list`, `codex plugin list`, and `copilot plugin list` still show:

```bash
claude plugin uninstall ponytail@ponytail
claude plugin uninstall ecc@ecc
claude plugin uninstall superpowers@claude-plugins-official
claude plugin uninstall claude-mem@thedotmack
claude plugin uninstall code-simplifier@claude-plugins-official
claude plugin uninstall skill-creator@claude-plugins-official
claude plugin uninstall firecrawl@claude-plugins-official
claude plugin uninstall andrej-karpathy-skills@karpathy-skills
claude plugin marketplace remove ponytail
claude plugin marketplace remove ecc
claude plugin marketplace remove thedotmack
claude plugin marketplace remove karpathy-skills
codex plugin remove ponytail@ponytail
codex plugin remove superpowers@openai-curated
codex plugin marketplace remove ponytail
copilot plugin uninstall ponytail@ponytail
copilot plugin marketplace remove ponytail
```

The pinned Karpathy Guidelines copy that the `skills` CLI installed for Codex, OpenCode, and Copilot is normally `~/.agents/skills/karpathy-guidelines`; delete that directory. For OpenCode, delete the `@dietrichgebert/ponytail@…` entry from the `plugin` array in `opencode.jsonc` or `opencode.json`. ECC records every file it installed for OpenCode in `ecc-install-state.json`, in OpenCode's configuration directory since ECC 2.2 and in `~/.opencode` before that; remove the files it lists, but keep `~/.opencode/bin`, where OpenCode's own installer places the `opencode` binary. `~/.claude-mem` holds the `claude-mem` database and settings, `~/.claude/ecc/state.db` is ECC's state cache, and `~/.config/ponytail/` is Ponytail's ledger; delete them once their data is no longer needed. Codex keeps trusted-hook entries named `ponytail@ponytail:…` under `[hooks.state]` in `~/.codex/config.toml`, which can be deleted after the plugin is gone.

## Cross-agent distribution

| Capability | Claude Code | Codex | OpenCode | GitHub Copilot |
| --- | --- | --- | --- | --- |
| Repository-owned skills | Native plugin or installer | Native plugin or installer | Installer | Shared `.agents/skills` plus instructions |
| Humanizer | Claude plugin | Pinned portable skill | Pinned portable skill | Discovers Codex copy |
| Frontend Design | Claude plugin | Pinned portable skill | Pinned portable skill | Discovers Codex copy |
| Code simplification | Built-in `/simplify` and repository `simplify-code` skill | Repository `simplify-code` skill | Repository `simplify-code` skill | Repository `simplify-code` skill |
| Context7 | Official Claude plugin | Exact local MCP package | Exact local MCP package | Exact local MCP package |
| Playwright/browser | Official Playwright plugin | Codex Browser plugin | Existing OpenCode web tools; no forced duplicate | Exact Playwright MCP in CLI |

The profile does not pretend that plugin formats or hook lifecycles are interchangeable. Portable skills are shared directly; client-native plugins and MCP servers are mapped only where a maintained integration exists.

## Reconciliation behavior

`scripts/sync_agent_stack.py`:

- validates all marketplace names, plugin IDs, sources, and portable-skill commit pins;
- audits current Claude, Codex, Copilot CLI, OpenCode, VS Code, and MCP state before planning changes;
- adds missing marketplaces, plugins, MCP servers, and the VS Code Copilot extension only with `--apply`;
- leaves unknown plugins untouched;
- refuses automatic marketplace source replacement;
- excludes plugins marked `requiresExplicitOptIn` unless `--include-sensitive` is explicit;
- installs portable skills through the exact `skills@1.7.4` CLI with telemetry disabled;
- fetches each portable source at a full Git commit, verifies a clean checkout, and installs from that local cache.

The profile schema also supports Codex marketplaces pinned to a full commit, Copilot CLI marketplaces and plugins, and exactly pinned OpenCode npm plugins. The default profile currently declares none of them.

`scripts/sync_instructions.py` merges one short, ownership-marked rule block into each client's documented personal instruction file. It preserves unrelated content, rejects malformed markers, supports dry-run/check/uninstall, and never copies conversation history into instructions.

The block deliberately duplicates a small part of the skills. Skills are model-invoked: only their name and description reach the system prompt, and the body loads when the agent decides it is relevant. That works for task-shaped skills such as `simplify-code`, but a passive rule offers no moment of invocation, so it is silently skipped. Only the rules that must hold on every edit belong in the block; keeping it short is what keeps it read.

The reconciler is additive and intentionally has no external-stack uninstall mode because the same plugins may predate this repository. Use the relevant upstream manager to remove an external plugin after reviewing its stored data and shared dependencies. The repository-owned skills still support tracked `--uninstall` through `install.sh` and `install.ps1`.

Claude marketplace updates remain upstream-controlled. In particular, the MCP definitions inside the official Context7 and Playwright plugins use unpinned or `latest` npm references. Use `--update` deliberately and inspect upstream changes before broad rollout.

A weekly `pin-freshness` workflow compares every pinned source and package version in the profile with upstream and maintains a single tracking issue when something moved. Applying updates stays a deliberate local step — review the change, bump the pin, then run `python3 scripts/sync_agent_stack.py --apply --update`; unattended auto-apply of third-party agent code is intentionally not offered.

The external portable sources are fetched at full commits before installation. Humanizer produced scanner findings that require context: Cisco flagged its hidden plugin manifests and file-type inference, while SkillSpector interpreted the literal phrase "without warning" in a before/after writing example as anti-refusal language and flagged unpinned `npx skills` examples in upstream documentation. Manual inspection found no instruction to suppress safety warnings, and this profile replaces those install examples with an exact CLI version and verified commit checkout. Frontend Design is pinned to the reviewed official Claude plugin repository commit. Re-review these findings whenever a pin changes.

The 2026-10-31 re-review of Humanizer 3.1.0 and Frontend Design 1.1.1 found the same shapes again: the "announced without warning" example survives in Humanizer's dash rule, its README and AGENTS.md still show unpinned `npx skills add` commands, and its read-only `scripts/validate-package.py` is what SkillSpector reports as an undeclared `file_read` capability. Frontend Design's copywriting rule "Errors don't apologize" matches the disclaimer-suppression pattern, and both skills carry license texts whose "not limited to" wording matches the scope-creep pattern. None of these is an instruction to the agent.

SkillSpector also reports one low-confidence scope-creep finding on the repository's own `surgical-implementation` skill: the guardrail sentence "Expand scope only when the requested behavior cannot be implemented safely without it" pattern-matches as scope expansion. The line restricts scope changes rather than enabling them, so it is kept and documented as a false positive instead of weakening the guardrail.

The matching GitHub code-scanning alerts — including license-text scope-creep notes, the permissionless `file_read` heuristic, and Cisco's hidden-manifest and file-type findings on the pinned external skills — are reviewed false positives; dismiss them with per-alert comments instead of rewording upstream text. The repository's own audit skills trigger the same pattern matchers on checklist text ("no `rm -rf` with an unset variable", "`verify=False` is never used", "without asking" inside a prohibition), and Cisco's Magika heuristic occasionally reads a four-line `agents/openai.yaml` as a protocol-buffer text file. Re-triage any new alert whenever a pin changes.

## Useful patterns adopted

| Source | Useful pattern | Adoption here |
| --- | --- | --- |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | Surface consequential assumptions, prefer the simplest sufficient design, keep edits surgical, verify goals | Added the small `surgical-implementation` skill instead of copying the full text |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | Multi-agent profiles and harness-specific adapters | Added one declarative stack profile while preserving separate agent adapters |
| [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | Index first, retrieve detail only when needed | Kept progressive disclosure; excluded memory databases, transcripts, settings, and cloud sync data from Git |
| [blader/humanizer](https://github.com/blader/humanizer) | A portable core skill with optional agent-native packaging | Uses the Claude plugin for Claude and a pinned standard skill for Codex/OpenCode |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Small composable skills, repository setup, shared domain language | Kept skills narrow and added an explicit personal stack profile rather than a monolithic process framework |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Workflow checkpoints, evidence gates, progressive disclosure | Strengthened the define-build-verify path across `surgical-implementation` and `verify-changes` |

## Deliberately not adopted

- Third-party plugin source code is not vendored into this repository.
- Persistent-memory databases, observations, summaries, settings, and credentials are never synchronized through Git.
- The full ECC or Addy Osmani lifecycle libraries are not duplicated; both are large and overlap with the repository's own skills.
- External plugins are not silently removed, replaced, or updated by the normal skill installer.
- Plugins that inject context into every session, prompt, or tool call are not declared; see [Selection rule](#selection-rule).
