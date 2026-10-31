# Personal plugin stack

Reviewed on 2026-07-22; pins re-reviewed on 2026-10-31. The profile is declarative configuration, not proof that third-party code is safe.

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
| `ponytail` | `ponytail` | Agent orchestration | Executable integration code; from 5.3 the Claude Code plugin also keeps a per-task cost ledger under `~/.config/ponytail/band/` (on by default) and offers a webhook that stays off until a URL is configured |
| `skill-creator` | `claude-plugins-official` | Skill creation | Writes skill artifacts |
| `superpowers` | `claude-plugins-official` | Engineering workflows | Broad instruction surface |
| `claude-mem` | `thedotmack` | Persistent cross-session context | Explicit opt-in: captures tool use and session context |
| `humanizer` | `humanizer` | Natural prose rewriting | Instruction-only skill/plugin |

`claude-mem` remains opt-in, and Claude's built-in `computer-use` capability is outside plugin management. The profile accepts `forrestchang/andrej-karpathy-skills` as a legacy marketplace alias but uses `multica-ai/andrej-karpathy-skills` for new installations. External plugin updates occur only with `--update`.

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
- resolves ECC's OpenCode install state in the directory `ecc-install` and OpenCode use (`OPENCODE_CONFIG_DIR`, else `$XDG_CONFIG_HOME/opencode`, else `~/.config/opencode`) and keeps its managed MCP entries out of files ECC's ledger owns;
- leaves unknown plugins untouched;
- refuses automatic marketplace source replacement;
- excludes sensitive plugins unless `--include-sensitive` is explicit;
- installs portable skills through the exact `skills@1.7.4` CLI with telemetry disabled;
- fetches each portable source at a full Git commit, verifies a clean checkout, and installs from that local cache.

`scripts/sync_instructions.py` merges one short, ownership-marked rule block into each client's documented personal instruction file. It preserves unrelated content, rejects malformed markers, supports dry-run/check/uninstall, and never copies conversation history into instructions.

The block deliberately duplicates a small part of the skills. Skills are model-invoked: only their name and description reach the system prompt, and the body loads when the agent decides it is relevant. That works for task-shaped skills such as `simplify-code`, but a passive rule offers no moment of invocation, so it is silently skipped. Only the rules that must hold on every edit belong in the block; keeping it short is what keeps it read.

The reconciler is additive and intentionally has no external-stack uninstall mode because the same plugins may predate this repository. Use the relevant upstream manager to remove an external plugin after reviewing its stored data and shared dependencies. The repository-owned skills still support tracked `--uninstall` through `install.sh` and `install.ps1`.

ECC's native Codex target resolves `platform-configs` even for narrower agent/workflow module selections and writes `~/.codex/config.toml`. The default profile therefore does not run that target: doing so could replace unrelated Codex marketplaces, plugins, MCP servers, approval settings, or personal configuration. The OpenCode target remains enabled; since ECC 2.2 it installs into OpenCode's own configuration directory, and the ownership rules below keep it from replacing anything the reconciler or the user wrote there. Users who deliberately want the native Codex target should run ECC directly after backing up and reviewing their Codex configuration.

### ECC 2.2 on OpenCode

From 2.2.0, `ecc-install --target opencode` installs into `OPENCODE_CONFIG_DIR`, else `$XDG_CONFIG_HOME/opencode`, else `~/.config/opencode`, writes `ecc-install-state.json` there, and on its first run removes a legacy `~/.opencode` install file by file, but only files whose content still matches both its ledger and the package; anything edited or unrecorded is kept with a warning. The profile pins 2.2.3 and records the state as `.config/opencode/ecc-install-state.json`; the reconciler maps that `.config/opencode` prefix onto the same three-step lookup, with the usual rule that a redirected `UAS_HOME` ignores the real user's overrides, so the idempotence check reads the file the installer actually wrote. The recorded hook decision is part of that check.

The module selection resolves `platform-configs` as well, which copies ECC's own `opencode.json` (a default agent, agent and command definitions, `plugin: ["./plugins"]`, `skills.paths`, and a `permission` block that asks before any MCP tool), `package.json`, `plugins/`, `tools/`, `dist/`, `prompts/`, `instructions/`, `commands/`, `skills/`, `hooks/`, `scripts/`, and `mcp-configs/` into that directory, so what used to be an inert adapter root is now OpenCode's live configuration. Ownership is split by file. ECC owns what its ledger records and replaces those files on every upgrade; from 2.2.1 it skips a pre-existing file it does not record instead of claiming it. `sync_opencode_config.py` therefore never merges MCP entries into an `opencode.json` that the ledger lists and writes them to `opencode.jsonc` beside it, which OpenCode reads together with `opencode.json`; a user-owned `opencode.json` that predates the first ECC run keeps the merge, and ECC leaves it alone at the price of its own agent and command definitions. Do not add the `ecc-universal` npm package as an OpenCode plugin on top: the copied `plugins/` directory already is that plugin.

Because the selection includes `hooks-runtime`, 2.2 refuses to apply without an explicit decision, so the profile passes `--enable-hooks`. ECC's own disclosure for that runtime: it can modify project source files automatically, rewrite requested commands and start or stop processes, send transcript-derived text to an external LLM, probe and launch MCP processes, deny or alter edit, write, bash, and configuration operations, and persist session, observation, governance, notification, and cost records. The same hooks were installed by 2.1.0 without the prompt; the flag records consent for what the profile already selected. Every install is also mirrored into a derived SQLite projection at `~/.claude/ecc/state.db`, a cache whose write failures are reported as warnings.

Moving an existing machine: `python3 scripts/sync_agent_stack.py --component native --apply` runs the pinned installer once, which migrates `~/.opencode`; a second run or `--component native --check` then reports the component in sync. The 2.1.0 to 2.2.3 diff was read before the bump: the tarball's installer code, hooks, manifests, and package manifest match the `v2.2.3` tag (`.opencode/dist` is the build output), the package declares no install-time lifecycle script, the install path performs no network access, the only new runtime dependency is `js-yaml` 4.3.2, and the optional Nasiko CLI bridge downloads only through the separate `ecc nasiko install` command.

Claude marketplace updates remain upstream-controlled. In particular, the current external MCP definitions for Context7, Chrome DevTools, and Playwright use unpinned or `latest` npm references. Use `--update` deliberately and inspect upstream changes before broad rollout.

A weekly `pin-freshness` workflow compares every pinned source and package version in the profile with upstream and maintains a single tracking issue when something moved. Applying updates stays a deliberate local step — review the change, bump the pin, then run `python3 scripts/sync_agent_stack.py --apply --update`; unattended auto-apply of third-party agent code is intentionally not offered.

At the reviewed `claude-mem` commit (`f5633c1f84181673896c038cbe285131c6d669a3`), its Claude and Codex plugin manifests and marketplace entry all reported version `13.11.0`. The Claude marketplace remains branch-backed rather than commit-pinned, so later installs can still change upstream code.

The external portable sources are fetched at full commits before installation. Karpathy Guidelines produced no Cisco or SkillSpector findings. Humanizer produced scanner findings that require context: Cisco flagged its hidden plugin manifests and file-type inference, while SkillSpector interpreted the literal phrase "without warning" in a before/after writing example as anti-refusal language and flagged unpinned `npx skills` examples in upstream documentation. Manual inspection found no instruction to suppress safety warnings, and this profile replaces those install examples with an exact CLI version and verified commit checkout. Frontend Design is pinned to the reviewed official Claude plugin repository commit. Re-review these findings whenever a pin changes.

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
- Claude-Mem databases, observations, summaries, settings, and credentials are never synchronized through Git.
- The full ECC or Addy Osmani lifecycle libraries are not duplicated; both are large and would overlap with installed plugins.
- External plugins are not silently removed, replaced, or updated by the normal skill installer.
- ECC's native Codex installer is not automated because its platform configuration is not safely composable with an existing Codex profile.
