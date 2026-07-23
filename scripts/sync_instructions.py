#!/usr/bin/env python3
"""Safely manage the short global coding-comment rule for supported agents."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


START = "<!-- universal-agent-skills:comments:start -->"
END = "<!-- universal-agent-skills:comments:end -->"
RULES = """## Code comments

- Prefer self-explanatory code.
- Add comments only for non-obvious intent, invariants, constraints, workarounds, security boundaries, or surprising tradeoffs.
- Keep comments factual, neutral, and normally one sentence.
- Never narrate prompts, AI use, the user-agent collaboration, debugging history, or obvious code behavior in comments.
- Preserve required API documentation, license notices, generated markers, and safety-critical explanations."""
BLOCK = f"{START}\n{RULES}\n{END}"
SUPPORTED_AGENTS = ("codex", "claude", "opencode", "copilot")


@dataclass(frozen=True)
class InstructionTarget:
    agent: str
    path: Path


def targets(home: Path) -> dict[str, InstructionTarget]:
    return {
        "codex": InstructionTarget("codex", home / ".codex" / "AGENTS.md"),
        "claude": InstructionTarget("claude", home / ".claude" / "CLAUDE.md"),
        "opencode": InstructionTarget(
            "opencode", home / ".config" / "opencode" / "AGENTS.md"
        ),
        "copilot": InstructionTarget(
            "copilot", home / ".copilot" / "copilot-instructions.md"
        ),
    }


def replace_block(text: str, *, uninstall: bool) -> tuple[str, bool]:
    starts = text.count(START)
    ends = text.count(END)
    if starts != ends or starts > 1:
        raise ValueError("managed instruction markers are missing or duplicated")

    if starts == 1:
        start = text.index(START)
        end = text.index(END, start) + len(END)
        before = text[:start].rstrip()
        after = text[end:].lstrip()
        parts = [part for part in (before, "" if uninstall else BLOCK, after) if part]
        updated = "\n\n".join(parts)
    elif uninstall:
        updated = text.rstrip()
    else:
        prefix = text.rstrip()
        updated = f"{prefix}\n\n{BLOCK}" if prefix else BLOCK

    if updated:
        updated += "\n"
    return updated, updated != text


def atomic_write(path: Path, text: str) -> None:
    if path.is_symlink():
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = path.stat().st_mode if path.exists() else None
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
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
        description="Audit, install, or remove managed global agent instructions."
    )
    parser.add_argument("--apply", action="store_true", help="Write planned changes")
    parser.add_argument("--uninstall", action="store_true", help="Remove only the managed block")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when state differs")
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
    target_map = targets(home)
    selected = tuple(dict.fromkeys(args.agent or SUPPORTED_AGENTS))
    drift = False

    for agent in selected:
        target = target_map[agent]
        try:
            current = target.path.read_text(encoding="utf-8") if target.path.exists() else ""
            updated, changed = replace_block(current, uninstall=args.uninstall)
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"error: {agent}: {exc}", file=sys.stderr)
            return 1

        if not changed:
            print(f"unchanged [{agent}]: {target.path}")
            continue
        drift = True
        operation = "remove managed instructions from" if args.uninstall else "install instructions in"
        if not args.apply:
            print(f"would {operation} [{agent}]: {target.path}")
            continue
        try:
            if args.uninstall and not updated:
                if target.path.exists():
                    target.path.unlink()
                    print(f"removed empty managed file [{agent}]: {target.path}")
            else:
                atomic_write(target.path, updated)
                print(f"updated [{agent}]: {target.path}")
        except OSError as exc:
            print(f"error: {agent}: {exc}", file=sys.stderr)
            return 1

    if args.check and drift:
        return 1
    if not args.apply:
        print("instruction audit complete; no changes were made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
