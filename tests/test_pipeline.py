import unittest
from unittest import mock
from datetime import date, datetime, timezone

from openfinai_radar.classify import classify_item
from openfinai_radar.entities import build_entity_index
from openfinai_radar.models import FetchResult, RawItem
from openfinai_radar.pipeline import (
    _compute_heat,
    _fetch_all,
    _heat_level,
    _resolve_entities,
    build_distributions,
    build_graph,
    deduplicate,
)


class PipelineTests(unittest.TestCase):
    def test_resolve_entities_tags_watchlist_item(self):
        index = build_entity_index(
            [
                {
                    "id": "jpmorgan",
                    "canonical_name": "JPMorgan Chase",
                    "aliases": ["Chase"],
                    "region": "US",
                    "role": "finance_giant",
                }
            ]
        )
        item = RawItem(
            source_id="a",
            source_kind="rss_search",
            title="Chase launches AI assistant",
            url="https://a.example",
            publisher="Publisher",
            published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        _resolve_entities([item], index)
        self.assertEqual(item.entity, "JPMorgan Chase")
        self.assertTrue(item.is_watchlist)
        self.assertEqual(item.region, "US")

    def test_heat_and_graph(self):
        candidate = classify_item(
            RawItem(
                source_id="a",
                source_kind="rss_search",
                title="Bank launches generative AI agent for payments",
                url="https://a.example",
                publisher="Publisher",
                published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            )
        )
        candidate.heat = _compute_heat(candidate, date(2026, 8, 19))
        candidate.heat_level = _heat_level(candidate.heat)
        self.assertGreaterEqual(candidate.heat, 0)
        self.assertLessEqual(candidate.heat, 100)
        graph = build_graph([candidate])
        node_types = {node["type"] for node in graph["nodes"]}
        self.assertIn("case", node_types)
        self.assertIn("source", node_types)
        self.assertEqual(len(graph["edges"]), 1)

    def test_fetch_all_records_partial_health(self):
        def item(url):
            return RawItem(
                source_id="s",
                source_kind="rss_search",
                title="Acme Bank launches AI agent",
                url=url,
                publisher="Publisher",
                published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            )

        results = {
            "a": FetchResult(items=[item("https://a.example")], errors=[]),
            "b": FetchResult(items=[item("https://b.example")], errors=["q: boom"]),
            "c": FetchResult(items=[], errors=["q: dead"]),
        }

        def fake_fetch(source, entities=None):
            return results[source["id"]]

        with mock.patch("openfinai_radar.pipeline.fetch_source", side_effect=fake_fetch):
            raw, health = _fetch_all([{"id": "a"}, {"id": "b"}, {"id": "c"}])

        self.assertEqual(len(raw), 2)
        by_id = {entry["id"]: entry for entry in health}
        self.assertEqual(by_id["a"]["status"], "ok")
        self.assertEqual(by_id["b"]["status"], "partial")
        self.assertEqual(by_id["c"]["status"], "error")

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
