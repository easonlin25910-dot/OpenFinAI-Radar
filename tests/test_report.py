import unittest
from datetime import datetime, timezone

from openfinai_radar.classify import classify_item
from openfinai_radar.models import RawItem
from openfinai_radar.pipeline import build_distributions
from openfinai_radar.report import render_html


class ReportTests(unittest.TestCase):
    def test_html_contains_tabs_graph_and_card_data(self):
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
                "source_success_rate": 100.0,
            },
            "distributions": build_distributions([candidate]),
        }
        graph = {
            "nodes": [
                {"id": "c1", "type": "case", "label": "demo", "heat": 30, "relevance": 80, "is_watchlist": False}
            ],
            "edges": [],
        }
        page = render_html(run, [candidate], graph=graph)
        self.assertIn('id="radar-data"', page)
        self.assertIn('id="view-graph"', page)
        self.assertIn('id="view-board"', page)
        self.assertIn('id="view-calendar"', page)
        self.assertIn('id="view-region"', page)
        self.assertIn('id="search"', page)
        self.assertIn('id="sort"', page)
        self.assertIn('id="csv"', page)
        self.assertIn('graph-svg', page)
        self.assertIn("renderGraph", page)
        self.assertIn("renderCalendar", page)
        self.assertIn("renderBoard", page)
        self.assertIn("product_name", candidate.to_dict())
        self.assertIn("product_categories", candidate.to_dict())
        self.assertIn('"heat"', page)
        self.assertIn('"entity"', page)


if __name__ == "__main__":
    unittest.main()
