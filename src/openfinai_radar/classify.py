from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .models import Candidate, RawItem, TimeEvidence, resolve_effective_time


TERM_GROUPS: Dict[str, Dict[str, Sequence[str]]] = {
    "finance": {
        "banking": ("bank", "banking", "银行", "銀行", "banque", "banco", "finanz"),
        "insurance": ("insurance", "insurer", "保险", "保険", "assurance", "seguro"),
        "payments": ("payment", "payments", "wallet", "支付", "決済", "paiement", "pagos"),
        "wealth_and_markets": (
            "wealth", "asset management", "investment", "trading", "capital markets",
            "资管", "财富", "投资", "証券", "investissement",
        ),
        "lending_and_credit": ("lending", "loan", "credit", "mortgage", "贷款", "信贷", "融資"),
        "risk_and_compliance": (
            "compliance", "anti-money laundering", "aml", "fraud", "risk management",
            "合规", "反洗钱", "风控", "不正検知", "conformité",
        ),
        "fintech": ("fintech", "financial services", "金融科技", "金融サービス", "servicios financieros"),
        "financial_brand": (
            "alipay", "ant group", "razorpay", "stripe", "paypal", "plaid", "klarna", "revolut",
            "visa", "mastercard", "american express", "bloomberg", "lseg", "nasdaq", "swift",
            "jpmorgan", "jpmorgan chase", "goldman sachs", "morgan stanley", "citigroup", "citi",
            "hsbc", "barclays", "santander", "standard chartered", "deutsche bank", "ubs",
            "shинhan", "shinhan", "ant financial", "wealthfront", "robinhood",
        ),
    },
    "ai": {
        "agent": ("ai agent", "agentic", "copilot", "智能体", "智能代理", "aiエージェント", "agent ia"),
        "generative_ai": (
            "generative ai", "genai", "large language model", "llm", "生成式ai", "生成式人工智能",
            "生成ai", "生成ＡＩ", "ia générative", "inteligencia artificial generativa",
        ),
        "machine_learning": (
            "artificial intelligence", "machine learning", " ai ", "人工智能", "机器学习",
            "人工知能", "intelligence artificielle", "inteligencia artificial", " künstliche intelligenz",
            " ki ",
        ),
    },
    "event": {
        "product_launch": (
            "launch", "launched", "launches", "unveil", "unveils", "introduce", "introduces",
            "release", "released", "rolls out", "available", "发布", "推出", "上线", "正式发布",
            "開始", "提供開始", "導入", "lance", "lancement", "lanza", "lanzamiento", "einführung",
        ),
            "customer_deployment": (
            "deploy", "deployed", "goes live", "go live", "adopt", "adopts", "selected by", "selects",
            "implements", "implementation", "production", "integrates", "integration", "客户", "部署", "投产", "采用", "採用",
            "本番", "déploie", "adopta",
        ),
        "commercial_agreement": (
            "partnership", "partners with", "contract", "agreement", "paid", "customer", "collaboration",
            "合作", "携手", "签约", "采购", "中标", "打造", "契約", "提携", "partenariat", "acuerdo",
        ),
        "pilot": ("pilot", "proof of concept", "poc", "sandbox", "trial", "试点", "概念验证", "実証実験"),
        "scale": ("scale", "scaled", "rollout", "enterprise-wide", "millions of users", "规模化", "全面推广"),
    },
}

NEGATIVE_TERMS = (
    "opinion", "forecast", "stock price", "price prediction", "may change", "could transform",
    "explainer", "what is", "课程", "培训", "股价", "概念股", "会取代", "見通し",
)

STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with", "by", "from",
    "ai", "new", "its", "at", "as", "is", "are", "will", "financial", "finance",
}

GENERIC_EVENT_TOKENS = STOP_WORDS | {
    "launch", "launches", "launched", "unveils", "release", "released", "product", "platform",
    "model", "foundation", "powered", "agent", "agents", "agentic", "bank", "banking", "payments",
    "generative", "artificial", "intelligence", "deployment", "deploys", "financial", "services",
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def title_tokens(value: str) -> Set[str]:
    return {part for part in normalize_text(value).split() if len(part) > 1 and part not in STOP_WORDS}


def jaccard(left: str, right: str) -> float:
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def title_similarity(left: str, right: str) -> float:
    """Blend Jaccard with overlap coefficient for repeated syndicated headlines."""
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    return max(intersection / len(a | b), intersection / min(len(a), len(b)))


def same_named_event(left: str, right: str) -> bool:
    """Detect syndicated headlines that share an organization and named product."""
    a = {token for token in title_tokens(left) if token not in GENERIC_EVENT_TOKENS and len(token) > 3}
    b = {token for token in title_tokens(right) if token not in GENERIC_EVENT_TOKENS and len(token) > 3}
    return len(a & b) >= 2


def _matches(text: str, words: Iterable[str]) -> List[str]:
    return sorted({word.strip() for word in words if word.lower() in text})


def _signals(text: str) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for top_group, groups in TERM_GROUPS.items():
        for name, terms in groups.items():
            matches = _matches(text, terms)
            if matches:
                result[f"{top_group}:{name}"] = matches
    return result


def _group_names(signals: Dict[str, List[str]], prefix: str) -> List[str]:
    return sorted(key.split(":", 1)[1] for key in signals if key.startswith(prefix + ":"))


def _score(signals: Dict[str, List[str]], text: str) -> int:
    finance = len(_group_names(signals, "finance"))
    ai = len(_group_names(signals, "ai"))
    events = len(_group_names(signals, "event"))
    score = min(100, finance * 18 + ai * 20 + events * 22)
    score -= sum(14 for term in NEGATIVE_TERMS if term in text)
    return max(0, score)


def _stage_and_event(signals: Dict[str, List[str]]) -> Tuple[str, str]:
    events = set(_group_names(signals, "event"))
    if "scale" in events:
        return "M5", "scale"
    if "commercial_agreement" in events and "customer_deployment" in events:
        return "M4", "commercial_agreement"
    if "customer_deployment" in events:
        return "M3", "customer_deployment"
    if "product_launch" in events:
        return "M3", "product_launch"
    if "commercial_agreement" in events:
        return "M2", "commercial_agreement"
    if "pilot" in events:
        return "M2", "pilot"
    return "M0", "unclassified_signal"


def classify_item(item: RawItem, minimum_score: int = 58) -> Candidate:
    discovered = item.fetched_at.astimezone(timezone.utc)
    combined = normalize_text(f" {item.title} {item.description} ")
    signals = _signals(" " + combined + " ")
    if item.source_kind == "mcp_registry":
        signals.setdefault("ai:agent", []).append("official MCP Registry listing")
        signals.setdefault("event:product_launch", []).append("marketplace listing")
    score = _score(signals, combined)
    maturity, event_type = _stage_and_event(signals)

    time_evidence: List[TimeEvidence] = []
    evidence_time = None
    if item.published_at:
        evidence_time = item.published_at.date().isoformat()
        time_kind = "marketplace_listing" if item.source_kind == "mcp_registry" else "media_report"
        time_confidence = 0.85 if item.source_kind == "mcp_registry" else 0.65
        time_evidence.append(
            TimeEvidence(
                value=item.published_at.date(),
                kind=time_kind,
                confidence=time_confidence,
                source_url=item.url,
            )
        )
    effective = resolve_effective_time(time_evidence, discovered)
    normalized = normalize_text(item.title)
    identifier = "finai-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    status = "estimated_from_evidence" if effective.kind != "system_discovery" else "discovery_time_only"
    domains = _group_names(signals, "finance")
    ai_types = _group_names(signals, "ai")
    summary = (
        f"{item.publisher}于{effective.value.isoformat()}公开“{item.title}”。"
        f"标题或摘要包含金融场景（{'、'.join(domains) or '待确认'}）、"
        f"AI能力（{'、'.join(ai_types) or '待确认'}）和{event_type}信号，"
        f"自动暂判为{maturity}；当前有效时间取证据发布时间，需人工核对真实业务事件时间。"
    )
    has_required_signals = bool(domains and ai_types and _group_names(signals, "event"))
    review_status = "needs_review" if score >= minimum_score and has_required_signals else "below_threshold"
    return Candidate(
        id=identifier,
        title=item.title,
        normalized_title=normalized,
        publisher=item.publisher,
        source_ids=[item.source_id],
        evidence_urls=[item.url],
        evidence_time=evidence_time,
        event_time=None,
        listing_time=evidence_time if item.source_kind == "mcp_registry" else None,
        first_public_time=evidence_time,
        discovered_at=discovered.isoformat(),
        effective_time=effective.value.isoformat(),
        effective_time_type=effective.kind,
        effective_time_confidence=effective.confidence,
        effective_time_precision=effective.precision,
        time_status=status,
        event_type=event_type,
        maturity=maturity,
        finance_domains=domains,
        ai_types=ai_types,
        relevance_score=score,
        evidence_strength=1,
        summary=summary,
        review_status=review_status,
        signals=signals,
    )
