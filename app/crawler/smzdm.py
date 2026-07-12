from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import structlog

from app.database import Post, Repository

logger = structlog.get_logger()

SMZDM_ID_PATTERN = re.compile(r"/p/([^/?#]+)/?")


@dataclass(frozen=True)
class SmzdmConfig:
    search_urls: tuple[str, ...]
    include_keywords: tuple[str, ...] = (
        "猫",
        "猫粮",
        "猫砂",
        "罐头",
        "餐包",
        "冻干",
        "驱虫",
    )
    user_agent: str = "Mozilla/5.0 CatDealRadar/0.1"
    timeout_seconds: int = 20


@dataclass(frozen=True)
class SmzdmItem:
    item_id: str
    title: str
    url: str


class SmzdmCrawler:
    def __init__(self, config: SmzdmConfig, repository: Repository) -> None:
        self._config = config
        self._repository = repository

    def fetch_latest_items(self) -> list[SmzdmItem]:
        items: list[SmzdmItem] = []
        seen_ids: set[str] = set()
        for url in self._config.search_urls:
            html = fetch_html(
                url,
                user_agent=self._config.user_agent,
                timeout_seconds=self._config.timeout_seconds,
            )
            for item in parse_smzdm_items(
                html,
                base_url=url,
                include_keywords=self._config.include_keywords,
            ):
                if item.item_id in seen_ids:
                    continue
                items.append(item)
                seen_ids.add(item.item_id)
        return items

    def save_latest_items(self, items: list[SmzdmItem]) -> list[Post]:
        fetched_at = datetime.now(UTC)
        processed_posts: list[Post] = []
        created_count = 0

        for item in items:
            source_id = f"smzdm:{item.item_id}"
            existing_post = self._repository.get_post_by_douban_id(source_id)
            post = Post(
                id=existing_post.id if existing_post else None,
                douban_post_id=source_id,
                title=item.title,
                content=item.title,
                url=item.url,
                created_at=existing_post.created_at if existing_post else fetched_at,
                fetched_at=fetched_at,
            )
            if existing_post is None:
                processed_posts.append(self._repository.create_post(post))
                created_count += 1
            elif _post_content_changed(existing_post, post):
                processed_posts.append(self._repository.update_post(post))
            else:
                processed_posts.append(existing_post)

        logger.info(
            "smzdm_items_saved",
            created_count=created_count,
            processed_count=len(processed_posts),
            parsed_count=len(items),
        )
        return processed_posts

    def run_once(self) -> list[Post]:
        return self.save_latest_items(self.fetch_latest_items())


def parse_smzdm_items(
    content: str,
    *,
    base_url: str,
    include_keywords: tuple[str, ...],
) -> list[SmzdmItem]:
    if content.lstrip().startswith("<?xml"):
        return _parse_rss_items(content, include_keywords)

    parser = _SmzdmLinkParser(base_url)
    parser.feed(content)
    items: list[SmzdmItem] = []
    seen_ids: set[str] = set()
    for link in parser.links:
        title = _clean_text(link.title)
        if not title or not _has_include_keyword(title, include_keywords):
            continue
        item_id = _item_id(link.url)
        if item_id in seen_ids:
            continue
        items.append(SmzdmItem(item_id=item_id, title=title, url=link.url))
        seen_ids.add(item_id)
    return items


def _parse_rss_items(content: str, include_keywords: tuple[str, ...]) -> list[SmzdmItem]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise RuntimeError(f"Failed to parse SMZDM RSS: {error}") from error

    items: list[SmzdmItem] = []
    seen_ids: set[str] = set()
    for node in root.findall("./channel/item"):
        title = _clean_text(node.findtext("title") or "")
        url = _canonical_url(node.findtext("link") or "")
        if not title or not _has_include_keyword(title, include_keywords):
            continue
        if not _is_smzdm_item_url(url):
            continue
        item_id = _item_id(url)
        if item_id in seen_ids:
            continue
        items.append(SmzdmItem(item_id=item_id, title=title, url=url))
        seen_ids.add(item_id)
    return items


def fetch_html(url: str, *, user_agent: str, timeout_seconds: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.smzdm.com/",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as error:
        detail = error.read(300).decode("utf-8", errors="replace").replace("\n", " ")
        msg = f"Failed to fetch SMZDM page: {url} (status={error.code} body={detail[:200]})"
        raise RuntimeError(msg) from error
    except URLError as error:
        msg = f"Failed to fetch SMZDM page: {url} ({error.reason})"
        raise RuntimeError(msg) from error


@dataclass
class _Link:
    url: str
    title: str
    title_from_attr: bool = False


class _SmzdmLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._current_link: _Link | None = None
        self.links: list[_Link] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if not href:
            return

        url = _canonical_url(urljoin(self._base_url, href))
        if not _is_smzdm_item_url(url):
            return

        title = attrs_dict.get("title") or ""
        self._current_link = _Link(
            url=url,
            title=title,
            title_from_attr=bool(title.strip()),
        )

    def handle_data(self, data: str) -> None:
        if self._current_link is not None and not self._current_link.title_from_attr:
            self._current_link.title += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link is not None:
            self.links.append(self._current_link)
            self._current_link = None


def _post_content_changed(existing_post: Post, latest_post: Post) -> bool:
    return existing_post.title != latest_post.title or existing_post.url != latest_post.url


def _is_smzdm_item_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("smzdm.com") and SMZDM_ID_PATTERN.search(parsed.path) is not None


def _item_id(url: str) -> str:
    parsed = urlparse(url)
    match = SMZDM_ID_PATTERN.search(parsed.path)
    if match:
        return match.group(1)
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()


def _clean_text(value: str) -> str:
    return " ".join(unescape(value).split())


def _has_include_keyword(title: str, include_keywords: tuple[str, ...]) -> bool:
    if any(keyword in title for keyword in ("狗", "犬")) and "猫" not in title:
        return False
    return any(keyword in title for keyword in include_keywords)
