from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple


_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff]")


def _alias_matches(text: str, alias: str) -> bool:
    """Match an entity alias without ASCII substring false positives.

    CJK aliases and multi-word aliases are matched as substrings; a single ASCII
    token is matched as a whole word so ``Citi`` does not match ``city`` and
    ``Nu`` does not match ``number``.
    """
    alias = alias.strip()
    if not alias:
        return False
    if " " in alias or _CJK_RE.search(alias):
        return alias.lower() in text
    pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def build_entity_index(
    entities: Sequence[Dict[str, object]],
) -> List[Tuple[str, Dict[str, object]]]:
    """Return ``(alias, entity)`` pairs sorted longest-first for greedy matching."""
    pairs: List[Tuple[str, Dict[str, object]]] = []
    for entity in entities:
        name = str(entity.get("canonical_name", ""))
        aliases = [str(alias) for alias in entity.get("aliases", [])]
        for alias in aliases + [name]:
            alias = alias.strip()
            if alias:
                pairs.append((alias, entity))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs


def resolve_entity(
    text: str, index: Sequence[Tuple[str, Dict[str, object]]]
) -> Optional[Dict[str, object]]:
    """Return the first watchlist entity mentioned in ``text``, if any."""
    normalized = " " + text.lower() + " "
    for alias, entity in index:
        if _alias_matches(normalized, alias):
            return entity
    return None
