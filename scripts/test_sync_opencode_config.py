#!/usr/bin/env python3
"""Tests for the OpenCode MCP configuration merge."""

from __future__ import annotations

import unittest

import sync_opencode_config as sync


class OpenCodeConfigTests(unittest.TestCase):
    def test_merge_preserves_existing_keys(self) -> None:
        current = {"$schema": "test", "plugin": ["example"]}
        desired = {
            "context7": {
                "type": "local",
                "command": ["npx", "-y", "context7@1.2.3"],
                "enabled": True,
            }
        }
        updated, changed = sync.merge_config(current, desired)
        self.assertEqual(changed, ["context7"])
        self.assertEqual(updated["plugin"], ["example"])
        refreshed, changed = sync.merge_config(updated, desired)
        self.assertEqual(changed, [])
        self.assertEqual(refreshed, updated)

    def test_unmanaged_conflict_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            sync.merge_config(
                {"mcp": {"context7": {"type": "remote", "url": "https://example"}}},
                {"context7": {"type": "local", "command": ["context7"]}},
            )


if __name__ == "__main__":
    unittest.main()
