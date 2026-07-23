#!/usr/bin/env python3
"""Validate repository structure without third-party dependencies."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from sync_agent_stack import validate_profile


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^]]*]\(([^)]+)\)")
ALLOWED_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing opening YAML delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing closing YAML delimiter") from exc

    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, "\n".join(lines[end + 1 :]).strip()


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    skill_file = path / "SKILL.md"
    if not skill_file.is_file():
        return [f"{path}: missing SKILL.md"]

    text = skill_file.read_text(encoding="utf-8")
    try:
        metadata, body = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{skill_file}: {exc}"]

    unknown = set(metadata) - ALLOWED_FIELDS
    if unknown:
        errors.append(f"{skill_file}: unsupported fields: {', '.join(sorted(unknown))}")

    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not NAME_RE.fullmatch(name):
        errors.append(f"{skill_file}: invalid name: {name!r}")
    if name != path.name:
        errors.append(f"{skill_file}: name must match directory {path.name!r}")
    if not description or len(description) > 1024:
        errors.append(f"{skill_file}: description must contain 1-1024 characters")
    if not body:
        errors.append(f"{skill_file}: instruction body is empty")
    if len(text.splitlines()) > 500:
        errors.append(f"{skill_file}: keep SKILL.md under 500 lines")
    if "TODO" in text:
        errors.append(f"{skill_file}: unresolved TODO marker")

    for raw_target in LINK_RE.findall(body):
        target = raw_target.split("#", 1)[0].strip()
        if not target or "://" in target or target.startswith(("#", "mailto:")):
            continue
        resolved = (path / target).resolve()
        try:
            resolved.relative_to(path.resolve())
        except ValueError:
            errors.append(f"{skill_file}: link escapes skill directory: {raw_target}")
            continue
        if not resolved.exists():
            errors.append(f"{skill_file}: broken relative link: {raw_target}")

    openai_yaml = path / "agents" / "openai.yaml"
    if openai_yaml.exists():
        yaml_text = openai_yaml.read_text(encoding="utf-8")
        if f"${name}" not in yaml_text:
            errors.append(f"{openai_yaml}: default_prompt must mention ${name}")
    return errors


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def validate_manifests() -> list[str]:
    errors: list[str] = []
    paths = [
        ROOT / ".codex-plugin" / "plugin.json",
        ROOT / ".claude-plugin" / "plugin.json",
        ROOT / ".claude-plugin" / "marketplace.json",
        ROOT / ".agents" / "plugins" / "marketplace.json",
    ]
    loaded: dict[Path, dict] = {}
    for path in paths:
        try:
            loaded[path] = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")

    for path in paths[:2]:
        manifest = loaded.get(path, {})
        if manifest.get("name") != "universal-agent-skills":
            errors.append(f"{path}: unexpected plugin name")
        if manifest.get("skills") != "./skills/":
            errors.append(f"{path}: skills must point to ./skills/")

    codex_market = loaded.get(paths[3], {})
    for plugin in codex_market.get("plugins", []):
        policy = plugin.get("policy", {})
        if not {"installation", "authentication"} <= set(policy):
            errors.append(f"{paths[3]}: every plugin requires installation and authentication policy")
        if not plugin.get("category"):
            errors.append(f"{paths[3]}: every plugin requires a category")
    return errors


def validate_adapters() -> list[str]:
    errors: list[str] = []
    path = ROOT / "adapters" / "agents.tsv"
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            errors.append(f"{path}:{number}: expected three tab-separated fields")
            continue
        agent, global_path, project_path = parts
        if not NAME_RE.fullmatch(agent):
            errors.append(f"{path}:{number}: invalid agent id")
        if agent in seen:
            errors.append(f"{path}:{number}: duplicate agent id")
        seen.add(agent)
        for value in (global_path, project_path):
            if Path(value).is_absolute() or ".." in Path(value).parts:
                errors.append(f"{path}:{number}: adapter paths must be safe and relative")
    required = {"codex", "claude", "opencode", "copilot", "universal"}
    if not required <= seen:
        errors.append(f"{path}: missing adapters: {', '.join(sorted(required - seen))}")
    return errors


def validate_profiles() -> list[str]:
    errors: list[str] = []
    profiles_dir = ROOT / "profiles"
    paths = sorted(profiles_dir.glob("*.json"))
    if not paths:
        return [f"{profiles_dir}: no agent stack profiles found"]
    for path in paths:
        try:
            profile = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        errors.extend(f"{path}: {error}" for error in validate_profile(profile))
    return errors


def main() -> int:
    errors: list[str] = []
    skill_dirs = sorted(path for path in SKILLS.iterdir() if path.is_dir())
    if not skill_dirs:
        errors.append(f"{SKILLS}: no skills found")
    for path in skill_dirs:
        errors.extend(validate_skill(path))
    errors.extend(validate_manifests())
    errors.extend(validate_adapters())
    errors.extend(validate_profiles())

    if os.name != "nt":
        for name in (
            "install.sh",
            "bootstrap.sh",
            "scripts/check_pin_freshness.py",
            "scripts/sync_agent_stack.py",
            "scripts/sync_instructions.py",
            "scripts/sync_opencode_config.py",
            "scripts/test-install.sh",
            "scripts/test_check_pin_freshness.py",
            "scripts/test_sync_agent_stack.py",
            "scripts/test_sync_instructions.py",
            "scripts/test_sync_opencode_config.py",
        ):
            path = ROOT / name
            if path.exists() and not os.access(path, os.X_OK):
                errors.append(f"{path}: file is not executable")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"Validated {len(skill_dirs)} skills, plugin manifests, agent adapters, and stack profiles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
