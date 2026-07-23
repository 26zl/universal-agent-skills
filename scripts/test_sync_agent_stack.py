#!/usr/bin/env python3
"""Unit tests for the agent stack profile and planner."""

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import sync_agent_stack as stack


PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "default.json"


class AgentStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    def test_profile_is_valid(self) -> None:
        self.assertEqual(stack.validate_profile(self.profile), [])

    def test_marketplace_sources_reject_unsafe_values(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["claude"]["marketplaces"][0]["source"] = (
            "https://token@example.com/repository.git"
        )
        self.assertTrue(
            any("credential-free HTTPS URL" in error for error in stack.validate_profile(profile))
        )

    def test_karpathy_legacy_source_is_accepted(self) -> None:
        desired = next(
            item
            for item in self.profile["claude"]["marketplaces"]
            if item["name"] == "karpathy-skills"
        )
        self.assertTrue(
            stack.source_matches("forrestchang/andrej-karpathy-skills", desired)
        )

    def test_sensitive_plugin_requires_opt_in(self) -> None:
        plan = stack.build_claude_plan(
            self.profile,
            [],
            [],
            include_sensitive=False,
            update=False,
        )
        commands = [action.command for action in plan.actions]
        self.assertFalse(any("claude-mem@thedotmack" in command for command in commands))
        self.assertTrue(any("skipped sensitive plugin" in note for note in plan.notices))

    def test_sensitive_plugin_can_be_planned_explicitly(self) -> None:
        plan = stack.build_claude_plan(
            self.profile,
            [],
            [],
            include_sensitive=True,
            update=False,
        )
        commands = [action.command for action in plan.actions]
        self.assertTrue(any("claude-mem@thedotmack" in command for command in commands))

    def test_source_drift_blocks_apply_plan(self) -> None:
        plan = stack.build_claude_plan(
            self.profile,
            [
                {
                    "name": "ecc",
                    "source": "github",
                    "repo": "unexpected/ecc-fork",
                }
            ],
            [],
            include_sensitive=False,
            update=False,
        )
        self.assertTrue(any("ecc" in item for item in plan.blocking))
        self.assertFalse(
            any(
                action.command[:4] == ("claude", "plugin", "install", "ecc@ecc")
                for action in plan.actions
            )
        )

    def test_portable_skills_use_pinned_cli_and_disable_telemetry(self) -> None:
        actions = stack.build_portable_skill_actions(
            self.profile, cache_root=Path("/tmp/test-agent-stack-cache")
        )
        self.assertEqual(len(actions), 3)
        self.assertIn("skills@1.5.9", actions[0].command)
        self.assertEqual(dict(actions[0].environment)["DISABLE_TELEMETRY"], "1")
        self.assertEqual(
            actions[0].checkout.commit,
            "2c606141936f1eeef17fa3043a72095b4765b9c2",
        )
        self.assertNotIn(self.profile["portableSkills"][0]["source"], actions[0].command)

    def test_codex_plan_adds_pinned_marketplace_before_plugins(self) -> None:
        plan = stack.build_codex_plan(
            self.profile, [], [], update=False, codex_command="codex-test"
        )
        self.assertIn("missing Codex marketplace: ponytail", plan.drift)
        commands = [action.command for action in plan.actions]
        self.assertEqual(
            commands[0],
            (
                "codex-test",
                "plugin",
                "marketplace",
                "add",
                "DietrichGebert/ponytail",
                "--ref",
                "16f29800fd2681bdf24f3eb4ccffe38be3baec6b",
            ),
        )
        self.assertTrue(any(command[-1] == "ponytail@ponytail" for command in commands))

    def test_copilot_plan_uses_marketplace_plugin_id(self) -> None:
        plan = stack.build_copilot_plan(
            self.profile,
            "Included with GitHub Copilot:\n",
            "No plugins installed.\n",
            update=False,
            copilot_command="copilot-test",
        )
        commands = [action.command for action in plan.actions]
        self.assertIn(
            ("copilot-test", "plugin", "install", "ponytail@ponytail"), commands
        )

    def test_opencode_plugin_is_exactly_pinned(self) -> None:
        plan = stack.build_opencode_plan(
            self.profile, '{"plugin": []}', update=False, opencode_command="opencode-test"
        )
        self.assertEqual(
            plan.actions[0].command,
            (
                "opencode-test",
                "plugin",
                "@dietrichgebert/ponytail@4.8.4",
                "--global",
            ),
        )

    def test_native_ecc_installers_are_target_specific(self) -> None:
        actions = stack.build_native_installer_actions(
            self.profile, "npx-test", Path("/tmp/missing-ecc-state")
        )
        self.assertEqual(len(actions), 1)
        self.assertTrue(
            all("--package=ecc-universal@2.0.0" in action.command for action in actions)
        )
        self.assertIn("opencode", actions[0].command)

    def test_mcp_plan_uses_each_clients_supported_syntax(self) -> None:
        plan = stack.build_mcp_plan(
            self.profile,
            {"codex": set(), "opencode": set(), "copilot": set()},
            profile_path=PROFILE_PATH,
            codex_command="codex-test",
            opencode_command="opencode-test",
            copilot_command="copilot-test",
        )
        commands = [action.command for action in plan.actions]
        self.assertIn(
            (
                "codex-test",
                "mcp",
                "add",
                "context7",
                "--",
                "npx",
                "-y",
                "@upstash/context7-mcp@3.2.4",
            ),
            commands,
        )
        self.assertTrue(
            any(
                any(part.endswith("sync_opencode_config.py") for part in command)
                and command[-1] == "--apply"
                and "--profile" in command
                and str(PROFILE_PATH) in command
                for command in commands
            )
        )
        self.assertTrue(
            any(command[:6] == ("copilot-test", "mcp", "add", "playwright", "--", "npx") for command in commands)
        )

    def test_mcp_conflict_requires_update(self) -> None:
        plan = stack.build_mcp_plan(
            self.profile,
            {"codex": set(), "opencode": set(), "copilot": set()},
            profile_path=PROFILE_PATH,
            conflicting_names={"codex": {"context7"}},
            codex_command="codex-test",
        )
        self.assertTrue(any("--update" in item for item in plan.blocking))
        self.assertFalse(
            any(action.command[1:3] == ("mcp", "remove") for action in plan.actions)
        )
        updated = stack.build_mcp_plan(
            self.profile,
            {"codex": set(), "opencode": set(), "copilot": set()},
            profile_path=PROFILE_PATH,
            update=True,
            conflicting_names={"codex": {"context7"}},
            codex_command="codex-test",
        )
        self.assertIn(
            ("codex-test", "mcp", "remove", "context7"),
            [action.command for action in updated.actions],
        )
        self.assertEqual(updated.blocking, [])

    def test_sensitive_opt_out_is_not_drift(self) -> None:
        plan = stack.build_claude_plan(
            self.profile,
            [],
            [],
            include_sensitive=False,
            update=False,
        )
        self.assertFalse(any("claude-mem" in item for item in plan.drift))

    def test_copilot_marketplace_source_drift_blocks(self) -> None:
        plan = stack.build_copilot_plan(
            self.profile,
            "ponytail https://github.com/unexpected/ponytail-fork\n",
            "No plugins installed.\n",
            update=False,
            copilot_command="copilot-test",
        )
        self.assertTrue(any("ponytail" in item for item in plan.blocking))
        self.assertFalse(
            any("marketplace" in action.command for action in plan.actions)
        )

    def test_planners_tolerate_missing_optional_sections(self) -> None:
        minimal = {
            "skillsCli": {"package": "skills", "version": "1.5.9", "disableTelemetry": True},
            "claude": {},
            "codex": {},
            "copilot": {},
            "opencode": {},
            "vscode": {},
        }
        self.assertEqual(
            stack.build_claude_plan(
                minimal, [], [], include_sensitive=False, update=False
            ).actions,
            [],
        )
        self.assertEqual(stack.build_codex_plan(minimal, [], [], update=False).actions, [])
        self.assertEqual(stack.build_copilot_plan(minimal, "", "", update=False).actions, [])
        self.assertEqual(stack.build_opencode_plan(minimal, "", update=False).actions, [])
        self.assertEqual(stack.build_vscode_plan(minimal, "").actions, [])
        self.assertEqual(
            stack.build_mcp_plan(minimal, {}, profile_path=PROFILE_PATH).actions, []
        )
        self.assertEqual(stack.build_native_installer_actions(minimal, "npx-test"), [])
        self.assertEqual(stack.build_portable_skill_actions(minimal, "npx-test"), [])

    def test_pinned_checkout_is_verified_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            (source / "SKILL.md").write_text("test\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "SKILL.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    "fixture",
                ],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            checkout = stack.PinnedCheckout(source.as_uri(), commit, root / "cache")
            stack.ensure_pinned_checkout(checkout)
            stack.ensure_pinned_checkout(checkout)
            self.assertEqual((checkout.path / "SKILL.md").read_text(), "test\n")
            (checkout.path / "SKILL.md").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "local changes"):
                stack.ensure_pinned_checkout(checkout)


if __name__ == "__main__":
    unittest.main()
