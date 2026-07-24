#!/usr/bin/env python3
"""Audit or reconcile the external agent stack declared in a profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import sync_instructions as instruction_sync


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "profiles" / "default.json"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PLUGIN_ID_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*@[a-z0-9]+(?:-[a-z0-9]+)*$"
)
PINNED_GITHUB_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+)/tree/(?P<commit>[0-9a-f]{40})$"
)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
NPM_PACKAGE_RE = re.compile(
    r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$"
)
EXECUTABLE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
VSCODE_EXTENSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.[A-Za-z0-9][A-Za-z0-9._-]*$")
GITHUB_SHORTHAND_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$"
)
ALLOWED_RISKS = {"standard", "elevated", "sensitive"}
ALLOWED_SKILL_AGENTS = {"claude-code", "codex", "opencode"}
ALLOWED_MCP_AGENTS = {"codex", "opencode", "copilot"}


@dataclass(frozen=True)
class Action:
    label: str
    command: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()
    checkout: PinnedCheckout | None = None


@dataclass(frozen=True)
class PinnedCheckout:
    repository: str
    commit: str
    path: Path


@dataclass
class Plan:
    actions: list[Action]
    notices: list[str]
    drift: list[str]
    blocking: list[str]


def load_profile(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("profile must be a JSON object")
    return value


def normalize_source(value: str) -> str:
    source = value.strip().lower()
    if source.startswith("git@github.com:"):
        source = source.removeprefix("git@github.com:")
    for prefix in ("git+https://github.com/", "https://github.com/"):
        if source.startswith(prefix):
            source = source.removeprefix(prefix)
            break
    return source.removesuffix(".git").rstrip("/")


def is_safe_marketplace_source(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith("-"):
        return False
    if GITHUB_SHORTHAND_RE.fullmatch(value):
        return all(part not in {".", ".."} for part in value.split("/"))
    parsed = urlsplit(value)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and parsed.path not in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if profile.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if not NAME_RE.fullmatch(str(profile.get("name", ""))):
        errors.append("profile name must be lowercase kebab-case")

    skills_cli = profile.get("skillsCli")
    if not isinstance(skills_cli, dict):
        errors.append("skillsCli must be an object")
    else:
        if skills_cli.get("package") != "skills":
            errors.append("skillsCli.package must be 'skills'")
        if not SEMVER_RE.fullmatch(str(skills_cli.get("version", ""))):
            errors.append("skillsCli.version must be an exact semantic version")
        if not isinstance(skills_cli.get("disableTelemetry"), bool):
            errors.append("skillsCli.disableTelemetry must be a boolean")

    claude = profile.get("claude")
    if not isinstance(claude, dict):
        errors.append("claude must be an object")
        claude = {}

    marketplaces = claude.get("marketplaces", [])
    if not isinstance(marketplaces, list):
        errors.append("claude.marketplaces must be an array")
        marketplaces = []
    marketplace_names: set[str] = set()
    for index, marketplace in enumerate(marketplaces):
        prefix = f"claude.marketplaces[{index}]"
        if not isinstance(marketplace, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = str(marketplace.get("name") or "")
        source = marketplace.get("source")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{prefix}.name must be lowercase kebab-case")
        elif name in marketplace_names:
            errors.append(f"{prefix}.name is duplicated")
        else:
            marketplace_names.add(name)
        if not is_safe_marketplace_source(source):
            errors.append(
                f"{prefix}.source must be a GitHub owner/repo or credential-free HTTPS URL"
            )
        aliases = marketplace.get("acceptedSources", [])
        if not isinstance(aliases, list) or not all(
            is_safe_marketplace_source(alias) for alias in aliases
        ):
            errors.append(f"{prefix}.acceptedSources must contain safe strings")

    plugins = claude.get("plugins", [])
    if not isinstance(plugins, list):
        errors.append("claude.plugins must be an array")
        plugins = []
    plugin_ids: set[str] = set()
    for index, plugin in enumerate(plugins):
        prefix = f"claude.plugins[{index}]"
        if not isinstance(plugin, dict):
            errors.append(f"{prefix} must be an object")
            continue
        plugin_id = str(plugin.get("id") or "")
        if not PLUGIN_ID_RE.fullmatch(plugin_id):
            errors.append(f"{prefix}.id must be plugin@marketplace in kebab-case")
        elif plugin_id in plugin_ids:
            errors.append(f"{prefix}.id is duplicated")
        else:
            plugin_ids.add(plugin_id)
        if "@" in plugin_id:
            marketplace_name = plugin_id.rsplit("@", 1)[1]
            if marketplace_name not in marketplace_names:
                errors.append(f"{prefix}.id references an undeclared marketplace")
        if not isinstance(plugin.get("enabled"), bool):
            errors.append(f"{prefix}.enabled must be a boolean")
        if plugin.get("risk") not in ALLOWED_RISKS:
            errors.append(f"{prefix}.risk must be standard, elevated, or sensitive")
        if not isinstance(plugin.get("reason"), str) or not plugin.get("reason"):
            errors.append(f"{prefix}.reason must be a non-empty string")
        explicit = plugin.get("requiresExplicitOptIn", False)
        if not isinstance(explicit, bool):
            errors.append(f"{prefix}.requiresExplicitOptIn must be a boolean")
        if explicit and plugin.get("risk") != "sensitive":
            errors.append(f"{prefix} can require explicit opt-in only when risk is sensitive")

    codex = profile.get("codex")
    if not isinstance(codex, dict):
        errors.append("codex must be an object")
        codex = {}
    errors.extend(validate_native_plugin_section("codex", codex, require_ref=True))

    copilot = profile.get("copilot")
    if not isinstance(copilot, dict):
        errors.append("copilot must be an object")
        copilot = {}
    errors.extend(validate_native_plugin_section("copilot", copilot, require_ref=False))

    opencode = profile.get("opencode")
    if not isinstance(opencode, dict):
        errors.append("opencode must be an object")
        opencode = {}
    opencode_plugins = opencode.get("plugins", [])
    if not isinstance(opencode_plugins, list):
        errors.append("opencode.plugins must be an array")
        opencode_plugins = []
    seen_packages: set[str] = set()
    for index, plugin in enumerate(opencode_plugins):
        prefix = f"opencode.plugins[{index}]"
        if not isinstance(plugin, dict):
            errors.append(f"{prefix} must be an object")
            continue
        package = str(plugin.get("package") or "")
        if not NPM_PACKAGE_RE.fullmatch(package):
            errors.append(f"{prefix}.package must be a safe npm package name")
        elif package in seen_packages:
            errors.append(f"{prefix}.package is duplicated")
        else:
            seen_packages.add(package)
        if not SEMVER_RE.fullmatch(str(plugin.get("version", ""))):
            errors.append(f"{prefix}.version must be an exact semantic version")
        errors.extend(validate_risk_reason(prefix, plugin))

    vscode = profile.get("vscode")
    if not isinstance(vscode, dict):
        errors.append("vscode must be an object")
        vscode = {}
    extensions = vscode.get("extensions", [])
    if not isinstance(extensions, list):
        errors.append("vscode.extensions must be an array")
        extensions = []
    extension_ids: set[str] = set()
    for index, extension in enumerate(extensions):
        prefix = f"vscode.extensions[{index}]"
        if not isinstance(extension, dict):
            errors.append(f"{prefix} must be an object")
            continue
        extension_id = extension.get("id")
        if not VSCODE_EXTENSION_RE.fullmatch(str(extension_id or "")):
            errors.append(f"{prefix}.id must be a publisher.extension identifier")
        elif str(extension_id).lower() in extension_ids:
            errors.append(f"{prefix}.id is duplicated")
        else:
            extension_ids.add(str(extension_id).lower())
        errors.extend(validate_risk_reason(prefix, extension))

    mcp_servers = profile.get("mcpServers", [])
    if not isinstance(mcp_servers, list):
        errors.append("mcpServers must be an array")
        mcp_servers = []
    mcp_names: set[str] = set()
    for index, server in enumerate(mcp_servers):
        prefix = f"mcpServers[{index}]"
        if not isinstance(server, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = str(server.get("name") or "")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{prefix}.name must be lowercase kebab-case")
        elif name in mcp_names:
            errors.append(f"{prefix}.name is duplicated")
        else:
            mcp_names.add(name)
        transport = server.get("transport")
        if transport == "http":
            parsed = urlsplit(str(server.get("url", "")))
            if not (
                parsed.scheme == "https"
                and parsed.hostname
                and parsed.username is None
                and parsed.password is None
                and not parsed.fragment
            ):
                errors.append(f"{prefix}.url must be a credential-free HTTPS URL")
        elif transport == "stdio":
            command = server.get("command")
            if not isinstance(command, list) or not command or not all(
                isinstance(item, str) and item and "\x00" not in item for item in command
            ):
                errors.append(f"{prefix}.command must contain non-empty strings")
        else:
            errors.append(f"{prefix}.transport must be http or stdio")
        agents = server.get("agents")
        if not isinstance(agents, list) or not agents:
            errors.append(f"{prefix}.agents must be a non-empty array")
        elif (
            not all(isinstance(agent, str) for agent in agents)
            or len(set(agents)) != len(agents)
            or not set(agents) <= ALLOWED_MCP_AGENTS
        ):
            errors.append(f"{prefix}.agents contains duplicates or unsupported agents")
        errors.extend(validate_risk_reason(prefix, server))

    native_installers = profile.get("nativeInstallers", [])
    if not isinstance(native_installers, list):
        errors.append("nativeInstallers must be an array")
        native_installers = []
    installer_names: set[str] = set()
    for index, installer in enumerate(native_installers):
        prefix = f"nativeInstallers[{index}]"
        if not isinstance(installer, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = str(installer.get("name") or "")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{prefix}.name must be lowercase kebab-case")
        elif name in installer_names:
            errors.append(f"{prefix}.name is duplicated")
        else:
            installer_names.add(name)
        if not NPM_PACKAGE_RE.fullmatch(str(installer.get("package", ""))):
            errors.append(f"{prefix}.package must be a safe npm package name")
        if not SEMVER_RE.fullmatch(str(installer.get("version", ""))):
            errors.append(f"{prefix}.version must be an exact semantic version")
        if not EXECUTABLE_RE.fullmatch(str(installer.get("executable", ""))):
            errors.append(f"{prefix}.executable must be a safe executable name")
        state_path = Path(str(installer.get("statePath", "")))
        if (
            str(state_path) in {"", "."}
            or state_path.is_absolute()
            or ".." in state_path.parts
        ):
            errors.append(f"{prefix}.statePath must be a safe home-relative path")
        arguments = installer.get("arguments")
        if not isinstance(arguments, list) or not all(
            isinstance(item, str) and item and "\x00" not in item for item in arguments
        ):
            errors.append(f"{prefix}.arguments must contain non-empty strings")
        errors.extend(validate_risk_reason(prefix, installer))

    portable = profile.get("portableSkills", [])
    if not isinstance(portable, list):
        errors.append("portableSkills must be an array")
        portable = []
    portable_names: set[str] = set()
    for index, skill in enumerate(portable):
        prefix = f"portableSkills[{index}]"
        if not isinstance(skill, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = str(skill.get("name") or "")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{prefix}.name must be lowercase kebab-case")
        elif name in portable_names:
            errors.append(f"{prefix}.name is duplicated")
        else:
            portable_names.add(name)
        if not PINNED_GITHUB_RE.fullmatch(str(skill.get("source", ""))):
            errors.append(f"{prefix}.source must be a GitHub URL pinned to a full commit")
        agents = skill.get("agents")
        if not isinstance(agents, list) or not agents:
            errors.append(f"{prefix}.agents must be a non-empty array")
        elif (
            not all(isinstance(agent, str) for agent in agents)
            or len(set(agents)) != len(agents)
            or not set(agents) <= ALLOWED_SKILL_AGENTS
        ):
            errors.append(f"{prefix}.agents contains duplicates or unsupported agents")
        if skill.get("scope") != "global":
            errors.append(f"{prefix}.scope must be global")
    return errors


def validate_risk_reason(prefix: str, item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if item.get("risk") not in ALLOWED_RISKS:
        errors.append(f"{prefix}.risk must be standard, elevated, or sensitive")
    if not isinstance(item.get("reason"), str) or not item.get("reason"):
        errors.append(f"{prefix}.reason must be a non-empty string")
    return errors


def validate_native_plugin_section(
    section_name: str, section: dict[str, Any], *, require_ref: bool
) -> list[str]:
    errors: list[str] = []
    marketplaces = section.get("marketplaces", [])
    if not isinstance(marketplaces, list):
        return [f"{section_name}.marketplaces must be an array"]
    marketplace_names: set[str] = set()
    for index, marketplace in enumerate(marketplaces):
        prefix = f"{section_name}.marketplaces[{index}]"
        if not isinstance(marketplace, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = str(marketplace.get("name") or "")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{prefix}.name must be lowercase kebab-case")
        elif name in marketplace_names:
            errors.append(f"{prefix}.name is duplicated")
        else:
            marketplace_names.add(name)
        if not is_safe_marketplace_source(marketplace.get("source")):
            errors.append(f"{prefix}.source must be a safe marketplace source")
        if require_ref and not FULL_SHA_RE.fullmatch(str(marketplace.get("ref", ""))):
            errors.append(f"{prefix}.ref must be a full Git commit")

    plugins = section.get("plugins", [])
    if not isinstance(plugins, list):
        return [*errors, f"{section_name}.plugins must be an array"]
    plugin_ids: set[str] = set()
    for index, plugin in enumerate(plugins):
        prefix = f"{section_name}.plugins[{index}]"
        if not isinstance(plugin, dict):
            errors.append(f"{prefix} must be an object")
            continue
        plugin_id = str(plugin.get("id") or "")
        if not PLUGIN_ID_RE.fullmatch(plugin_id):
            errors.append(f"{prefix}.id must be plugin@marketplace in kebab-case")
        elif plugin_id in plugin_ids:
            errors.append(f"{prefix}.id is duplicated")
        else:
            plugin_ids.add(plugin_id)
        if "@" in plugin_id:
            market_name = plugin_id.rsplit("@", 1)[1]
            if market_name not in marketplace_names and not market_name.startswith("openai-"):
                errors.append(f"{prefix}.id references an undeclared marketplace")
        if not isinstance(plugin.get("enabled"), bool):
            errors.append(f"{prefix}.enabled must be a boolean")
        errors.extend(validate_risk_reason(prefix, plugin))
    return errors


def marketplace_source(entry: dict[str, Any]) -> str:
    source_type = entry.get("source")
    if source_type == "github":
        return str(entry.get("repo", ""))
    if source_type in {"git", "url"}:
        return str(entry.get("url", ""))
    if source_type == "directory":
        return str(entry.get("path", ""))
    return str(entry.get("repo") or entry.get("url") or entry.get("path") or "")


def source_matches(current: str, desired: dict[str, Any]) -> bool:
    allowed = [desired["source"], *desired.get("acceptedSources", [])]
    normalized = normalize_source(current)
    return any(normalized == normalize_source(candidate) for candidate in allowed)


def codex_marketplace_revision(
    marketplace: dict[str, Any], git_command: str = "git"
) -> str | None:
    root_value = marketplace.get("root")
    if not isinstance(root_value, str) or not root_value:
        return None
    root = Path(root_value)
    metadata_path = root / ".codex-marketplace-install.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        revision = metadata.get("revision") if isinstance(metadata, dict) else None
        head = subprocess.run(
            [
                git_command,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(root),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            [
                git_command,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (
        FileNotFoundError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ):
        return None
    unexpected_status = [
        line
        for line in status.splitlines()
        if line != "?? .codex-marketplace-install.json"
    ]
    if not isinstance(revision, str) or revision != head or unexpected_status:
        return None
    return revision


def codex_plugin_revision(
    plugin: dict[str, Any],
    marketplace: dict[str, Any],
    git_command: str = "git",
) -> str | None:
    root_value = marketplace.get("root")
    name = plugin.get("name")
    market_name = plugin.get("marketplaceName")
    version = plugin.get("version")
    source_data = marketplace.get("marketplaceSource")
    source = source_data.get("source") if isinstance(source_data, dict) else None
    if (
        not isinstance(root_value, str)
        or not isinstance(name, str)
        or not NAME_RE.fullmatch(name)
        or not isinstance(market_name, str)
        or not NAME_RE.fullmatch(market_name)
        or not isinstance(version, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version) is None
        or not isinstance(source, str)
    ):
        return None
    root = Path(root_value)
    if len(root.parents) < 3:
        return None
    cache = root.parents[2] / "plugins" / "cache" / market_name / name / version
    if not cache.is_dir() or not (cache / ".git").is_dir():
        return None
    git_prefix = [
        git_command,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(cache),
    ]
    try:
        head = subprocess.run(
            [*git_prefix, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            [*git_prefix, "status", "--porcelain", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        origin = subprocess.run(
            [*git_prefix, "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (
        FileNotFoundError,
        OSError,
        UnicodeError,
        subprocess.CalledProcessError,
    ):
        return None
    if status or normalize_source(origin) != normalize_source(source):
        return None
    return head


def source_cache_root() -> Path:
    override = os.environ.get("UAS_SOURCE_CACHE")
    if override:
        return Path(override).expanduser()
    home = Path(os.environ.get("UAS_HOME") or Path.home()).expanduser()
    if os.name == "nt":
        data_home = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    else:
        data_home = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    return data_home / "universal-agent-skills" / "sources"


def pinned_checkout(skill: dict[str, Any], cache_root: Path) -> PinnedCheckout:
    match = PINNED_GITHUB_RE.fullmatch(skill["source"])
    if match is None:
        raise ValueError(f"portable skill {skill['name']} does not have a pinned source")
    owner = match.group("owner")
    repo = match.group("repo").removesuffix(".git")
    commit = match.group("commit")
    return PinnedCheckout(
        repository=f"https://github.com/{owner}/{repo}.git",
        commit=commit,
        path=cache_root / skill["name"] / commit,
    )


def build_claude_plan(
    profile: dict[str, Any],
    current_marketplaces: list[dict[str, Any]],
    current_plugins: list[dict[str, Any]],
    *,
    include_sensitive: bool,
    update: bool,
    claude_command: str = "claude",
) -> Plan:
    actions: list[Action] = []
    notices: list[str] = []
    drift: list[str] = []
    blocking: list[str] = []
    desired_markets = {
        item["name"]: item for item in profile["claude"].get("marketplaces", [])
    }
    current_markets: dict[str, dict[str, Any]] = {}
    for item in current_marketplaces:
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("Claude marketplace inventory contains an invalid name")
        current_markets[name] = item
    current_plugin_map: dict[str, dict[str, Any]] = {}
    for item in current_plugins:
        plugin_id = item.get("id")
        if not isinstance(plugin_id, str) or not plugin_id:
            raise RuntimeError("Claude plugin inventory contains an invalid id")
        current_plugin_map[plugin_id] = item
    desired_plugins = profile["claude"].get("plugins", [])

    active_plugins = [
        item
        for item in desired_plugins
        if item["enabled"]
        and (include_sensitive or not item.get("requiresExplicitOptIn", False))
    ]
    active_market_names = {item["id"].rsplit("@", 1)[1] for item in active_plugins}
    blocked_markets: set[str] = set()

    for name, desired in desired_markets.items():
        if name not in active_market_names:
            continue
        current = current_markets.get(name)
        if current is None:
            drift.append(f"missing Claude marketplace: {name}")
            actions.append(
                Action(
                    f"add Claude marketplace {name}",
                    (
                        claude_command,
                        "plugin",
                        "marketplace",
                        "add",
                        desired["source"],
                        "--scope",
                        "user",
                    ),
                )
            )
            continue
        current_source = marketplace_source(current)
        if not source_matches(current_source, desired):
            message = (
                f"Claude marketplace {name} uses {current_source!r}, expected "
                f"{desired['source']!r}; replace it manually after reviewing the source change"
            )
            drift.append(message)
            blocking.append(message)
            blocked_markets.add(name)
        elif update:
            actions.append(
                Action(
                    f"update Claude marketplace {name}",
                    (claude_command, "plugin", "marketplace", "update", name),
                )
            )

    for plugin in desired_plugins:
        plugin_id = plugin["id"]
        market_name = plugin_id.rsplit("@", 1)[1]
        sensitive_blocked = plugin.get("requiresExplicitOptIn", False) and not include_sensitive
        current = current_plugin_map.get(plugin_id)
        if not plugin["enabled"]:
            if current is not None:
                if current.get("enabled") is True:
                    drift.append(f"Claude plugin should be disabled: {plugin_id}")
                    actions.append(
                        Action(
                            f"disable Claude plugin {plugin_id}",
                            (
                                claude_command,
                                "plugin",
                                "disable",
                                plugin_id,
                                "--scope",
                                "user",
                            ),
                        )
                    )
                else:
                    notices.append(f"desired plugin is disabled: {plugin_id}")
            continue
        if current is None:
            if sensitive_blocked:
                notices.append(
                    f"skipped sensitive plugin {plugin_id}; pass --include-sensitive after reviewing its data capture"
                )
                continue
            drift.append(f"missing Claude plugin: {plugin_id}")
            if market_name not in blocked_markets:
                actions.append(
                    Action(
                        f"install Claude plugin {plugin_id}",
                        (claude_command, "plugin", "install", plugin_id, "--scope", "user"),
                    )
                )
            continue
        if sensitive_blocked:
            notices.append(f"left sensitive plugin unchanged: {plugin_id}")
            continue
        if plugin["enabled"] and not current.get("enabled", False):
            drift.append(f"disabled Claude plugin: {plugin_id}")
            actions.append(
                Action(
                    f"enable Claude plugin {plugin_id}",
                    (claude_command, "plugin", "enable", plugin_id, "--scope", "user"),
                )
            )
        if update and market_name not in blocked_markets:
            actions.append(
                Action(
                    f"update Claude plugin {plugin_id}",
                    (claude_command, "plugin", "update", plugin_id, "--scope", "user"),
                )
            )

    desired_ids = {item["id"] for item in desired_plugins}
    extras = sorted(set(current_plugin_map) - desired_ids)
    if extras:
        notices.append(
            "left unlisted Claude plugins unchanged: " + ", ".join(extras)
        )
    return Plan(actions, notices, drift, blocking)


def build_codex_plan(
    profile: dict[str, Any],
    current_marketplaces: list[dict[str, Any]],
    current_plugins: list[dict[str, Any]],
    *,
    update: bool,
    codex_command: str = "codex",
) -> Plan:
    actions: list[Action] = []
    notices: list[str] = []
    drift: list[str] = []
    blocking: list[str] = []
    blocked_markets: set[str] = set()
    replaced_markets: set[str] = set()
    desired = profile["codex"]
    desired_markets = {
        item["name"]: item for item in desired.get("marketplaces", [])
    }
    current_markets: dict[str, dict[str, Any]] = {}
    for item in current_marketplaces:
        name = item.get("name")
        # Codex lists built-in marketplaces (openai-*) without a marketplaceSource; enforce shape only for markets the profile manages.
        if not isinstance(name, str) or name not in desired_markets:
            continue
        source_data = item.get("marketplaceSource")
        if not isinstance(source_data, dict) or not isinstance(
            source_data.get("source"), str
        ):
            raise RuntimeError(f"Codex marketplace inventory is malformed: {name}")
        current_markets[name] = item

    for marketplace in desired_markets.values():
        name = marketplace["name"]
        current = current_markets.get(name)
        if current is None:
            drift.append(f"missing Codex marketplace: {name}")
            replaced_markets.add(name)
            actions.append(
                Action(
                    f"add Codex marketplace {name}",
                    (
                        codex_command,
                        "plugin",
                        "marketplace",
                        "add",
                        marketplace["source"],
                        "--ref",
                        marketplace["ref"],
                    ),
                )
            )
            continue
        source_data = current["marketplaceSource"]
        source = source_data["source"]
        if not source_matches(source, marketplace):
            message = (
                f"Codex marketplace {name} uses {source!r}, expected "
                f"{marketplace['source']!r}; replace it manually after review"
            )
            drift.append(message)
            blocking.append(message)
            blocked_markets.add(name)
            continue
        revision = codex_marketplace_revision(current)
        if revision == marketplace["ref"]:
            continue
        displayed_revision = repr(revision) if revision else "an unverified revision"
        message = (
            f"Codex marketplace {name} uses {displayed_revision}, expected revision "
            f"{marketplace['ref']}"
        )
        drift.append(message)
        if not update:
            blocking.append(f"{message}; rerun with --update to replace it")
            blocked_markets.add(name)
            continue
        replaced_markets.add(name)
        actions.extend(
            (
                Action(
                    f"remove outdated Codex marketplace {name}",
                    (codex_command, "plugin", "marketplace", "remove", name),
                ),
                Action(
                    f"add pinned Codex marketplace {name}",
                    (
                        codex_command,
                        "plugin",
                        "marketplace",
                        "add",
                        marketplace["source"],
                        "--ref",
                        marketplace["ref"],
                    ),
                )
            )
        )

    current_plugin_map: dict[str, dict[str, Any]] = {}
    for item in current_plugins:
        plugin_id = item.get("pluginId")
        if not isinstance(plugin_id, str) or not plugin_id:
            raise RuntimeError("Codex plugin inventory contains an invalid pluginId")
        if item.get("installed") is True:
            current_plugin_map[plugin_id] = item
    for plugin in desired.get("plugins", []):
        plugin_id = plugin["id"]
        marketplace_name = plugin_id.rsplit("@", 1)[1]
        current = current_plugin_map.get(plugin_id)
        if not plugin["enabled"]:
            if current is not None:
                if current.get("enabled") is True:
                    message = (
                        f"Codex plugin is active but disabled in the profile: {plugin_id}; "
                        "disable or remove it manually"
                    )
                    drift.append(message)
                    blocking.append(message)
                else:
                    notices.append(f"desired plugin is disabled: {plugin_id}")
            continue
        if current is None:
            drift.append(f"missing Codex plugin: {plugin_id}")
            if marketplace_name in blocked_markets:
                continue
            actions.append(
                Action(
                    f"install Codex plugin {plugin_id}",
                    (codex_command, "plugin", "add", plugin_id),
                )
            )
            continue
        if marketplace_name in replaced_markets:
            actions.extend(
                (
                    Action(
                        f"remove outdated Codex plugin {plugin_id}",
                        (codex_command, "plugin", "remove", plugin_id),
                    ),
                    Action(
                        f"install Codex plugin {plugin_id} from the pinned marketplace",
                        (codex_command, "plugin", "add", plugin_id),
                    ),
                )
            )
            continue
        desired_market = desired_markets.get(marketplace_name)
        current_market = current_markets.get(marketplace_name)
        if desired_market is not None and current_market is not None:
            plugin_revision = codex_plugin_revision(current, current_market)
            if plugin_revision != desired_market["ref"]:
                displayed = (
                    repr(plugin_revision)
                    if plugin_revision
                    else "an unverified revision"
                )
                message = (
                    f"Codex plugin {plugin_id} uses {displayed}, expected revision "
                    f"{desired_market['ref']}"
                )
                drift.append(message)
                if not update:
                    blocking.append(f"{message}; rerun with --update to reinstall it")
                    continue
                actions.extend(
                    (
                        Action(
                            f"remove outdated Codex plugin {plugin_id}",
                            (codex_command, "plugin", "remove", plugin_id),
                        ),
                        Action(
                            f"reinstall Codex plugin {plugin_id}",
                            (codex_command, "plugin", "add", plugin_id),
                        ),
                    )
                )
                continue
        if not current.get("enabled", False):
            message = f"Codex plugin is installed but disabled: {plugin_id}"
            drift.append(message)
            blocking.append(message)

    desired_ids = {item["id"] for item in desired.get("plugins", [])}
    extras = sorted(set(current_plugin_map) - desired_ids)
    if extras:
        notices.append("left unlisted Codex plugins unchanged: " + ", ".join(extras))
    return Plan(actions, notices, drift, blocking)


def build_copilot_plan(
    profile: dict[str, Any],
    marketplace_output: str,
    plugin_output: str,
    *,
    update: bool,
    copilot_command: str = "copilot",
) -> Plan:
    actions: list[Action] = []
    drift: list[str] = []
    blocking: list[str] = []
    desired = profile["copilot"]
    normalized_market_output = normalize_source(marketplace_output)

    for marketplace in desired.get("marketplaces", []):
        name = marketplace["name"]
        source = normalize_source(marketplace["source"])
        name_present = name.lower() in marketplace_output.lower()
        if name_present and source not in normalized_market_output:
            message = (
                f"Copilot CLI marketplace {name} does not match {marketplace['source']!r}; "
                "replace it manually after reviewing the source change"
            )
            drift.append(message)
            blocking.append(message)
            continue
        if not name_present:
            drift.append(f"missing Copilot CLI marketplace: {name}")
            actions.append(
                Action(
                    f"add Copilot CLI marketplace {name}",
                    (
                        copilot_command,
                        "plugin",
                        "marketplace",
                        "add",
                        marketplace["source"],
                    ),
                )
            )

    for plugin in desired.get("plugins", []):
        plugin_id = plugin["id"]
        plugin_name = plugin_id.split("@", 1)[0]
        installed = plugin_id.lower() in plugin_output.lower()
        if not plugin["enabled"]:
            if installed:
                message = (
                    f"Copilot CLI plugin is installed but disabled in the profile: "
                    f"{plugin_id}; uninstall it manually"
                )
                drift.append(message)
                blocking.append(message)
            continue
        if not installed:
            drift.append(f"missing Copilot CLI plugin: {plugin_id}")
            actions.append(
                Action(
                    f"install Copilot CLI plugin {plugin_id}",
                    (copilot_command, "plugin", "install", plugin_id),
                )
            )
        elif update:
            actions.append(
                Action(
                    f"update Copilot CLI plugin {plugin_id}",
                    (copilot_command, "plugin", "update", plugin_name),
                )
            )
    return Plan(actions, [], drift, blocking)


def opencode_config_path() -> Path:
    home = Path(os.environ.get("UAS_HOME") or Path.home()).expanduser()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    jsonc = config_home / "opencode" / "opencode.jsonc"
    plain = config_home / "opencode" / "opencode.json"
    return jsonc if jsonc.exists() or not plain.exists() else plain


def opencode_plugin_entries(config_text: str) -> list[str]:
    try:
        value = json.loads(jsonc_to_json(config_text)) if config_text.strip() else {}
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenCode config contains invalid JSONC") from exc
    if not isinstance(value, dict):
        raise RuntimeError("OpenCode config must be a JSON object")
    entries = value.get("plugin", [])
    if not isinstance(entries, list) or not all(
        isinstance(entry, str) for entry in entries
    ):
        raise RuntimeError("OpenCode config 'plugin' value must be a string array")
    return entries


def build_opencode_plan(
    profile: dict[str, Any],
    config_text: str,
    *,
    update: bool,
    opencode_command: str = "opencode",
) -> Plan:
    actions: list[Action] = []
    drift: list[str] = []
    notices: list[str] = []
    entries = opencode_plugin_entries(config_text)
    for plugin in profile["opencode"].get("plugins", []):
        package = plugin["package"]
        pinned = f"{package}@{plugin['version']}"
        if pinned in entries:
            continue
        unpinned = any(
            entry == package or entry.startswith(f"{package}@") for entry in entries
        )
        if unpinned and not update:
            drift.append(f"OpenCode plugin is not pinned to {plugin['version']}: {package}")
            notices.append(f"pass --update to replace the OpenCode plugin pin for {package}")
            continue
        drift.append(f"missing or outdated OpenCode plugin: {pinned}")
        command = [opencode_command, "plugin", pinned, "--global"]
        if unpinned:
            command.append("--force")
        actions.append(Action(f"install OpenCode plugin {pinned}", tuple(command)))
    return Plan(actions, notices, drift, [])


def argument_value(arguments: list[str], flag: str) -> str | None:
    if flag not in arguments:
        return None
    index = arguments.index(flag)
    if index + 1 >= len(arguments):
        raise RuntimeError(f"nativeInstallers argument {flag} requires a value")
    return arguments[index + 1]


def build_native_installer_actions(
    profile: dict[str, Any],
    npx_command: str = "npx",
    home: Path | None = None,
) -> list[Action]:
    actions: list[Action] = []
    resolved_home = home or Path(os.environ.get("UAS_HOME") or Path.home()).expanduser()
    for installer in profile.get("nativeInstallers", []):
        state_path = resolved_home / installer["statePath"]
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        source_state = state.get("source")
        target_state = state.get("target")
        request_state = state.get("request")
        source_state = source_state if isinstance(source_state, dict) else {}
        target_state = target_state if isinstance(target_state, dict) else {}
        request_state = request_state if isinstance(request_state, dict) else {}
        arguments = installer["arguments"]
        target = argument_value(arguments, "--target")
        requested_profile = argument_value(arguments, "--profile")
        modules_value = argument_value(arguments, "--modules")
        requested_modules = modules_value.split(",") if modules_value else []
        if (
            state.get("schemaVersion") == "ecc.install.v1"
            and source_state.get("repoVersion") == installer["version"]
            and target_state.get("target") == target
            and request_state.get("profile") == requested_profile
            and request_state.get("modules", []) == requested_modules
        ):
            continue
        package = f"{installer['package']}@{installer['version']}"
        actions.append(
            Action(
                f"ensure native integration {installer['name']}",
                (
                    npx_command,
                    "--yes",
                    f"--package={package}",
                    installer["executable"],
                    *arguments,
                ),
                (("DISABLE_TELEMETRY", "1"),),
            )
        )
    return actions


def build_native_plan(
    profile: dict[str, Any],
    npx_command: str = "npx",
    home: Path | None = None,
) -> Plan:
    actions = build_native_installer_actions(profile, npx_command, home)
    drift = [
        f"native integration differs from the profile: "
        f"{action.label.removeprefix('ensure native integration ')}"
        for action in actions
    ]
    return Plan(actions, [], drift, [])


def build_vscode_plan(
    profile: dict[str, Any], extension_output: str, code_command: str = "code"
) -> Plan:
    installed = {
        line.split("@", 1)[0].strip().lower()
        for line in extension_output.splitlines()
        if line.strip()
    }
    actions: list[Action] = []
    drift: list[str] = []
    for extension in profile["vscode"].get("extensions", []):
        extension_id = extension["id"]
        if extension_id.lower() in installed:
            continue
        drift.append(f"missing VS Code extension: {extension_id}")
        actions.append(
            Action(
                f"install VS Code extension {extension_id}",
                (code_command, "--install-extension", extension_id),
            )
        )
    return Plan(actions, [], drift, [])


def vscode_extension_inventory(code_command: str, listed_output: str) -> str:
    entries = [listed_output]
    executable = shutil.which(code_command)
    if executable is None:
        return listed_output
    resolved = Path(executable).resolve()
    roots = {
        resolved.parents[1] / "extensions" if len(resolved.parents) > 1 else resolved,
        resolved.parents[1] / "resources" / "app" / "extensions"
        if len(resolved.parents) > 1
        else resolved,
    }
    for root in roots:
        if not root.is_dir():
            continue
        for manifest in root.glob("*/package.json"):
            try:
                value = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            publisher = value.get("publisher")
            name = value.get("name")
            version = value.get("version")
            if publisher and name:
                entries.append(f"{publisher}.{name}@{version or ''}")
    return "\n".join(entries)


def build_mcp_plan(
    profile: dict[str, Any],
    current_names: dict[str, set[str]],
    *,
    profile_path: Path,
    update: bool = False,
    conflicting_names: dict[str, set[str]] | None = None,
    codex_command: str = "codex",
    opencode_command: str = "opencode",
    copilot_command: str = "copilot",
) -> Plan:
    commands = {
        "codex": codex_command,
        "opencode": opencode_command,
        "copilot": copilot_command,
    }
    actions: list[Action] = []
    drift: list[str] = []
    blocking: list[str] = []
    conflicts = conflicting_names or {}
    configure_opencode = False
    update_opencode = False
    for server in profile.get("mcpServers", []):
        for agent in server["agents"]:
            name = server["name"]
            is_conflict = name.lower() in conflicts.get(agent, set())
            if not is_conflict and name.lower() in current_names.get(agent, set()):
                continue
            executable = commands[agent]
            if is_conflict:
                drift.append(f"{agent} MCP server differs from the profile: {name}")
                if not update:
                    blocking.append(
                        f"{agent} MCP server {name} differs from the profile; "
                        "rerun with --update to replace it"
                    )
                    continue
                if agent != "opencode":
                    actions.append(
                        Action(
                            f"remove outdated {agent} MCP server {name}",
                            (executable, "mcp", "remove", name),
                        )
                    )
            else:
                drift.append(f"missing {agent} MCP server: {name}")
            if agent == "opencode":
                configure_opencode = True
                update_opencode = update_opencode or is_conflict
                continue
            if server["transport"] == "http":
                if agent == "copilot":
                    command = (
                        executable,
                        "mcp",
                        "add",
                        "--transport",
                        "http",
                        name,
                        server["url"],
                    )
                else:
                    command = (
                        executable,
                        "mcp",
                        "add",
                        name,
                        "--url",
                        server["url"],
                    )
            elif agent == "copilot":
                command = (
                    executable,
                    "mcp",
                    "add",
                    name,
                    "--",
                    *server["command"],
                )
            elif agent == "codex":
                command = (
                    executable,
                    "mcp",
                    "add",
                    name,
                    "--",
                    *server["command"],
                )
            else:
                raise ValueError(f"stdio MCP automation is unsupported for {agent}")
            actions.append(Action(f"configure {agent} MCP server {name}", command))
    if configure_opencode:
        command = [
            sys.executable,
            str(ROOT / "scripts" / "sync_opencode_config.py"),
            "--profile",
            str(profile_path),
            "--apply",
        ]
        if update_opencode:
            command.append("--update")
        actions.append(
            Action("configure OpenCode MCP servers from the profile", tuple(command))
        )
    return Plan(actions, [], drift, blocking)


def codex_mcp_matches(server: dict[str, Any], current: dict[str, Any]) -> bool:
    allowed_current = {
        "name",
        "enabled",
        "disabled_reason",
        "transport",
        "startup_timeout_sec",
        "tool_timeout_sec",
        "auth_status",
    }
    if set(current) - allowed_current or current.get("enabled") is not True:
        return False
    if current.get("startup_timeout_sec") is not None:
        return False
    if current.get("tool_timeout_sec") is not None:
        return False
    transport = current.get("transport")
    if not isinstance(transport, dict):
        return False
    if server["transport"] == "http":
        allowed = {
            "type",
            "url",
            "bearer_token_env_var",
            "http_headers",
            "env_http_headers",
        }
        return (
            not set(transport) - allowed
            and transport.get("type") == "streamable_http"
            and transport.get("url") == server["url"]
            and transport.get("bearer_token_env_var") is None
            and transport.get("http_headers") in (None, {})
            and transport.get("env_http_headers") in (None, {})
        )
    allowed = {"type", "command", "args", "env", "env_vars", "cwd"}
    return (
        not set(transport) - allowed
        and transport.get("type") == "stdio"
        and transport.get("command") == server["command"][0]
        and transport.get("args") == server["command"][1:]
        and transport.get("env") in (None, {})
        and transport.get("env_vars") in (None, [])
        and transport.get("cwd") is None
    )


def opencode_mcp_matches(server: dict[str, Any], current: dict[str, Any]) -> bool:
    if current.get("enabled") is not True:
        return False
    if server["transport"] == "http":
        return (
            not set(current) - {"type", "url", "enabled"}
            and current.get("type") == "remote"
            and current.get("url") == server["url"]
        )
    return (
        not set(current) - {"type", "command", "enabled"}
        and current.get("type") == "local"
        and current.get("command") == server["command"]
    )


def copilot_mcp_matches(server: dict[str, Any], current: dict[str, Any]) -> bool:
    if current.get("enabled") is not True:
        return False
    allowed_metadata = {"enabled", "tools", "source"}
    if current.get("tools", ["*"]) != ["*"]:
        return False
    if server["transport"] == "http":
        return (
            not set(current) - (allowed_metadata | {"type", "url"})
            and current.get("type") in {"http", "remote"}
            and current.get("url") == server["url"]
        )
    return (
        not set(current) - (allowed_metadata | {"type", "command", "args"})
        and current.get("type") == "local"
        and current.get("command") == server["command"][0]
        and current.get("args") == server["command"][1:]
    )


def mcp_inventory(
    profile: dict[str, Any],
    agent: str,
    current_servers: dict[str, Any],
    matcher,
) -> tuple[set[str], set[str]]:
    desired = {
        server["name"]: server
        for server in profile.get("mcpServers", [])
        if agent in server["agents"]
    }
    matching: set[str] = set()
    conflicting: set[str] = set()
    for name, server in desired.items():
        entries = [
            value
            for key, value in current_servers.items()
            if str(key).lower() == name.lower()
        ]
        if not entries:
            continue
        if (
            len(entries) == 1
            and isinstance(entries[0], dict)
            and matcher(server, entries[0])
        ):
            matching.add(name.lower())
        else:
            conflicting.add(name.lower())
    return matching, conflicting


def jsonc_to_json(text: str) -> str:
    characters = list(text)
    in_string = False
    escaped = False
    index = 0
    while index < len(characters):
        character = characters[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            index += 1
            continue
        if character == "/" and index + 1 < len(characters):
            following = characters[index + 1]
            if following == "/":
                characters[index] = characters[index + 1] = " "
                index += 2
                while index < len(characters) and characters[index] not in "\r\n":
                    characters[index] = " "
                    index += 1
                continue
            if following == "*":
                characters[index] = characters[index + 1] = " "
                index += 2
                while index + 1 < len(characters):
                    if characters[index] == "*" and characters[index + 1] == "/":
                        characters[index] = characters[index + 1] = " "
                        index += 2
                        break
                    if characters[index] not in "\r\n":
                        characters[index] = " "
                    index += 1
                else:
                    raise ValueError("unterminated JSONC block comment")
                continue
        index += 1

    in_string = False
    escaped = False
    for index, character in enumerate(characters):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character != ",":
            continue
        following = index + 1
        while following < len(characters) and characters[following].isspace():
            following += 1
        if following < len(characters) and characters[following] in "]}":
            characters[index] = " "
    return "".join(characters)


def opencode_mcp_inventory(
    profile: dict[str, Any], config_text: str
) -> tuple[set[str], set[str]]:
    try:
        value = json.loads(jsonc_to_json(config_text)) if config_text else {}
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenCode config contains invalid JSONC") from exc
    if not isinstance(value, dict):
        raise RuntimeError("OpenCode config must be a JSON object")
    current = value.get("mcp", {})
    if not isinstance(current, dict):
        raise RuntimeError("OpenCode config 'mcp' value must be an object")
    return mcp_inventory(profile, "opencode", current, opencode_mcp_matches)


def guard_jsonc_opencode_plan(
    plan: Plan,
    profile: dict[str, Any],
    current_names: set[str],
    conflicting_names: set[str],
    config_text: str,
) -> Plan:
    if not config_text:
        return plan
    try:
        json.loads(config_text)
        return plan
    except json.JSONDecodeError:
        pass
    desired_names = {
        server["name"].lower()
        for server in profile.get("mcpServers", [])
        if "opencode" in server["agents"]
    }
    if not conflicting_names and desired_names <= current_names:
        return plan
    actions = [
        action
        for action in plan.actions
        if not any(
            part.endswith("sync_opencode_config.py") for part in action.command
        )
    ]
    message = (
        "OpenCode MCP drift requires a manual JSONC-preserving merge; "
        "automatic apply supports plain JSON only"
    )
    return Plan(actions, [*plan.notices, message], plan.drift, [*plan.blocking, message])


def copilot_mcp_inventory(
    profile: dict[str, Any], value: Any
) -> tuple[set[str], set[str]]:
    if not isinstance(value, dict) or not isinstance(value.get("mcpServers"), dict):
        raise RuntimeError("Copilot MCP list returned an unexpected JSON shape")
    return mcp_inventory(
        profile, "copilot", value["mcpServers"], copilot_mcp_matches
    )


def build_portable_skill_actions(
    profile: dict[str, Any],
    npx_command: str = "npx",
    cache_root: Path | None = None,
) -> list[Action]:
    cli = profile["skillsCli"]
    package = f"{cli['package']}@{cli['version']}"
    resolved_cache = cache_root or source_cache_root()
    environment: tuple[tuple[str, str], ...] = ()
    if cli["disableTelemetry"]:
        environment = (("DISABLE_TELEMETRY", "1"),)
    actions: list[Action] = []
    for skill in profile.get("portableSkills", []):
        checkout = pinned_checkout(skill, resolved_cache)
        command = [
            npx_command,
            "--yes",
            package,
            "add",
            str(checkout.path),
            "--skill",
            skill["name"],
            "--global",
        ]
        for agent in skill["agents"]:
            command.extend(("--agent", agent))
        command.append("--yes")
        actions.append(
            Action(
                f"ensure portable skill {skill['name']} for {', '.join(skill['agents'])}",
                tuple(command),
                environment,
                checkout,
            )
        )
    return actions


def pinned_checkout_issue(
    checkout: PinnedCheckout, git_command: str = "git"
) -> str | None:
    target = checkout.path
    if not target.exists() and not target.is_symlink():
        return "cache is missing"
    if not target.is_dir() or not (target / ".git").is_dir():
        return "cache path is unmanaged"
    try:
        head = subprocess.run(
            [
                git_command,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(target),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            [
                git_command,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(target),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        origin = subprocess.run(
            [
                git_command,
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(target),
                "remote",
                "get-url",
                "origin",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (
        FileNotFoundError,
        OSError,
        UnicodeError,
        subprocess.CalledProcessError,
    ):
        return "cache cannot be verified"
    if head != checkout.commit:
        return f"cache has unexpected commit {head!r}"
    if status:
        return "cache has local changes"
    if normalize_source(origin) != normalize_source(checkout.repository):
        return f"cache has unexpected origin {origin!r}"
    return None


def frontmatter_skill_name(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    for line in lines[1:end]:
        match = re.fullmatch(
            r"name:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*", line
        )
        if match:
            return match.group(1)
    return None


def portable_skill_source(checkout: PinnedCheckout, name: str) -> Path | None:
    candidates = [
        skill_file.parent
        for skill_file in checkout.path.rglob("SKILL.md")
        if frontmatter_skill_name(skill_file) == name
    ]
    return candidates[0] if len(candidates) == 1 else None


def directory_snapshot(path: Path) -> dict[str, tuple[str, str]]:
    snapshot: dict[str, tuple[str, str]] = {}
    for entry in path.rglob("*"):
        relative = entry.relative_to(path)
        if ".git" in relative.parts:
            continue
        key = relative.as_posix()
        if entry.is_symlink():
            snapshot[key] = ("link", os.readlink(entry))
        elif entry.is_dir():
            snapshot[key] = ("directory", "")
        elif entry.is_file():
            snapshot[key] = ("file", hashlib.sha256(entry.read_bytes()).hexdigest())
        else:
            snapshot[key] = ("other", "")
    return snapshot


def build_portable_skill_plan(
    profile: dict[str, Any],
    npx_command: str = "npx",
    cache_root: Path | None = None,
    home: Path | None = None,
) -> Plan:
    resolved_cache = cache_root or source_cache_root()
    resolved_home = home or Path(os.environ.get("UAS_HOME") or Path.home()).expanduser()
    planned_actions = build_portable_skill_actions(
        profile, npx_command, resolved_cache
    )
    actions: list[Action] = []
    drift: list[str] = []
    blocking: list[str] = []
    for skill, action in zip(profile.get("portableSkills", []), planned_actions):
        name = skill["name"]
        checkout = action.checkout
        if checkout is None:
            raise RuntimeError(f"portable skill has no pinned checkout: {name}")
        issue = pinned_checkout_issue(checkout)
        if issue == "cache is missing":
            drift.append(f"portable skill {name} {issue}")
            actions.append(action)
            continue
        if issue:
            message = f"portable skill {name} {issue}"
            drift.append(message)
            blocking.append(message)
            continue
        source = portable_skill_source(checkout, name)
        if source is None:
            message = f"portable skill {name} source cannot be identified uniquely"
            drift.append(message)
            blocking.append(message)
            continue
        target = resolved_home / ".agents" / "skills" / name
        try:
            if target.is_symlink():
                matches = target.resolve() == source.resolve()
            else:
                matches = (
                    target.is_dir()
                    and directory_snapshot(target) == directory_snapshot(source)
                )
        except OSError as exc:
            message = f"portable skill {name} cannot be verified: {exc}"
            drift.append(message)
            blocking.append(message)
            continue
        if not matches:
            drift.append(f"portable skill differs from the pinned source: {name}")
            actions.append(action)
    return Plan(actions, [], drift, blocking)


def build_instruction_plan(home: Path | None = None) -> Plan:
    resolved_home = home or Path(os.environ.get("UAS_HOME") or Path.home()).expanduser()
    drift: list[str] = []
    for target in instruction_sync.targets(resolved_home).values():
        try:
            current = (
                target.path.read_text(encoding="utf-8") if target.path.exists() else ""
            )
            _, changed = instruction_sync.replace_block(current, uninstall=False)
        except (OSError, UnicodeError, ValueError) as exc:
            raise RuntimeError(f"cannot audit {target.agent} instructions: {exc}") from exc
        if changed:
            drift.append(f"global instructions differ for {target.agent}")
    actions: list[Action] = []
    if drift:
        actions.append(
            Action(
                "ensure global comment instructions",
                (
                    sys.executable,
                    str(ROOT / "scripts" / "sync_instructions.py"),
                    "--apply",
                ),
                (("UAS_HOME", str(resolved_home)),),
            )
        )
    return Plan(actions, [], drift, [])


def run_output(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"required command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{shlex.join(command)} timed out") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "command failed").strip()
        raise RuntimeError(f"{shlex.join(command)}: {detail}") from exc
    return result.stdout


def run_json_value(command: list[str]) -> Any:
    try:
        return json.loads(run_output(command))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{shlex.join(command)} returned invalid JSON") from exc


def run_json(command: list[str]) -> list[dict[str, Any]]:
    value = run_json_value(command)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RuntimeError(f"{shlex.join(command)} returned an unexpected JSON shape")
    return value


def run_checked(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    try:
        subprocess.run(command, check=True, env=environment)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"command failed ({exc.returncode}): {shlex.join(command)}") from exc


def ensure_pinned_checkout(checkout: PinnedCheckout, git_command: str = "git") -> None:
    target = checkout.path
    if target.exists() or target.is_symlink():
        issue = pinned_checkout_issue(checkout, git_command)
        if issue:
            raise RuntimeError(f"portable-skill {issue}: {target}")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".checkout-", dir=target.parent))
    try:
        run_checked([git_command, "init", "-q", str(temporary)])
        run_checked(
            [git_command, "-C", str(temporary), "remote", "add", "origin", checkout.repository]
        )
        run_checked(
            [
                git_command,
                "-C",
                str(temporary),
                "fetch",
                "--depth",
                "1",
                "origin",
                checkout.commit,
            ]
        )
        run_checked(
            [git_command, "-C", str(temporary), "checkout", "-q", "--detach", "FETCH_HEAD"]
        )
        result = subprocess.run(
            [git_command, "-C", str(temporary), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() != checkout.commit:
            raise RuntimeError(
                f"fetched commit does not match requested pin for {checkout.repository}"
            )
        if target.exists() or target.is_symlink():
            raise RuntimeError(f"portable-skill cache path appeared during install: {target}")
        temporary.replace(target)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"failed to create pinned checkout: {target}") from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def execute_action(action: Action) -> None:
    env = os.environ.copy()
    env.update(action.environment)
    if action.checkout is not None:
        ensure_pinned_checkout(action.checkout)
    run_checked(list(action.command), environment=env)


def print_plan(plan: Plan, apply: bool) -> None:
    for item in plan.drift:
        print(f"drift: {item}")
    for item in plan.notices:
        print(f"note: {item}")
    for action in plan.actions:
        prefix = "run" if apply else "would run"
        env_prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in action.environment)
        command = shlex.join(action.command)
        rendered = f"{env_prefix} {command}".strip()
        if action.checkout is not None:
            print(
                f"{prefix}: fetch {action.checkout.repository} at "
                f"{action.checkout.commit} into {action.checkout.path}"
            )
        print(f"{prefix}: {action.label}\n  {rendered}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or reconcile the declared cross-agent plugin and skill stack."
    )
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--apply", action="store_true", help="Perform the planned changes")
    parser.add_argument("--update", action="store_true", help="Update configured external plugins")
    parser.add_argument(
        "--include-sensitive",
        action="store_true",
        help="Allow installation or updates of explicit opt-in plugins such as claude-mem",
    )
    parser.add_argument(
        "--component",
        action="append",
        choices=(
            "claude",
            "codex",
            "copilot",
            "opencode",
            "vscode",
            "mcp",
            "native",
            "skills",
            "instructions",
        ),
        help="Limit reconciliation to a component; repeat to select more than one",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when selected stack state drifts",
    )
    parser.add_argument("--validate-only", action="store_true", help="Validate the profile without tools")
    parser.add_argument(
        "--claude-command",
        default=os.environ.get("UAS_CLAUDE_COMMAND", "claude"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--npx-command",
        default=os.environ.get("UAS_NPX_COMMAND", "npx"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--codex-command",
        default=os.environ.get("UAS_CODEX_COMMAND", "codex"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--copilot-command",
        default=os.environ.get("UAS_COPILOT_COMMAND", "copilot"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--opencode-command",
        default=os.environ.get("UAS_OPENCODE_COMMAND", "opencode"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--code-command",
        default=os.environ.get("UAS_CODE_COMMAND", "code"),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if args.apply and args.check:
        parser.error("--apply and --check cannot be combined")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        profile = load_profile(args.profile.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: cannot load profile: {exc}", file=sys.stderr)
        return 2
    errors = validate_profile(profile)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"validated agent stack profile: {profile['name']}")
    if args.validate_only:
        return 0

    components = set(
        args.component
        or (
            "claude",
            "codex",
            "copilot",
            "opencode",
            "vscode",
            "mcp",
            "native",
            "skills",
            "instructions",
        )
    )
    plans: list[Plan] = []
    try:
        native_actions: list[Action] = []
        if "native" in components:
            native_plan = build_native_plan(profile, args.npx_command)
            native_actions = native_plan.actions
            if (
                args.apply
                and native_actions
                and shutil.which(args.npx_command) is None
            ):
                raise RuntimeError(f"required command not found: {args.npx_command}")
            plans.append(native_plan)
        native_resets_codex = any(
            action.label == "ensure native integration ecc-codex"
            for action in native_actions
        )
        if "claude" in components:
            if shutil.which(args.claude_command) is None:
                raise RuntimeError(f"required command not found: {args.claude_command}")
            markets = run_json(
                [args.claude_command, "plugin", "marketplace", "list", "--json"]
            )
            plugins = run_json([args.claude_command, "plugin", "list", "--json"])
            plans.append(
                build_claude_plan(
                    profile,
                    markets,
                    plugins,
                    include_sensitive=args.include_sensitive,
                    update=args.update,
                    claude_command=args.claude_command,
                )
            )
        if "codex" in components:
            if shutil.which(args.codex_command) is None:
                raise RuntimeError(f"required command not found: {args.codex_command}")
            marketplace_value = run_json_value(
                [args.codex_command, "plugin", "marketplace", "list", "--json"]
            )
            plugin_value = run_json_value(
                [args.codex_command, "plugin", "list", "--available", "--json"]
            )
            if not isinstance(marketplace_value, dict) or not isinstance(
                marketplace_value.get("marketplaces"), list
            ):
                raise RuntimeError("Codex marketplace list returned an unexpected JSON shape")
            if not isinstance(plugin_value, dict) or not isinstance(
                plugin_value.get("installed"), list
            ):
                raise RuntimeError("Codex plugin list returned an unexpected JSON shape")
            plans.append(
                build_codex_plan(
                    profile,
                    [] if native_resets_codex else marketplace_value["marketplaces"],
                    [] if native_resets_codex else plugin_value["installed"],
                    update=args.update,
                    codex_command=args.codex_command,
                )
            )
        if "copilot" in components:
            if shutil.which(args.copilot_command) is None:
                raise RuntimeError(f"required command not found: {args.copilot_command}")
            plans.append(
                build_copilot_plan(
                    profile,
                    run_output(
                        [args.copilot_command, "plugin", "marketplace", "list"]
                    ),
                    run_output([args.copilot_command, "plugin", "list"]),
                    update=args.update,
                    copilot_command=args.copilot_command,
                )
            )
        if "opencode" in components:
            if shutil.which(args.opencode_command) is None:
                raise RuntimeError(f"required command not found: {args.opencode_command}")
            config = opencode_config_path()
            config_text = config.read_text(encoding="utf-8") if config.exists() else ""
            plans.append(
                build_opencode_plan(
                    profile,
                    config_text,
                    update=args.update,
                    opencode_command=args.opencode_command,
                )
            )
        if "vscode" in components:
            if shutil.which(args.code_command) is None:
                raise RuntimeError(f"required command not found: {args.code_command}")
            plans.append(
                build_vscode_plan(
                    profile,
                    vscode_extension_inventory(
                        args.code_command,
                        run_output(
                            [args.code_command, "--list-extensions", "--show-versions"]
                        ),
                    ),
                    args.code_command,
                )
            )
        if "mcp" in components:
            required_mcp_agents = {
                agent
                for server in profile.get("mcpServers", [])
                for agent in server["agents"]
            }
            mcp_commands = {
                "codex": args.codex_command,
                "opencode": args.opencode_command,
                "copilot": args.copilot_command,
            }
            for agent in required_mcp_agents:
                if shutil.which(mcp_commands[agent]) is None:
                    raise RuntimeError(f"required command not found: {mcp_commands[agent]}")
            current_names: dict[str, set[str]] = {}
            conflicting_names: dict[str, set[str]] = {}
            if "codex" in required_mcp_agents:
                codex_mcp = run_json_value([args.codex_command, "mcp", "list", "--json"])
                if not isinstance(codex_mcp, list):
                    raise RuntimeError("Codex MCP list returned an unexpected JSON shape")
                if native_resets_codex:
                    current_names["codex"] = set()
                else:
                    desired_codex = {
                        server["name"]: server
                        for server in profile.get("mcpServers", [])
                        if "codex" in server["agents"]
                    }
                    current_names["codex"] = set()
                    conflicting_names["codex"] = set()
                    for item in codex_mcp:
                        if not isinstance(item, dict):
                            continue
                        name = str(item.get("name", "")).lower()
                        desired_server = desired_codex.get(name)
                        if desired_server is None:
                            continue
                        if codex_mcp_matches(desired_server, item):
                            current_names["codex"].add(name)
                        else:
                            conflicting_names["codex"].add(name)
            if "opencode" in required_mcp_agents:
                config = opencode_config_path()
                config_text = config.read_text(encoding="utf-8") if config.exists() else ""
                (
                    current_names["opencode"],
                    conflicting_names["opencode"],
                ) = opencode_mcp_inventory(profile, config_text)
            if "copilot" in required_mcp_agents:
                (
                    current_names["copilot"],
                    conflicting_names["copilot"],
                ) = copilot_mcp_inventory(
                    profile,
                    run_json_value(
                        [args.copilot_command, "mcp", "list", "--json"]
                    ),
                )
            mcp_plan = build_mcp_plan(
                profile,
                current_names,
                profile_path=args.profile,
                update=args.update,
                conflicting_names=conflicting_names,
                codex_command=args.codex_command,
                opencode_command=args.opencode_command,
                copilot_command=args.copilot_command,
            )
            if "opencode" in required_mcp_agents:
                mcp_plan = guard_jsonc_opencode_plan(
                    mcp_plan,
                    profile,
                    current_names.get("opencode", set()),
                    conflicting_names.get("opencode", set()),
                    config_text,
                )
            plans.append(mcp_plan)
        if "skills" in components:
            skill_plan = build_portable_skill_plan(profile, args.npx_command)
            if args.apply and skill_plan.actions:
                for command in ("git", args.npx_command):
                    if shutil.which(command) is None:
                        raise RuntimeError(f"required command not found: {command}")
            plans.append(skill_plan)
        if "instructions" in components:
            plans.append(build_instruction_plan())
    except (RuntimeError, OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for plan in plans:
        print_plan(plan, args.apply)
    blocking = [item for plan in plans for item in plan.blocking]
    drift = [item for plan in plans for item in plan.drift]
    if blocking and args.apply:
        print(
            "error: refusing partial reconciliation while managed state is unsafe",
            file=sys.stderr,
        )
        return 1
    if args.check:
        return 1 if drift else 0
    if not args.apply:
        print("audit complete; no changes were made")
        return 0

    sys.stdout.flush()
    try:
        for plan in plans:
            for action in plan.actions:
                execute_action(action)
    except (RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("agent stack reconciliation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
