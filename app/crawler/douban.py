from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

import structlog

from app.crawler.parser import ParsedPost, parse_douban_group_posts
from app.database import Post, Repository

logger = structlog.get_logger()


@dataclass(frozen=True)
class DoubanGroupConfig:
    group_url: str
    tab_name: str
    cookie: str | None = None
    user_agent: str = "Mozilla/5.0 CatDealRadar/0.1"
    timeout_seconds: int = 20


class DoubanCrawler:
    def __init__(self, config: DoubanGroupConfig, repository: Repository) -> None:
        self._config = config
        self._repository = repository

    def fetch_latest_posts(self) -> list[ParsedPost]:
        html = fetch_html(
            self._config.group_url,
            cookie=self._config.cookie,
            user_agent=self._config.user_agent,
            timeout_seconds=self._config.timeout_seconds,
        )
        return parse_douban_group_posts(html, base_url=self._config.group_url)

    def save_new_posts(self, posts: list[ParsedPost]) -> list[Post]:
        fetched_at = datetime.now(UTC)
        saved_posts: list[Post] = []

        for parsed_post in posts:
            post = Post(
                douban_post_id=parsed_post.douban_post_id,
                title=parsed_post.title,
                content=parsed_post.title,
                url=parsed_post.url,
                created_at=parsed_post.created_at or fetched_at,
                fetched_at=fetched_at,
            )
            saved_post = self._repository.create_post_if_new(post)
            if saved_post is not None:
                saved_posts.append(saved_post)

        logger.info("douban_posts_saved", saved_count=len(saved_posts), parsed_count=len(posts))
        return saved_posts

    def run_once(self) -> list[Post]:
        return self.save_new_posts(self.fetch_latest_posts())


def fetch_html(
    url: str,
    *,
    cookie: str | None,
    user_agent: str,
    timeout_seconds: int,
) -> str:
    headers = {"User-Agent": user_agent}
    if cookie:
        headers["Cookie"] = cookie

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except URLError as error:
        msg = f"Failed to fetch Douban page: {url}"
        raise RuntimeError(msg) from error
