#!/usr/bin/env python3
"""Prefix SkillSpector SARIF artifact URIs so they resolve to the real files.

SkillSpector writes ``artifactLocation.uri`` relative to the scanned directory,
so a finding in ``skills/<skill>/SKILL.md`` is recorded as ``SKILL.md``. GitHub
code scanning resolves those against the repository root and mislabels them as
top-level files (e.g. the repo's own README). Prefixing each URI with the
scanned directory makes the findings point at the real skill files.
"""

from __future__ import annotations

import json
import sys


def prefix_uri(uri: str, prefix: str) -> str:
    # Leave absolute, already-prefixed and URL-scheme paths untouched so the
    # rewrite is idempotent and never doubles a prefix.
    if not uri or uri.startswith(prefix) or uri.startswith("/") or "://" in uri:
        return uri
    return prefix + uri


def _rewrite_physical(location: object, prefix: str) -> None:
    if not isinstance(location, dict):
        return
    physical = location.get("physicalLocation")
    if not isinstance(physical, dict):
        return
    artifact = physical.get("artifactLocation")
    if isinstance(artifact, dict) and isinstance(artifact.get("uri"), str):
        artifact["uri"] = prefix_uri(artifact["uri"], prefix)


def rewrite(sarif: dict, prefix: str) -> dict:
    runs = sarif.get("runs")
    for run in runs if isinstance(runs, list) else []:
        if not isinstance(run, dict):
            continue
        for artifact in run.get("artifacts") or []:
            if isinstance(artifact, dict):
                location = artifact.get("location")
                if isinstance(location, dict) and isinstance(location.get("uri"), str):
                    location["uri"] = prefix_uri(location["uri"], prefix)
        for result in run.get("results") or []:
            if not isinstance(result, dict):
                continue
            for key in ("locations", "relatedLocations"):
                for location in result.get(key) or []:
                    _rewrite_physical(location, prefix)
    return sarif


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: prefix_sarif.py <sarif-file> <uri-prefix>", file=sys.stderr)
        return 2
    path, prefix = argv
    if not prefix.endswith("/"):
        prefix += "/"
    with open(path, encoding="utf-8") as handle:
        sarif = json.load(handle)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rewrite(sarif, prefix), handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
