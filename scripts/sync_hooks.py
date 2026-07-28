#!/usr/bin/env python3
"""Manage the Claude Code PreToolUse guard hook for direct-installer users.

Plugin installs load hooks/hooks.json automatically; a symlink install has no
plugin root, so the same hook is registered in settings.json instead.
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
MARKER = "universal-agent-skills"
EVENT = "PreToolUse"
MATCHER = "Bash|Edit|Write|MultiEdit|NotebookEdit"


def entry() -> dict:
    return {
        "matcher": MATCHER,
        "hooks": [
            {
                "type": "command",
                "command": f'python3 "{GUARD}"',
                "timeout": 10,
                "statusMessage": "Checking always-on rules...",
            }
        ],
    }


def owned(group: object) -> bool:
    if not isinstance(group, dict):
        return False
    hooks = group.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(isinstance(hook, dict) and MARKER in str(hook.get("command", "")) for hook in hooks)


def replace_entry(settings: dict, *, uninstall: bool) -> tuple[dict, bool]:
    updated = json.loads(json.dumps(settings))
    hooks = updated.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        raise ValueError("settings.json has a non-object 'hooks' value")

    groups = (hooks or {}).get(EVENT, [])
    if not isinstance(groups, list):
        raise ValueError(f"settings.json has a non-array '{EVENT}' value")

    kept = [group for group in groups if not owned(group)]
    if not uninstall:
        kept.append(entry())

    if kept:
        updated.setdefault("hooks", {})[EVENT] = kept
    elif hooks is not None:
        updated["hooks"].pop(EVENT, None)
        if not updated["hooks"]:
            updated.pop("hooks")

    return updated, updated != settings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit, install, or remove the Claude Code guard hook.")
    parser.add_argument("--apply", action="store_true", help="Write planned changes")
    parser.add_argument("--uninstall", action="store_true", help="Remove only the managed hook")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when state differs")
    args = parser.parse_args(argv)
    if args.apply and args.check:
        parser.error("--apply and --check cannot be combined")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    home = Path(os.environ.get("UAS_HOME") or Path.home()).expanduser()
    path = home / ".claude" / "settings.json"

    if not args.uninstall and not GUARD.is_file():
        print(f"error: guard hook is missing: {GUARD}", file=sys.stderr)
        return 1

    try:
        raw = path.read_text(encoding="utf-8") if path.exists() else ""
        settings = json.loads(raw) if raw.strip() else {}
        if not isinstance(settings, dict):
            raise ValueError("settings.json must contain a JSON object")
        updated, changed = replace_entry(settings, uninstall=args.uninstall)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not changed:
        print(f"unchanged [claude]: {path}")
        return 0

    operation = "remove guard hook from" if args.uninstall else "install guard hook in"
    if not args.apply:
        print(f"would {operation} [claude]: {path}")
        if args.check:
            return 1
        print("hook audit complete; no changes were made")
        return 0

    try:
        atomic_write(path, json.dumps(updated, indent=2) + "\n")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"updated [claude]: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
