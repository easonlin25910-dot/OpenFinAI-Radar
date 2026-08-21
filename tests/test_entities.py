import unittest

from openfinai_radar.entities import build_entity_index, resolve_entity


ENTITIES = [
    {
        "id": "jpmorgan",
        "canonical_name": "JPMorgan Chase",
        "aliases": ["JPMorgan", "Chase", "摩根大通"],
        "region": "US",
        "role": "finance_giant",
    },
    {
        "id": "nubank",
        "canonical_name": "Nubank",
        "aliases": ["Nubank", "Nu"],
        "region": "BR",
        "role": "finance_giant",
    },
]


class EntityTests(unittest.TestCase):
    def setUp(self):
        self.index = build_entity_index(ENTITIES)

    def test_cjk_alias_resolves(self):
        self.assertEqual(resolve_entity("摩根大通推出AI助手", self.index)["id"], "jpmorgan")

    def test_ascii_alias_resolves(self):
        self.assertEqual(resolve_entity("Chase launches AI assistant", self.index)["id"], "jpmorgan")

    def test_short_alias_does_not_match_substring(self):
        self.assertIsNone(resolve_entity("number of users grows", self.index))


if __name__ == "__main__":
    unittest.main()
