#!/usr/bin/env python3
"""Block tool calls that break the rules a model-invoked skill cannot enforce.

Reads a Claude Code PreToolUse payload on stdin. Exit 2 blocks the call and
returns stderr to the agent; any other failure exits 0 so a broken guard never
stops legitimate work.
"""

from __future__ import annotations

import json
import re
import sys

BLOCK = 2

# Approved destructive commands re-run with this prefix; the marker keeps the
# approval visible in the transcript instead of silently relaxing the guard.
ALLOW = re.compile(r"\bUAS_ALLOW=1\b")

# Documentation and tests must be able to quote a violation. A marker on the same
# line exempts that one match and stays greppable, unlike splitting the literal.
ALLOW_INLINE = "uas-allow"

# Values shaped so they cannot validate against a real service are the documented
# way to write examples, so they must not trip the secret rules.
PLACEHOLDER = re.compile(
    r"x{4,}|\.{3}|example|placeholder|redacted|changeme|dummy|fake|sample|"
    r"your[-_]|my[-_]|<[^>]{1,40}>|\{\{|\$\{|test[-_]?key",
    re.IGNORECASE,
)

SECRETS = (
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"), "Anthropic API key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}"), "OpenAI-style API key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"), "Google API key"),
    (re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"), "private key"),
)

AI_VENDOR_NAMES = (
    "claude",
    "anthropic",
    "chatgpt",
    "gpt-[0-9]",
    "openai",
    "copilot",
    "codex",
    "cursor",
    "gemini",
    "devin",
)
# The footer rule drops names that read as ordinary prose; an attribution trailer
# keeps them because its own prefix already makes the match unambiguous.
AMBIGUOUS_IN_PROSE = ("cursor",)
AI_VENDORS = "|".join(AI_VENDOR_NAMES)
AI_FOOTER_VENDORS = "|".join(
    name for name in AI_VENDOR_NAMES if name not in AMBIGUOUS_IN_PROSE
)
AI_TRACES = (
    (
        re.compile(rf"(?mi)^[ \t]*(?:Co-Authored-By|Signed-off-by):.*(?:{AI_VENDORS})"),
        "AI attribution trailer",
    ),
    (
        re.compile(rf"(?i)generated (?:with|by) \[?(?:{AI_FOOTER_VENDORS})"),
        "generated-with footer",
    ),
    (re.compile(r"\N{ROBOT FACE}"), "robot signature"),
)

# Rules match within one shell segment; a separator ends the command that a flag
# could otherwise be borrowed from.
SEGMENT = r"[^|;&\n]*"
# The pipe rule keeps "&" because query strings use it, and a fetch joined by "&&"
# to an interpreter is still fetch-then-execute.
PIPED_SEGMENT = r"[^|;\n]*"

REMOTE_EXEC = re.compile(
    rf"\b(?:curl|wget)\b{PIPED_SEGMENT}\|\s*(?:sudo\s+)?(?:[a-z]*sh|python[0-9.]*|perl|ruby|node)\b"
)

GIT_PUSH_FORCE = re.compile(
    rf"\bgit\b{SEGMENT}\bpush\b{SEGMENT}(?<![\w-])(?:-f|--force)(?![\w-])"
)
RM_TARGET = re.compile(
    r"\brm\b(?:\s+-[A-Za-z]+)*\s+(?:-[A-Za-z]+\s+)*(/|/\*|~|~/\*|\$HOME)(?:\s|$)"
)
RM_RECURSIVE_FORCE = re.compile(
    r"\brm\b(?:\s+-[A-Za-z]*[rR][A-Za-z]*f[A-Za-z]*|\s+-[A-Za-z]*f[A-Za-z]*[rR][A-Za-z]*|\s+-[rR]\b.*\s-f\b|\s+-f\b.*\s-[rR]\b)"
)

DESTRUCTIVE = (
    (
        lambda c: bool(GIT_PUSH_FORCE.search(c)),
        "force-push (use --force-with-lease)",
    ),
    (
        lambda c: bool(re.search(rf"\bgit\b{SEGMENT}\breset\b{SEGMENT}--hard", c)),
        "git reset --hard",
    ),
    (
        lambda c: bool(re.search(r"\bgit\s+filter-(?:branch|repo)\b", c)),
        "history rewrite",
    ),
    (
        lambda c: bool(re.search(rf"\bgit\b{SEGMENT}\bpush\b{SEGMENT}--delete\b", c)),
        "remote branch or tag deletion",
    ),
    (
        lambda c: bool(RM_RECURSIVE_FORCE.search(c) and RM_TARGET.search(c)),
        "recursive delete of a root or home path",
    ),
    (
        lambda c: bool(
            re.search(
                r"(?i)\b(?:drop\s+(?:table|database|schema)|truncate\s+table)\b", c
            )
        ),
        "destructive SQL",
    ),
)


def allows_inline(text: str, index: int) -> bool:
    # The preceding line counts because code formatters relocate a trailing comment
    # when they reflow arguments, which would silently void a same-line marker.
    end = text.find("\n", index)
    head = text if end < 0 else text[:end]
    return any(ALLOW_INLINE in line.lower() for line in head.rsplit("\n", 2)[-2:])


def scan_text(text: str, rules: tuple) -> list[str]:
    findings = []
    for pattern, label in rules:
        for match in pattern.finditer(text):
            if PLACEHOLDER.search(match.group(0)):
                continue
            if allows_inline(text, match.start()):
                continue
            findings.append(label)
            break
    return findings


def edited_text(tool_input: dict) -> str:
    keys = ("content", "new_string", "new_source", "command")
    parts = [str(tool_input.get(key, "")) for key in keys]
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        parts += [
            str(edit.get("new_string", "")) for edit in edits if isinstance(edit, dict)
        ]
    return "\n".join(part for part in parts if part)


def review(tool_name: str, tool_input: dict) -> list[str]:
    text = edited_text(tool_input)
    if not text:
        return []

    findings = scan_text(text, SECRETS + AI_TRACES)
    if tool_name != "Bash":
        return findings

    # Matching is on raw command text, so a destructive command quoted inside a
    # string is blocked too; UAS_ALLOW=1 covers that case rather than a shell parser.
    command = str(tool_input.get("command", ""))
    if REMOTE_EXEC.search(command):
        findings.append("remote script piped into an interpreter")
    if not ALLOW.search(command):
        findings += [label for predicate, label in DESTRUCTIVE if predicate(command)]
    return findings


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool_name = str(payload.get("tool_name", ""))
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return 0
        findings = review(tool_name, tool_input)
    except (OSError, ValueError, TypeError, AttributeError, re.error):
        return 0

    if not findings:
        return 0

    print(
        "universal-agent-skills guard blocked this call: "
        + "; ".join(dict.fromkeys(findings))
        + ".\nRemove the violation. To keep it on purpose, add uas-allow on the same "
        "line; for an approved destructive command ask the user first and re-run it "
        "prefixed with UAS_ALLOW=1.",
        file=sys.stderr,
    )
    return BLOCK


if __name__ == "__main__":
    raise SystemExit(main())
