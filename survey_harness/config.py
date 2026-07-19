"""Load the single survey quality configuration without requiring PyYAML."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

CONFIG_PATH = Path(__file__).parent / "config" / "quality_profiles.yaml"


def _load_mapping(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - JSON-compatible default needs no dependency
            raise RuntimeError(f"{path} is not JSON-compatible YAML and PyYAML is unavailable") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"quality config must be an object: {path}")
    return data


def load_config(path: Path | None = None) -> Dict[str, Any]:
    return _load_mapping(path or CONFIG_PATH)


def load_profile(name: str, path: Path | None = None) -> Dict[str, Any]:
    config = load_config(path)
    profiles = config.get("profiles", {})
    if name not in profiles:
        raise KeyError(f"unknown quality profile {name!r}; choose from {sorted(profiles)}")
    profile = deepcopy(profiles[name])
    profile["name"] = name
    profile["dimensions"] = deepcopy(config["dimensions"])
    return profile

