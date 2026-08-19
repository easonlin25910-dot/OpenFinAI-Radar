from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from .classify import classify_item, same_named_event, title_similarity
from .config import load_config
from .fetchers import fetch_source
from .models import Candidate, RawItem
from .report import write_reports


def _merge(target: Candidate, incoming: Candidate) -> None:
    target.source_ids = sorted(set(target.source_ids + incoming.source_ids))
    target.evidence_urls = list(dict.fromkeys(target.evidence_urls + incoming.evidence_urls))
    target.duplicate_titles.append(incoming.title)
    target.evidence_strength = min(5, len(target.evidence_urls))
    target.relevance_score = max(target.relevance_score, incoming.relevance_score)
    if incoming.effective_time < target.effective_time:
        target.effective_time = incoming.effective_time
        target.evidence_time = incoming.evidence_time


def deduplicate(candidates: List[Candidate]) -> Tuple[List[Candidate], int]:
    kept: List[Candidate] = []
    merged = 0
    for candidate in sorted(candidates, key=lambda item: (-item.relevance_score, item.effective_time)):
        duplicate = None
        for existing in kept:
            date_distance = abs(
                (date.fromisoformat(existing.effective_time) - date.fromisoformat(candidate.effective_time)).days
            )
            if date_distance <= 10 and (
                existing.normalized_title == candidate.normalized_title
                or title_similarity(existing.title, candidate.title) >= 0.62
                or same_named_event(existing.title, candidate.title)
            ):
                duplicate = existing
                break
        if duplicate:
            _merge(duplicate, candidate)
            merged += 1
        else:
            kept.append(candidate)
    return kept, merged


def _fetch_all(sources: List[Dict[str, object]]) -> Tuple[List[RawItem], List[Dict[str, object]]]:
    raw: List[RawItem] = []
    health: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=min(6, len(sources))) as executor:
        futures = {executor.submit(fetch_source, source): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                items = future.result()
                raw.extend(items)
                health.append({"id": source["id"], "status": "ok", "items": len(items)})
            except Exception as error:  # source failure must not abort the whole radar
                health.append(
                    {"id": source["id"], "status": "error", "items": 0, "error": str(error)[:300]}
                )
    return raw, sorted(health, key=lambda item: str(item["id"]))


def run_radar(
    *,
    days: int,
    as_of: date,
    config_path: Path,
    output_dir: Path,
    site_path: Path,
    limit: int = 100,
) -> Dict[str, object]:
    if days < 1:
        raise ValueError("days must be positive")
    config = load_config(config_path)
    window_start = as_of - timedelta(days=days - 1)
    raw, health = _fetch_all(config["sources"])
    in_window = [
        item
        for item in raw
        if item.published_at and window_start <= item.published_at.date() <= as_of
    ]
    classified = [
        classify_item(item, minimum_score=int(config.get("minimum_score", 58)))
        for item in in_window
    ]
    accepted = [item for item in classified if item.review_status == "needs_review"]
    deduplicated, merged = deduplicate(accepted)
    deduplicated.sort(key=lambda item: (item.effective_time, item.relevance_score), reverse=True)
    total_candidates = len(deduplicated)
    reported = deduplicated[:limit]
    ok_sources = sum(1 for item in health if item["status"] == "ok")
    source_rate = round(ok_sources / max(1, len(health)) * 100, 1)
    run: Dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"days": days, "start": window_start.isoformat(), "end": as_of.isoformat()},
        "time_policy": {
            "business_event_preferred": True,
            "current_automatic_fallback": "media_report",
            "warning": "Evidence publication time is not necessarily product release time.",
        },
        "metrics": {
            "raw_items": len(raw),
            "items_in_window": len(in_window),
            "accepted_candidates": total_candidates,
            "reported_candidates": len(reported),
            "deduplicated_items": merged,
            "below_threshold": len(classified) - len(accepted),
            "source_success_rate": source_rate,
            "sources_ok": ok_sources,
            "sources_total": len(health),
        },
        "source_health": health,
    }
    write_reports(output_dir, site_path, run, reported)
    return run
