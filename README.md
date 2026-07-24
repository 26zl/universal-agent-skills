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
├── install.sh / install.ps1        # Local install, sync, and uninstall
├── bootstrap.sh / bootstrap.ps1    # Clone/update + install
├── scripts/sync_instructions.py    # Safe global instruction merge/remove
└── .github/workflows/              # Validation, tests, and scanners
```

`coding-style` tells agents to prefer self-explanatory code and use short, neutral comments only when intent or constraints are not obvious. It explicitly avoids conversational, first-person, AI-like narration.

`simplify-code` provides the portable equivalent of a focused code-simplifier workflow while preserving behavior. `surgical-implementation` keeps changes small, makes material assumptions visible, and prevents drive-by refactoring. `verify-changes` requires focused validation evidence before an agent reports completion.

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

Without `--project-dir` the current directory is used; PowerShell accepts the same through `-Scope project -ProjectDir`. Project installations land in the project's own discovery paths (`.claude/skills`, `.agents/skills`, `.opencode/skills`) and are tracked separately from global installations, so uninstalling one scope never touches the other. Prefer `--mode copy` for shared projects because symbolic links point into your local clone.

## Bootstrap one-liner for macOS and Linux

Pin a full commit for immutable installs, or use a protected release tag for release-oriented installs:

```bash
curl -fsSL https://raw.githubusercontent.com/26zl/universal-agent-skills/v0.3.0/bootstrap.sh | sh -s -- --repo https://github.com/26zl/universal-agent-skills.git --ref v0.3.0
```

For a rolling installation that follows `main`, change both occurrences of `v0.3.0` to `main`. Rerun the same command to sync another computer or refresh an existing installation.

Add `--with-agent-stack` to reconcile the complete declared stack: Claude plugins, Codex and Copilot CLI plugins, the OpenCode Ponytail plugin, the VS Code Copilot extension, Context7/Playwright MCP servers, ECC adapters, pinned portable skills, and global comment instructions. `claude-mem` is excluded unless the command also includes `--include-sensitive-plugins` because it persistently captures session and tool-use context:

```bash
curl -fsSL https://raw.githubusercontent.com/26zl/universal-agent-skills/v0.3.0/bootstrap.sh | sh -s -- --repo https://github.com/26zl/universal-agent-skills.git --ref v0.3.0 --with-agent-stack --include-sensitive-plugins
```

Piping remote code into a shell trades reviewability for convenience. For higher assurance, download the script, inspect it, and execute it from disk. The bootstrap itself refuses root execution (Windows administrator sessions remain allowed because symbolic links may require elevation there), accepts HTTPS or SSH repositories by default, verifies an existing checkout's origin, refuses dirty managed checkouts, and checks out the exact fetched ref.

Agent-stack reconciliation requires Python 3.9 or newer. Direct repository-skill installation does not require Python.

## Windows PowerShell

From a clone:

```powershell
.\bootstrap.ps1
```

Pinned remote bootstrap in one line:

```powershell
$repo='https://github.com/26zl/universal-agent-skills'; $file=Join-Path $env:TEMP 'uas-bootstrap.ps1'; Invoke-WebRequest "$repo/raw/v0.3.0/bootstrap.ps1" -OutFile $file; & $file -Repo "$repo.git" -Ref v0.3.0
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

ECC's native Codex target is intentionally not automated because ECC 2.0.0 writes the complete `~/.codex/config.toml`, even when narrower workflow modules are requested. Portable skills, Codex-native plugins, and MCP mappings provide the safe Codex layer without replacing unrelated user settings.

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

The always-on comment rule is merged between ownership markers in `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, and `~/.copilot/copilot-instructions.md`. Existing text is preserved. Audit or remove only the managed block with:

```bash
python3 scripts/sync_instructions.py
python3 scripts/sync_instructions.py --apply --uninstall
```

External-stack removal is deliberately manual because some listed plugins already existed before this repository. The normal `--uninstall` option remains ownership-tracked for repository-owned skills.

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

Remove only entries owned by this installer:

```bash
./install.sh --uninstall
```

The PowerShell equivalents are `-DryRun`, `-Update`, and `-Uninstall`.

If a target already exists and is not managed by this repository, installation stops. `--force` or `-Force` moves the conflict to a timestamped backup instead of deleting it.

State is stored under:

- POSIX: `${XDG_STATE_HOME:-~/.local/state}/universal-agent-skills/installed.tsv`
- Windows: `%LOCALAPPDATA%\universal-agent-skills\installed.json`

## Native plugin installation

Direct skill installation is the most portable option. Native plugins are useful when an agent should manage the bundle as a versioned package.

Use one method per machine: combining the native plugin with a direct installation surfaces the same skills twice. Plugin-provided skills are namespaced by the client, so neither copy overrides the other; they simply both appear.

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
