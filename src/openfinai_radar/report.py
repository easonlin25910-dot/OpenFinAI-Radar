from __future__ import annotations

import html
import json
import urllib.parse
from pathlib import Path
from typing import Dict, List

from .models import Candidate


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
            f"""<article class="card" data-stage="{case.maturity}" data-time="{case.time_status}">
              <div class="meta"><time>{case.effective_time}</time><strong>{case.relevance_score}</strong></div>
              <h2>{html.escape(case.title)}</h2>
              <div class="tags">{tags}</div>
              <p>{html.escape(case.summary)}</p>
              <footer>{html.escape(case.publisher)} · {links} · <a href="{feedback}" target="_blank">反馈</a></footer>
            </article>"""
        )
    return "\n".join(blocks) or '<p class="empty">本时间窗口没有达到阈值的候选案例。</p>'


def render_html(run: Dict[str, object], cases: List[Candidate]) -> str:
    metrics = run["metrics"]  # type: ignore[assignment]
    window = run["window"]  # type: ignore[assignment]
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
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 7px 22px #1a32320c}}
.card h2{{font:700 20px/1.35 Georgia,"Songti SC",serif;margin:10px 0}}.meta{{display:flex;justify-content:space-between;color:var(--muted)}}.meta strong{{color:var(--accent)}}
.tag{{display:inline-block;background:#dcecea;color:#155d58;padding:3px 8px;margin:0 5px 5px 0;border-radius:999px;font-size:12px}}
footer{{border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:13px}}a{{color:var(--accent)}}
</style></head><body>
<header><h1>OpenFinAI Radar</h1><p>以时间窗口和证据链为核心的全球金融AI创新发现雷达。自动结果是候选情报，不等于事实核验。</p>
<div class="metrics"><div class="metric"><b>{metrics['accepted_candidates']}</b>候选案例</div><div class="metric"><b>{metrics['raw_items']}</b>原始信息</div><div class="metric"><b>{metrics['deduplicated_items']}</b>去重合并</div><div class="metric"><b>{metrics['source_success_rate']}%</b>来源成功率</div></div></header>
<main><div class="notice">窗口：{window['start']} 至 {window['end']}。所有案例当前均使用证据发布时间作为降级时间；真实产品发布或上线时间需人工补证。</div><div class="grid">{_cards(cases)}</div></main>
</body></html>"""


def render_markdown(run: Dict[str, object], cases: List[Candidate]) -> str:
    window = run["window"]  # type: ignore[assignment]
    metrics = run["metrics"]  # type: ignore[assignment]
    lines = [
        "# OpenFinAI Radar — 最近30天运行结果",
        "",
        f"时间窗口：**{window['start']}—{window['end']}**（含首尾日期）",
        "",
        "> 自动发现结果属于候选情报。当前版本以证据发布日期作为降级时间，不把它冒充产品真实发布时间。",
        "",
        "## 运行指标",
        "",
        f"- 原始信息：{metrics['raw_items']}",
        f"- 窗口内信息：{metrics['items_in_window']}",
        f"- 达到阈值的候选：{metrics['accepted_candidates']}",
        f"- 去重合并数量：{metrics['deduplicated_items']}",
        f"- 来源成功率：{metrics['source_success_rate']}%",
        "",
        "## 候选案例",
        "",
    ]
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
