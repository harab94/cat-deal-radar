from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

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


def parse_douban_topic_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    return _clean_text(" ".join(parser.text_parts))


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
            url=_canonical_topic_url(self._base_url, match.group(1)),
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


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture_depth = 0
        self._skip_depth = 0
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return

        if self._capture_depth:
            self._capture_depth += 1
        elif _is_topic_content_container(attrs):
            self._capture_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._capture_depth:
            self._capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_depth and not self._skip_depth:
            self.text_parts.append(data)


def _clean_text(value: str) -> str:
    return " ".join(unescape(value).split())


def _canonical_topic_url(base_url: str, topic_id: str) -> str:
    parsed = urlparse(base_url)
    host = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else base_url
    return urljoin(host, f"/group/topic/{topic_id}/")


def _is_topic_content_container(attrs: list[tuple[str, str | None]]) -> bool:
    attrs_dict = dict(attrs)
    element_id = attrs_dict.get("id", "")
    class_names = attrs_dict.get("class", "")
    return element_id == "link-report" or any(
        name in class_names
        for name in (
            "topic-content",
            "topic-richtext",
            "rich-content",
        )
    )


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
