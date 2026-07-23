# Security policy

## Report a vulnerability

Use GitHub's private security advisory flow for this repository. Do not include secrets, access tokens, private prompts, or sensitive logs in a public issue.

## Trust model

Agent skills are instructions that may influence tool use and can bundle executable files. Treat every external skill as untrusted code until it has been reviewed.

Before installing a third-party contribution:

1. Read `SKILL.md` and all referenced files.
2. Inspect bundled scripts and binaries.
3. Check for network access, credential access, destructive commands, hidden instructions, and unnecessary permissions.
4. Run both configured scanners.
5. Test in an isolated account or sandbox when impact is uncertain.

## Bootstrap guidance

Prefer a reviewed clone or a bootstrap URL pinned to an immutable release tag or full commit. A `curl | sh` or downloaded PowerShell one-liner is convenient but executes remote code before the repository scanners can protect the local machine.

The installers reduce accidental damage by tracking ownership, rejecting unknown conflicts, using backups for forced replacements, and constraining removals to registered agent paths. They do not make a malicious repository safe.

## External agent stack

The external stack reconciler is dry-run by default. `--apply` authorizes remote marketplace and skill installation; `--update` additionally authorizes new upstream plugin code. Marketplace source mismatches stop reconciliation rather than being replaced automatically.

Portable third-party skills are fetched into a managed cache at a full Git commit, verified for the expected HEAD and a clean working tree, then installed with a fixed `skills` CLI version. CLI telemetry is disabled. The installer refuses an existing cache path that is unmanaged, dirty, or at another commit. Claude marketplaces cannot be pinned to an exact commit through the marketplace-add command, so review updates before applying them.

`claude-mem` is opt-in because it captures session and tool-use context, stores persistent local data, and can support cloud sync. Never commit its database, transcripts, settings, credentials, or generated observations. Use its private-content controls, retention settings, and local data location only after reviewing the upstream documentation.

MCP servers bundled by external plugins execute separate packages and may access the browser, network, local files, or credentials. The profile records this risk but cannot make an upstream unpinned `latest` dependency reproducible.

## Scanner limitations

Cisco Skill Scanner and NVIDIA SkillSpector are complementary best-effort controls. A clean result does not prove that a skill is benign. False positives and false negatives are possible, and human review remains required.

CI scans repository-owned skills and materializes the profile's portable third-party skills at their exact commits for separate scans. It does not scan complete Claude marketplace plugins, MCP packages, or code fetched by those plugins at runtime.

## Supported versions

Security fixes are applied to the current `main` branch and the latest tagged release.
