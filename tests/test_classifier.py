import unittest
from datetime import datetime, timezone

from openfinai_radar.classify import classify_item, jaccard, same_named_event, title_similarity
from openfinai_radar.models import RawItem


class ClassifierTests(unittest.TestCase):
    def make_item(self, title):
        return RawItem(
            source_id="fixture",
            source_kind="rss_search",
            title=title,
            url="https://example.com/evidence",
            publisher="Example",
            published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )

    def test_financial_ai_launch_is_accepted(self):
        result = classify_item(self.make_item("Bank launches generative AI agent for payments"))
        self.assertEqual(result.review_status, "needs_review")
        self.assertEqual(result.event_type, "product_launch")
        self.assertIn("banking", result.finance_domains)

    def test_opinion_without_event_is_rejected(self):
        result = classify_item(self.make_item("Opinion: what is artificial intelligence?"))
        self.assertEqual(result.review_status, "below_threshold")

    def test_title_similarity(self):
        score = jaccard(
            "Acme Bank launches generative AI payment agent",
            "Acme Bank launches new AI payment agent",
        )
        self.assertGreater(score, 0.55)
        self.assertGreater(
            title_similarity(
                "Razorpay launches Vulcan AI model for payments",
                "Razorpay unveils Vulcan, an AI payments foundation model",
            ),
            0.60,
        )
        self.assertTrue(
            same_named_event(
                "Razorpay launches Vulcan AI model for payments",
                "India's first AI payments foundation model Vulcan launched by Razorpay",
            )
        )

    def test_non_financial_ai_launch_is_rejected(self):
        result = classify_item(self.make_item("TCS launches agentic AI for drug development"))
        self.assertEqual(result.review_status, "below_threshold")

    def test_mcp_listing_uses_marketplace_time(self):
        item = self.make_item("Constellation Finance Data")
        item.source_kind = "mcp_registry"
        item.description = "Financial and covenant data for public credit"
        result = classify_item(item)
        self.assertEqual(result.effective_time_type, "marketplace_listing")
        self.assertEqual(result.listing_time, "2026-08-10")
        self.assertEqual(result.review_status, "needs_review")


if __name__ == "__main__":
    unittest.main()
