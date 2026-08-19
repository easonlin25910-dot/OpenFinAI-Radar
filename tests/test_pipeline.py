import unittest

from openfinai_radar.classify import classify_item
from openfinai_radar.models import RawItem
from openfinai_radar.pipeline import build_distributions, deduplicate
from datetime import datetime, timezone


class PipelineTests(unittest.TestCase):
    def test_duplicate_evidence_is_merged(self):
        common = dict(
            source_kind="rss_search",
            publisher="Publisher",
            published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        one = classify_item(RawItem(source_id="a", title="Acme Bank launches generative AI payment agent", url="https://a.example", **common))
        two = classify_item(RawItem(source_id="b", title="Acme Bank launches new generative AI payment agent", url="https://b.example", **common))
        result, merged = deduplicate([one, two])
        self.assertEqual(len(result), 1)
        self.assertEqual(merged, 1)
        self.assertEqual(len(result[0].evidence_urls), 2)

    def test_unrelated_banks_are_not_merged(self):
        common = dict(
            source_kind="rss_search",
            publisher="Publisher",
            published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        one = classify_item(RawItem(source_id="a", title="Ruya Bank deploys agentic AI in production", url="https://a.example", **common))
        two = classify_item(RawItem(source_id="b", title="Suryoday Bank deploys agentic AI across operations", url="https://b.example", **common))
        result, merged = deduplicate([one, two])
        self.assertEqual(len(result), 2)
        self.assertEqual(merged, 0)

    def test_distributions_cover_stage_event_relevance_and_innovation(self):
        candidate = classify_item(
            RawItem(
                source_id="a",
                source_kind="rss_search",
                title="Bank launches generative AI agent for payments",
                url="https://a.example",
                publisher="Publisher",
                published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
                fetched_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            )
        )
        result = build_distributions([candidate])
        self.assertEqual(result["maturity"]["M3"], 1)
        self.assertEqual(result["event_type"]["product_launch"], 1)
        self.assertEqual(sum(result["relevance"].values()), 1)
        self.assertEqual(sum(result["innovation"].values()), 1)


if __name__ == "__main__":
    unittest.main()
