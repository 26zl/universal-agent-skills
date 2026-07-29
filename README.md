# Universal Agent Skills

[![Validate](https://github.com/26zl/universal-agent-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/26zl/universal-agent-skills/actions/workflows/validate.yml)
[![Test installers](https://github.com/26zl/universal-agent-skills/actions/workflows/test-installers.yml/badge.svg)](https://github.com/26zl/universal-agent-skills/actions/workflows/test-installers.yml)
[![Scan skills](https://github.com/26zl/universal-agent-skills/actions/workflows/security.yml/badge.svg)](https://github.com/26zl/universal-agent-skills/actions/workflows/security.yml)
[![Release](https://img.shields.io/github/v/tag/26zl/universal-agent-skills?label=release&sort=semver)](https://github.com/26zl/universal-agent-skills/tags)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

```text
███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
███████╗█████╔╝ ██║██║     ██║     ███████╗
╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
███████║██║  ██╗██║███████╗███████╗███████║
╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝
```

A canonical, version-controlled collection of [Agent Skills](https://agentskills.io/specification) that can be shared across Codex, Claude Code, OpenCode, GitHub Copilot, and compatible coding agents.

The repository is both:

- a portable skill source under `skills/`;
- a native Claude Code and Codex plugin at the repository root.

The installers are idempotent, support symbolic links or copies, track what they own, refuse unmanaged conflicts by default, and provide dry-run and uninstall modes.

## What is included

```text
.
├── skills/                         # Canonical Agent Skills
│   ├── coding-style/
│   ├── data-minimization/
│   ├── destructive-ops-approval/
│   ├── license-compliance/
│   ├── no-ai-traces/
│   ├── secret-hygiene/
│   ├── simplify-code/
│   ├── supply-chain-pinning/
│   ├── surgical-implementation/
│   └── verify-changes/
├── profiles/default.json           # Desired external plugin/skill stack
├── adapters/agents.tsv             # Agent discovery paths
├── .claude-plugin/                 # Claude plugin + marketplace metadata
├── .codex-plugin/                  # Codex plugin metadata
├── .agents/plugins/marketplace.json
├── hooks/                          # Shared guard + Claude Code and OpenCode adapters
├── install.sh / install.ps1        # Local install, sync, and uninstall
├── bootstrap.sh / bootstrap.ps1    # Clone/update + install
├── scripts/sync_instructions.py    # Safe global instruction merge/remove
├── scripts/sync_hooks.py           # Guard registration for direct installs
└── .github/workflows/              # Validation, tests, and scanners
```

`coding-style` tells agents to prefer self-explanatory code and use short, neutral comments only when intent or constraints are not obvious. It explicitly avoids conversational, first-person, AI-like narration, and keeps identifiers, comments, and commit messages in English even when the conversation is in another language.

`simplify-code` provides the portable equivalent of a focused code-simplifier workflow while preserving behavior. `surgical-implementation` keeps changes small, makes material assumptions visible, prevents drive-by refactoring, and requires a defect found along the way to be fixed as its own change instead of silently skipped. `verify-changes` requires focused validation evidence before an agent reports completion.

`no-ai-traces` keeps delivered work — commits, pull requests, release notes, comments, and documentation — free of assistant self-reference such as Co-Authored-By trailers, generated-with footers, or session narration. Explicit organizational disclosure requirements always take precedence over the skill.

`secret-hygiene`, `data-minimization`, `supply-chain-pinning`, `destructive-ops-approval`, and `license-compliance` form a workplace governance set: secret values never enter code or output, real personal data stays out of tests and logs, dependencies are justified and pinned, irreversible operations wait for explicit approval, and third-party code enters only with a compatible license and preserved attribution.

## Supported targets

| Agent | Global target | Project target | Native plugin |
| --- | --- | --- | --- |
| Codex | `~/.agents/skills` | `.agents/skills` | Yes |
| Claude Code | `~/.claude/skills` | `.claude/skills` | Yes |
| OpenCode | `~/.config/opencode/skills` | `.opencode/skills` | Skills directly |
| GitHub Copilot | `~/.agents/skills` | `.agents/skills` | CLI plugins; editor uses skills/instructions |
| Other Agent Skills clients | `~/.agents/skills` | `.agents/skills` | Client-dependent |

OpenCode also discovers the Claude-compatible and `.agents/skills` locations. GitHub Copilot and Codex share the standard `.agents/skills` target, so the `copilot` and `universal` adapter names are aliases of `codex` and do not create duplicate skills.

See [Agent compatibility](docs/agent-compatibility.md) for the source documentation and discovery behavior.

## Install from a clone

```bash
git clone https://github.com/26zl/universal-agent-skills.git
cd universal-agent-skills
./bootstrap.sh
```

The default is a global symbolic-link installation for Codex/GitHub Copilot, Claude Code, and OpenCode. Editing a canonical skill updates every linked agent immediately.

You do not need to uninstall existing entries first. The direct skill installer manages only its own recorded targets and refuses unmanaged path conflicts unless `--force` is explicit. The stack reconciler leaves entries outside the profile unchanged; for entries declared in the profile, `--apply` may install or enable them, and `--update` may update them.

Use copies when symbolic links are unavailable or undesirable:

```bash
./install.sh --mode copy
```

Install only selected agents or skills:

```bash
./install.sh --agents codex,opencode
./install.sh --skill coding-style
```

Install into the current project instead of the user profile:

```bash
./install.sh --scope project --project-dir ~/path/to/project
```

Without `--project-dir` the current directory is used; PowerShell accepts the same through `-Scope project -ProjectDir`. Project installations land in the project's own discovery paths (`.claude/skills`, `.agents/skills`, `.opencode/skills`) and are tracked separately from global installations. Prefer `--mode copy` for shared projects because symbolic links point into your local clone.

## Reviewed bootstrap for macOS and Linux

Pin a full commit for immutable installs, or use a protected release tag for release-oriented installs:

```bash
bootstrap=$(mktemp)
curl -fsSL https://raw.githubusercontent.com/26zl/universal-agent-skills/v0.3.5/bootstrap.sh -o "$bootstrap"
less "$bootstrap"
sh "$bootstrap" --repo https://github.com/26zl/universal-agent-skills.git --ref v0.3.5
rm -f "$bootstrap"
```

For a rolling installation that follows `main`, change both occurrences of `v0.3.5` to `main`. Rerun the same command to sync another computer or refresh an existing installation.

To reconcile the complete declared stack, replace the `sh "$bootstrap"` line above with the following command before removing the temporary file. `claude-mem` is excluded unless the command also includes `--include-sensitive-plugins` because it persistently captures session and tool-use context:

```bash
sh "$bootstrap" --repo https://github.com/26zl/universal-agent-skills.git --ref v0.3.5 --with-agent-stack --include-sensitive-plugins
```

The complete stack includes Claude, Codex, Copilot CLI, OpenCode and VS Code integrations, Context7/Playwright MCP servers, ECC adapters, pinned portable skills, and global comment instructions. The bootstrap itself refuses root execution (Windows administrator sessions remain allowed because symbolic links may require elevation there), accepts HTTPS or SSH repositories by default, verifies an existing checkout's origin, refuses dirty managed checkouts, and checks out the exact fetched ref.

Agent-stack reconciliation requires Python 3.9 or newer. Direct repository-skill installation does not require Python.

## Windows PowerShell

From a clone:

```powershell
.\bootstrap.ps1
```

Pinned remote bootstrap in one line:

```powershell
$repo='https://github.com/26zl/universal-agent-skills'; $file=Join-Path $env:TEMP 'uas-bootstrap.ps1'; Invoke-WebRequest "$repo/raw/v0.3.5/bootstrap.ps1" -OutFile $file; Get-Content $file; & $file -Repo "$repo.git" -Ref v0.3.5
```

PowerShell `auto` mode tries symbolic links first and falls back to copies when Windows Developer Mode or sufficient privileges are unavailable.

Use `-WithAgentStack` to include the external stack and `-IncludeSensitivePlugins` to opt into `claude-mem`.

## Personal agent stack

The canonical profile reflects the current Claude setup plus `claude-mem` and `humanizer`. It includes:

- `andrej-karpathy-skills`, ECC, Ponytail, `claude-mem`, and Humanizer from their own marketplaces;
- the official `code-simplifier`, Context7, Firecrawl, Frontend Design, Playwright, Skill Creator, and Superpowers plugins;
- commit-pinned Karpathy Guidelines, Humanizer, and Frontend Design skills for Codex/OpenCode; Copilot discovers the Codex copies through `~/.agents/skills`.
- Codex-native Browser, Computer Use, Superpowers, and Ponytail plugins.
- Copilot CLI Ponytail plus the VS Code extension, repository instructions, shared skills, Context7, and Playwright.
- Ponytail and ECC through their native OpenCode integrations.

ECC's native Codex target is intentionally not automated because it writes the complete `~/.codex/config.toml`, even when narrower workflow modules are requested. Portable skills, Codex-native plugins, and MCP mappings provide the safe Codex layer without replacing unrelated user settings.

Audit without changing the machine:

```bash
python3 scripts/sync_agent_stack.py
```

Install missing standard plugins, integrations, instructions, and portable skills:

```bash
python3 scripts/sync_agent_stack.py --apply
```

Include persistent-memory capture only after reviewing its privacy and storage behavior:

```bash
python3 scripts/sync_agent_stack.py --apply --include-sensitive
```

Add `--update` to refresh already-installed external plugins. The reconciler never removes plugins that are not in the profile and refuses to replace a marketplace whose source differs. It disables anonymous `skills` CLI telemetry and uses exact package versions plus full commit URLs for portable third-party skills.

The always-on comment rules and hard rules are merged between ownership markers in `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, and `~/.copilot/copilot-instructions.md`. Skills load only when an agent chooses to invoke them, so the block carries the subset that must hold on every edit: comment style plus the hard rules from `secret-hygiene`, `no-ai-traces`, `data-minimization`, and `destructive-ops-approval`. Existing text is preserved. Audit the managed block with:

```bash
python3 scripts/sync_instructions.py
```

Removal for every install path is covered under [Uninstall](#uninstall).

## Enforcement layers

A skill is model-invoked: only its name and description reach the system prompt, and the body loads when the agent decides it is relevant. That fits a task-shaped skill such as `simplify-code`, which the user asks for by name. A passive rule offers no such moment, so it is read past. Three layers cover the difference:

| Layer | Mechanism | Strength |
| --- | --- | --- |
| Skill | `skills/<name>/SKILL.md` | Loaded when the agent judges it relevant |
| Instruction block | `scripts/sync_instructions.py` | Present in every context; can still be reasoned past |
| Guard hook | `hooks/guard.py` | Blocks the tool call outright |

| Skill | Instruction block | Guard hook |
| --- | --- | --- |
| `coding-style` | Comment rules | — |
| `no-ai-traces` | Yes | Attribution trailers, generated-with footers, robot signatures |
| `secret-hygiene` | Yes | Known token and private-key shapes |
| `destructive-ops-approval` | Yes | Force-push, `reset --hard`, history rewrite, remote branch deletion, recursive delete of a root or home path, destructive SQL |
| `data-minimization` | Yes | — |
| `supply-chain-pinning` | — | Remote scripts piped into an interpreter |
| `license-compliance` | — | — |
| `simplify-code` | — | — |
| `surgical-implementation` | — | — |
| `verify-changes` | — | — |

The empty cells are deliberate. Whether a comment earns its place, whether a record is real or synthetic, whether a license is compatible, and whether a change is minimal are judgments no pattern decides; a regex that guessed at them would block correct work and be switched off within a day. Those skills stay advisory.

The guard reads a `PreToolUse` payload and exits 2 to block, returning the reason to the agent. Any malformed input exits 0, so a broken guard never stops legitimate work. Values shaped as placeholders are exempt from the secret rules, which is what the `secret-hygiene` skill already requires of examples.

Destructive commands are blocked rather than forbidden: the block is what forces the approval conversation the skill asks for. After the user approves, the agent re-runs the command prefixed with `UAS_ALLOW=1`, which releases only the destructive rules and leaves the marker visible in the transcript.

Documentation and tests have to be able to quote a violation, so a `uas-allow` marker exempts a single match on its own line or the line directly above it. Never a file, and never a whole block. It is the honest form of an escape that splitting a literal already provided invisibly — a reviewer can grep for the marker but not for a broken-up constant.

Prefer the marker on its own line above the quoted violation. A code formatter that reflows arguments relocates a trailing comment, which is why the preceding line counts at all.

Command rules match raw text, so a destructive command quoted inside a string — `echo "never run git push --force"` — is blocked as well. The same `UAS_ALLOW=1` prefix clears it. Shell-accurate quote parsing would remove that case at the cost of a parser that fails open on the constructs it does not model, which is the worse trade for a guard.

Claude Code plugin installs load `hooks/hooks.json` automatically. A symlink or copy install has no plugin root, so the hook is registered in `~/.claude/settings.json` instead. OpenCode loads a shim from its plugin directory that re-exports the plugin from this checkout:

```bash
python3 scripts/sync_hooks.py                      # audit both
python3 scripts/sync_hooks.py --apply              # register both
python3 scripts/sync_hooks.py --agent opencode     # limit to one
```

Registration is idempotent, preserves hooks it does not own, refuses to replace an unmanaged plugin file, and is removed with `--uninstall --apply`.

### Portability of each layer

| Layer | Codex | Claude Code | OpenCode | Copilot |
| --- | --- | --- | --- | --- |
| Skills | Yes | Yes | Yes | Yes |
| Instruction block | Yes | Yes | Yes | Yes |
| Guard | No | Yes | Yes | No |

The guard reaches as far as each agent offers an interception point: Claude Code through a `PreToolUse` hook, OpenCode through a plugin's `tool.execute.before`. Codex and Copilot CLI document no equivalent in [Agent compatibility](docs/agent-compatibility.md), so the instruction block is the strongest layer there — run `sync_instructions.py` without `--agent` to cover all four rather than the one in front of you.

Both guards run the same `hooks/guard.py`; `hooks/opencode-guard.js` only maps OpenCode's tool names and camel-cased arguments onto the same payload. Keeping one rule set in one language is what stops the two from drifting apart. On OpenCode the mapping covers `bash`, `edit`, and `write`, the tools whose argument shapes its documentation makes observable.

See [Plugin stack](docs/plugin-stack.md) for the complete inventory, risk notes, and the patterns adopted from the reviewed repositories.

## Common operations

Preview changes:

```bash
./install.sh --dry-run
```

Refresh a normal branch clone and reinstall:

```bash
./install.sh --update
```

For a checkout created by `bootstrap.sh`, rerun the bootstrap command with the same repository and ref. Link installations immediately use the refreshed source; copy installations are recopied.

The PowerShell equivalents are `-DryRun` and `-Update`. To remove installed skills or plugins, see [Uninstall](#uninstall).

If a target already exists and is not managed by this repository, installation stops. `--force` or `-Force` moves the conflict to a timestamped backup instead of deleting it.

State is stored under:

- POSIX: `${XDG_STATE_HOME:-~/.local/state}/universal-agent-skills/installed.tsv`
- Windows: `%LOCALAPPDATA%\universal-agent-skills\installed.json`

## Native plugin installation

Direct skill installation is the most portable option. Native plugins are useful when an agent should manage the bundle as a versioned package.

Use one method per machine: combining the native plugin with a direct installation surfaces the same skills twice. Plugin-provided skills are namespaced by the client, so neither copy overrides the other; they simply both appear. The installer warns when it finds a native plugin beside the direct installation, but it never removes the plugin for you.

### Claude Code

Inside Claude Code:

```text
/plugin marketplace add https://github.com/26zl/universal-agent-skills.git
/plugin install universal-agent-skills@universal-agent-skills
```

For local development:

```bash
claude --plugin-dir /absolute/path/to/universal-agent-skills
```

### Codex

```bash
codex plugin marketplace add https://github.com/26zl/universal-agent-skills.git
codex plugin add universal-agent-skills@universal-agent-skills
```

Restart the relevant app or open a new task if a newly installed plugin is not discovered immediately.

### GitHub Copilot CLI

Copilot CLI understands the same plugin marketplace shape:

```bash
copilot plugin marketplace add https://github.com/26zl/universal-agent-skills.git
copilot plugin install universal-agent-skills@universal-agent-skills
```

VS Code Copilot consumes the repository's `.github/copilot-instructions.md`, root `AGENTS.md`, and standard skills. It does not execute every Claude Code hook or plugin, so support is capability-mapped rather than binary-identical.

## Uninstall

Removal depends on how you installed. Each path below is self-contained; pick the one you used.

### Skills from `install.sh` or the bootstrap one-liner

The installer removes only what it recorded in `installed.tsv` and never touches unmanaged files. Preview first, then remove:

```bash
./install.sh --dry-run --uninstall        # show what would be removed
./install.sh --uninstall                  # remove every skill this repo owns
```

Narrow it the same way you installed; global and project installs are tracked separately, so removing one never affects the other:

```bash
./install.sh --uninstall --agents codex --skill coding-style     # a single agent/skill
./install.sh --uninstall --scope project --project-dir /path     # a project install
```

Bootstrap users can rerun the one-liner with `--uninstall`, or call `./install.sh --uninstall` from the cached clone at `~/.local/share/universal-agent-skills/repo`. On Windows, use `install.ps1 -Uninstall` or `bootstrap.ps1 -Uninstall` with the same options.

### Personal instruction block

```bash
python3 scripts/sync_instructions.py --apply --uninstall
```

### Guard hook

```bash
python3 scripts/sync_hooks.py --apply --uninstall
```

### Native plugin added through a marketplace

`install.sh --uninstall` does not manage native plugins; each client keeps its own registry. Reverse the two install steps with that client's commands:

| Client | Remove the plugin | Remove the marketplace |
| --- | --- | --- |
| Claude Code | `/plugin uninstall universal-agent-skills@universal-agent-skills` | `/plugin marketplace remove universal-agent-skills` |
| Codex | `codex plugin remove universal-agent-skills@universal-agent-skills` | `codex plugin marketplace remove universal-agent-skills` |
| GitHub Copilot CLI | `copilot plugin uninstall universal-agent-skills@universal-agent-skills` | `copilot plugin marketplace remove universal-agent-skills` |

Removing a marketplace also removes the plugins installed from it: Claude Code warns first, and Copilot CLI requires `--force` while plugins remain.

### External stack plugins

Third-party plugins declared in the profile (for example `ponytail`) may predate this repository, so their removal is deliberately manual. Remove them with each plugin's upstream manager after reviewing stored data and shared dependencies; see `docs/plugin-stack.md`.

## Adding a skill

Create `skills/<skill-name>/SKILL.md` using the open specification:

```markdown
---
name: skill-name
description: Describe what the skill does and exactly when it should trigger.
---

# Skill title

Write concise, imperative instructions.
```

Names must be lowercase kebab-case, match the directory name, and remain at most 64 characters. Put scripts, references, or assets inside the skill only when the workflow needs them. Keep detailed material out of `SKILL.md` until it is needed through progressive disclosure.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete checks.

## Validation and security

Run the dependency-free local checks and POSIX installer tests:

```bash
python3 scripts/validate.py
python3 scripts/test_sync_agent_stack.py
python3 scripts/test_sync_instructions.py
python3 scripts/test_sync_opencode_config.py
python3 scripts/test_check_pin_freshness.py
python3 scripts/test_hooks.py
./scripts/test-install.sh
```

CI adds:

- the official `skills-ref` specification validator;
- installer tests on Linux, macOS, and Windows;
- a version-pinned [Cisco AI Defense Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner) with strict policy, behavioral analysis, and a high-severity failure gate;
- commit-pinned [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) static scans and SARIF uploads;
- isolated scans of the commit-pinned Karpathy Guidelines, Humanizer, and Frontend Design sources declared in the profile;
- a weekly pin-freshness workflow that files a tracking issue when a pinned upstream source or package version moves;
- pinned GitHub Action commits and Dependabot updates.

Automated scanners are defense-in-depth, not a guarantee. Review every skill and bundled executable before trusting it. See [SECURITY.md](SECURITY.md).

## Design influences

This repository adopts several useful patterns from the referenced projects:

- [mattpocock/skills](https://github.com/mattpocock/skills): small, composable skills plus a root-level Claude plugin whose marketplace source is `./`.
- [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills): explicit trigger descriptions, verification gates, and documentation for multiple agents.
- [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills): surface material assumptions, prefer simple designs, and keep changes surgical.
- [affaan-m/ECC](https://github.com/affaan-m/ECC): profile-driven multi-agent distribution while keeping agent adapters separate.
- [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem): progressive disclosure for retrieved context, with persistent data kept outside Git.
- [blader/humanizer](https://github.com/blader/humanizer): one portable skill artifact with agent-specific distribution wrappers.
- [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector): independent static and semantic security analysis with SARIF output.
- [cisco-ai-defense/skill-scanner](https://github.com/cisco-ai-defense/skill-scanner): CI-native, policy-based scanning and behavioral analysis.

The canonical source remains standard `SKILL.md` folders. Agent-specific behavior is kept in adapters and plugin manifests rather than duplicated copies of each skill. See [Design notes](docs/design-notes.md) for the tradeoffs.

## License

MIT. Security scanners and other referenced projects retain their own licenses.
