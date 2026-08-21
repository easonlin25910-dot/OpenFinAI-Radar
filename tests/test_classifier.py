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

    def test_application_scenario_explains_use_and_value(self):
        result = classify_item(
            self.make_item(
                "Razorpay launches payments foundation model for fraud detection and routing"
            )
        )
        self.assertIn("支付交易", result.application_scenario)
        self.assertIn("欺诈", result.expected_value)
        self.assertEqual(result.innovation_level, "substantive")
        self.assertIn("专用或基础模型", result.innovation_assessment)

    def test_agent_label_alone_does_not_prove_innovation(self):
        result = classify_item(self.make_item("Bank launches AI agent for internal operations"))
        self.assertEqual(result.innovation_level, "not_demonstrated")
        self.assertIn("暂未证明", result.innovation_assessment)

    def test_merchant_platform_gets_specific_scenario(self):
        result = classify_item(self.make_item("Alipay launches agentic commerce platform for merchants"))
        self.assertIn("商户", result.application_scenario)

    def test_product_identity_official_page_audience_and_category(self):
        result = classify_item(
            self.make_item(
                "KTX Launches Skills Kit to Connect AI Agents With Trading Intelligence and Execution"
            )
        )
        self.assertEqual(result.product_name, "KTX Skills Kit")
        self.assertEqual(result.product_name_status, "explicit")
        self.assertEqual(result.official_url_status, "confirmed_product_page")
        self.assertEqual(result.customer_type, "to_b")
        self.assertIn("investment_markets", result.product_categories)
        self.assertTrue(result.product_search_url.startswith("https://www.google.com/search?q="))

    def test_personal_loan_product_is_to_c_and_lending(self):
        result = classify_item(
            self.make_item("MoneyBuddy launches AI personal loan assistant for borrowers")
        )
        self.assertEqual(result.customer_type, "to_c")
        self.assertIn("lending_financing", result.product_categories)

    def test_company_homepage_is_not_presented_as_product_page(self):
        result = classify_item(
            self.make_item("Razorpay launches Vulcan AI model for payments")
        )
        self.assertEqual(result.official_url, "https://razorpay.com/")
        self.assertEqual(result.official_url_status, "official_company_homepage")

    def test_api_token_does_not_match_inside_capital(self):
        result = classify_item(
            self.make_item("Acme launches AI platform for capital markets intelligence")
        )
        self.assertEqual(result.customer_type, "undisclosed")

    def test_foundation_model_without_ai_keyword_is_accepted(self):
        result = classify_item(
            self.make_item("Razorpay launches payments foundation model for fraud detection")
        )
        self.assertEqual(result.review_status, "needs_review")
        self.assertIn("generative_ai", result.ai_types)

    def test_watchlist_entity_surfaces_event_without_finance_ai_keywords(self):
        item = self.make_item("OpenAI launches finance agent")
        item.entity = "OpenAI"
        item.entity_role = "ai_giant"
        item.is_watchlist = True
        result = classify_item(item)
        self.assertEqual(result.review_status, "needs_review")
        self.assertIn("machine_learning", result.ai_types)


if __name__ == "__main__":
    unittest.main()
