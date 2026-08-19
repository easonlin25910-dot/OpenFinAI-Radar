from __future__ import annotations

import html
import json
import urllib.parse
from pathlib import Path
from typing import Dict, List

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
            for value in [case.maturity, case.event_type] + case.finance_domains[:2] + case.ai_types[:1]
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
        blocks.append(
            f"""<article class="card" data-stage="{case.maturity}" data-relevance="{case.relevance_score}" data-innovation="{case.innovation_level}" data-time="{case.time_status}">
              <div class="meta"><time>{case.effective_time}</time><strong>{case.relevance_score}</strong></div>
              <h2>{html.escape(case.title)}</h2>
              <div class="tags">{tags}</div>
              <p>{html.escape(case.summary)}</p>
              <div class="insight"><h3>产品应用场景</h3><p>{html.escape(case.application_scenario)}</p></div>
              <div class="insight"><h3>预期作用与价值</h3><p>{html.escape(case.expected_value)}</p></div>
              <div class="insight innovation"><h3>创新判断 · {html.escape(INNOVATION_LABELS.get(case.innovation_level, case.innovation_level))}</h3><p>{html.escape(case.innovation_assessment)}</p></div>
              <footer>{html.escape(case.publisher)} · {links} · <a href="{feedback}" target="_blank">反馈</a></footer>
            </article>"""
        )
    return "\n".join(blocks) or '<p class="empty">本时间窗口没有达到阈值的候选案例。</p>'


def render_html(run: Dict[str, object], cases: List[Candidate]) -> str:
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
.filters{{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr)) auto auto;gap:12px;align-items:end;margin:0 0 22px;padding:16px;background:#fffdf7;border:1px solid var(--line);border-radius:14px;position:sticky;top:8px;z-index:5;box-shadow:0 8px 24px #1a323214}}.filter label{{display:block;font-size:12px;font-weight:700;color:var(--muted);margin-bottom:5px}}.filter select{{width:100%;min-height:40px;border:1px solid var(--line);border-radius:9px;background:white;color:var(--ink);padding:7px 10px;font:inherit}}.filters button{{min-height:40px;border:0;border-radius:9px;padding:8px 15px;background:var(--accent);color:white;font-weight:700;cursor:pointer}}.result-count{{align-self:center;white-space:nowrap;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 7px 22px #1a32320c}}
.card[hidden]{{display:none}}.empty-filter{{display:none;padding:30px;text-align:center;background:#fffdf7;border:1px solid var(--line);border-radius:14px}}.empty-filter.visible{{display:block}}
.card h2{{font:700 20px/1.35 Georgia,"Songti SC",serif;margin:10px 0}}.meta{{display:flex;justify-content:space-between;color:var(--muted)}}.meta strong{{color:var(--accent)}}
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
  <button id="reset-filters" type="button">重置筛选</button><strong class="result-count" id="result-count" aria-live="polite">显示 {total} / {total}</strong>
</section>
<div class="empty-filter" id="empty-filter">没有符合当前筛选条件的候选案例。</div><div class="grid" id="case-grid">{_cards(cases)}</div></main>
<script>
(() => {{
  const cards = [...document.querySelectorAll('.card')];
  const stage = document.querySelector('#stage-filter');
  const relevance = document.querySelector('#relevance-filter');
  const innovation = document.querySelector('#innovation-filter');
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
        (innovation.value === 'all' || card.dataset.innovation === innovation.value);
      card.hidden = !show;
      if (show) visible += 1;
    }});
    count.textContent = `显示 ${{visible}} / ${{cards.length}}`;
    empty.classList.toggle('visible', visible === 0);
    const params = new URLSearchParams();
    if (stage.value !== 'all') params.set('stage', stage.value);
    if (relevance.value !== 'all') params.set('relevance', relevance.value);
    if (innovation.value !== 'all') params.set('innovation', innovation.value);
    history.replaceState(null, '', params.size ? `?${{params}}` : location.pathname);
  }};
  const params = new URLSearchParams(location.search);
  if ([...stage.options].some(option => option.value === params.get('stage'))) stage.value = params.get('stage');
  if ([...relevance.options].some(option => option.value === params.get('relevance'))) relevance.value = params.get('relevance');
  if ([...innovation.options].some(option => option.value === params.get('innovation'))) innovation.value = params.get('innovation');
  [stage, relevance, innovation].forEach(control => control.addEventListener('change', applyFilters));
  document.querySelector('#reset-filters').addEventListener('click', () => {{ stage.value = relevance.value = innovation.value = 'all'; applyFilters(); }});
  applyFilters();
}})();
</script>
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
        lines.extend(
            [
                f"### {index}. {case.title}",
                "",
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
    (output_dir / "report.md").write_text(render_markdown(run, cases), encoding="utf-8")
    site_path.write_text(render_html(run, cases), encoding="utf-8")
