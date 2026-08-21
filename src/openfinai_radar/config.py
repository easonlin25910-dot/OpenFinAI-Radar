from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("version") != 1:
        raise ValueError("Unsupported config version")
    if not config.get("sources"):
        raise ValueError("At least one source is required")
    return config


def load_env(path: Path) -> None:
    """Load a minimal ``.env`` file without overriding real environment values."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def load_watchlist(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "entities": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"version": 1, "entities": []}
