#!/usr/bin/env python3
"""Validate repository-owned plugin files without external dependencies."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SUPPORTED_EVENTS = {"UserPromptSubmit", "Stop"}


def load_object(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def verify(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / ".codex-plugin" / "plugin.json"
    hooks_path = root / "hooks" / "hooks.json"
    runner_path = root / "scripts" / "token-counter"
    rates_path = root / "config" / "model_rates.json"

    for path in (manifest_path, hooks_path, runner_path, rates_path):
        if not path.is_file():
            errors.append(f"missing required file: {path.relative_to(root)}")
    if errors:
        return errors

    manifest = load_object(manifest_path)
    if manifest.get("name") != root.name:
        errors.append("plugin name must match the repository directory name")
    version = manifest.get("version")
    if not isinstance(version, str) or SEMVER.fullmatch(version) is None:
        errors.append("plugin version must be strict semantic versioning")
    if "hooks" in manifest:
        errors.append("plugin manifest must use default hooks/hooks.json discovery")

    hooks_document = load_object(hooks_path)
    hooks = hooks_document.get("hooks")
    if not isinstance(hooks, Mapping):
        errors.append("hooks.json must contain a hooks object")
    else:
        missing_events = SUPPORTED_EVENTS.difference(str(key) for key in hooks)
        if missing_events:
            errors.append(f"missing hook events: {', '.join(sorted(missing_events))}")
        for event in SUPPORTED_EVENTS:
            groups = hooks.get(event)
            if not isinstance(groups, list) or not groups:
                errors.append(f"{event} must contain at least one matcher group")

    rates = load_object(rates_path)
    models = rates.get("models")
    if not isinstance(models, Mapping) or not models:
        errors.append("model_rates.json must contain at least one model")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    try:
        errors = verify(root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"plugin verification failed: {error}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"plugin verification failed: {error}", file=sys.stderr)
        return 1
    print("Plugin repository verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
