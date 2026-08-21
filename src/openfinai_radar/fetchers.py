from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Optional, Sequence

from .models import FetchResult, RawItem


USER_AGENT = "OpenFinAI-Radar/0.3 (+https://github.com/easonlin25910-dot/OpenFinAI-Radar)"
TAG_RE = re.compile(r"<[^>]+>")
_RETRYABLE_HTTP_CODES = (429, 500, 502, 503, 504)


def _text(node: Optional[ET.Element], default: str = "") -> str:
    return default if node is None or node.text is None else node.text.strip()


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value or ""))).strip()


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _short_error(error: BaseException) -> str:
    return str(error).strip()[:240]


def _request(
    url: str,
    timeout: int,
    retries: int,
    backoff: float,
    *,
    method: str = "GET",
    payload: Optional[Dict[str, object]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> bytes:
    """Fetch bytes with a short retry loop for transient network failures."""
    last_error: Optional[BaseException] = None
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        try:
            request_headers = {"User-Agent": USER_AGENT}
            if headers:
                request_headers.update(headers)
            if body is not None:
                request_headers.setdefault("Content-Type", "application/json")
            request = urllib.request.Request(
                url, data=body, headers=request_headers, method=method
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in _RETRYABLE_HTTP_CODES or attempt == retries - 1:
                raise
        except (urllib.error.URLError, OSError) as error:
            last_error = error
            if attempt == retries - 1:
                raise
        time.sleep(backoff * (2 ** attempt))
    raise last_error if last_error is not None else RuntimeError("unreachable retry state")


def _open_bytes(url: str, timeout: int, retries: int, backoff: float) -> bytes:
    return _request(url, timeout, retries, backoff)


def _post_json(
    url: str,
    payload: Dict[str, object],
    token: str,
    timeout: int,
    retries: int,
    backoff: float,
) -> bytes:
    return _request(
        url,
        timeout,
        retries,
        backoff,
        method="POST",
        payload=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def _publisher(item: ET.Element, title: str) -> str:
    for child in item:
        if child.tag.split("}")[-1].lower() in {"source", "provider"} and _text(child):
            return _text(child)
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Unknown"


def _rss_items(data: bytes) -> Iterable[Dict[str, object]]:
    root = ET.fromstring(data)
    rss_items = root.findall(".//item")
    if rss_items:
        for item in rss_items:
            title = _text(item.find("title"))
            yield {
                "title": title,
                "link": _text(item.find("link")),
                "description": _clean_html(_text(item.find("description"))),
                "published_at": _parse_date(
                    _text(item.find("pubDate")) or _text(item.find("date"))
                ),
                "publisher": _publisher(item, title),
            }
        return

    atom_ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", atom_ns):
        link_node = entry.find("a:link", atom_ns)
        yield {
            "title": _text(entry.find("a:title", atom_ns)),
            "link": "" if link_node is None else link_node.attrib.get("href", ""),
            "description": _clean_html(
                _text(entry.find("a:summary", atom_ns))
                or _text(entry.find("a:content", atom_ns))
            ),
            "published_at": _parse_date(
                _text(entry.find("a:published", atom_ns))
                or _text(entry.find("a:updated", atom_ns))
            ),
            "publisher": "Unknown",
        }


def _rss_item(source: Dict[str, object], parsed: Dict[str, object], query: str) -> Optional[RawItem]:
    title = str(parsed["title"]).strip()
    link = str(parsed["link"]).strip()
    if not title or not link:
        return None
    publisher = str(parsed["publisher"])
    if publisher != "Unknown" and title.endswith(" - " + publisher):
        title = title[: -(len(publisher) + 3)].strip()
    description = str(parsed["description"])
    # Google News RSS descriptions repeat the headline and publisher.
    # Removing those prevents a publisher such as "BankInfoSecurity"
    # from falsely supplying the financial-domain signal.
    description = description.replace(title, " ")
    if publisher != "Unknown":
        description = description.replace(publisher, " ")
    description = re.sub(r"\s+", " ", description).strip()
    return RawItem(
        source_id=str(source["id"]),
        source_kind="rss_search",
        title=title,
        url=link,
        publisher=publisher,
        published_at=parsed["published_at"],  # type: ignore[arg-type]
        description=description,
        query=query,
        language=str(source.get("language", "en")),
        channel="news",
    )


def fetch_rss_search(
    source: Dict[str, object],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
) -> FetchResult:
    items: List[RawItem] = []
    errors: List[str] = []
    for query in source.get("queries", []):
        encoded = urllib.parse.quote_plus(str(query))
        url = str(source["url_template"]).replace("{query}", encoded)
        try:
            data = _open_bytes(url, timeout, retries, backoff)
        except Exception as error:  # a single query must not drop the whole source
            errors.append(f"{query}: {_short_error(error)}")
            continue
        try:
            for parsed in _rss_items(data):
                item = _rss_item(source, parsed, str(query))
                if item is not None:
                    items.append(item)
        except Exception as error:
            errors.append(f"{query}: parse error {_short_error(error)}")
    return FetchResult(items=items, errors=errors)


def fetch_mcp_registry(
    source: Dict[str, object],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
) -> FetchResult:
    """Fetch finance-related products from the official MCP Registry shelf."""
    items: List[RawItem] = []
    errors: List[str] = []
    seen = set()
    for query in source.get("queries", []):
        url = str(source["url_template"]).replace(
            "{query}", urllib.parse.quote_plus(str(query))
        )
        try:
            data = _open_bytes(url, timeout, retries, backoff)
            payload = json.loads(data.decode("utf-8"))
        except Exception as error:
            errors.append(f"{query}: {_short_error(error)}")
            continue
        for entry in payload.get("servers", []):
            server = entry.get("server", {})
            official = entry.get("_meta", {}).get(
                "io.modelcontextprotocol.registry/official", {}
            )
            if official.get("isLatest") is False:
                continue
            name = str(server.get("name", ""))
            version = str(server.get("version", ""))
            unique = (name, version)
            if unique in seen:
                continue
            seen.add(unique)
            published = _parse_date(str(official.get("publishedAt", "")))
            repository = server.get("repository") or {}
            link = str(
                server.get("websiteUrl")
                or repository.get("url")
                or "https://registry.modelcontextprotocol.io"
            )
            title = str(server.get("title") or name)
            publisher = name.split("/", 1)[0] if "/" in name else name
            items.append(
                RawItem(
                    source_id=str(source["id"]),
                    source_kind="mcp_registry",
                    title=title,
                    url=link,
                    publisher=publisher or "MCP publisher",
                    published_at=published,
                    description=str(server.get("description", "")),
                    query=str(query),
                    language="en",
                    channel="marketplace",
                )
            )
    return FetchResult(items=items, errors=errors)


def _parse_gdelt_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        return datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch_gdelt(
    source: Dict[str, object],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
) -> FetchResult:
    """Fetch yesterday's global news from the free GDELT 2.0 DOC API."""
    items: List[RawItem] = []
    errors: List[str] = []
    seen = set()
    for query in source.get("queries", []):
        url = (
            "https://api.gdeltproject.org/api/v2/doc/doc?query="
            + urllib.parse.quote_plus(str(query))
            + "&mode=artlist&maxrecords=250&format=json&timespan=1d"
        )
        try:
            data = _open_bytes(url, timeout, retries, backoff)
            payload = json.loads(data.decode("utf-8"))
        except Exception as error:
            errors.append(f"{query}: {_short_error(error)}")
            continue
        for article in payload.get("articles", []):
            title = str(article.get("title", "")).strip()
            link = str(article.get("url", "")).strip()
            if not title or not link or (title, link) in seen:
                continue
            seen.add((title, link))
            items.append(
                RawItem(
                    source_id=str(source["id"]),
                    source_kind="gdelt",
                    title=title,
                    url=link,
                    publisher=str(article.get("domain", "") or "GDELT"),
                    published_at=_parse_gdelt_date(str(article.get("seendate", ""))),
                    description="",
                    query=str(query),
                    language=str(article.get("language", "") or source.get("language", "en")),
                    channel="news",
                )
            )
        time.sleep(1.0)
    return FetchResult(items=items, errors=errors)


def fetch_producthunt(
    source: Dict[str, object],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
) -> FetchResult:
    """Fetch yesterday's top Product Hunt launches (requires PRODUCTHUNT_TOKEN)."""
    token = os.environ.get("PRODUCTHUNT_TOKEN", "")
    if not token:
        return FetchResult(items=[], errors=["PRODUCTHUNT_TOKEN not set"])
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1)
    query = (
        "query Posts($after: DateTime, $before: DateTime) {"
        " posts(order: VOTES, first: 50, postedAfter: $after, postedBefore: $before) {"
        "  edges { node { id name tagline url votesCount topics { edges { node { name } } } } } } }"
    )
    variables = {
        "after": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "before": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        data = _post_json(
            "https://api.producthunt.com/v2/api/graphql",
            {"query": query, "variables": variables},
            token,
            timeout,
            retries,
            backoff,
        )
        payload = json.loads(data.decode("utf-8"))
    except Exception as error:
        return FetchResult(items=[], errors=[_short_error(error)])

    items: List[RawItem] = []
    posts = payload.get("data", {}).get("posts", {}).get("edges", [])
    for edge in posts:
        node = edge.get("node", {})
        title = str(node.get("name", "")).strip()
        link = str(node.get("url", "")).strip()
        if not title:
            continue
        tagline = str(node.get("tagline", "") or "")
        topics = [
            str(topic.get("node", {}).get("name", ""))
            for topic in node.get("topics", {}).get("edges", [])
        ]
        description = (tagline + " " + " ".join(topics)).strip()
        items.append(
            RawItem(
                source_id=str(source["id"]),
                source_kind="product_hunt",
                title=title,
                url=link or f"https://www.producthunt.com/posts/{node.get('id', '')}",
                publisher="Product Hunt",
                published_at=start,
                description=description,
                query="daily-top",
                language="en",
                channel="community",
            )
        )
    return FetchResult(items=items, errors=[])


def fetch_github(
    source: Dict[str, object],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
) -> FetchResult:
    """Fetch recently created finance+AI repositories from GitHub search."""
    token = os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_PUSH_TOKEN", "")
    items: List[RawItem] = []
    errors: List[str] = []
    seen = set()
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    for query in source.get("queries", []):
        q = f"{query} created:>{since}"
        url = (
            "https://api.github.com/search/repositories?q="
            + urllib.parse.quote_plus(q)
            + "&sort=updated&order=desc&per_page=30"
        )
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            data = _request(url, timeout, retries, backoff, headers=headers)
            payload = json.loads(data.decode("utf-8"))
        except Exception as error:
            errors.append(f"{query}: {_short_error(error)}")
            continue
        for repo in payload.get("items", []):
            name = str(repo.get("full_name", "")).strip()
            link = str(repo.get("html_url", "")).strip()
            if not name or not link or (name, link) in seen:
                continue
            seen.add((name, link))
            description = str(repo.get("description", "") or "")
            topics = " ".join(repo.get("topics", []) or [])
            items.append(
                RawItem(
                    source_id=str(source["id"]),
                    source_kind="github",
                    title=name,
                    url=link,
                    publisher=name.split("/", 1)[0] if "/" in name else name,
                    published_at=_parse_date(str(repo.get("created_at", ""))),
                    description=(description + " " + topics).strip(),
                    query=str(query),
                    language=str(repo.get("language", "") or source.get("language", "en")),
                    channel="code",
                )
            )
    return FetchResult(items=items, errors=errors)


def fetch_hackernews(
    source: Dict[str, object],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
) -> FetchResult:
    """Fetch yesterday's Hacker News stories from the free Algolia API."""
    items: List[RawItem] = []
    errors: List[str] = []
    seen = set()
    since = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    for query in source.get("queries", []):
        url = (
            "https://hn.algolia.com/api/v1/search_by_date?query="
            + urllib.parse.quote_plus(str(query))
            + f"&tags=story&hitsPerPage=50&numericFilters=created_at_i>{since}"
        )
        try:
            data = _open_bytes(url, timeout, retries, backoff)
            payload = json.loads(data.decode("utf-8"))
        except Exception as error:
            errors.append(f"{query}: {_short_error(error)}")
            continue
        for hit in payload.get("hits", []):
            title = str(hit.get("title", "")).strip()
            link = str(hit.get("url", "") or "").strip()
            if not title or (title, link) in seen:
                continue
            seen.add((title, link))
            object_id = str(hit.get("objectID", ""))
            items.append(
                RawItem(
                    source_id=str(source["id"]),
                    source_kind="hackernews",
                    title=title,
                    url=link or f"https://news.ycombinator.com/item?id={object_id}",
                    publisher="Hacker News",
                    published_at=_parse_date(str(hit.get("created_at", ""))),
                    description=f"points {hit.get('points', 0)} comments {hit.get('num_comments', 0)}",
                    query=str(query),
                    language="en",
                    channel="community",
                )
            )
    return FetchResult(items=items, errors=errors)


def fetch_watchlist(
    source: Dict[str, object],
    entities: Sequence[Dict[str, object]],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
) -> FetchResult:
    """Fixed check: search each watched company's latest AI/finance activity."""
    items: List[RawItem] = []
    errors: List[str] = []
    keyword = str(source.get("keyword", "AI"))
    for entity in entities:
        name = str(entity.get("canonical_name", "")).strip()
        if not name:
            continue
        query = f'"{name}" {keyword}'
        url = str(source["url_template"]).replace(
            "{query}", urllib.parse.quote_plus(query)
        )
        try:
            data = _open_bytes(url, timeout, retries, backoff)
        except Exception as error:
            errors.append(f"{name}: {_short_error(error)}")
            continue
        try:
            for parsed in _rss_items(data):
                item = _rss_item(source, parsed, query)
                if item is not None:
                    items.append(item)
        except Exception as error:
            errors.append(f"{name}: parse error {_short_error(error)}")
    return FetchResult(items=items, errors=errors)


def fetch_source(
    source: Dict[str, object],
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 0.5,
    entities: Optional[Sequence[Dict[str, object]]] = None,
) -> FetchResult:
    if source.get("type") == "rss_search":
        return fetch_rss_search(source, timeout, retries, backoff)
    if source.get("type") == "mcp_registry":
        return fetch_mcp_registry(source, timeout, retries, backoff)
    if source.get("type") == "gdelt":
        return fetch_gdelt(source, timeout, retries, backoff)
    if source.get("type") == "product_hunt":
        return fetch_producthunt(source, timeout, retries, backoff)
    if source.get("type") == "github":
        return fetch_github(source, timeout, retries, backoff)
    if source.get("type") == "hackernews":
        return fetch_hackernews(source, timeout, retries, backoff)
    if source.get("type") == "watchlist":
        return fetch_watchlist(source, entities or [], timeout, retries, backoff)
    raise ValueError("Unsupported source type: " + str(source.get("type")))
