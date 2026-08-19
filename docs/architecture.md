# Architecture and time policy

## Product boundary

OpenFinAI Radar separates three layers that conventional news aggregators often mix together:

1. **Evidence** — a page, listing, filing, announcement or article that can be observed at a known time.
2. **Event** — a launch, pilot, production deployment, contract or scaled rollout in the financial sector.
3. **Case** — one normalized entity that can accumulate several events and several pieces of evidence over time.

The v0.1 implementation creates event candidates. Human review and later adapters will promote candidates into verified cases.

## Pipeline

```text
Source adapters
  -> raw evidence
  -> calendar-window filter
  -> finance + AI + event signal gate
  -> maturity and event classification
  -> time fallback with provenance
  -> cross-source deduplication
  -> candidate registry
  -> JSON / Markdown / HTML
```

Every adapter fails independently. `run.json` records source health so a successful report cannot hide a silent source outage.

## Time semantics

The default 30-day window is inclusive. With `--as-of 2026-08-19`, it covers 2026-07-21 through 2026-08-19.

The data model preserves these distinct concepts:

| Field | Meaning |
| --- | --- |
| `event_time` | Product launch, customer go-live or other business event |
| `evidence_time` | Publication time of an announcement or report |
| `listing_time` | First known product-shelf registration time |
| `first_public_time` | Earliest currently known public trace |
| `discovered_at` | When this radar first observed the evidence |
| `effective_time` | Best available time selected by the documented hierarchy |

An item can appear in a 30-day provisional view because it was newly reported even when the underlying product is older. Once an earlier product event is verified, it should move from “new product” to “new evidence about an older product.” This correction is a feature, not a failure: the audit history makes temporal uncertainty visible.

## Maturity scale

- M0 — concept or unclassified signal
- M1 — demo or prototype
- M2 — pilot, sandbox or non-binding partnership
- M3 — available product or production deployment
- M4 — paid contract, named customer plus deployment, or measured business outcome
- M5 — scaled, repeated or enterprise-wide use

Heuristic maturity is always `needs_review` in v0.1.

## Recall and precision

The system cannot prove that no case was missed. It can make omission measurable by maintaining a hindsight gold set, comparing independent source channels, tracking late discoveries and recording source outages. Planned headline metrics are window recall, precision at the review cutoff, detection delay, primary-evidence ratio and unresolved-time ratio.

## Responsible collection

Adapters should respect terms of service, robots guidance, rate limits and copyright. Store the URL, publisher, timestamp, hash, necessary short evidence and derived structured facts. Do not mirror full copyrighted articles.

