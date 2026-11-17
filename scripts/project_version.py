"""Report the version of this checkout from its plugin manifest."""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / ".claude-plugin" / "plugin.json"


def version_string() -> str:
    try:
        version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        version = "unknown"
    return f"universal-agent-skills {version}"
