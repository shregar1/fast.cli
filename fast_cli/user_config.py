"""Optional user defaults for project generation (``~/.config/fastmvc/defaults.toml``).

Reads are best-effort: missing file or parse errors yield an empty mapping so the
CLI keeps working without configuration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pragma: no cover


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "fastmvc"
    return Path.home() / ".config" / "fastmvc"


def defaults_path() -> Path:
    return config_dir() / "defaults.toml"


def load_user_defaults() -> dict[str, Any]:
    """Load ``[defaults]`` from the TOML file, or return ``{}``."""
    path = defaults_path()
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = tomllib.loads(text)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    d = data.get("defaults")
    return dict(d) if isinstance(d, dict) else {}
