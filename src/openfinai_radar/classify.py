from __future__ import annotations

import hashlib
import re
import unicodedata
import urllib.parse
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

FINANCE_LABELS = {
    "banking": "银行业务",
    "insurance": "保险",
    "payments": "支付",
    "wealth_and_markets": "财富管理与资本市场",
    "lending_and_credit": "信贷",
    "risk_and_compliance": "风险与合规",
    "fintech": "金融科技",
    "financial_brand": "金融机构",
}

EVENT_LABELS = {
    "product_launch": "产品发布",
    "customer_deployment": "客户部署",
    "commercial_agreement": "商业合作",
    "pilot": "试点",
    "scale": "规模化应用",
    "unclassified_signal": "待分类事件",
}

INNOVATION_LEVELS = {
    "substantive": 4,
    "application_design": 3,
    "incremental": 2,
    "not_demonstrated": 1,
}

CONFIRMED_PRODUCT_PAGES = {
    "ktx skills kit": "https://www.ktx.com/en/trade-skills",
    "visa intelligent commerce": "https://global-corporate.review.visa.com/sites/visa-perspectives/newsroom/visa-intelligent-commerce-connect-ai-shopping-for-businesses.html",
}

OFFICIAL_COMPANY_SITES = {
    "alipay": "https://www.alipay.com/",
    "ant group": "https://www.antgroup.com/",
    "razorpay": "https://razorpay.com/",
    "visa": "https://www.visa.com/",
    "mastercard": "https://www.mastercard.com/",
    "stripe": "https://stripe.com/",
    "paypal": "https://www.paypal.com/",
    "plaid": "https://plaid.com/",
    "klarna": "https://www.klarna.com/",
    "revolut": "https://www.revolut.com/",
    "bloomberg": "https://www.bloomberg.com/",
    "lseg": "https://www.lseg.com/",
    "nasdaq": "https://www.nasdaq.com/",
    "swift": "https://www.swift.com/",
    "jpmorgan": "https://www.jpmorgan.com/",
    "goldman sachs": "https://www.goldmansachs.com/",
    "morgan stanley": "https://www.morganstanley.com/",
    "citigroup": "https://www.citigroup.com/",
    "citi": "https://www.citi.com/",
    "hsbc": "https://www.hsbc.com/",
    "barclays": "https://www.barclays.com/",
    "santander": "https://www.santander.com/",
    "standard chartered": "https://www.sc.com/",
    "deutsche bank": "https://www.db.com/",
    "ubs": "https://www.ubs.com/",
    "shinhan": "https://www.shinhangroup.com/",
}

TO_B_TERMS = (
    "enterprise", "institution", "financial institutions", "business", "merchant", "b2b",
    "bank", "banking operations", "employee", "internal", "advisor", "broker", "insurer",
    "compliance", "api", "integration", "developer", "skills kit", "sme", "企业", "机构",
    "商户", "银行", "员工", "内部", "顾问", "合规", "法人", "企業", "銀行", "法人向け",
)

TO_C_TERMS = (
    "consumer", "personal finance", "personal loan", "retail customer", "individual",
    "borrower", "household", "end user", "wallet assistant", "mortgage loan", "个人", "消费者",
    "个人金融", "个人贷款", "零售客户", "借款人", "用户", "個人", "消費者", "個人向け",
)

DOMAIN_TO_PRODUCT_CATEGORY = {
    "banking": "banking_operations",
    "payments": "payments_wallets",
    "lending_and_credit": "lending_financing",
    "insurance": "insurance",
    "wealth_and_markets": "investment_markets",
    "risk_and_compliance": "risk_compliance_fraud",
    "fintech": "fintech_infrastructure",
}

PRODUCT_CATEGORY_ORDER = tuple(DOMAIN_TO_PRODUCT_CATEGORY.values()) + ("other_finance",)


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


def _application_details(
    text: str, domains: List[str], ai_types: List[str]
) -> Tuple[str, str]:
    """Explain likely use and value without inventing facts absent from evidence."""
    agent = "agent" in ai_types
    scenario_key = "generic"
    if "payments" in domains and any(term in text for term in ("fraud", "欺诈", "不正検知")):
        scenario_key = "payment_risk"
        scenario = "用于支付交易的风险识别、路由或成功率优化，把AI判断嵌入交易处理环节。"
        value = "预期减少欺诈损失和人工规则维护，并提高支付成功率；实际提升幅度仍需客户或官方数据验证。"
    elif "payments" in domains and agent:
        scenario_key = "agent_payments"
        scenario = "面向AI智能体的支付场景，使智能体能够在授权、身份和风控约束下调用支付服务或完成交易。"
        value = "预期降低智能体完成商业交易的系统接入成本；是否实现端到端自主支付仍需核查产品权限和风控边界。"
    elif "wealth_and_markets" in domains and any(term in text for term in ("trading", "trade", "交易", "証券")):
        scenario_key = "trading"
        scenario = "用于交易研究与执行工作流，让交易员或AI智能体调用行情、分析能力，并在有权限的情况下连接交易执行。"
        value = "预期缩短从信息分析到交易决策的时间；对收益率、风险和执行质量的影响尚无可核验结论。"
    elif "lending_and_credit" in domains and any(term in text for term in ("match", "matching", "匹配")):
        scenario_key = "loan_matching"
        scenario = "用于贷款产品匹配，根据借款需求或客户条件辅助筛选适合的个人、企业或按揭贷款方案。"
        value = "预期减少人工比较和初筛时间、提高申请转化；匹配准确率及是否影响授信决策仍需核验。"
    elif "lending_and_credit" in domains:
        scenario_key = "credit"
        scenario = "用于信贷流程中的客户筛选、信用分析、授信辅助或贷后管理，具体环节以原始产品资料为准。"
        value = "预期提高信贷处理效率和风险识别能力；现有自动证据不足以证明审批质量或坏账率改善。"
    elif "risk_and_compliance" in domains:
        scenario_key = "compliance"
        scenario = "用于合规、反洗钱、欺诈或审计检查，辅助识别异常、整理证据并生成待人工复核的结果。"
        value = "预期降低重复审查工作量并缩短调查时间；不能据此认定系统可替代合规责任人。"
    elif "insurance" in domains:
        scenario_key = "insurance"
        scenario = "用于保险销售、承保、保单服务或理赔流程中的信息处理与任务辅助，具体环节需结合产品原文确认。"
        value = "预期缩短服务响应和材料处理时间；现有证据不足以确认承保或理赔指标改善。"
    elif "banking" in domains and any(term in text for term in ("appraisal", "valuation", "鑑定", "估值")):
        scenario_key = "appraisal"
        scenario = "用于银行房地产或抵押物估值材料的检查，AI智能体辅助核对报告内容并提示需要人工确认的问题。"
        value = "预期减少报告复核耗时并提升检查一致性；自动系统不会把报道中的效果数字视为已验证事实。"
    elif "banking" in domains and any(term in text for term in ("customer service", "contact center", "voicebot", "客服", "オペレーター")):
        scenario_key = "bank_service"
        scenario = "用于银行客户服务，通过生成式AI或语音智能体回答问题、分流请求并辅助完成服务流程。"
        value = "预期缩短等待时间、提高自助服务覆盖率；复杂咨询和高风险操作仍应由人工接管。"
    elif "banking" in domains:
        scenario_key = "bank_operations"
        scenario = "用于银行内部运营或客户业务流程，通过AI分析信息、辅助员工或执行受控的流程任务。"
        value = "预期减少重复操作和跨系统查询时间；具体业务效果需由部署范围和生产指标证明。"
    elif "financial_brand" in domains and any(
        term in text for term in ("merchant", "retail", "commerce", "商户", "零售", "comercio", "minorista")
    ):
        scenario_key = "merchant_operations"
        scenario = "面向商户或零售经营场景，为商品、营销、客户交互或交易流程提供AI工具；具体开放能力需查看产品原文。"
        value = "预期降低商户使用AI和连接经营系统的门槛；现有证据不足以证明销售转化或运营效率提升。"
    else:
        labels = "、".join(FINANCE_LABELS.get(item, item) for item in domains) or "金融业务"
        scenario = f"用于{labels}中的信息分析或流程辅助；当前公开标题和摘要不足以确定更具体的使用环节。"
        value = "现有证据只能确认AI与金融业务有关，尚不能可靠判断实际效果或商业价值。"

    percentage = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
    if percentage:
        value += f" 来源文字提到约{percentage.group(1)}%的量化变化，但指标口径、基线和归因尚未核验。"
    return scenario, value


def _innovation_assessment(text: str, ai_types: List[str]) -> Tuple[str, str, List[str]]:
    """Conservatively identify innovation that is explicit in the evidence text."""
    patterns = [
        (
            "substantive",
            ("foundation model", "domain-specific model", "vertical model", "金融大模型", "基座模型"),
            "公开文字明确提到面向金融任务的专用或基础模型，属于可能的模型层创新；训练数据、基准和技术差异仍需核验。",
            "金融专用模型",
        ),
        (
            "substantive",
            ("protocol", "agent-to-agent", "cross-platform", "mcp", "协议", "跨端互联"),
            "公开文字明确提到面向智能体的协议或跨系统接口，属于可能的基础设施创新；开放程度和实际采用情况仍需核验。",
            "智能体协议或接口",
        ),
        (
            "application_design",
            ("autonomous", "agentic payment", "payments for ai agents", "execution", "智能体支付", "自主执行"),
            "创新点主要在应用设计：让AI从给出建议进一步连接受控的交易或执行流程；自主程度和安全边界仍需核验。",
            "AI连接业务执行",
        ),
        (
            "application_design",
            ("multi-agent", "agentic workflow", "agentic ai", "多智能体", "智能体工作流"),
            "创新点可能在智能体工作流设计，而非新的底层模型；是否显著优于常规自动化仍需产品细节或生产指标证明。",
            "智能体工作流",
        ),
    ]
    for level, terms, assessment, signal in patterns:
        matched = sorted({term for term in terms if term in text})
        if matched:
            return level, assessment, [signal] + matched
    if any(term in text for term in ("copilot", "chatbot", "assistant", "voicebot", "助手")):
        return (
            "incremental",
            "现有信息更像把成熟的对话式AI嵌入既有金融流程，属于增量体验或效率改进；未发现新的AI技术证据。",
            ["既有流程中的对话式AI"],
        )
    if "agent" in ai_types:
        return (
            "not_demonstrated",
            "虽然使用了“智能体/Agent”表述，但现有信息没有说明自主规划、工具调用或闭环执行等差异，暂未证明存在实质创新。",
            [],
        )
    return (
        "not_demonstrated",
        "现有公开标题和摘要未显示新的AI技术或明显不同的应用设计，先按常规AI功能发布处理，不为其补写创新故事。",
        [],
    )


def _trim_product_fragment(value: str) -> str:
    value = re.split(
        r"\s+(?:to|with|across|at|as)\s+|\s+-\s+|[,:;，：；–—]",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    value = re.sub(r"^(?:a|an|the|new|its)\s+", "", value.strip(), flags=re.IGNORECASE)
    return value.strip(" .'")[:100]


def _product_identity(item: RawItem) -> Tuple[str, str, str, str, str]:
    """Return product name, name status, search URL, official URL and URL status."""
    title = re.sub(r"\s+", " ", item.title).strip()
    product_name = ""
    vendor = ""
    name_status = "undisclosed"

    if item.source_kind == "mcp_registry":
        product_name = title
        vendor = item.publisher
        name_status = "explicit"
    else:
        quoted = re.search(r"[“\"「『]([^”\"」』]{2,100})[”\"」』]", title)
        launch = re.search(
            r"^(.{2,70}?)\s+(?:launches|launched|unveils|unveiled|introduces|introduced|releases|released|rolls out)\s+(.+)$",
            title,
            flags=re.IGNORECASE,
        )
        chinese = re.search(r"^(.{2,50}?)(?:正式发布|正式推出|发布|推出|上线)(.+)$", title)
        if quoted:
            product_name = quoted.group(1).strip()
            name_status = "explicit"
        elif launch:
            vendor = launch.group(1).strip()
            fragment = _trim_product_fragment(launch.group(2))
            product_name = f"{vendor} {fragment}" if fragment else ""
            generic = normalize_text(fragment) in {
                "ai platform", "ai agent", "agentic ai platform", "ai tool", "ai assistant",
                "artificial intelligence platform", "generative ai platform",
            }
            has_named_token = any(
                token[:1].isupper()
                for token in fragment.split()
                if token.lower() not in {"ai", "agent", "agentic"}
            )
            name_status = "explicit" if has_named_token and not generic else "descriptive"
        elif chinese:
            vendor = chinese.group(1).strip("，,：: ")
            fragment = re.split(r"[，,；;]|联合|携手|面向", chinese.group(2), maxsplit=1)[0].strip()
            product_name = f"{vendor} {fragment}" if fragment else ""
            name_status = "explicit" if any(mark in title for mark in ("“", "「", "《")) else "descriptive"

    if not product_name:
        deploy = re.split(
            r"\s+(?:deploys?|adopts?|implements?|integrates?|partners? with)\s+",
            title,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        vendor = deploy.strip() if deploy and deploy != title else item.publisher
        capability = "Agentic AI系统" if "agent" in normalize_text(title) else "AI产品"
        product_name = f"{vendor} 未公开名称{capability}"
        name_status = "undisclosed"

    identity_text = normalize_text(f"{product_name} {title}")
    official_url = ""
    official_status = "not_confirmed"
    if item.source_kind == "mcp_registry" and item.url:
        official_url = item.url
        official_status = "confirmed_product_or_repository"
    else:
        for key, url in CONFIRMED_PRODUCT_PAGES.items():
            if key in identity_text:
                official_url = url
                official_status = "confirmed_product_page"
                break
        if not official_url:
            for key in sorted(OFFICIAL_COMPANY_SITES, key=len, reverse=True):
                if key in identity_text:
                    official_url = OFFICIAL_COMPANY_SITES[key]
                    official_status = "official_company_homepage"
                    break

    search_terms = title if name_status == "undisclosed" else f'"{product_name}" {vendor or item.publisher}'
    search_url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(search_terms)
    return product_name, name_status, search_url, official_url, official_status


def _customer_type(text: str) -> Tuple[str, str]:
    business_signals = sorted({term for term in TO_B_TERMS if term in text})
    consumer_signals = sorted({term for term in TO_C_TERMS if term in text})
    if business_signals and consumer_signals:
        return (
            "both",
            "公开标题或摘要同时指向机构用户和个人/终端客户，暂判为TO B与TO C兼有。",
        )
    if business_signals:
        return (
            "to_b",
            f"公开标题或摘要出现机构侧信号（{'、'.join(business_signals[:4])}），暂判为TO B。",
        )
    if consumer_signals:
        return (
            "to_c",
            f"公开标题或摘要出现个人用户信号（{'、'.join(consumer_signals[:4])}），暂判为TO C。",
        )
    return "undisclosed", "现有公开标题和摘要没有说明直接客户或使用者类型，标记为不公开。"


def _product_categories(domains: Sequence[str]) -> List[str]:
    categories = {
        DOMAIN_TO_PRODUCT_CATEGORY[domain]
        for domain in domains
        if domain in DOMAIN_TO_PRODUCT_CATEGORY
    }
    if not categories:
        return ["other_finance"]
    return [category for category in PRODUCT_CATEGORY_ORDER if category in categories]


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
    product_name, product_name_status, product_search_url, official_url, official_url_status = (
        _product_identity(item)
    )
    customer_type, customer_type_assessment = _customer_type(combined)
    product_categories = _product_categories(domains)
    application_scenario, expected_value = _application_details(combined, domains, ai_types)
    innovation_level, innovation_assessment, innovation_signals = _innovation_assessment(
        combined, ai_types
    )
    domain_text = "、".join(FINANCE_LABELS.get(domain, domain) for domain in domains) or "待确认金融场景"
    summary = (
        f"该候选涉及{domain_text}，被识别为{EVENT_LABELS.get(event_type, event_type)}，"
        f"成熟度暂定{maturity}。当前判断依据{item.publisher}公开的标题或短摘要；"
        "业务事件时间、产品能力和应用效果仍需原始来源核验。"
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
        product_name=product_name,
        product_name_status=product_name_status,
        product_search_url=product_search_url,
        official_url=official_url or None,
        official_url_status=official_url_status,
        customer_type=customer_type,
        customer_type_assessment=customer_type_assessment,
        product_categories=product_categories,
        application_scenario=application_scenario,
        expected_value=expected_value,
        innovation_level=innovation_level,
        innovation_assessment=innovation_assessment,
        innovation_signals=innovation_signals,
        review_status=review_status,
        signals=signals,
    )
