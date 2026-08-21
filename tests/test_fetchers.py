import unittest
from unittest import mock

import urllib.error

from openfinai_radar import fetchers


_RSS = (
    b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
    b"<item><title>Acme Bank launches AI agent</title>"
    b"<link>https://example.com/1</link>"
    b"<pubDate>Wed, 10 Aug 2026 12:00:00 GMT</pubDate>"
    b"<source>Example</source><description>desc</description></item>"
    b"</channel></rss>"
)

_GDELT = (
    b'{"articles":[{"title":"JPMorgan launches AI assistant",'
    b'"url":"https://news.example/1","seendate":"20260810T030000Z",'
    b'"domain":"example.com","language":"English"}]}'
)

_GITHUB = (
    b'{"items":[{"full_name":"acme/fin-ai",'
    b'"html_url":"https://github.com/acme/fin-ai",'
    b'"description":"AI for finance","created_at":"2026-08-10T00:00:00Z",'
    b'"topics":["fintech","ai"],"language":"Python"}]}'
)


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class FetcherTests(unittest.TestCase):
    def test_open_bytes_retries_transient_errors(self):
        with mock.patch("openfinai_radar.fetchers.urllib.request.urlopen") as urlopen:
            urlopen.side_effect = [
                urllib.error.URLError("temporary"),
                _FakeResponse(b"ok"),
            ]
            result = fetchers._open_bytes("https://example.com", timeout=1, retries=3, backoff=0)
        self.assertEqual(result, b"ok")
        self.assertEqual(urlopen.call_count, 2)

    def test_rss_search_isolates_failed_queries(self):
        source = {
            "id": "fixture",
            "type": "rss_search",
            "language": "en",
            "url_template": "https://example.com/rss?q={query}",
            "queries": ["broken", "working"],
        }

        def fake_open(url, timeout, retries, backoff):
            if "broken" in url:
                raise urllib.error.URLError("boom")
            return _RSS

        with mock.patch("openfinai_radar.fetchers._open_bytes", side_effect=fake_open):
            result = fetchers.fetch_rss_search(source, retries=1, backoff=0)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].url, "https://example.com/1")
        self.assertEqual(len(result.errors), 1)
        self.assertIn("boom", result.errors[0])

    def test_gdelt_parses_articles(self):
        source = {"id": "gdelt", "type": "gdelt", "language": "en", "queries": ["finance AI"]}
        with mock.patch("openfinai_radar.fetchers._open_bytes", return_value=_GDELT):
            result = fetchers.fetch_gdelt(source, retries=1, backoff=0)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].source_kind, "gdelt")
        self.assertEqual(result.items[0].channel, "news")
        self.assertEqual(result.items[0].published_at.year, 2026)

    def test_github_parses_repos(self):
        source = {"id": "github", "type": "github", "queries": ["fintech ai"]}
        with mock.patch("openfinai_radar.fetchers._request", return_value=_GITHUB):
            result = fetchers.fetch_github(source, retries=1, backoff=0)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].source_kind, "github")
        self.assertEqual(result.items[0].channel, "code")

    def test_producthunt_requires_token(self):
        source = {"id": "ph", "type": "product_hunt"}
        with mock.patch.dict("os.environ", {}, clear=True):
            result = fetchers.fetch_producthunt(source, retries=1, backoff=0)
        self.assertEqual(len(result.items), 0)
        self.assertTrue(result.errors)

    def test_watchlist_fetches_per_entity(self):
        source = {
            "id": "watchlist",
            "type": "watchlist",
            "keyword": "AI",
            "url_template": "https://example.com/rss?q={query}",
        }
        entities = [
            {"canonical_name": "JPMorgan Chase"},
            {"canonical_name": "OpenAI"},
        ]
        with mock.patch("openfinai_radar.fetchers._open_bytes", return_value=_RSS):
            result = fetchers.fetch_watchlist(source, entities, retries=1, backoff=0)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].query, '"JPMorgan Chase" AI')
        self.assertEqual(result.items[1].query, '"OpenAI" AI')


if __name__ == "__main__":
    unittest.main()
