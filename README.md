# OpenFinAI Radar

面向全球金融 AI 商业化创新的、以时间窗口与证据链为核心的开源发现雷达。

它回答的不是“互联网上一共有多少个 AI 工具”，而是：

> 最近 30 天，哪些金融 AI 产品、Agent、客户部署、试点或规模化事件首次公开出现？系统在公开证据出现后多久发现它们？

[查看最近一次 Markdown 报告](outputs/latest/report.md) · [查看结构化案例](outputs/latest/cases.json) · [打开静态仪表盘](site/index.html)

## 当前能力

- 按可复现的日期窗口运行，默认最近 30 个自然日。
- 同时保留证据时间、货架登记时间、系统发现时间和有效时间。
- 真实产品发布/上线时间缺失时，明确使用降级时间并降低置信度。
- 通过金融、AI、商业化事件三重信号筛选候选。
- 合并多语言新闻和多个来源对同一事件的重复报道。
- 同时监控新闻发现通道和官方 MCP Registry 产品货架。
- 输出 JSON、Markdown 和无后端静态 HTML。
- 每日 GitHub Actions 自动运行，也支持本地一条命令运行。

当前版本是 **v0.1 候选发现系统**，自动结果不等于事实核验。它追求先建立可评测的高召回基线，再通过真实使用反馈改进准确率、来源覆盖率和摘要质量。

## 快速开始

只需要 Python 3.9 或更高版本，无第三方运行依赖：

```bash
PYTHONPATH=src python3 -m openfinai_radar run --days 30
```

复现仓库中 2026-07-21 至 2026-08-19 的首次运行：

```bash
PYTHONPATH=src python3 -m openfinai_radar run \
  --days 30 \
  --as-of 2026-08-19
```

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## 时间模型

系统不会把文章发布日期伪装成产品发布时间。时间优先级为：

1. 产品发布；
2. 客户生产上线；
3. 官方公告；
4. 监管或采购记录；
5. 产品货架首次登记；
6. 技术版本发布；
7. 媒体报道；
8. 系统首次发现。

首版 RSS 适配器通常只能取得第 7 级时间，MCP Registry 适配器可取得第 5 级时间。因此报告中的 `effective_time_type`、`effective_time_confidence` 和 `time_status` 是必读字段。

完整设计见 [时间与系统架构](docs/architecture.md)。

## 输出

每次运行生成：

- `outputs/latest/run.json`：窗口、来源健康度和运行指标；
- `outputs/latest/cases.json`：机器可读候选案例及证据；
- `outputs/latest/report.md`：适合阅读和审核的报告；
- `site/index.html`：可直接打开的静态仪表盘。

核心案例定义为：

```text
机构 × AI产品/能力 × 金融业务场景 × 商业化事件 × 时间 × 证据
```

## 当前来源与扩展方向

`config/sources.json` 当前包括：

- 英文、中文、日文、法文、西班牙文新闻搜索 RSS；
- Bing News RSS；
- 官方 MCP Registry 的金融相关产品登记。

后续适配器将覆盖云市场、金融软件市场、监管沙盒、公司新闻中心、采购公告、GitHub、Hugging Face、Product Hunt 等。来源数量本身不是 KPI；目标是在明确时间窗口内提高重大案例召回率，并缩短公开证据出现后的发现延迟。

## 评测方向

项目将持续记录：

- 最近 30 天金标准案例召回率；
- 24 小时、72 小时和 7 天内发现比例；
- 发现延迟中位数；
- 发布时间未知和降级时间比例；
- 误报、重复、阶段误判和重大漏报；
- 摘要事实性、完整性和业务价值评分。

## 参与贡献

欢迎提交新来源、漏报案例、误报和时间校正。请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，或使用仓库 Issue 表单。

## English

OpenFinAI Radar is an evidence-first, time-windowed discovery radar for global financial-AI commercialization events. It keeps event time, evidence time, marketplace listing time and discovery time separate; deduplicates multilingual evidence; and produces reproducible JSON, Markdown and HTML reports.

The v0.1 output is a **candidate intelligence queue**, not a verified factual database. Contributions that improve source coverage, event-time resolution, precision and recall are welcome.

## License

Code is released under the [MIT License](LICENSE). Source articles remain the property of their publishers; this repository stores links, metadata and short derived summaries rather than copied full text.

