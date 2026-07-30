#!/usr/bin/env python3
"""Manage the guard hook registration for agents that can intercept tool calls.

Claude Code plugin installs load hooks/hooks.json automatically; a symlink
install has no plugin root, so the hook is registered in settings.json instead.
OpenCode loads plugins from its own plugin directory, where a small shim
re-exports the real plugin from this checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sync_instructions import atomic_write

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "hooks" / "guard.py"
PLUGIN = ROOT / "hooks" / "opencode-guard.js"
SHIM_MARKER = "// managed-by=universal-agent-skills; component=opencode-guard-shim"
GUARD_SUFFIX = "/hooks/guard.py"
EVENT = "PreToolUse"
MATCHER = "Bash|Edit|Write|MultiEdit|NotebookEdit"
SUPPORTED_AGENTS = ("claude", "opencode")


def claude_settings(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def config_home(home: Path) -> Path:
    # XDG_CONFIG_HOME describes where the real user's config lives, so it applies
    # only when this run targets that home; a redirected home must stay contained.
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg and home == Path.home():
        return Path(xdg)
    return home / ".config"


def opencode_plugin(home: Path) -> Path:
    return config_home(home) / "opencode" / "plugins" / "universal-agent-skills.js"


def shim() -> str:
    return (
        f"{SHIM_MARKER}\n"
        f'export {{ UniversalAgentSkillsGuard }} from "{PLUGIN.as_uri()}";\n'
    )


def entry() -> dict:
    # Mirrors hooks/hooks.json so the entry survives whichever platform reads it; a
    # missing interpreter exits 0 rather than blocking every call. The path is left
    # as this machine renders it, since a checkout path does not port anyway.
    return {
        "matcher": MATCHER,
        "hooks": [
            {
                "type": "command",
                "command": f'command -v python3 >/dev/null 2>&1 || exit 0; python3 "{GUARD}"',
                "commandWindows": (
                    "if (-not (Get-Command python -ErrorAction SilentlyContinue)) { exit 0 }; "
                    f'python "{GUARD}"; exit $LASTEXITCODE'
                ),
                "timeout": 10,
                "statusMessage": "Checking always-on rules...",
            }
        ],
    }


def owns_hook(hook: object) -> bool:
    # The checkout path is baked into the command, so ownership keys on the layout
    # that survives a move; matching the whole entry would strand the old one.
    # Windows renders the path with backslashes, so compare on a normalised form.
    if not isinstance(hook, dict):
        return False
    return GUARD_SUFFIX in str(hook.get("command", "")).replace("\\", "/")


def owned(group: object) -> bool:
    if not isinstance(group, dict):
        return False
    hooks = group.get("hooks")
    return isinstance(hooks, list) and any(owns_hook(hook) for hook in hooks)


def without_guard(group: object) -> object | None:
    # A group may hold foreign hooks beside ours, so prune per hook and drop the
    # group only once nothing of the user's is left in it.
    if not owned(group):
        return group
    kept = [hook for hook in group["hooks"] if not owns_hook(hook)]
    return {**group, "hooks": kept} if kept else None


def replace_entry(settings: dict, *, uninstall: bool) -> tuple[dict, bool]:
    updated = json.loads(json.dumps(settings))
    hooks = updated.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        raise ValueError("settings.json has a non-object 'hooks' value")

    groups = (hooks or {}).get(EVENT, [])
    if not isinstance(groups, list):
        raise ValueError(f"settings.json has a non-array '{EVENT}' value")

    kept = [pruned for pruned in map(without_guard, groups) if pruned is not None]
    if not uninstall:
        kept.append(entry())

    if kept:
        updated.setdefault("hooks", {})[EVENT] = kept
    elif hooks is not None:
        updated["hooks"].pop(EVENT, None)
        if not updated["hooks"]:
            updated.pop("hooks")

    return updated, updated != settings


def plan_claude(home: Path, *, uninstall: bool) -> tuple[Path, str | None, bool]:
    path = claude_settings(home)
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    settings = json.loads(raw) if raw.strip() else {}
    if not isinstance(settings, dict):
        raise ValueError("settings.json must contain a JSON object")
    updated, changed = replace_entry(settings, uninstall=uninstall)
    if not changed:
        return path, None, False
    return path, json.dumps(updated, indent=2) + "\n", True


def plan_opencode(home: Path, *, uninstall: bool) -> tuple[Path, str | None, bool]:
    path = opencode_plugin(home)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    # Ownership keys on the marker alone, so a shim written by an earlier checkout
    # path stays updatable and removable instead of becoming unmanaged.
    if current and not current.startswith(SHIM_MARKER):
        raise ValueError(f"refusing to replace an unmanaged plugin: {path}")
    if uninstall:
        return path, None, bool(current)
    desired = shim()
    return path, desired, current != desired


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit, install, or remove the tool-call guard."
    )
    parser.add_argument("--apply", action="store_true", help="Write planned changes")
    parser.add_argument(
        "--uninstall", action="store_true", help="Remove only the managed guard"
    )
    parser.add_argument(
        "--check", action="store_true", help="Exit non-zero when state differs"
    )
    parser.add_argument(
        "--agent",
        action="append",
        choices=SUPPORTED_AGENTS,
        help="Limit to an agent; repeat for more than one",
    )
    args = parser.parse_args(argv)
    if args.apply and args.check:
        parser.error("--apply and --check cannot be combined")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    home = Path(os.environ.get("UAS_HOME") or Path.home()).expanduser()
    selected = tuple(dict.fromkeys(args.agent or SUPPORTED_AGENTS))
    planners = {"claude": plan_claude, "opencode": plan_opencode}
    drift = False

    required_sources = {
        "claude": ((GUARD, "guard hook"),),
        "opencode": ((GUARD, "guard hook"), (PLUGIN, "OpenCode plugin")),
    }
    checked: set[Path] = set()
    for agent in selected:
        for source, label in required_sources[agent]:
            if source in checked:
                continue
            checked.add(source)
            if not args.uninstall and not source.is_file():
                print(f"error: {label} is missing: {source}", file=sys.stderr)
                return 1

    for agent in selected:
        try:
            path, content, changed = planners[agent](home, uninstall=args.uninstall)
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"error: {agent}: {exc}", file=sys.stderr)
            return 1

        if not changed:
            print(f"unchanged [{agent}]: {path}")
            continue
        drift = True
        operation = "remove guard from" if args.uninstall else "install guard in"
        if not args.apply:
            print(f"would {operation} [{agent}]: {path}")
            continue
        try:
            if content is None:
                if path.exists():
                    path.unlink()
                print(f"removed [{agent}]: {path}")
            else:
                atomic_write(path, content)
                print(f"updated [{agent}]: {path}")
        except OSError as exc:
            print(f"error: {agent}: {exc}", file=sys.stderr)
            return 1

    if args.check and drift:
        return 1
    if not args.apply:
        print("guard audit complete; no changes were made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
