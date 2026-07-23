#!/usr/bin/env python3
"""Report profile pins that are behind their upstream sources."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "profiles" / "default.json"
PINNED_GITHUB_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"
    r"/tree/(?P<commit>[0-9a-f]{40})$"
)
NPM_SPEC_RE = re.compile(r"^(?P<name>@?[A-Za-z0-9._/-]+)@(?P<version>\d+\.\d+\.\d+)$")


def find_pins(profile: dict) -> list[tuple[str, str, str, str]]:
    pins: list[tuple[str, str, str, str]] = []
    for skill in profile.get("portableSkills", []):
        match = PINNED_GITHUB_RE.fullmatch(str(skill.get("source", "")))
        if match:
            pins.append(
                (
                    "git",
                    f"portable skill {skill['name']}",
                    f"{match['owner']}/{match['repo']}",
                    match["commit"],
                )
            )
    for marketplace in profile.get("codex", {}).get("marketplaces", []):
        ref = marketplace.get("ref")
        if ref:
            pins.append(
                ("git", f"codex marketplace {marketplace['name']}", marketplace["source"], ref)
            )
    cli = profile.get("skillsCli", {})
    if cli.get("package") and cli.get("version"):
        pins.append(("npm", "skills CLI", cli["package"], cli["version"]))
    for plugin in profile.get("opencode", {}).get("plugins", []):
        pins.append(
            ("npm", f"opencode plugin {plugin['package']}", plugin["package"], plugin["version"])
        )
    for installer in profile.get("nativeInstallers", []):
        pins.append(
            (
                "npm",
                f"native installer {installer['name']}",
                installer["package"],
                installer["version"],
            )
        )
    for server in profile.get("mcpServers", []):
        for part in server.get("command", []):
            match = NPM_SPEC_RE.fullmatch(part)
            if match:
                pins.append(
                    ("npm", f"MCP server {server['name']}", match["name"], match["version"])
                )
    return pins


def latest_git_commit(repository: str) -> str:
    url = repository if repository.startswith("https://") else f"https://github.com/{repository}"
    if not url.endswith(".git"):
        url += ".git"
    result = subprocess.run(
        ["git", "ls-remote", url, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout.split()[0]


def latest_npm_version(package: str) -> str:
    encoded = urllib.parse.quote(package, safe="@")
    with urllib.request.urlopen(
        f"https://registry.npmjs.org/{encoded}/latest", timeout=30
    ) as response:
        return json.load(response)["version"]


def build_report(pins, resolve_git, resolve_npm):
    stale: list[tuple[str, str, str, str]] = []
    errors: list[str] = []
    for kind, label, target, pinned in pins:
        try:
            latest = resolve_git(target) if kind == "git" else resolve_npm(target)
        except Exception as exc:
            errors.append(f"{label}: cannot resolve upstream ({exc})")
            continue
        if latest != pinned:
            stale.append((label, target, pinned, latest))
    return stale, errors


def render(stale, errors, total: int, markdown: bool) -> str:
    lines: list[str] = []
    if markdown:
        lines.append("## Upstream pin updates available")
        lines.append("")
    for label, target, pinned, latest in stale:
        lines.append(f"- **{label}** (`{target}`): pinned `{pinned}`, upstream `{latest}`")
    for error in errors:
        lines.append(f"- warning: {error}")
    if not stale and not errors:
        lines.append(f"All {total} pins match their upstream sources.")
    if stale and markdown:
        lines.append("")
        lines.append(
            "Git rows compare against the repository HEAD, so unrelated upstream commits "
            "can also appear. Review each change, bump the pin in `profiles/default.json`, "
            "run the validators, then apply locally with "
            "`python3 scripts/sync_agent_stack.py --apply --update`."
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare profile pins with upstream sources.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--format", choices=("text", "issue"), default="text")
    args = parser.parse_args(argv or sys.argv[1:])

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    pins = find_pins(profile)
    stale, errors = build_report(pins, latest_git_commit, latest_npm_version)
    sys.stdout.write(render(stale, errors, len(pins), markdown=args.format == "issue"))
    if stale:
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
