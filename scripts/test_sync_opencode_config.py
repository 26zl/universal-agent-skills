#!/usr/bin/env python3
"""Tests for the OpenCode MCP configuration merge."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_explicit_update_replaces_profile_named_conflict(self) -> None:
        current = {
            "mcp": {
                "context7": {
                    "type": "local",
                    "command": ["npx", "-y", "unexpected-package@1.0.0"],
                    "enabled": True,
                }
            }
        }
        desired = {
            "context7": {
                "type": "local",
                "command": ["npx", "-y", "@upstash/context7-mcp@3.2.5"],
                "enabled": True,
            }
        }
        updated, changed = sync.merge_config(current, desired, replace_conflicts=True)
        self.assertEqual(updated["mcp"]["context7"], desired["context7"])
        self.assertEqual(changed, ["context7"])

    def test_empty_xdg_config_home_uses_home_default(self) -> None:
        home = Path("/expected-home")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
            self.assertEqual(
                sync.config_path(home),
                home / ".config" / "opencode" / "opencode.jsonc",
            )

    def test_opencode_config_dir_applies_to_the_real_home_only(self) -> None:
        redirected = Path("/expected-home")
        with mock.patch.dict(
            os.environ, {"OPENCODE_CONFIG_DIR": "/occ", "XDG_CONFIG_HOME": "/xdg"}
        ):
            self.assertEqual(sync.config_root(Path.home()), Path("/occ"))
            self.assertEqual(
                sync.config_root(redirected), redirected / ".config" / "opencode"
            )
        with mock.patch.dict(
            os.environ, {"OPENCODE_CONFIG_DIR": "", "XDG_CONFIG_HOME": "/xdg"}
        ):
            self.assertEqual(sync.config_root(Path.home()), Path("/xdg/opencode"))

    def test_ecc_managed_opencode_json_is_left_to_ecc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".config" / "opencode"
            root.mkdir(parents=True)
            plain = root / "opencode.json"
            plain.write_text('{"plugin": ["./plugins"]}\n', encoding="utf-8")
            self.assertEqual(sync.config_path(Path(directory)), plain)
            (root / sync.ECC_STATE_NAME).write_text(
                json.dumps(
                    {
                        "schemaVersion": "ecc.install.v1",
                        "operations": [
                            {
                                "kind": "copy-file",
                                "ownership": "managed",
                                "destinationPath": str(plain),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync.config_path(Path(directory)), root / "opencode.jsonc")


if __name__ == "__main__":
    unittest.main()
