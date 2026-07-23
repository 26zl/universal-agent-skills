# Design notes

## Canonical source

Skills live once under `skills/`. Agent directories receive links or managed copies. This avoids editing several generated variants and makes drift detectable.

Symbolic links are the default on macOS and Linux because they preserve a single source of truth. Copy mode supports Windows policies, containers, network filesystems, and tools that do not follow links. Copy mode writes a private ownership marker only to the installed copy.

## Direct skills and plugins

Direct skill installation is the broad compatibility path. The repository root also contains both Claude and Codex manifests, so the same canonical `skills/` tree can be installed as a native plugin without duplication.

The two plugin formats are not treated as interchangeable. They have separate manifests and marketplace files but share only standards-compatible skill content.

## Reference repository decisions

| Reference | Adopted | Deliberate difference |
| --- | --- | --- |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Small composable skills; root plugin; `source: "./"` marketplace pattern | This repo also provides deterministic cross-agent adapters and uninstall state. |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Clear trigger descriptions, workflow gates, multi-agent documentation | Example skills stay intentionally small instead of shipping a full lifecycle framework. |
| [Karpathy Guidelines](https://github.com/multica-ai/andrej-karpathy-skills) | Assumption control, simplicity, surgical changes, goal-based verification | The concepts are distilled into a short portable workflow rather than duplicated prose. |
| [ECC](https://github.com/affaan-m/ECC) | Profile-driven distribution across multiple harnesses | Third-party code remains upstream; this repo owns only the desired-state profile and adapters. |
| [Claude-Mem](https://github.com/thedotmack/claude-mem) | Progressive retrieval from index to detail | Persistent memory data and settings are explicitly excluded from repository sync. |
| [Humanizer](https://github.com/blader/humanizer) | Portable core skill with optional native packaging | Claude uses its plugin while Codex/OpenCode receive a commit-pinned skill; Copilot discovers the Codex copy. |
| [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector) | Independent static scan and SARIF | LLM analysis is disabled in public CI to avoid secrets, cost, and nondeterminism. |
| [Cisco Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner) | Strict policy, behavioral analysis, reusable CI workflow, high-severity gate | Human review remains mandatory; a clean scan is never presented as certification. |

## Installer safety

- Remote bootstrap refuses root and insecure repository URLs by default.
- Existing managed checkouts must have the expected origin and a clean working tree.
- Agent targets are loaded from a constrained, repository-owned adapter registry.
- Existing unmanaged paths cause failure.
- Forced replacement creates a timestamped backup.
- Uninstall checks both recorded path and ownership before removal.
- Dry-run avoids state, directory, and target writes.
- External stack reconciliation is a separate explicit action and never uninstalls unknown plugins.
- Sensitive persistent-memory behavior requires an additional opt-in flag.

## Updates

Rerunning bootstrap fetches the requested branch, tag, or commit and reinstalls. Link mode picks up source changes as soon as the checkout moves. Copy mode refreshes each managed copy atomically.

Release tags or full commits are recommended for stable machines. A `main` ref is useful for a personal rolling channel but is not reproducible.
