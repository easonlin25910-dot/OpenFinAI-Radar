from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Optional

from .models import RawItem


USER_AGENT = "OpenFinAI-Radar/0.1 (+https://github.com/easonlin25910-dot/OpenFinAI-Radar)"
TAG_RE = re.compile(r"<[^>]+>")


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


def fetch_rss_search(source: Dict[str, object], timeout: int = 25) -> List[RawItem]:
    results: List[RawItem] = []
    for query in source.get("queries", []):
        encoded = urllib.parse.quote_plus(str(query))
        url = str(source["url_template"]).replace("{query}", encoded)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
        for parsed in _rss_items(data):
            title = str(parsed["title"])
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
            results.append(
                RawItem(
                    source_id=str(source["id"]),
                    source_kind="rss_search",
                    title=title,
                    url=str(parsed["link"]),
                    publisher=publisher,
                    published_at=parsed["published_at"],  # type: ignore[arg-type]
                    description=description,
                    query=str(query),
                    language=str(source.get("language", "en")),
                )
            )
    return results


def fetch_source(source: Dict[str, object]) -> List[RawItem]:
    if source.get("type") == "rss_search":
        return fetch_rss_search(source)
    if source.get("type") == "mcp_registry":
        return fetch_mcp_registry(source)
    raise ValueError("Unsupported source type: " + str(source.get("type")))


def fetch_mcp_registry(source: Dict[str, object], timeout: int = 25) -> List[RawItem]:
    """Fetch finance-related products from the official MCP Registry shelf."""
    results: List[RawItem] = []
    seen = set()
    for query in source.get("queries", []):
        url = str(source["url_template"]).replace("{query}", urllib.parse.quote_plus(str(query)))
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        for entry in payload.get("servers", []):
            server = entry.get("server", {})
            official = entry.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
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
            link = str(server.get("websiteUrl") or repository.get("url") or "https://registry.modelcontextprotocol.io")
            title = str(server.get("title") or name)
            publisher = name.split("/", 1)[0] if "/" in name else name
            results.append(
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
                )
            )
    return results
