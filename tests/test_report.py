import unittest
from datetime import datetime, timezone

from openfinai_radar.classify import classify_item
from openfinai_radar.models import RawItem
from openfinai_radar.pipeline import build_distributions
from openfinai_radar.report import render_html


class ReportTests(unittest.TestCase):
    def test_html_contains_composable_filters_and_card_data(self):
        candidate = classify_item(
            RawItem(
                source_id="fixture",
                source_kind="rss_search",
                title="Bank launches generative AI agent for payments",
                url="https://example.com/evidence",
                publisher="Example",
                published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
                fetched_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            )
        )
        run = {
            "window": {"start": "2026-07-21", "end": "2026-08-19"},
            "metrics": {
                "accepted_candidates": 1,
                "raw_items": 1,
                "deduplicated_items": 0,
                "source_success_rate": 100.0,
            },
            "distributions": build_distributions([candidate]),
        }
        page = render_html(run, [candidate])
        self.assertIn('id="stage-filter"', page)
        self.assertIn('id="relevance-filter"', page)
        self.assertIn('id="innovation-filter"', page)
        self.assertIn('data-stage="M3"', page)
        self.assertIn('data-relevance="', page)
        self.assertIn('data-innovation="', page)
        self.assertIn("applyFilters", page)
        self.assertIn("URLSearchParams", page)


if __name__ == "__main__":
    unittest.main()
