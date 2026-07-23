#!/usr/bin/env python3
"""Safely merge managed MCP entries into a valid OpenCode JSON config."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "profiles" / "default.json"


def config_path(home: Path) -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    jsonc = config_home / "opencode" / "opencode.jsonc"
    plain = config_home / "opencode" / "opencode.json"
    return jsonc if jsonc.exists() or not plain.exists() else plain


def desired_servers(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    desired: dict[str, dict[str, Any]] = {}
    for server in profile["mcpServers"]:
        if "opencode" not in server["agents"]:
            continue
        if server["transport"] == "stdio":
            desired[server["name"]] = {
                "type": "local",
                "command": server["command"],
                "enabled": True,
            }
        else:
            desired[server["name"]] = {
                "type": "remote",
                "url": server["url"],
                "enabled": True,
            }
    return desired


def merge_config(
    current: dict[str, Any], desired: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    updated = json.loads(json.dumps(current))
    mcp = updated.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        raise ValueError("top-level 'mcp' value must be an object")
    changed: list[str] = []
    for name, definition in desired.items():
        if mcp.get(name) == definition:
            continue
        if name in mcp:
            raise ValueError(
                f"refusing to replace unmanaged OpenCode MCP entry: {name}"
            )
        mcp[name] = definition
        changed.append(name)
    return updated, changed


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink():
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = path.stat().st_mode if path.exists() else None
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if existing_mode is not None:
            os.chmod(temporary, existing_mode)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or merge managed MCP entries into OpenCode configuration."
    )
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.check:
        parser.error("--apply and --check cannot be combined")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    home = Path(os.environ.get("UAS_HOME", Path.home())).expanduser()
    path = config_path(home)
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "$schema": "https://opencode.ai/config.json"
        }
        if not isinstance(current, dict):
            raise ValueError("OpenCode config must be a JSON object")
        updated, changed = merge_config(current, desired_servers(profile))
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(
            f"error: cannot safely merge {path}: {exc}; comments must be removed or the MCP entry added manually",
            file=sys.stderr,
        )
        return 1

    if not changed:
        print(f"unchanged [opencode MCP]: {path}")
        return 0
    print(f"{'updating' if args.apply else 'would update'} [opencode MCP]: {path}")
    print("managed MCP entries: " + ", ".join(changed))
    if args.check:
        return 1
    if args.apply:
        try:
            atomic_write(path, updated)
        except OSError as exc:
            print(f"error: cannot write {path}: {exc}", file=sys.stderr)
            return 1
    else:
        print("OpenCode config audit complete; no changes were made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
