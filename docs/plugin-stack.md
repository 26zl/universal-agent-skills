# Personal plugin stack

Reviewed on 2026-07-22. The profile is declarative configuration, not proof that third-party code is safe.

## Desired Claude Code plugins

| Plugin | Marketplace | Current role | Risk note |
| --- | --- | --- | --- |
| `andrej-karpathy-skills` | `karpathy-skills` | Minimal, goal-driven implementation guidance | Instruction-only plugin |
| `code-simplifier` | `claude-plugins-official` | Focused simplification | Instruction workflow |
| `context7` | `claude-plugins-official` | Current library documentation | Networked MCP server |
| `ecc` | `ecc` | Large engineering workflow bundle | Skills, commands, hooks, and MCP configuration |
| `firecrawl` | `claude-plugins-official` | Web crawling | Network and credential access |
| `frontend-design` | `claude-plugins-official` | Frontend design guidance | Instruction workflow |
| `playwright` | `claude-plugins-official` | Browser testing | Browser-control MCP server |
| `ponytail` | `ponytail` | Agent orchestration | Executable integration code |
| `skill-creator` | `claude-plugins-official` | Skill creation | Writes skill artifacts |
| `superpowers` | `claude-plugins-official` | Engineering workflows | Broad instruction surface |
| `claude-mem` | `thedotmack` | Persistent cross-session context | Explicit opt-in: captures tool use and session context |
| `humanizer` | `humanizer` | Natural prose rewriting | Instruction-only skill/plugin |

The first ten entries were confirmed from the local Claude CLI. `claude-mem` and `humanizer` were added to the desired profile from the requested repositories. Claude's built-in `computer-use` capability is not managed as a plugin.

The installed Karpathy marketplace still records `forrestchang/andrej-karpathy-skills`; the requested `multica-ai/andrej-karpathy-skills` source resolves to the same reviewed commit. The profile accepts the former as an alias but uses the latter for new machines.

The installed ECC marketplace checkout was at `b6652335d32d2f2a664e12a09af646bf644b6c86`, while the reviewed upstream head was `b6fe5a71e194d711d9aa8f56024ddf7ca53fad0c`. No update was applied. The `--update` flag intentionally leaves that decision to the user.

## Cross-agent distribution

| Capability | Claude Code | Codex | OpenCode | GitHub Copilot |
| --- | --- | --- | --- | --- |
| Repository-owned skills | Native plugin or installer | Native plugin or installer | Installer | Shared `.agents/skills` plus instructions |
| Karpathy Guidelines | Claude plugin | Pinned portable skill | Pinned portable skill | Discovers Codex copy |
| Humanizer | Claude plugin | Pinned portable skill | Pinned portable skill | Discovers Codex copy |
| Frontend Design | Claude plugin | Pinned portable skill | Pinned portable skill | Discovers Codex copy |
| Code simplification | Official Claude plugin | Repository `simplify-code` skill | Repository `simplify-code` skill | Repository `simplify-code` skill |
| ECC | Claude plugin | Not auto-installed because upstream's adapter owns `~/.codex/config.toml` | Exact native ECC OpenCode target | Not installed; no maintained Copilot target |
| Ponytail | Claude plugin | Commit-pinned marketplace plugin | Exact npm plugin | Marketplace plugin in CLI; instructions in editor |
| Superpowers | Official Claude plugin | Codex-curated plugin | No identical maintained package | No identical maintained package |
| Context7 | Official Claude plugin | Exact local MCP package | Exact local MCP package | Exact local MCP package |
| Playwright/browser | Official Playwright plugin | Codex Browser plugin | Existing OpenCode web tools; no forced duplicate | Exact Playwright MCP in CLI |
| Firecrawl | Official Claude plugin | Not auto-configured without service credentials | Not auto-configured without service credentials | Not auto-configured without service credentials |
| Claude-Mem | Explicit opt-in Claude plugin | Not auto-installed | Not auto-installed | Not compatible |

The profile does not pretend that plugin formats or hook lifecycles are interchangeable. Portable skills are shared directly; client-native plugins and MCP servers are mapped only where a maintained integration exists.

## Reconciliation behavior

`scripts/sync_agent_stack.py`:

- validates all marketplace names, plugin IDs, sources, and portable-skill commit pins;
- audits current Claude, Codex, Copilot CLI, OpenCode, VS Code, and MCP state before planning changes;
- adds missing marketplaces, plugins, MCP servers, native adapters, and the VS Code Copilot extension only with `--apply`;
- leaves unknown plugins untouched;
- refuses automatic marketplace source replacement;
- excludes sensitive plugins unless `--include-sensitive` is explicit;
- installs portable skills through the exact `skills@1.5.9` CLI with telemetry disabled;
- fetches each portable source at a full Git commit, verifies a clean checkout, and installs from that local cache.

`scripts/sync_instructions.py` merges one short, ownership-marked comment rule into each client's documented personal instruction file. It preserves unrelated content, rejects malformed markers, supports dry-run/check/uninstall, and never copies conversation history into instructions.

The reconciler is additive and intentionally has no external-stack uninstall mode because the same plugins may predate this repository. Use the relevant upstream manager to remove an external plugin after reviewing its stored data and shared dependencies. The repository-owned skills still support tracked `--uninstall` through `install.sh` and `install.ps1`.

ECC 2.0.0's Codex target resolves `platform-configs` even for narrower agent/workflow module selections and writes `~/.codex/config.toml`. The default profile therefore does not run that target: doing so could replace unrelated Codex marketplaces, plugins, MCP servers, approval settings, or personal configuration. The OpenCode target remains enabled because it installs into ECC's separate `~/.opencode` adapter root. Users who deliberately want the native Codex target should run ECC directly after backing up and reviewing their Codex configuration.

Claude marketplace updates remain upstream-controlled. In particular, the current external MCP definitions for Context7, Chrome DevTools, and Playwright use unpinned or `latest` npm references. Use `--update` deliberately and inspect upstream changes before broad rollout.

A weekly `pin-freshness` workflow compares every pinned source and package version in the profile with upstream and maintains a single tracking issue when something moved. Applying updates stays a deliberate local step — review the change, bump the pin, then run `python3 scripts/sync_agent_stack.py --apply --update`; unattended auto-apply of third-party agent code is intentionally not offered.

At the reviewed `claude-mem` commit (`f5633c1f84181673896c038cbe285131c6d669a3`), its Claude and Codex plugin manifests and marketplace entry all reported version `13.11.0`. The Claude marketplace remains branch-backed rather than commit-pinned, so later installs can still change upstream code.

The external portable sources are fetched at full commits before installation. Karpathy Guidelines produced no Cisco or SkillSpector findings. Humanizer produced scanner findings that require context: Cisco flagged its hidden plugin manifests and file-type inference, while SkillSpector interpreted the literal phrase "without warning" in a before/after writing example as anti-refusal language and flagged unpinned `npx skills` examples in upstream documentation. Manual inspection found no instruction to suppress safety warnings, and this profile replaces those install examples with an exact CLI version and verified commit checkout. Frontend Design is pinned to the reviewed official Claude plugin repository commit. Re-review these findings whenever a pin changes.

SkillSpector also reports one low-confidence scope-creep finding on the repository's own `surgical-implementation` skill: the guardrail sentence "Expand scope only when the requested behavior cannot be implemented safely without it" pattern-matches as scope expansion. The line restricts scope changes rather than enabling them, so it is kept and documented as a false positive instead of weakening the guardrail.

The matching GitHub code-scanning alerts — including license-text scope-creep notes, the permissionless `file_read` heuristic, and Cisco's hidden-manifest and file-type findings on the pinned external skills — are dismissed as reviewed false positives with per-alert comments. Re-triage any new alert whenever a pin changes.

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
- Claude-Mem databases, observations, summaries, settings, and credentials are never synchronized through Git.
- The full ECC or Addy Osmani lifecycle libraries are not duplicated; both are large and would overlap with installed plugins.
- External plugins are not silently removed, replaced, or updated by the normal skill installer.
- ECC's native Codex installer is not automated because its platform configuration is not safely composable with an existing Codex profile.
