#!/usr/bin/env python3
"""Tests for managed global instruction synchronization."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import sync_instructions as instructions


SCRIPT = Path(__file__).with_name("sync_instructions.py")


class InstructionSyncTests(unittest.TestCase):
    def test_managed_block_preserves_unrelated_text(self) -> None:
        original = "# Personal rule\n\nKeep this.\n"
        installed, changed = instructions.replace_block(original, uninstall=False)
        self.assertTrue(changed)
        self.assertIn("Keep this.", installed)
        self.assertIn(instructions.START, installed)
        refreshed, changed = instructions.replace_block(installed, uninstall=False)
        self.assertFalse(changed)
        self.assertEqual(refreshed, installed)
        removed, changed = instructions.replace_block(installed, uninstall=True)
        self.assertTrue(changed)
        self.assertEqual(removed, original)

    def test_malformed_markers_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing or duplicated"):
            instructions.replace_block(instructions.START, uninstall=False)

    def test_apply_check_and_uninstall_use_overridden_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            env = {**os.environ, "UAS_HOME": str(home)}
            apply = subprocess.run(
                [str(SCRIPT), "--apply"], env=env, capture_output=True, text=True
            )
            self.assertEqual(apply.returncode, 0, apply.stderr)
            for target in instructions.targets(home).values():
                self.assertIn(instructions.START, target.path.read_text(encoding="utf-8"))
            check = subprocess.run(
                [str(SCRIPT), "--check"], env=env, capture_output=True, text=True
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            uninstall = subprocess.run(
                [str(SCRIPT), "--apply", "--uninstall"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertTrue(all(not target.path.exists() for target in instructions.targets(home).values()))


if __name__ == "__main__":
    unittest.main()
