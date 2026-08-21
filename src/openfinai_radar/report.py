from __future__ import annotations

import html
import json
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

from .models import Candidate


MATURITY_LABELS = {
    "M0": "M0 概念/未分类",
    "M1": "M1 演示/原型",
    "M2": "M2 试点/合作",
    "M3": "M3 产品可用/部署",
    "M4": "M4 付费/成效",
    "M5": "M5 规模化",
}

EVENT_LABELS = {
    "product_launch": "产品发布",
    "customer_deployment": "客户部署",
    "commercial_agreement": "商业合作",
    "pilot": "试点",
    "scale": "规模化应用",
    "unclassified_signal": "待分类",
}

INNOVATION_LABELS = {
    "substantive": "可能存在实质创新",
    "application_design": "应用设计创新",
    "incremental": "增量改进",
    "not_demonstrated": "未证明有实质创新",
}

CUSTOMER_TYPE_LABELS = {
    "to_b": "TO B",
    "to_c": "TO C",
    "both": "TO B & TO C",
    "undisclosed": "不公开",
}

PRODUCT_NAME_STATUS_LABELS = {
    "explicit": "明确产品名",
    "descriptive": "描述性名称",
    "undisclosed": "名称未公开",
}

OFFICIAL_URL_STATUS_LABELS = {
    "confirmed_product_page": "已确认产品页",
    "confirmed_product_or_repository": "官方产品页或代码库",
    "official_company_homepage": "官方机构主页，非产品专页",
    "not_confirmed": "暂未确认",
}

PRODUCT_CATEGORY_LABELS = {
    "banking_operations": "银行运营与客户服务",
    "payments_wallets": "支付与钱包",
    "lending_financing": "信贷与融资",
    "insurance": "保险",
    "investment_markets": "投资理财与资本市场",
    "risk_compliance_fraud": "风险合规与反欺诈",
    "fintech_infrastructure": "金融科技基础设施",
    "other_finance": "其他金融场景",
}

DISPLAY_ORDERS = {
    "maturity": ["M5", "M4", "M3", "M2", "M1", "M0"],
    "event_type": ["scale", "customer_deployment", "product_launch", "commercial_agreement", "pilot", "unclassified_signal"],
    "relevance": ["90-100", "75-89", "60-74", "<60"],
    "innovation": ["substantive", "application_design", "incremental", "not_demonstrated"],
}


def _label(group: str, key: str) -> str:
    mappings = {
        "maturity": MATURITY_LABELS,
        "event_type": EVENT_LABELS,
        "innovation": INNOVATION_LABELS,
    }
    return mappings.get(group, {}).get(key, key)


def _distribution_chart(title: str, group: str, values: Dict[str, int], total: int) -> str:
    rows = []
    keys = DISPLAY_ORDERS[group] + [key for key in values if key not in DISPLAY_ORDERS[group]]
    for key in keys:
        count = values.get(key, 0)
        if not count:
            continue
        percent = count / max(1, total) * 100
        rows.append(
            '<div class="bar-row">'
            f'<span>{html.escape(_label(group, key))}</span>'
            f'<div class="bar"><i style="width:{percent:.1f}%"></i></div>'
            f'<b>{count} · {percent:.1f}%</b></div>'
        )
    return f'<section class="dist"><h2>{html.escape(title)}</h2>{"".join(rows)}</section>'


def _markdown_distribution(title: str, group: str, values: Dict[str, int], total: int) -> List[str]:
    lines = [f"### {title}", "", "| 分类 | 数量 | 占比 |", "| --- | ---: | ---: |"]
    keys = DISPLAY_ORDERS[group] + [key for key in values if key not in DISPLAY_ORDERS[group]]
    for key in keys:
        count = values.get(key, 0)
        if count:
            lines.append(f"| {_label(group, key)} | {count} | {count / max(1, total) * 100:.1f}% |")
    lines.append("")
    return lines


def _cards(cases: List[Candidate]) -> str:
    blocks = []
    for case in cases:
        tags = "".join(
            f'<span class="tag">{html.escape(value)}</span>'
            for value in [case.maturity, case.event_type, CUSTOMER_TYPE_LABELS.get(case.customer_type, case.customer_type)]
            + [PRODUCT_CATEGORY_LABELS.get(category, category) for category in case.product_categories]
            + case.ai_types[:1]
        )
        links = " · ".join(
            f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noreferrer">证据 {index}</a>'
            for index, url in enumerate(case.evidence_urls, 1)
        )
        feedback_title = urllib.parse.quote(f"[case] {case.title}")
        feedback = (
            "https://github.com/easonlin25910-dot/OpenFinAI-Radar/issues/new"
            f"?template=case-feedback.yml&title={feedback_title}"
        )
        if case.official_url:
            official_address = (
                f'<a href="{html.escape(case.official_url, quote=True)}" target="_blank" rel="noreferrer">打开官方地址</a>'
                f' <small>({html.escape(OFFICIAL_URL_STATUS_LABELS.get(case.official_url_status, case.official_url_status))})</small>'
            )
        else:
            official_address = '<span>暂未确认</span>'
        blocks.append(
            f"""<article class="card" data-stage="{case.maturity}" data-relevance="{case.relevance_score}" data-innovation="{case.innovation_level}" data-customer="{case.customer_type}" data-categories="{' '.join(case.product_categories)}" data-time="{case.time_status}">
              <div class="meta"><time>{case.effective_time}</time><strong>{case.relevance_score}</strong></div>
              <h2>{html.escape(case.product_name)}</h2>
              <p class="source-title">来源标题：{html.escape(case.title)}</p>
              <div class="tags">{tags}</div>
              <div class="identity"><p><b>产品名称状态：</b>{html.escape(PRODUCT_NAME_STATUS_LABELS.get(case.product_name_status, case.product_name_status))}</p><p><b>产品分类：</b>{html.escape('、'.join(PRODUCT_CATEGORY_LABELS.get(category, category) for category in case.product_categories))}</p><p><b>客户类型：</b>{html.escape(CUSTOMER_TYPE_LABELS.get(case.customer_type, case.customer_type))}</p><p><b>官方地址：</b>{official_address}</p><p><a href="{html.escape(case.product_search_url, quote=True)}" target="_blank" rel="noreferrer">在 Google 检索该产品</a></p></div>
              <p>{html.escape(case.summary)}</p>
              <div class="insight"><h3>客户类型判断</h3><p>{html.escape(case.customer_type_assessment)}</p></div>
              <div class="insight"><h3>产品应用场景</h3><p>{html.escape(case.application_scenario)}</p></div>
              <div class="insight"><h3>预期作用与价值</h3><p>{html.escape(case.expected_value)}</p></div>
              <div class="insight innovation"><h3>创新判断 · {html.escape(INNOVATION_LABELS.get(case.innovation_level, case.innovation_level))}</h3><p>{html.escape(case.innovation_assessment)}</p></div>
              <footer>{html.escape(case.publisher)} · {links} · <a href="{feedback}" target="_blank">反馈</a></footer>
            </article>"""
        )
    return "\n".join(blocks) or '<p class="empty">本时间窗口没有达到阈值的候选案例。</p>'


def render_html_legacy(run: Dict[str, object], cases: List[Candidate]) -> str:
    metrics = run["metrics"]  # type: ignore[assignment]
    window = run["window"]  # type: ignore[assignment]
    distributions = run.get("distributions", {})  # type: ignore[assignment]
    total = len(cases)
    charts = "".join(
        [
            _distribution_chart("成熟阶段", "maturity", distributions.get("maturity", {}), total),
            _distribution_chart("商业化事件", "event_type", distributions.get("event_type", {}), total),
            _distribution_chart("相关度", "relevance", distributions.get("relevance", {}), total),
            _distribution_chart("创新判断", "innovation", distributions.get("innovation", {}), total),
        ]
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenFinAI Radar</title>
<style>
:root{{--ink:#102a2e;--muted:#617478;--paper:#f3f0e8;--card:#fffdf7;--accent:#0a7069;--line:#d9d5ca}}
*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);background:var(--paper);font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"PingFang SC",sans-serif}}
header{{padding:56px max(5vw,24px) 30px;background:linear-gradient(135deg,#092f34,#0b6b66);color:white}}
header h1{{font:700 clamp(32px,6vw,68px)/1.05 Georgia,serif;margin:0 0 12px}}header p{{max-width:760px;color:#d9eeeb}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px;margin-top:28px;max-width:850px}}
.metric{{padding:14px;border:1px solid #ffffff35;border-radius:12px;background:#ffffff10}}.metric b{{display:block;font-size:24px}}
main{{width:min(1120px,92vw);margin:28px auto 80px}}.notice{{padding:16px 18px;border-left:4px solid #d59b35;background:#fff8e6;margin-bottom:22px}}
.distributions{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px;margin:0 0 26px}}.dist{{background:#fffdf7;border:1px solid var(--line);border-radius:14px;padding:16px}}.dist h2{{font-size:16px;margin:0 0 12px}}
.bar-row{{display:grid;grid-template-columns:105px 1fr 70px;align-items:center;gap:8px;margin:8px 0;font-size:12px}}.bar-row b{{text-align:right;font-weight:600}}.bar{{height:8px;background:#e5e2d8;border-radius:8px;overflow:hidden}}.bar i{{display:block;height:100%;background:var(--accent)}}
.filters{{display:grid;grid-template-columns:repeat(5,minmax(125px,1fr)) auto auto;gap:12px;align-items:end;margin:0 0 22px;padding:16px;background:#fffdf7;border:1px solid var(--line);border-radius:14px;position:sticky;top:8px;z-index:5;box-shadow:0 8px 24px #1a323214}}.filter label{{display:block;font-size:12px;font-weight:700;color:var(--muted);margin-bottom:5px}}.filter select{{width:100%;min-height:40px;border:1px solid var(--line);border-radius:9px;background:white;color:var(--ink);padding:7px 10px;font:inherit}}.filters button{{min-height:40px;border:0;border-radius:9px;padding:8px 15px;background:var(--accent);color:white;font-weight:700;cursor:pointer}}.result-count{{align-self:center;white-space:nowrap;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 7px 22px #1a32320c}}
.card[hidden]{{display:none}}.empty-filter{{display:none;padding:30px;text-align:center;background:#fffdf7;border:1px solid var(--line);border-radius:14px}}.empty-filter.visible{{display:block}}
.card h2{{font:700 20px/1.35 Georgia,"Songti SC",serif;margin:10px 0}}.meta{{display:flex;justify-content:space-between;color:var(--muted)}}.meta strong{{color:var(--accent)}}
.source-title{{font-size:13px;color:var(--muted);margin:0 0 10px}}.identity{{margin:12px 0;padding:12px 14px;border:1px dashed var(--line);border-radius:10px}}.identity p{{margin:4px 0}}small{{color:var(--muted)}}
.tag{{display:inline-block;background:#dcecea;color:#155d58;padding:3px 8px;margin:0 5px 5px 0;border-radius:999px;font-size:12px}}
.insight{{margin:14px 0;padding:12px 14px;background:#f4f1e9;border-radius:10px}}.insight h3{{font-size:13px;margin:0 0 4px;color:var(--accent)}}.insight p{{margin:0}}.innovation{{border-left:3px solid #d59b35}}
footer{{border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:13px}}a{{color:var(--accent)}}
@media(max-width:760px){{.filters{{grid-template-columns:1fr;position:static}}.result-count{{justify-self:start}}}}
</style></head><body>
<header><h1>OpenFinAI Radar</h1><p>以时间窗口和证据链为核心的全球金融AI创新发现雷达。自动结果是候选情报，不等于事实核验。</p>
<div class="metrics"><div class="metric"><b>{metrics['accepted_candidates']}</b>候选案例</div><div class="metric"><b>{metrics['raw_items']}</b>原始信息</div><div class="metric"><b>{metrics['deduplicated_items']}</b>去重合并</div><div class="metric"><b>{metrics['source_success_rate']}%</b>来源成功率</div></div></header>
<main><div class="notice">窗口：{window['start']} 至 {window['end']}。分布统计基于本页展示的 {total} 条候选。真实产品发布或上线时间及自动推断内容仍需人工补证。</div><div class="distributions">{charts}</div>
<section class="filters" aria-label="候选案例筛选">
  <div class="filter"><label for="stage-filter">成熟阶段</label><select id="stage-filter"><option value="all">全部阶段</option><option value="M5">M5 规模化</option><option value="M4">M4 付费/成效</option><option value="M3">M3 产品可用/部署</option><option value="M2">M2 试点/合作</option><option value="M1">M1 演示/原型</option><option value="M0">M0 概念/未分类</option></select></div>
  <div class="filter"><label for="relevance-filter">相关度</label><select id="relevance-filter"><option value="all">全部相关度</option><option value="90-100">90—100 高相关</option><option value="75-89">75—89 较高相关</option><option value="60-74">60—74 基础相关</option><option value="under-60">60 以下</option></select></div>
  <div class="filter"><label for="innovation-filter">创新判断</label><select id="innovation-filter"><option value="all">全部创新判断</option><option value="substantive">可能存在实质创新</option><option value="application_design">应用设计创新</option><option value="incremental">增量改进</option><option value="not_demonstrated">未证明有实质创新</option></select></div>
  <div class="filter"><label for="customer-filter">客户类型</label><select id="customer-filter"><option value="all">全部客户类型</option><option value="to_b">TO B</option><option value="to_c">TO C</option><option value="both">TO B &amp; TO C</option><option value="undisclosed">不公开</option></select></div>
  <div class="filter"><label for="category-filter">产品分类</label><select id="category-filter"><option value="all">全部产品分类</option><option value="banking_operations">银行运营与客户服务</option><option value="payments_wallets">支付与钱包</option><option value="lending_financing">信贷与融资</option><option value="insurance">保险</option><option value="investment_markets">投资理财与资本市场</option><option value="risk_compliance_fraud">风险合规与反欺诈</option><option value="fintech_infrastructure">金融科技基础设施</option><option value="other_finance">其他金融场景</option></select></div>
  <button id="reset-filters" type="button">重置筛选</button><strong class="result-count" id="result-count" aria-live="polite">显示 {total} / {total}</strong>
</section>
<div class="empty-filter" id="empty-filter">没有符合当前筛选条件的候选案例。</div><div class="grid" id="case-grid">{_cards(cases)}</div></main>
<script>
(() => {{
  const cards = [...document.querySelectorAll('.card')];
  const stage = document.querySelector('#stage-filter');
  const relevance = document.querySelector('#relevance-filter');
  const innovation = document.querySelector('#innovation-filter');
  const customer = document.querySelector('#customer-filter');
  const category = document.querySelector('#category-filter');
  const count = document.querySelector('#result-count');
  const empty = document.querySelector('#empty-filter');
  const inRelevanceRange = (score, range) => range === 'all' ||
    (range === '90-100' && score >= 90) ||
    (range === '75-89' && score >= 75 && score < 90) ||
    (range === '60-74' && score >= 60 && score < 75) ||
    (range === 'under-60' && score < 60);
  const applyFilters = () => {{
    let visible = 0;
    cards.forEach(card => {{
      const show = (stage.value === 'all' || card.dataset.stage === stage.value) &&
        inRelevanceRange(Number(card.dataset.relevance), relevance.value) &&
        (innovation.value === 'all' || card.dataset.innovation === innovation.value) &&
        (customer.value === 'all' || card.dataset.customer === customer.value) &&
        (category.value === 'all' || card.dataset.categories.split(' ').includes(category.value));
      card.hidden = !show;
      if (show) visible += 1;
    }});
    count.textContent = `显示 ${{visible}} / ${{cards.length}}`;
    empty.classList.toggle('visible', visible === 0);
    const params = new URLSearchParams();
    if (stage.value !== 'all') params.set('stage', stage.value);
    if (relevance.value !== 'all') params.set('relevance', relevance.value);
    if (innovation.value !== 'all') params.set('innovation', innovation.value);
    if (customer.value !== 'all') params.set('customer', customer.value);
    if (category.value !== 'all') params.set('category', category.value);
    history.replaceState(null, '', params.size ? `?${{params}}` : location.pathname);
  }};
  const params = new URLSearchParams(location.search);
  if ([...stage.options].some(option => option.value === params.get('stage'))) stage.value = params.get('stage');
  if ([...relevance.options].some(option => option.value === params.get('relevance'))) relevance.value = params.get('relevance');
  if ([...innovation.options].some(option => option.value === params.get('innovation'))) innovation.value = params.get('innovation');
  if ([...customer.options].some(option => option.value === params.get('customer'))) customer.value = params.get('customer');
  if ([...category.options].some(option => option.value === params.get('category'))) category.value = params.get('category');
  [stage, relevance, innovation, customer, category].forEach(control => control.addEventListener('change', applyFilters));
  document.querySelector('#reset-filters').addEventListener('click', () => {{ stage.value = relevance.value = innovation.value = customer.value = category.value = 'all'; applyFilters(); }});
  applyFilters();
}})();
</script>
</body></html>"""


_PAGE_CSS = """
:root{--ink:#102a2e;--muted:#617478;--paper:#f3f0e8;--card:#fffdf7;--accent:#0a7069;--line:#d9d5ca;--gold:#d59b35}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--paper);font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"PingFang SC",sans-serif}
header{padding:44px max(5vw,24px) 26px;background:linear-gradient(135deg,#092f34,#0b6b66);color:#fff}
header h1{font:700 clamp(30px,6vw,62px)/1.05 Georgia,serif;margin:0 0 10px}header p{max-width:760px;color:#d9eeeb}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:24px;max-width:860px}
.metric{padding:14px;border:1px solid #ffffff35;border-radius:12px;background:#ffffff10}.metric b{display:block;font-size:22px}
main{width:min(1160px,94vw);margin:24px auto 80px}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
.tabs button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:8px 16px;font:inherit;font-weight:700;cursor:pointer}
.tabs button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.notice{padding:14px 16px;border-left:4px solid var(--gold);background:#fff8e6;margin-bottom:18px}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 14px;padding:14px;background:var(--card);border:1px solid var(--line);border-radius:14px;position:sticky;top:8px;z-index:5;box-shadow:0 8px 24px #1a323214}
.filters input[type=search],.filters select{min-height:38px;border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--ink);padding:6px 10px;font:inherit}
.filters input[type=search]{flex:1 1 220px}
.filters button{min-height:38px;border:0;border-radius:9px;padding:7px 14px;background:var(--accent);color:#fff;font-weight:700;cursor:pointer}
.chipbar{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px;align-items:center;font-size:13px;color:var(--muted)}
.chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:4px 11px;font-size:13px;cursor:pointer}
.chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.result-count{color:var(--muted);white-space:nowrap;margin-left:auto}
.distributions{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:12px;margin:0 0 18px}
.dist{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}.dist h2{font-size:15px;margin:0 0 10px}
.bar-row{display:grid;grid-template-columns:100px 1fr 68px;align-items:center;gap:8px;margin:7px 0;font-size:12px}.bar-row b{text-align:right;font-weight:600}.bar{height:8px;background:#e5e2d8;border-radius:8px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 7px 22px #1a32320c;display:flex;flex-direction:column}
.card h2{font:700 19px/1.35 Georgia,"Songti SC",serif;margin:8px 0}
.meta{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:13px}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700}
.badge.watch{background:#dcecea;color:#155d58}.badge.new{background:#e8f4e8;color:#2c6e2c}
.badge.heat-high{background:#fbe3e3;color:#a33}.badge.heat-medium{background:#fdf3dd;color:#a06b0a}.badge.heat-low{background:#eceef0;color:#617478}
.source-title{font-size:13px;color:var(--muted);margin:0 0 8px}
.identity{margin:10px 0;padding:10px 12px;border:1px dashed var(--line);border-radius:10px;font-size:13px}.identity p{margin:3px 0}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0}
.tag{display:inline-block;background:#dcecea;color:#155d58;padding:2px 8px;border-radius:999px;font-size:12px}
.insight{margin:10px 0;padding:10px 12px;background:#f4f1e9;border-radius:10px;font-size:14px}.insight h3{font-size:13px;margin:0 0 3px;color:var(--accent)}.insight p{margin:0}.innovation{border-left:3px solid var(--gold)}
footer{margin-top:auto;border-top:1px solid var(--line);padding-top:10px;color:var(--muted);font-size:12px}a{color:var(--accent)}
.empty{padding:30px;text-align:center;background:var(--card);border:1px solid var(--line);border-radius:14px;color:var(--muted)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;overflow:auto}.panel h2{font-size:16px;margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}th{color:var(--muted)}td.num,th.num{text-align:right}
.heatbar{height:8px;background:#e5e2d8;border-radius:8px;overflow:hidden;display:inline-block;width:100px;vertical-align:middle}.heatbar i{display:block;height:100%;background:var(--gold)}
#calendar{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
.cal-day{border:1px solid var(--line);border-radius:8px;padding:6px;min-height:56px;background:#fff}.cal-day .d{font-size:12px;color:var(--muted)}.cal-day .n{font-size:18px;font-weight:700}
#region{display:flex;flex-direction:column;gap:10px}.region-row{display:grid;grid-template-columns:70px 1fr 160px;gap:10px;align-items:center;font-size:14px}
#graph-svg{width:100%;height:640px;display:block}
.legend{display:flex;gap:14px;margin:8px 0;font-size:12px;color:var(--muted)}.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:4px}
@media(max-width:720px){.filters{position:static}#calendar{grid-template-columns:repeat(4,1fr)}}
"""


_PAGE_JS = r"""
(() => {
  const DATA = JSON.parse(document.getElementById('radar-data').textContent);
  const cases = DATA.cases || [];
  const graph = DATA.graph || {nodes: [], edges: []};

  const LAB = {
    maturity: {"M0":"M0 概念","M1":"M1 演示/原型","M2":"M2 试点/合作","M3":"M3 产品可用/部署","M4":"M4 付费/成效","M5":"M5 规模化"},
    innovation: {"substantive":"实质创新","application_design":"应用设计创新","incremental":"增量改进","not_demonstrated":"未证明创新"},
    customer: {"to_b":"TO B","to_c":"TO C","both":"TO B & TO C","undisclosed":"不公开"},
    category: {"banking_operations":"银行运营","payments_wallets":"支付与钱包","lending_financing":"信贷与融资","insurance":"保险","investment_markets":"投资理财与资本市场","risk_compliance_fraud":"风险合规与反欺诈","fintech_infrastructure":"金融科技基础设施","other_finance":"其他金融场景"},
    tech: {"foundation_model":"基础模型","rag":"RAG","voice":"语音","copilot":"Copilot","agent_workflow":"Agent 工作流","infrastructure":"基础设施","other":"其他"},
    heat: {"high":"高热度","medium":"中热度","low":"低热度"}
  };

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const uniq = arr => [...new Set(arr)].sort();
  const state = {q:'', sort:'heat', cats:new Set(), entities:new Set(), regions:new Set(), watch:false};

  function filtered(){
    const q = state.q.trim().toLowerCase();
    const list = cases.filter(c => {
      if (state.watch && !c.is_watchlist) return false;
      if (state.cats.size && !(c.product_categories || []).some(x => state.cats.has(x))) return false;
      if (state.entities.size && !state.entities.has(c.entity)) return false;
      if (state.regions.size && !state.regions.has(c.region)) return false;
      if (q) {
        const hay = (c.product_name + ' ' + (c.title || '') + ' ' + (c.entity || '') + ' ' + (c.summary || '')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const sorters = {
      heat: (a,b) => b.heat - a.heat,
      relevance: (a,b) => b.relevance_score - a.relevance_score,
      time: (a,b) => String(b.effective_time || '').localeCompare(String(a.effective_time || ''))
    };
    return list.sort(sorters[state.sort] || sorters.heat);
  }

  function cardHTML(c){
    const cats = (c.product_categories || []).map(x => LAB.category[x] || x);
    const tags = [LAB.maturity[c.maturity] || c.maturity, c.event_type, LAB.customer[c.customer_type] || c.customer_type, ...cats, c.tech_layer ? (LAB.tech[c.tech_layer] || c.tech_layer) : ''].filter(Boolean);
    const badges = [];
    if (c.is_watchlist) badges.push('<span class="badge watch">头部公司</span>');
    if (c.is_new) badges.push('<span class="badge new">新</span>');
    badges.push('<span class="badge heat-' + esc(c.heat_level) + '">' + (LAB.heat[c.heat_level] || '') + ' ' + c.heat + '</span>');
    if ((c.evidence_strength || 1) > 1) badges.push('<span class="badge heat-low">' + c.evidence_strength + ' 源</span>');
    const official = c.official_url ? '<a href="' + esc(c.official_url) + '" target="_blank" rel="noreferrer">官方地址</a>' : '暂未确认';
    const links = (c.evidence_urls || []).slice(0, 5).map((u, i) => '<a href="' + esc(u) + '" target="_blank" rel="noreferrer">证据' + (i + 1) + '</a>').join(' · ');
    return '<article class="card">' +
      '<div class="meta"><time>' + esc(c.effective_time) + '</time><strong>' + c.relevance_score + '</strong></div>' +
      '<h2>' + esc(c.product_name || c.title) + '</h2>' +
      (c.entity ? '<div class="meta">' + esc(c.entity) + (c.region ? ' · ' + esc(c.region) : '') + '</div>' : '') +
      '<div class="badges">' + badges.join('') + '</div>' +
      '<p class="source-title">来源标题：' + esc(c.title) + '</p>' +
      '<div class="identity">' +
        '<p><b>机构：</b>' + esc(c.entity || '未识别') + '</p>' +
        '<p><b>分类：</b>' + esc(cats.join('、') || '其他金融场景') + '</p>' +
        '<p><b>客户类型：</b>' + esc(LAB.customer[c.customer_type] || c.customer_type) + '</p>' +
        '<p><b>官方地址：</b>' + official + '</p>' +
      '</div>' +
      '<div class="tags">' + tags.map(t => '<span class="tag">' + esc(t) + '</span>').join('') + '</div>' +
      '<p>' + esc(c.summary) + '</p>' +
      '<div class="insight"><h3>应用场景</h3><p>' + esc(c.application_scenario) + '</p></div>' +
      '<div class="insight"><h3>预期价值</h3><p>' + esc(c.expected_value) + '</p></div>' +
      '<div class="insight innovation"><h3>创新判断 · ' + esc(LAB.innovation[c.innovation_level] || c.innovation_level) + '</h3><p>' + esc(c.innovation_assessment) + '</p></div>' +
      '<footer>' + esc(c.publisher) + ' · ' + links + ' · <a href="' + esc(c.product_search_url) + '" target="_blank" rel="noreferrer">Google 检索</a></footer>' +
    '</article>';
  }

  function toggle(set, v){ set.has(v) ? set.delete(v) : set.add(v); }

  function renderChips(){
    const catVals = uniq(cases.flatMap(c => c.product_categories || []));
    const entityVals = uniq(cases.map(c => c.entity).filter(Boolean));
    const regionVals = uniq(cases.map(c => c.region).filter(Boolean));
    const mk = (v, label, on) => '<button class="chip' + (on ? ' on' : '') + '" data-val="' + esc(v) + '">' + esc(label) + '</button>';
    document.getElementById('chip-cat').innerHTML = '分类：' + catVals.map(v => mk(v, LAB.category[v] || v, state.cats.has(v))).join('');
    document.getElementById('chip-entity').innerHTML = '机构：' + entityVals.map(v => mk(v, v, state.entities.has(v))).join('');
    document.getElementById('chip-region').innerHTML = '地区：' + regionVals.map(v => mk(v, v, state.regions.has(v))).join('');
    document.querySelectorAll('#chip-cat .chip').forEach(el => el.onclick = () => { toggle(state.cats, el.dataset.val); renderChips(); renderCards(); });
    document.querySelectorAll('#chip-entity .chip').forEach(el => el.onclick = () => { toggle(state.entities, el.dataset.val); renderChips(); renderCards(); });
    document.querySelectorAll('#chip-region .chip').forEach(el => el.onclick = () => { toggle(state.regions, el.dataset.val); renderChips(); renderCards(); });
  }

  function renderCards(){
    const list = filtered();
    document.getElementById('result-count').textContent = '显示 ' + list.length + ' / ' + cases.length;
    document.getElementById('case-grid').innerHTML = list.map(cardHTML).join('') || '<p class="empty">没有符合条件的候选案例。</p>';
  }

  function renderBoard(){
    const m = {};
    cases.forEach(c => { if (!c.entity) return; m[c.entity] = m[c.entity] || {count:0, heat:0, region:c.region}; m[c.entity].count++; m[c.entity].heat += c.heat; });
    const rows = Object.entries(m).sort((a,b) => b[1].heat - a[1].heat).map(([k,v]) =>
      '<tr><td>' + esc(k) + '</td><td>' + esc(v.region || '') + '</td><td class="num">' + v.count + '</td><td class="num"><span class="heatbar"><i style="width:' + Math.min(100, v.heat) + '%"></i></span> ' + v.heat + '</td></tr>').join('');
    document.getElementById('board').innerHTML = '<thead><tr><th>机构</th><th>地区</th><th class="num">案例数</th><th class="num">热度合计</th></tr></thead><tbody>' + rows + '</tbody>';
  }

  function renderCalendar(){
    const counts = {}; cases.forEach(c => { counts[c.effective_time] = (counts[c.effective_time] || 0) + 1; });
    const win = DATA.window; const start = new Date(win.start); const end = new Date(win.end);
    const days = []; for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) days.push(d.toISOString().slice(0, 10));
    const max = Math.max(1, ...Object.values(counts));
    document.getElementById('calendar').innerHTML = days.map(d => {
      const n = counts[d] || 0; const alpha = n ? 0.12 + 0.88 * n / max : 0;
      return '<div class="cal-day" style="background:rgba(10,112,105,' + alpha.toFixed(2) + ')">' +
        '<div class="d">' + d.slice(5) + '</div><div class="n" style="color:' + (n > 0 ? '#fff' : '#617478') + '">' + n + '</div></div>';
    }).join('');
  }

  function renderRegion(){
    const m = {};
    cases.forEach(c => { const r = c.region || '未知'; m[r] = m[r] || {count:0, heat:0}; m[r].count++; m[r].heat += c.heat; });
    const max = Math.max(1, ...Object.values(m).map(v => v.heat));
    document.getElementById('region').innerHTML = Object.entries(m).sort((a,b) => b[1].heat - a[1].heat).map(([r,v]) =>
      '<div class="region-row"><span>' + esc(r) + '</span><span class="heatbar" style="width:100%"><i style="width:' + (v.heat / max * 100) + '%"></i></span><span class="num">' + v.count + ' 例 / ' + v.heat + ' 热度</span></div>').join('');
  }

  function renderGraph(){
    const svg = document.getElementById('graph-svg');
    const W = 1000, H = 640;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    const nodes = graph.nodes.map(n => Object.assign({}, n, {x: Math.random() * W, y: Math.random() * H, vx: 0, vy: 0}));
    const byId = {}; nodes.forEach(n => byId[n.id] = n);
    const links = graph.edges.filter(e => byId[e.source] && byId[e.target]).map(e => ({s: byId[e.source], t: byId[e.target], w: e.weight || 1}));
    const color = n => ({case:'#0a7069', entity:'#d59b35', source:'#8a7fb0'}[n.type] || '#999');
    const radius = n => n.type === 'case' ? 5 + Math.min(12, (n.heat || 0) / 10) : (n.type === 'entity' ? 9 : 5);
    for (let it = 0; it < 200; it++) {
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j]; let dx = a.x - b.x, dy = a.y - b.y; let d2 = dx * dx + dy * dy; if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
        const d = Math.sqrt(d2), f = 1400 / d2; a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f;
      }
      links.forEach(l => { const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y; const d = Math.sqrt(dx * dx + dy * dy) || 1; const f = (d - 90) * 0.03; l.s.vx += dx / d * f; l.s.vy += dy / d * f; l.t.vx -= dx / d * f; l.t.vy -= dy / d * f; });
      nodes.forEach(n => { n.vx = (n.vx + (W / 2 - n.x) * 0.02) * 0.85; n.vy = (n.vy + (H / 2 - n.y) * 0.02) * 0.85; n.x = Math.max(15, Math.min(W - 15, n.x + n.vx)); n.y = Math.max(15, Math.min(H - 15, n.y + n.vy)); });
    }
    const lines = links.map(l => '<line x1="' + l.s.x + '" y1="' + l.s.y + '" x2="' + l.t.x + '" y2="' + l.t.y + '" stroke="#c9c4b8" stroke-width="' + Math.min(3, 0.4 + l.w * 0.6) + '"/>').join('');
    const gs = nodes.map(n => '<g class="gnode" transform="translate(' + n.x.toFixed(1) + ',' + n.y.toFixed(1) + ')" data-id="' + esc(n.id) + '" data-type="' + esc(n.type) + '" data-label="' + esc(n.label) + '"><circle r="' + radius(n) + '" fill="' + color(n) + '" stroke="#fff"/><text y="' + (radius(n) + 12) + '" text-anchor="middle" font-size="10">' + esc(n.label) + '</text></g>').join('');
    svg.innerHTML = lines + gs;
    svg.querySelectorAll('.gnode').forEach(g => g.addEventListener('click', () => {
      const n = byId[g.dataset.id];
      state.q = ''; state.cats.clear(); state.entities.clear(); state.regions.clear();
      if (n.type === 'entity') state.entities.add(n.label);
      else if (n.type === 'case') state.q = n.label;
      document.getElementById('search').value = state.q;
      renderChips(); show('view-cards'); renderCards();
    }));
  }

  function show(view){
    document.querySelectorAll('.view').forEach(v => v.hidden = (v.id !== view));
    document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  }

  document.getElementById('search').addEventListener('input', e => { state.q = e.target.value; renderCards(); });
  document.getElementById('sort').addEventListener('change', e => { state.sort = e.target.value; renderCards(); });
  document.getElementById('watch').addEventListener('change', e => { state.watch = e.target.checked; renderCards(); });
  document.getElementById('reset').addEventListener('click', () => {
    state.q = ''; state.cats.clear(); state.entities.clear(); state.regions.clear(); state.watch = false;
    document.getElementById('search').value = ''; document.getElementById('watch').checked = false; document.getElementById('sort').value = 'heat';
    renderChips(); renderCards();
  });
  document.getElementById('csv').addEventListener('click', () => {
    const cols = ['product_name','entity','region','maturity','event_type','innovation_level','customer_type','tech_layer','heat','heat_level','relevance_score','effective_time','title'];
    const head = cols.join(',');
    const body = filtered().map(c => cols.map(k => '"' + String(c[k] == null ? '' : c[k]).replace(/"/g, '""') + '"').join(',')).join('\n');
    const blob = new Blob(['\ufeff' + head + '\n' + body], {type: 'text/csv;charset=utf-8'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'openfinai-radar.csv'; a.click();
  });
  document.querySelectorAll('.tabs button').forEach(b => b.addEventListener('click', () => show(b.dataset.view)));

  renderChips(); renderCards(); renderBoard(); renderCalendar(); renderRegion(); renderGraph(); show('view-cards');
})();
"""


def render_html(
    run: Dict[str, object],
    cases: List[Candidate],
    graph: Optional[Dict[str, object]] = None,
) -> str:
    metrics = run["metrics"]  # type: ignore[assignment]
    window = run["window"]  # type: ignore[assignment]
    distributions = run.get("distributions", {})  # type: ignore[assignment]
    total = len(cases)
    charts = "".join(
        [
            _distribution_chart("成熟阶段", "maturity", distributions.get("maturity", {}), total),
            _distribution_chart("商业化事件", "event_type", distributions.get("event_type", {}), total),
            _distribution_chart("相关度", "relevance", distributions.get("relevance", {}), total),
            _distribution_chart("创新判断", "innovation", distributions.get("innovation", {}), total),
        ]
    )
    data = {
        "window": window,
        "metrics": metrics,
        "cases": [case.to_dict() for case in cases],
        "graph": graph or {"nodes": [], "edges": []},
    }
    data_json = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenFinAI Radar</title>
<style>{_PAGE_CSS}</style></head><body>
<header><h1>OpenFinAI Radar</h1><p>以时间窗口和证据链为核心的全球金融AI创新发现雷达。自动结果是候选情报，不等于事实核验。</p>
<div class="metrics"><div class="metric"><b>{metrics['accepted_candidates']}</b>候选案例</div><div class="metric"><b>{metrics['raw_items']}</b>原始信息</div><div class="metric"><b>{metrics.get('watchlist_candidates', 0)}</b>头部公司</div><div class="metric"><b>{metrics.get('hot_candidates', 0)}</b>高热度</div><div class="metric"><b>{metrics['source_success_rate']}%</b>来源成功率</div></div></header>
<main>
<nav class="tabs"><button data-view="view-cards" class="active">卡片</button><button data-view="view-graph">图谱</button><button data-view="view-board">机构榜</button><button data-view="view-calendar">热力日历</button><button data-view="view-region">地区分布</button></nav>
<div class="notice">窗口：{window['start']} 至 {window['end']}。本页展示 {total} 条候选。真实产品发布时间及自动推断内容仍需人工核验。</div>
<section id="view-cards" class="view">
  <div class="filters"><input id="search" type="search" placeholder="搜索产品 / 机构 / 标题…"><select id="sort"><option value="heat">按热度</option><option value="relevance">按相关度</option><option value="time">按时间</option></select><label><input id="watch" type="checkbox"> 只看头部公司</label><button id="reset" type="button">重置</button><button id="csv" type="button">导出 CSV</button><span class="result-count" id="result-count"></span></div>
  <div id="chip-cat" class="chipbar"></div>
  <div id="chip-entity" class="chipbar"></div>
  <div id="chip-region" class="chipbar"></div>
  <div class="distributions">{charts}</div>
  <div class="grid" id="case-grid"></div>
</section>
<section id="view-graph" class="view" hidden><div class="panel"><h2>产品 ↔ 机构 ↔ 来源 关系图谱</h2><div class="legend"><span><i style="background:#0a7069"></i>案例</span><span><i style="background:#d59b35"></i>机构</span><span><i style="background:#8a7fb0"></i>来源</span><span style="margin-left:auto">点击节点可联动筛选卡片</span></div><svg id="graph-svg"></svg></div></section>
<section id="view-board" class="view" hidden><div class="panel"><h2>机构热度排行榜</h2><table id="board"></table></div></section>
<section id="view-calendar" class="view" hidden><div class="panel"><h2>30 天发现节奏</h2><div id="calendar"></div></div></section>
<section id="view-region" class="view" hidden><div class="panel"><h2>地区热度分布</h2><div id="region"></div></div></section>
</main>
<script type="application/json" id="radar-data">{data_json}</script>
<script>{_PAGE_JS}</script>
</body></html>"""


def render_markdown(run: Dict[str, object], cases: List[Candidate]) -> str:
    window = run["window"]  # type: ignore[assignment]
    metrics = run["metrics"]  # type: ignore[assignment]
    distributions = run.get("distributions", {})  # type: ignore[assignment]
    lines = [
        "# OpenFinAI Radar — 最近30天运行结果",
        "",
        f"时间窗口：**{window['start']}—{window['end']}**（含首尾日期）",
        "",
        "> 自动发现结果属于候选情报。RSS候选通常以证据发布日期作为降级时间，不把它冒充产品真实发布时间。",
        "",
        "## 运行指标",
        "",
        f"- 原始信息：{metrics['raw_items']}",
        f"- 窗口内信息：{metrics['items_in_window']}",
        f"- 达到阈值的候选：{metrics['accepted_candidates']}",
        f"- 去重合并数量：{metrics['deduplicated_items']}",
        f"- 来源成功率：{metrics['source_success_rate']}%",
        "",
        "## 分布统计",
        "",
        f"> 统计口径：本报告展示的 {len(cases)} 条候选案例。",
        "",
    ]
    lines.extend(_markdown_distribution("成熟阶段", "maturity", distributions.get("maturity", {}), len(cases)))
    lines.extend(_markdown_distribution("商业化事件", "event_type", distributions.get("event_type", {}), len(cases)))
    lines.extend(_markdown_distribution("相关度", "relevance", distributions.get("relevance", {}), len(cases)))
    lines.extend(_markdown_distribution("创新判断", "innovation", distributions.get("innovation", {}), len(cases)))
    lines.extend(["## 候选案例", ""])
    for index, case in enumerate(cases, 1):
        official_url = (
            f"[{case.official_url}]({case.official_url})（{OFFICIAL_URL_STATUS_LABELS.get(case.official_url_status, case.official_url_status)}）"
            if case.official_url
            else "暂未确认"
        )
        category_text = "、".join(
            PRODUCT_CATEGORY_LABELS.get(category, category)
            for category in case.product_categories
        )
        lines.extend(
            [
                f"### {index}. {case.product_name}",
                "",
                f"- 来源标题：{case.title}",
                f"- 产品名称状态：{PRODUCT_NAME_STATUS_LABELS.get(case.product_name_status, case.product_name_status)}",
                f"- 产品分类：{category_text}",
                f"- 客户类型：{CUSTOMER_TYPE_LABELS.get(case.customer_type, case.customer_type)}。{case.customer_type_assessment}",
                f"- Google 检索：[搜索该产品]({case.product_search_url})",
                f"- 官方地址：{official_url}",
                f"- 有效时间：{case.effective_time}（{case.effective_time_type}，置信度 {case.effective_time_confidence:.2f}）",
                f"- 阶段/事件：{case.maturity} / {case.event_type}",
                f"- 相关度：{case.relevance_score}/100；审核状态：{case.review_status}",
                f"- 发布者：{case.publisher}",
                f"- 摘要：{case.summary}",
                f"- 产品应用场景：{case.application_scenario}",
                f"- 预期作用与价值：{case.expected_value}",
                f"- 创新判断：{INNOVATION_LABELS.get(case.innovation_level, case.innovation_level)}。{case.innovation_assessment}",
                f"- 证据：{' · '.join(case.evidence_urls)}",
                "",
            ]
        )
    return "\n".join(lines)


def write_reports(
    output_dir: Path,
    site_path: Path,
    run: Dict[str, object],
    cases: List[Candidate],
    graph: Optional[Dict[str, object]] = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    site_path.parent.mkdir(parents=True, exist_ok=True)
    case_payload = [case.to_dict() for case in cases]
    with (output_dir / "cases.json").open("w", encoding="utf-8") as handle:
        json.dump(case_payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with (output_dir / "run.json").open("w", encoding="utf-8") as handle:
        json.dump(run, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if graph is not None:
        with (output_dir / "graph.json").open("w", encoding="utf-8") as handle:
            json.dump(graph, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    (output_dir / "report.md").write_text(render_markdown(run, cases), encoding="utf-8")
    site_path.write_text(render_html(run, cases, graph=graph), encoding="utf-8")
