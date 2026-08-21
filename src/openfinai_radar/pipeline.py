from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .classify import classify_item, same_named_event, title_similarity
from .config import load_config, load_env, load_watchlist
from .entities import build_entity_index, resolve_entity
from .fetchers import fetch_source
from .models import Candidate, RawItem
from .report import write_reports


INNOVATION_RANK = {
    "not_demonstrated": 1,
    "incremental": 2,
    "application_design": 3,
    "substantive": 4,
}

CHANNEL_WEIGHTS = {
    "official": 30,
    "marketplace": 22,
    "news": 14,
    "community": 12,
    "code": 12,
}


def _merge(target: Candidate, incoming: Candidate) -> None:
    target.source_ids = sorted(set(target.source_ids + incoming.source_ids))
    target.evidence_urls = list(dict.fromkeys(target.evidence_urls + incoming.evidence_urls))
    target.duplicate_titles.append(incoming.title)
    target.evidence_strength = min(5, len(target.evidence_urls))
    target.relevance_score = max(target.relevance_score, incoming.relevance_score)
    if target.product_name_status == "undisclosed" and incoming.product_name_status != "undisclosed":
        target.product_name = incoming.product_name
        target.product_name_status = incoming.product_name_status
        target.product_search_url = incoming.product_search_url
    if not target.official_url and incoming.official_url:
        target.official_url = incoming.official_url
        target.official_url_status = incoming.official_url_status
    if target.customer_type == "undisclosed" and incoming.customer_type != "undisclosed":
        target.customer_type = incoming.customer_type
        target.customer_type_assessment = incoming.customer_type_assessment
    elif {target.customer_type, incoming.customer_type} == {"to_b", "to_c"}:
        target.customer_type = "both"
        target.customer_type_assessment = "不同公开证据分别指向机构用户和个人/终端客户，暂判为TO B与TO C兼有。"
    target.product_categories = list(
        dict.fromkeys(target.product_categories + incoming.product_categories)
    )
    if INNOVATION_RANK.get(incoming.innovation_level, 0) > INNOVATION_RANK.get(
        target.innovation_level, 0
    ):
        target.innovation_level = incoming.innovation_level
        target.innovation_assessment = incoming.innovation_assessment
        target.innovation_signals = incoming.innovation_signals
    target.channels = sorted(set(target.channels + incoming.channels))
    seen_urls = {item.get("url") for item in target.evidence}
    for evidence in incoming.evidence:
        if evidence.get("url") not in seen_urls:
            target.evidence.append(evidence)
            seen_urls.add(evidence.get("url"))
    if not target.entity and incoming.entity:
        target.entity = incoming.entity
        target.entity_role = incoming.entity_role
        target.region = incoming.region
    target.is_watchlist = target.is_watchlist or incoming.is_watchlist
    if target.tech_layer == "other" and incoming.tech_layer != "other":
        target.tech_layer = incoming.tech_layer
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
                or (
                    same_named_event(existing.title, candidate.title)
                    and title_similarity(existing.title, candidate.title) >= 0.45
                )
            ):
                duplicate = existing
                break
        if duplicate:
            _merge(duplicate, candidate)
            merged += 1
        else:
            kept.append(candidate)
    return kept, merged


def _fetch_all(
    sources: List[Dict[str, object]],
    entities: Optional[List[Dict[str, object]]] = None,
) -> Tuple[List[RawItem], List[Dict[str, object]]]:
    raw: List[RawItem] = []
    health: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=min(6, len(sources))) as executor:
        futures = {
            executor.submit(fetch_source, source, entities=entities or []): source
            for source in sources
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                raw.extend(result.items)
                if result.errors and result.items:
                    status = "partial"
                elif result.errors and not result.items:
                    status = "error"
                else:
                    status = "ok"
                health.append(
                    {
                        "id": source["id"],
                        "status": status,
                        "items": len(result.items),
                        "errors": result.errors,
                    }
                )
            except Exception as error:  # source failure must not abort the whole radar
                health.append(
                    {
                        "id": source["id"],
                        "status": "error",
                        "items": 0,
                        "errors": [str(error)[:300]],
                    }
                )
    return raw, sorted(health, key=lambda item: str(item["id"]))


def build_distributions(cases: List[Candidate]) -> Dict[str, Dict[str, int]]:
    distributions: Dict[str, Dict[str, int]] = {
        "maturity": {},
        "event_type": {},
        "relevance": {"90-100": 0, "75-89": 0, "60-74": 0, "<60": 0},
        "innovation": {},
    }
    for case in cases:
        distributions["maturity"][case.maturity] = distributions["maturity"].get(case.maturity, 0) + 1
        distributions["event_type"][case.event_type] = distributions["event_type"].get(case.event_type, 0) + 1
        distributions["innovation"][case.innovation_level] = distributions["innovation"].get(case.innovation_level, 0) + 1
        if case.relevance_score >= 90:
            bucket = "90-100"
        elif case.relevance_score >= 75:
            bucket = "75-89"
        elif case.relevance_score >= 60:
            bucket = "60-74"
        else:
            bucket = "<60"
        distributions["relevance"][bucket] += 1
    return distributions


def _heat_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _compute_heat(candidate: Candidate, as_of: date) -> int:
    channels = {evidence.get("channel", "news") for evidence in candidate.evidence}
    diversity = sum(CHANNEL_WEIGHTS.get(channel, 8) for channel in channels)
    volume = min(len(candidate.evidence), 10) * 2
    recency = 0
    try:
        recency = max(0, 10 - (as_of - date.fromisoformat(candidate.effective_time)).days)
    except (ValueError, TypeError):
        pass
    watchlist_bonus = 10 if candidate.is_watchlist else 0
    return min(100, diversity + volume + recency + watchlist_bonus)


def _resolve_entities(items: List[RawItem], index) -> None:
    for item in items:
        text = f"{item.title} {item.publisher} {item.description}"
        entity = resolve_entity(text, index)
        if entity:
            item.entity = str(entity.get("canonical_name", ""))
            item.entity_role = str(entity.get("role", ""))
            item.region = str(entity.get("region", ""))
            item.is_watchlist = True


def build_graph(cases: List[Candidate]) -> Dict[str, object]:
    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []
    node_ids = set()

    def add_node(node_id: str, node_type: str, label: str, **extra: object) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        node: Dict[str, object] = {"id": node_id, "type": node_type, "label": label}
        node.update(extra)
        nodes.append(node)

    for case in cases:
        case_id = case.id
        add_node(
            case_id,
            "case",
            case.product_name or case.title,
            heat=case.heat,
            relevance=case.relevance_score,
            is_watchlist=case.is_watchlist,
        )
        if case.entity:
            entity_id = "entity:" + case.entity
            add_node(entity_id, "entity", case.entity, region=case.region)
            edges.append({"source": case_id, "target": entity_id, "type": "issued_by"})
        by_source: Dict[str, Dict[str, object]] = {}
        for evidence in case.evidence:
            source_id = str(evidence.get("source_id", "unknown"))
            entry = by_source.setdefault(
                source_id, {"channel": evidence.get("channel", "news"), "count": 0}
            )
            entry["count"] = int(entry["count"]) + 1
        for source_id, meta in by_source.items():
            source_node = "source:" + source_id
            add_node(source_node, "source", source_id, channel=meta["channel"])
            edges.append(
                {
                    "source": case_id,
                    "target": source_node,
                    "type": "mentioned_on",
                    "weight": meta["count"],
                }
            )
    return {"nodes": nodes, "edges": edges}


def _load_state(path: Path) -> Dict[str, object]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(path: Path, state: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_radar(
    *,
    days: int,
    as_of: date,
    config_path: Path,
    output_dir: Path,
    site_path: Path,
    limit: int = 100,
    env_path: Path = Path(".env"),
    watchlist_path: Path = Path("config/watchlist.json"),
) -> Dict[str, object]:
    if days < 1:
        raise ValueError("days must be positive")
    load_env(env_path)
    config = load_config(config_path)
    watchlist = load_watchlist(watchlist_path)
    entity_index = build_entity_index(watchlist.get("entities", []))
    window_start = as_of - timedelta(days=days - 1)
    raw, health = _fetch_all(config["sources"], watchlist.get("entities", []))
    _resolve_entities(raw, entity_index)
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
    state_path = output_dir / "state.json"
    previous_cases = _load_state(state_path).get("cases", {})
    if not isinstance(previous_cases, dict):
        previous_cases = {}
    next_cases: Dict[str, object] = {}
    for candidate in deduplicated:
        candidate.heat = _compute_heat(candidate, as_of)
        candidate.heat_level = _heat_level(candidate.heat)
        previous = previous_cases.get(candidate.id)
        if isinstance(previous, dict):
            candidate.is_new = False
            candidate.delta = max(
                0, len(candidate.evidence) - int(previous.get("evidence_count", 0))
            )
            next_cases[candidate.id] = {
                "first_seen": previous.get("first_seen", candidate.effective_time),
                "evidence_count": len(candidate.evidence),
            }
        else:
            candidate.is_new = True
            candidate.delta = len(candidate.evidence)
            next_cases[candidate.id] = {
                "first_seen": candidate.effective_time,
                "evidence_count": len(candidate.evidence),
            }
    _save_state(state_path, {"cases": next_cases})
    total_candidates = len(deduplicated)
    reported = deduplicated[:limit]
    graph = build_graph(reported)
    ok_sources = sum(1 for item in health if item["status"] == "ok")
    partial_sources = sum(1 for item in health if item["status"] == "partial")
    working_sources = ok_sources + partial_sources
    source_rate = round(working_sources / max(1, len(health)) * 100, 1)
    run: Dict[str, object] = {
        "schema_version": 3,
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
            "sources_partial": partial_sources,
            "sources_total": len(health),
            "watchlist_candidates": sum(1 for item in reported if item.is_watchlist),
            "new_candidates": sum(1 for item in reported if item.is_new),
            "hot_candidates": sum(1 for item in reported if item.heat_level == "high"),
        },
        "source_health": health,
        "distributions": build_distributions(reported),
    }
    write_reports(output_dir, site_path, run, reported, graph=graph)
    return run
