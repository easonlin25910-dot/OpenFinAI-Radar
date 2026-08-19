from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("version") != 1:
        raise ValueError("Unsupported config version")
    if not config.get("sources"):
        raise ValueError("At least one source is required")
    return config

