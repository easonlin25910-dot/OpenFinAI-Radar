import unittest

from openfinai_radar.classify import classify_item
from openfinai_radar.models import RawItem
from openfinai_radar.pipeline import deduplicate
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


if __name__ == "__main__":
    unittest.main()

