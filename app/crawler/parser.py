from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

TOPIC_ID_PATTERN = re.compile(r"/group/topic/(\d+)/?")


@dataclass(frozen=True)
class ParsedPost:
    douban_post_id: str
    title: str
    url: str
    created_at: datetime | None


def parse_douban_group_posts(html: str, *, base_url: str) -> list[ParsedPost]:
    parser = _DoubanTopicParser(base_url)
    parser.feed(html)
    return parser.posts


class _DoubanTopicParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._current_link: _TopicLink | None = None
        self._seen_ids: set[str] = set()
        self.posts: list[ParsedPost] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if not href:
            return

        match = TOPIC_ID_PATTERN.search(href)
        if not match:
            return

        self._current_link = _TopicLink(
            douban_post_id=match.group(1),
            url=urljoin(self._base_url, href),
            title_parts=[],
            created_at=_parse_datetime(attrs_dict.get("data-created-at")),
        )

    def handle_data(self, data: str) -> None:
        if self._current_link is not None:
            self._current_link.title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_link is None:
            return

        title = _clean_text("".join(self._current_link.title_parts))
        if title and self._current_link.douban_post_id not in self._seen_ids:
            self.posts.append(
                ParsedPost(
                    douban_post_id=self._current_link.douban_post_id,
                    title=title,
                    url=self._current_link.url,
                    created_at=self._current_link.created_at,
                )
            )
            self._seen_ids.add(self._current_link.douban_post_id)

        self._current_link = None


@dataclass
class _TopicLink:
    douban_post_id: str
    url: str
    title_parts: list[str]
    created_at: datetime | None


def _clean_text(value: str) -> str:
    return " ".join(unescape(value).split())


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
