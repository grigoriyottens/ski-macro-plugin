#!/usr/bin/env python3
"""Offline package checks, not an evaluation of model behavior or ERP access."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "ski-macro-assistant"
TARGET_PLUGIN_ID = "Plugin_735dbada42fc81918f61caa8229dd247"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inside(root, relative):
    resolved = (root / relative).resolve()
    require(resolved.is_relative_to(root.resolve()), f"Path escapes package: {relative}")
    return resolved


def validate(root=ROOT):
    catalog = json.loads((root / ".agents/plugins/marketplace.json").read_text())
    require(catalog["name"] == "wai-ski", "Unexpected marketplace identity")
    require(len(catalog["plugins"]) == 1, "Unexpected plugin count")
    entry = catalog["plugins"][0]
    require(entry["name"] == PLUGIN_NAME, "Plugin name changed")
    require(entry["pluginId"] == TARGET_PLUGIN_ID, "Wrong workspace migration target")
    require(entry["source"]["source"] == "local", "Expected in-repository source")
    plugin = inside(root, entry["source"]["path"])
    require(plugin == root.resolve() / "plugins" / PLUGIN_NAME, "Unexpected plugin path")
    require(entry["category"] == "Productivity", "Missing category")
    require(entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "Unexpected repository policy; configure workspace policies in ChatGPT")
    manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text())
    require(manifest["name"] == PLUGIN_NAME, "Manifest/catalog name mismatch")
    version = manifest["version"]
    require(re.fullmatch(r"\d+\.\d+\.\d+", version), "Release needs numeric semver")
    require(manifest["skills"] == "./skills/", "Unexpected skills path")
    require(not any(key in manifest for key in ("mcpServers", "apps", "hooks")),
            "Skills-only release must not bundle servers, apps, or hooks")
    require(manifest["author"]["name"], "Missing author")
    ui = manifest["interface"]
    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        require(isinstance(ui.get(key), str) and ui[key].strip(), f"Missing interface.{key}")
    prompts = ui["defaultPrompt"]
    require(isinstance(prompts, list) and 1 <= len(prompts) <= 3, "Invalid starter prompts")
    require(all(isinstance(p, str) and len(p) <= 128 for p in prompts), "Starter prompt too long")
    skill = plugin / "skills/macro-work-assistant"
    body = (skill / "SKILL.md").read_text()
    front = body.split("---", 2)
    require(len(front) == 3 and not front[0].strip(), "Missing YAML frontmatter")
    require(re.search(r"(?m)^name: macro-work-assistant$", front[1]), "Wrong skill name")
    require(f'version: "{version}"' in front[1], "Skill/manifest version mismatch")
    require("allow_implicit_invocation: true" in (skill / "agents/openai.yaml").read_text(),
            "Implicit invocation disabled")
    expected = {
        ".codex-plugin/plugin.json", "skills/macro-work-assistant/SKILL.md",
        "skills/macro-work-assistant/agents/openai.yaml",
        "skills/macro-work-assistant/references/macrodata-routing.md",
        "skills/macro-work-assistant/references/erp-writes.md",
        "skills/macro-work-assistant/references/contract-selection.md",
    }
    actual = set()
    for file in plugin.rglob("*"):
        require(not file.is_symlink(), f"Symlink not allowed in release: {file}")
        if not file.is_file():
            continue
        actual.add(file.relative_to(plugin).as_posix())
        require(file.stat().st_size < 100_000, f"Unexpected large file: {file}")
        text = file.read_text()
        require("[TODO:" not in text, f"Unfinished scaffold: {file}")
        if file.suffix == ".md":
            for target in re.findall(r"\]\(([^\s)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                linked = inside(plugin, str(file.parent.relative_to(plugin) / target.split("#")[0]))
                require(linked.is_file(), f"Broken reference: {file.name} -> {target}")
    require(actual == expected, f"Unexpected/missing package files: {actual ^ expected}")
    require("references/contract-selection.md" in body, "Classification reference is unreachable")
    return version


if __name__ == "__main__":
    print(f"PASS: package {PLUGIN_NAME} {validate()}; behavior/ERP tests not executed")
