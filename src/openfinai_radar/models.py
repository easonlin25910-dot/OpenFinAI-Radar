from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional


TIME_PRIORITY = {
    "product_release": 1,
    "customer_go_live": 2,
    "official_announcement": 3,
    "regulatory_or_procurement": 4,
    "marketplace_listing": 5,
    "technical_release": 6,
    "media_report": 7,
    "system_discovery": 8,
}


@dataclass(frozen=True)
class TimeEvidence:
    value: date
    kind: str
    confidence: float
    precision: str = "day"
    source_url: str = ""


@dataclass
class RawItem:
    source_id: str
    source_kind: str
    title: str
    url: str
    publisher: str
    published_at: Optional[datetime]
    description: str = ""
    query: str = ""
    language: str = "en"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Candidate:
    id: str
    title: str
    normalized_title: str
    publisher: str
    source_ids: List[str]
    evidence_urls: List[str]
    evidence_time: Optional[str]
    event_time: Optional[str]
    listing_time: Optional[str]
    first_public_time: Optional[str]
    discovered_at: str
    effective_time: str
    effective_time_type: str
    effective_time_confidence: float
    effective_time_precision: str
    time_status: str
    event_type: str
    maturity: str
    finance_domains: List[str]
    ai_types: List[str]
    relevance_score: int
    evidence_strength: int
    summary: str
    application_scenario: str
    expected_value: str
    innovation_level: str
    innovation_assessment: str
    innovation_signals: List[str] = field(default_factory=list)
    review_status: str = "needs_review"
    duplicate_titles: List[str] = field(default_factory=list)
    signals: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def resolve_effective_time(
    evidences: List[TimeEvidence], discovered_at: datetime
) -> TimeEvidence:
    """Return the best available time without discarding lower-grade evidence.

    Business-event times win over publication/listing times. Within a grade, the
    earliest public timestamp is used because it best represents discoverability.
    """
    if not evidences:
        return TimeEvidence(
            value=discovered_at.date(),
            kind="system_discovery",
            confidence=0.30,
            precision="day",
        )
    return min(
        evidences,
        key=lambda item: (TIME_PRIORITY.get(item.kind, 99), item.value),
    )
