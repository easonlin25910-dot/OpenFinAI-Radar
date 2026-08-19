from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .pipeline import run_radar


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openfinai-radar",
        description="Discover financial-AI commercialization events in a time window.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Fetch sources and build JSON, Markdown and HTML reports")
    run.add_argument("--days", type=int, default=30, help="Inclusive calendar-day window (default: 30)")
    run.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        help="Window end date in YYYY-MM-DD form (default: today)",
    )
    run.add_argument("--config", type=Path, default=Path("config/sources.json"))
    run.add_argument("--output", type=Path, default=Path("outputs/latest"))
    run.add_argument("--site", type=Path, default=Path("site/index.html"))
    run.add_argument("--limit", type=int, default=250, help="Maximum ranked candidates rendered in reports")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "run":
        result = run_radar(
            days=args.days,
            as_of=args.as_of,
            config_path=args.config,
            output_dir=args.output,
            site_path=args.site,
            limit=args.limit,
        )
        print(
            "OpenFinAI Radar: "
            f"{result['metrics']['accepted_candidates']} candidates from "
            f"{result['metrics']['raw_items']} raw items; "
            f"window {result['window']['start']}..{result['window']['end']}."
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
