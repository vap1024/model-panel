"""Route configuration, validation, and safe environment handling."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass
class Route:
    """A command-backed route and its descriptive metadata."""
    name: str
    command: list[str]
    model: str | None = None
    kind: str = "unknown"
    timeout_s: float = 30.0
    fingerprint: str | None = None


@dataclass
class PanelConfig:
    """Ordered collection of routes to invoke for one task."""
    routes: list[Route] = field(default_factory=list)


def validate_config(config: PanelConfig) -> None:
    """Reject ambiguous or unusable route declarations with clear errors."""
    names: set[str] = set()
    for route in config.routes:
        if not route.name.strip():
            raise ValueError("route name must not be empty")
        if route.name in names:
            raise ValueError(f"duplicate route name: {route.name}")
        names.add(route.name)
        if not route.command or not any(item.strip() for item in route.command):
            raise ValueError(f"route {route.name} command must not be empty")
        if route.timeout_s <= 0:
            raise ValueError(f"route {route.name} timeout_s must be positive")


def load_config(path: str | Path) -> PanelConfig:
    """Load and validate a JSON object containing a routes array."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("routes"), list):
        raise ValueError("config must be an object with a routes list")
    try:
        config = PanelConfig([Route(**entry) for entry in raw["routes"]])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid route configuration: {exc}") from exc
    validate_config(config)
    return config


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand_env(command: Sequence[str], environ: Mapping[str, str] | None = None) -> list[str]:
    """Expand environment placeholders in command items; fail on missing values."""
    values = os.environ if environ is None else environ
    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        if name in values and values[name] != "":
            return values[name]
        if default is not None:
            return default
        raise ValueError(f"missing environment variable: {name}")
    return [_ENV_PATTERN.sub(replace, item) for item in command]


def redact(text: str, secrets: Sequence[str]) -> str:
    """Replace known secret values in arbitrary output text."""
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "***")
    return text


def collect_secrets(env: Mapping[str, str] | None = None) -> list[str]:
    """Collect sufficiently long values from secret-like environment names."""
    values = os.environ if env is None else env
    markers = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    return [value for name, value in values.items() if any(mark in name.upper() for mark in markers) and len(value) >= 4]

