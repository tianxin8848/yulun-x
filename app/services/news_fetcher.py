from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        return None


def fetch_news_by_keyword(keyword: str, max_items: int = 30) -> list[dict[str, Any]]:
    keyword_variants = [keyword.strip()]
    if keyword.endswith("新闻"):
        stripped = keyword[: -len("新闻")].strip()
        if stripped:
            keyword_variants.append(stripped)

    base_templates = [
        "https://news.google.com/rss/search?q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=HK&ceid=HK:zh-Hant",
        "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
    ]

    seen_urls: set[str] = set()
    items: list[dict[str, Any]] = []

    for kw in keyword_variants:
        encoded = quote_plus(kw)
        for template in base_templates:
            url = template.format(q=encoded)
            feed = feedparser.parse(url)
            for entry in feed.entries:
                source_url = entry.get("link", "")
                if not source_url or source_url in seen_urls:
                    continue
                seen_urls.add(source_url)
                items.append(
                    {
                        "title": entry.get("title", "").strip(),
                        "source": entry.get("source", {}).get("title", "") if entry.get("source") else "",
                        "source_url": source_url,
                        "published_at": _parse_datetime(entry.get("published")),
                        "content": entry.get("summary", ""),
                    }
                )
                if len(items) >= max_items:
                    return items

    return items
