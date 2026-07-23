#!/usr/bin/env python3
"""Unit tests for the pin freshness checker."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import check_pin_freshness as freshness


PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "default.json"


class PinFreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    def test_default_profile_pins_are_found(self) -> None:
        pins = freshness.find_pins(self.profile)
        kinds = {kind for kind, _, _, _ in pins}
        labels = {label for _, label, _, _ in pins}
        self.assertEqual(kinds, {"git", "npm"})
        self.assertIn("portable skill karpathy-guidelines", labels)
        self.assertIn("codex marketplace ponytail", labels)
        self.assertIn("skills CLI", labels)
        self.assertIn("MCP server context7", labels)
        self.assertEqual(len(pins), 9)

    def test_stale_and_fresh_pins_are_separated(self) -> None:
        pins = [
            ("git", "portable skill sample", "owner/sample", "a" * 40),
            ("npm", "skills CLI", "skills", "1.5.9"),
        ]
        stale, errors = freshness.build_report(
            pins,
            resolve_git=lambda target: "b" * 40,
            resolve_npm=lambda package: "1.5.9",
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0][0], "portable skill sample")

    def test_resolver_failures_become_warnings(self) -> None:
        def broken(target: str) -> str:
            raise RuntimeError("offline")

        stale, errors = freshness.build_report(
            [("git", "portable skill sample", "owner/sample", "a" * 40)],
            resolve_git=broken,
            resolve_npm=broken,
        )
        self.assertEqual(stale, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("offline", errors[0])

    def test_render_reports_fresh_state(self) -> None:
        text = freshness.render([], [], total=9, markdown=False)
        self.assertIn("All 9 pins match", text)


if __name__ == "__main__":
    unittest.main()
