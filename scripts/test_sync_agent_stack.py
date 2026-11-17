#!/usr/bin/env python3
"""Unit tests for the agent stack profile and planner."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sync_agent_stack as stack
import sync_instructions as instructions
import validate as repository_validate


PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "default.json"
EXAMPLE_REF = "0123456789abcdef0123456789abcdef01234567"


def fixture_profile(profile: dict) -> dict:
    """Extend the default profile with synthetic entries for every planner path."""
    fixture = copy.deepcopy(profile)
    fixture["claude"]["marketplaces"].append(
        {"name": "example-market", "source": "example/market"}
    )
    fixture["claude"]["plugins"].append(
        {
            "id": "example-memory@example-market",
            "enabled": True,
            "risk": "sensitive",
            "requiresExplicitOptIn": True,
            "reason": "Synthetic plugin that persists session context.",
        }
    )
    fixture["codex"]["marketplaces"] = [
        {"name": "example-market", "source": "example/market", "ref": EXAMPLE_REF}
    ]
    fixture["codex"]["plugins"].append(
        {
            "id": "example-tools@example-market",
            "enabled": True,
            "risk": "standard",
            "reason": "Synthetic plugin from a pinned marketplace.",
        }
    )
    fixture["copilot"] = {
        "marketplaces": [{"name": "example-market", "source": "example/market"}],
        "plugins": [
            {
                "id": "example-tools@example-market",
                "enabled": True,
                "risk": "standard",
                "reason": "Synthetic Copilot CLI plugin.",
            }
        ],
    }
    fixture["opencode"] = {
        "plugins": [
            {
                "package": "@example/opencode-plugin",
                "version": "1.2.3",
                "risk": "standard",
                "reason": "Synthetic OpenCode plugin.",
            }
        ]
    }
    return fixture


class AgentStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        cls.fixture = fixture_profile(cls.profile)

    def test_profile_is_valid(self) -> None:
        self.assertEqual(stack.validate_profile(self.profile), [])
        self.assertEqual(stack.validate_profile(self.fixture), [])

    def test_plugin_versions_and_release_tags_are_validated(self) -> None:
        self.assertEqual(
            repository_validate.validate_plugin_versions(
                "1.2.3", "1.2.3", "tag", "v1.2.3"
            ),
            [],
        )
        self.assertTrue(repository_validate.validate_plugin_versions("1.2.3", "1.2.4"))
        self.assertTrue(
            repository_validate.validate_plugin_versions(
                "not-semver", "not-semver", "tag", "vnot-semver"
            )
        )
        self.assertTrue(
            repository_validate.validate_plugin_versions(
                "1.2.3", "1.2.3", "tag", "v9.9.9"
            )
        )

    def test_ai_prompts_lock_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills = root / "skills"
            (skills / "example-audit").mkdir(parents=True)
            (skills / "example-audit" / "SKILL.md").write_text("x\n", encoding="utf-8")
            lock = root / "ai-prompts.lock"
            valid = (
                "# Written by the exporter.\n"
                "source https://github.com/example/prompts\n"
                f"commit {'a' * 40}\n"
                "skill example-audit\n"
            )
            lock.write_text(valid, encoding="utf-8")
            self.assertEqual(
                repository_validate.validate_ai_prompts_lock(lock, skills), []
            )
            for broken, message in (
                (valid.replace("a" * 40, "main"), "commit"),
                (valid + "skill missing-skill\n", "missing-skill"),
                (valid + "skill example-audit\n", "twice"),
                (valid.replace("source", "origin"), "expected"),
            ):
                with self.subTest(message=message):
                    lock.write_text(broken, encoding="utf-8")
                    errors = repository_validate.validate_ai_prompts_lock(lock, skills)
                    self.assertTrue(any(message in error for error in errors), errors)

    def test_marketplace_sources_reject_unsafe_values(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["claude"]["marketplaces"][0]["source"] = (
            "https://token@example.com/repository.git"
        )
        self.assertTrue(
            any(
                "credential-free HTTPS URL" in error
                for error in stack.validate_profile(profile)
            )
        )

    def test_legacy_marketplace_source_is_accepted(self) -> None:
        desired = {
            "name": "example-market",
            "source": "example/market",
            "acceptedSources": ["legacy-owner/market"],
        }
        self.assertTrue(stack.source_matches("legacy-owner/market", desired))
        self.assertTrue(
            stack.source_matches("https://github.com/example/market.git", desired)
        )
        self.assertFalse(
            stack.source_matches("http://github.com/example/market.git", desired)
        )

    def test_disabled_plugins_are_not_installed(self) -> None:
        profile = copy.deepcopy(self.fixture)
        claude_plugin = profile["claude"]["plugins"][0]
        claude_plugin["enabled"] = False
        claude_plan = stack.build_claude_plan(
            profile, [], [], include_sensitive=False, update=False
        )
        self.assertFalse(
            any(claude_plugin["id"] in action.command for action in claude_plan.actions)
        )

        codex_plugin = profile["codex"]["plugins"][0]
        codex_plugin["enabled"] = False
        codex_plan = stack.build_codex_plan(profile, [], [], update=False)
        self.assertFalse(
            any(codex_plugin["id"] in action.command for action in codex_plan.actions)
        )

        copilot_plugin = profile["copilot"]["plugins"][0]
        copilot_plugin["enabled"] = False
        copilot_plan = stack.build_copilot_plan(profile, "", "", update=False)
        self.assertFalse(
            any(
                copilot_plugin["id"] in action.command
                for action in copilot_plan.actions
            )
        )

    def test_active_disabled_desired_plugins_are_drift(self) -> None:
        profile = copy.deepcopy(self.fixture)
        claude_plugin = profile["claude"]["plugins"][0]
        claude_plugin["enabled"] = False
        claude_plan = stack.build_claude_plan(
            profile,
            [],
            [{"id": claude_plugin["id"], "enabled": True}],
            include_sensitive=False,
            update=False,
        )
        self.assertTrue(claude_plan.drift)
        self.assertIn(
            ("claude", "plugin", "disable", claude_plugin["id"], "--scope", "user"),
            [action.command for action in claude_plan.actions],
        )

        codex_plugin = profile["codex"]["plugins"][0]
        codex_plugin["enabled"] = False
        codex_plan = stack.build_codex_plan(
            profile,
            [],
            [
                {
                    "pluginId": codex_plugin["id"],
                    "installed": True,
                    "enabled": True,
                }
            ],
            update=False,
        )
        self.assertTrue(codex_plan.drift)
        self.assertTrue(codex_plan.blocking)

        copilot_plugin = profile["copilot"]["plugins"][0]
        copilot_plugin["enabled"] = False
        copilot_plan = stack.build_copilot_plan(
            profile, "", copilot_plugin["id"], update=False
        )
        self.assertTrue(copilot_plan.drift)
        self.assertTrue(copilot_plan.blocking)

    def test_profile_validation_rejects_unhashable_agent_entries(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["mcpServers"][0]["agents"] = [{}]
        errors = stack.validate_profile(profile)
        self.assertTrue(any("agents" in error for error in errors))

    def test_planners_reject_malformed_external_inventory(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Claude marketplace"):
            stack.build_claude_plan(
                self.profile,
                [{"name": []}],
                [],
                include_sensitive=False,
                update=False,
            )
        with self.assertRaisesRegex(RuntimeError, "Codex marketplace"):
            stack.build_codex_plan(
                self.fixture,
                [
                    {
                        "name": "example-market",
                        "marketplaceSource": None,
                    }
                ],
                [],
                update=False,
            )

    def test_codex_plan_skips_unmanaged_builtin_marketplace(self) -> None:
        # Codex lists built-in openai-* marketplaces without a marketplaceSource; skip them instead of aborting.
        plan = stack.build_codex_plan(
            self.fixture,
            [{"name": "openai-curated", "root": "/tmp/plugins"}],
            [],
            update=False,
        )
        self.assertIsInstance(plan, stack.Plan)
        self.assertNotIn("missing Codex marketplace: openai-curated", plan.drift)

    def test_sensitive_plugin_requires_opt_in(self) -> None:
        plan = stack.build_claude_plan(
            self.fixture,
            [],
            [],
            include_sensitive=False,
            update=False,
        )
        commands = [action.command for action in plan.actions]
        self.assertFalse(
            any("example-memory@example-market" in command for command in commands)
        )
        self.assertFalse(
            any(
                "marketplace" in command and "example/market" in command
                for command in commands
            ),
            "a marketplace used only by a skipped plugin must not be added",
        )
        self.assertTrue(
            any("skipped sensitive plugin" in note for note in plan.notices)
        )

    def test_sensitive_plugin_can_be_planned_explicitly(self) -> None:
        plan = stack.build_claude_plan(
            self.fixture,
            [],
            [],
            include_sensitive=True,
            update=False,
        )
        commands = [action.command for action in plan.actions]
        self.assertTrue(
            any("example-memory@example-market" in command for command in commands)
        )

    def test_default_profile_declares_no_opt_in_plugins(self) -> None:
        plan = stack.build_claude_plan(
            self.profile, [], [], include_sensitive=False, update=False
        )
        self.assertFalse(
            any("sensitive plugin" in note for note in plan.notices),
            "the default profile installs completely without --include-sensitive",
        )

    def test_source_drift_blocks_apply_plan(self) -> None:
        plan = stack.build_claude_plan(
            self.profile,
            [
                {
                    "name": "humanizer",
                    "source": "github",
                    "repo": "unexpected/humanizer-fork",
                }
            ],
            [],
            include_sensitive=False,
            update=False,
        )
        self.assertTrue(any("humanizer" in item for item in plan.blocking))
        self.assertFalse(
            any(
                action.command[:4]
                == ("claude", "plugin", "install", "humanizer@humanizer")
                for action in plan.actions
            )
        )

    def test_portable_skills_use_pinned_cli_and_disable_telemetry(self) -> None:
        actions = stack.build_portable_skill_actions(
            self.profile, cache_root=Path("/tmp/test-agent-stack-cache")
        )
        skills = self.profile["portableSkills"]
        self.assertEqual(len(actions), len(skills))
        for skill, action in zip(skills, actions):
            with self.subTest(skill=skill["name"]):
                self.assertIn("skills@1.7.4", action.command)
                self.assertEqual(dict(action.environment)["DISABLE_TELEMETRY"], "1")
                self.assertEqual(
                    action.checkout.commit, skill["source"].rsplit("/", 1)[1]
                )
                self.assertNotIn(skill["source"], action.command)

    def test_codex_plan_adds_pinned_marketplace_before_plugins(self) -> None:
        plan = stack.build_codex_plan(
            self.fixture, [], [], update=False, codex_command="codex-test"
        )
        self.assertIn("missing Codex marketplace: example-market", plan.drift)
        commands = [action.command for action in plan.actions]
        self.assertEqual(
            commands[0],
            (
                "codex-test",
                "plugin",
                "marketplace",
                "add",
                "example/market",
                "--ref",
                EXAMPLE_REF,
            ),
        )
        self.assertTrue(
            any(command[-1] == "example-tools@example-market" for command in commands)
        )

    def test_codex_plan_enforces_pinned_marketplace_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = (
                Path(directory) / ".codex" / ".tmp" / "marketplaces" / "example-market"
            )
            root.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "fixture.txt"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
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
            revision = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (root / ".codex-marketplace-install.json").write_text(
                json.dumps({"revision": revision}),
                encoding="utf-8",
            )
            marketplace = {
                "name": "example-market",
                "root": str(root),
                "marketplaceSource": {
                    "sourceType": "git",
                    "source": "https://github.com/example/market.git",
                },
            }
            current_plugins = [
                {
                    "pluginId": "example-tools@example-market",
                    "name": "example-tools",
                    "marketplaceName": "example-market",
                    "version": "1.0.0",
                    "installed": True,
                    "enabled": True,
                }
            ]
            audit = stack.build_codex_plan(
                self.fixture, [marketplace], current_plugins, update=False
            )
            self.assertTrue(any("revision" in item for item in audit.drift))
            self.assertTrue(audit.blocking)

            updated = stack.build_codex_plan(
                self.fixture,
                [marketplace],
                current_plugins,
                update=True,
                codex_command="codex-test",
            )
            commands = [action.command for action in updated.actions]
            self.assertIn(
                ("codex-test", "plugin", "marketplace", "remove", "example-market"),
                commands,
            )
            self.assertIn(
                (
                    "codex-test",
                    "plugin",
                    "marketplace",
                    "add",
                    "example/market",
                    "--ref",
                    EXAMPLE_REF,
                ),
                commands,
            )
            self.assertIn(
                ("codex-test", "plugin", "remove", "example-tools@example-market"),
                commands,
            )
            self.assertIn(
                ("codex-test", "plugin", "add", "example-tools@example-market"),
                commands,
            )
            self.assertFalse(any("upgrade" in command for command in commands))
            self.assertEqual(updated.blocking, [])

    def test_copilot_plan_uses_marketplace_plugin_id(self) -> None:
        plan = stack.build_copilot_plan(
            self.fixture,
            "Included with GitHub Copilot:\n",
            "No plugins installed.\n",
            update=False,
            copilot_command="copilot-test",
        )
        commands = [action.command for action in plan.actions]
        self.assertIn(
            ("copilot-test", "plugin", "install", "example-tools@example-market"),
            commands,
        )

    def test_opencode_plugin_is_exactly_pinned(self) -> None:
        plan = stack.build_opencode_plan(
            self.fixture,
            '{"plugin": []}',
            update=False,
            opencode_command="opencode-test",
        )
        self.assertEqual(
            plan.actions[0].command,
            (
                "opencode-test",
                "plugin",
                "@example/opencode-plugin@1.2.3",
                "--global",
            ),
        )
        for config in (
            '{"plugin": [], "note": "@example/opencode-plugin@1.2.3"}',
            '{"plugin": ["@example/opencode-plugin@1.2.30"]}',
            '{"plugin": []} // @example/opencode-plugin@1.2.3',
        ):
            drifted = stack.build_opencode_plan(self.fixture, config, update=False)
            self.assertTrue(drifted.drift)

    def test_portable_skill_plan_verifies_installed_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: fixture-skill\ndescription: Test fixture.\n---\n\nFixture.\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q", str(source)], check=True)
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
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "remote",
                    "add",
                    "origin",
                    "https://github.com/example/fixture.git",
                ],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            profile = {
                "skillsCli": {
                    "package": "skills",
                    "version": "1.5.20",
                    "disableTelemetry": True,
                },
                "portableSkills": [
                    {
                        "name": "fixture-skill",
                        "source": (f"https://github.com/example/fixture/tree/{commit}"),
                        "agents": ["codex", "opencode"],
                        "scope": "global",
                    }
                ],
            }
            cache = root / "cache"
            checkout = cache / "fixture-skill" / commit
            checkout.parent.mkdir(parents=True)
            shutil.copytree(source, checkout)
            home = root / "home"
            target = home / ".agents" / "skills" / "fixture-skill"
            target.parent.mkdir(parents=True)
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git"))

            current = stack.build_portable_skill_plan(profile, "npx-test", cache, home)
            self.assertEqual(current.drift, [])
            self.assertEqual(current.actions, [])

            (target / "SKILL.md").write_text("changed\n", encoding="utf-8")
            drifted = stack.build_portable_skill_plan(profile, "npx-test", cache, home)
            self.assertTrue(any("fixture-skill" in item for item in drifted.drift))
            self.assertEqual(len(drifted.actions), 1)

    def test_instruction_plan_reports_only_real_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            drifted = stack.build_instruction_plan(home)
            self.assertEqual(len(drifted.drift), len(instructions.SUPPORTED_AGENTS))
            self.assertEqual(len(drifted.actions), 1)

            for target in instructions.targets(home).values():
                target.path.parent.mkdir(parents=True, exist_ok=True)
                target.path.write_text(instructions.BLOCK + "\n", encoding="utf-8")
            current = stack.build_instruction_plan(home)
            self.assertEqual(current.drift, [])
            self.assertEqual(current.actions, [])

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
                "@upstash/context7-mcp@4.4.4",
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
            any(
                command[:6] == ("copilot-test", "mcp", "add", "playwright", "--", "npx")
                for command in commands
            )
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
        disabled = {
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp@4.4.4"],
            },
            "enabled": False,
        }
        context7 = next(
            server
            for server in self.profile["mcpServers"]
            if server["name"] == "context7"
        )
        self.assertFalse(stack.codex_mcp_matches(context7, disabled))
        duplicate = stack.build_mcp_plan(
            self.profile,
            {
                "codex": {"context7"},
                "opencode": {"context7"},
                "copilot": {"context7", "playwright"},
            },
            profile_path=PROFILE_PATH,
            conflicting_names={"codex": {"context7"}},
        )
        self.assertTrue(
            any("codex MCP server differs" in item for item in duplicate.drift)
        )
        self.assertTrue(duplicate.blocking)

    def test_opencode_mcp_update_is_aggregated(self) -> None:
        profile = copy.deepcopy(self.profile)
        additional = copy.deepcopy(
            next(
                server
                for server in profile["mcpServers"]
                if server["name"] == "context7"
            )
        )
        additional["name"] = "context8"
        profile["mcpServers"].append(additional)
        updated = stack.build_mcp_plan(
            profile,
            {
                "codex": {"context7"},
                "opencode": set(),
                "copilot": {"context7", "playwright"},
            },
            profile_path=PROFILE_PATH,
            update=True,
            conflicting_names={"opencode": {"context7"}},
        )
        opencode_actions = [
            action
            for action in updated.actions
            if any(part.endswith("sync_opencode_config.py") for part in action.command)
        ]
        self.assertEqual(len(opencode_actions), 1)
        self.assertIn("--update", opencode_actions[0].command)

    def test_mcp_inventory_requires_matching_definitions(self) -> None:
        opencode_current, opencode_conflicts = stack.opencode_mcp_inventory(
            self.profile,
            json.dumps(
                {
                    "mcp": {
                        "context7": {
                            "type": "local",
                            "command": ["npx", "-y", "unexpected-package@1.0.0"],
                            "enabled": True,
                        }
                    }
                }
            ),
        )
        self.assertNotIn("context7", opencode_current)
        self.assertIn("context7", opencode_conflicts)

        copilot_current, copilot_conflicts = stack.copilot_mcp_inventory(
            self.profile,
            {
                "mcpServers": {
                    "playwright": {
                        "type": "local",
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp@0.0.1"],
                        "enabled": True,
                    }
                }
            },
        )
        self.assertNotIn("playwright", copilot_current)
        self.assertIn("playwright", copilot_conflicts)
        malformed_current, malformed_conflicts = stack.mcp_inventory(
            self.profile,
            "opencode",
            {"context7": "not-an-object"},
            stack.opencode_mcp_matches,
        )
        self.assertNotIn("context7", malformed_current)
        self.assertIn("context7", malformed_conflicts)
        duplicate_current, duplicate_conflicts = stack.mcp_inventory(
            self.profile,
            "opencode",
            {
                "context7": {
                    "type": "local",
                    "command": ["npx", "-y", "@upstash/context7-mcp@4.4.4"],
                    "enabled": True,
                },
                "Context7": {
                    "type": "local",
                    "command": ["npx", "-y", "@upstash/context7-mcp@4.4.4"],
                    "enabled": True,
                },
            },
            stack.opencode_mcp_matches,
        )
        self.assertNotIn("context7", duplicate_current)
        self.assertIn("context7", duplicate_conflicts)

    def test_mcp_inventory_accepts_jsonc_comments(self) -> None:
        current, conflicts = stack.opencode_mcp_inventory(
            self.profile,
            """
            {
              // Managed Context7 server.
              "mcp": {
                "context7": {
                  "type": "local",
                  "command": ["npx", "-y", "@upstash/context7-mcp@4.4.4"],
                  "enabled": true,
                },
              },
            }
            """,
        )
        self.assertIn("context7", current)
        self.assertNotIn("context7", conflicts)

    def test_jsonc_drift_blocks_automatic_opencode_merge(self) -> None:
        plan = stack.build_mcp_plan(
            self.profile,
            {
                "codex": {"context7"},
                "opencode": set(),
                "copilot": {"context7", "playwright"},
            },
            profile_path=PROFILE_PATH,
        )
        guarded = stack.guard_jsonc_opencode_plan(
            plan,
            self.profile,
            set(),
            set(),
            '{"mcp": { /* keep this comment */ }}',
        )
        self.assertTrue(guarded.blocking)
        self.assertFalse(
            any(
                any(part.endswith("sync_opencode_config.py") for part in action.command)
                for action in guarded.actions
            )
        )

    def test_mcp_matchers_reject_undeclared_execution_options(self) -> None:
        context7 = next(
            server
            for server in self.profile["mcpServers"]
            if server["name"] == "context7"
        )
        codex = {
            "enabled": True,
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp@4.4.4"],
                "env": {"UNDECLARED": "1"},
                "env_vars": [],
                "cwd": None,
            },
        }
        self.assertFalse(stack.codex_mcp_matches(context7, codex))
        opencode = {
            "type": "local",
            "command": ["npx", "-y", "@upstash/context7-mcp@4.4.4"],
            "enabled": True,
            "environment": {"UNDECLARED": "1"},
        }
        self.assertFalse(stack.opencode_mcp_matches(context7, opencode))
        copilot = {
            "type": "local",
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp@4.4.4"],
            "enabled": True,
            "tools": ["*"],
            "source": "user",
            "cwd": "/tmp",
        }
        self.assertFalse(stack.copilot_mcp_matches(context7, copilot))

    def test_empty_path_overrides_use_home_defaults(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "UAS_HOME": "",
                "UAS_SOURCE_CACHE": "",
                "XDG_CONFIG_HOME": "",
                "OPENCODE_CONFIG_DIR": "",
                "XDG_DATA_HOME": "",
                "LOCALAPPDATA": "",
            },
        ):
            home = Path.home()
            self.assertEqual(
                stack.opencode_config_path(),
                home / ".config" / "opencode" / "opencode.jsonc",
            )
            expected_data = (
                home / "AppData" / "Local"
                if os.name == "nt"
                else home / ".local" / "share"
            )
            self.assertEqual(
                stack.source_cache_root(),
                expected_data / "universal-agent-skills" / "sources",
            )

    def test_sensitive_opt_out_is_not_drift(self) -> None:
        plan = stack.build_claude_plan(
            self.fixture,
            [],
            [],
            include_sensitive=False,
            update=False,
        )
        self.assertFalse(any("example-memory" in item for item in plan.drift))

    def test_copilot_marketplace_source_drift_blocks(self) -> None:
        plan = stack.build_copilot_plan(
            self.fixture,
            "example-market https://github.com/unexpected/market-fork\n",
            "No plugins installed.\n",
            update=False,
            copilot_command="copilot-test",
        )
        self.assertTrue(any("example-market" in item for item in plan.blocking))
        self.assertFalse(
            any("marketplace" in action.command for action in plan.actions)
        )

    def test_planners_tolerate_missing_optional_sections(self) -> None:
        minimal = {
            "skillsCli": {
                "package": "skills",
                "version": "1.5.20",
                "disableTelemetry": True,
            },
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
        self.assertEqual(
            stack.build_codex_plan(minimal, [], [], update=False).actions, []
        )
        self.assertEqual(
            stack.build_copilot_plan(minimal, "", "", update=False).actions, []
        )
        self.assertEqual(
            stack.build_opencode_plan(minimal, "", update=False).actions, []
        )
        self.assertEqual(stack.build_vscode_plan(minimal, "").actions, [])
        self.assertEqual(
            stack.build_mcp_plan(minimal, {}, profile_path=PROFILE_PATH).actions, []
        )
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


class ComponentIsolation(unittest.TestCase):
    def run_main(self, *arguments: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as directory:
            stderr = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"UAS_HOME": directory}),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(stderr),
            ):
                return stack.main(list(arguments)), stderr.getvalue()

    def test_dry_run_skips_a_component_whose_command_is_missing(self) -> None:
        code, stderr = self.run_main(
            "--component", "claude", "--claude-command", "/nonexistent-cli"
        )
        self.assertEqual(code, 0)
        self.assertIn("warning: skipped claude", stderr)

    def test_apply_still_aborts_on_the_same_failure(self) -> None:
        code, stderr = self.run_main(
            "--apply", "--component", "claude", "--claude-command", "/nonexistent-cli"
        )
        self.assertEqual(code, 1)
        self.assertIn("required command not found", stderr)

    def test_check_reports_an_unevaluated_component(self) -> None:
        code, _ = self.run_main(
            "--check", "--component", "claude", "--claude-command", "/nonexistent-cli"
        )
        self.assertEqual(code, 1, "an unevaluated component cannot count as in sync")

    def test_a_section_that_declares_nothing_needs_no_cli(self) -> None:
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        profile["copilot"] = {"marketplaces": [], "plugins": []}
        profile["opencode"] = {"plugins": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            for component, flag in (
                ("copilot", "--copilot-command"),
                ("opencode", "--opencode-command"),
            ):
                with self.subTest(component=component):
                    code, stderr = self.run_main(
                        "--profile",
                        str(path),
                        "--apply",
                        "--component",
                        component,
                        flag,
                        "/nonexistent-cli",
                    )
                    self.assertEqual(code, 0, stderr)
                    self.assertNotIn("required command not found", stderr)


class VersionOption(unittest.TestCase):
    def test_every_cli_reports_the_manifest_version(self) -> None:
        scripts = Path(__file__).resolve().parent
        manifest = scripts.parent / ".claude-plugin" / "plugin.json"
        expected = (
            "universal-agent-skills "
            + json.loads(manifest.read_text(encoding="utf-8"))["version"]
        )
        for name in (
            "sync_agent_stack.py",
            "sync_instructions.py",
            "sync_hooks.py",
            "sync_opencode_config.py",
            "check_pin_freshness.py",
        ):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(scripts / name), "--version"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
