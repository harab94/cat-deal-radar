from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import structlog

from app.crawler.parser import (
    ParsedPost,
    parse_douban_group_posts,
    parse_douban_topic_comments,
    parse_douban_topic_text,
)
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

    def save_latest_posts(self, posts: list[ParsedPost]) -> list[Post]:
        fetched_at = datetime.now(UTC)
        processed_posts: list[Post] = []
        created_count = 0

        for parsed_post in posts:
            content, comments = self._fetch_post_detail(parsed_post)
            existing_post = self._repository.get_post_by_douban_id(parsed_post.douban_post_id)
            post = Post(
                id=existing_post.id if existing_post else None,
                douban_post_id=parsed_post.douban_post_id,
                title=parsed_post.title,
                content=content,
                url=parsed_post.url,
                created_at=existing_post.created_at
                if existing_post
                else parsed_post.created_at or fetched_at,
                fetched_at=fetched_at,
                comments=tuple(comments),
            )
            if existing_post is None:
                processed_posts.append(self._repository.create_post(post))
                created_count += 1
            elif _post_content_changed(existing_post, post):
                processed_posts.append(self._repository.update_post(post))
            else:
                processed_posts.append(existing_post)

        logger.info(
            "douban_posts_saved",
            created_count=created_count,
            processed_count=len(processed_posts),
            parsed_count=len(posts),
        )
        return processed_posts

    def save_new_posts(self, posts: list[ParsedPost]) -> list[Post]:
        return self.save_latest_posts(posts)

    def run_once(self) -> list[Post]:
        return self.save_latest_posts(self.fetch_latest_posts())

    def _fetch_post_detail(self, post: ParsedPost) -> tuple[str, list[str]]:
        try:
            html = fetch_html(
                post.url,
                cookie=self._config.cookie,
                user_agent=self._config.user_agent,
                timeout_seconds=self._config.timeout_seconds,
            )
        except RuntimeError as error:
            logger.warning(
                "douban_topic_fetch_failed",
                post_id=post.douban_post_id,
                error=str(error),
            )
            return post.title, []

        text = parse_douban_topic_text(html)
        return text or post.title, parse_douban_topic_comments(html)


def _post_content_changed(existing_post: Post, latest_post: Post) -> bool:
    return (
        existing_post.title != latest_post.title
        or existing_post.content != latest_post.content
        or existing_post.url != latest_post.url
    )


def fetch_html(
    url: str,
    *,
    cookie: str | None,
    user_agent: str,
    timeout_seconds: int,
) -> str:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.douban.com/",
    }
    if cookie:
        headers["Cookie"] = cookie

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as error:
        detail = _http_error_detail(error)
        msg = f"Failed to fetch Douban page: {url} ({detail})"
        raise RuntimeError(msg) from error
    except URLError as error:
        msg = f"Failed to fetch Douban page: {url} ({error.reason})"
        raise RuntimeError(msg) from error


def _http_error_detail(error: HTTPError) -> str:
    body = error.read(300).decode("utf-8", errors="replace").replace("\n", " ")
    if body:
        return f"status={error.code} reason={error.reason} body={body[:200]}"
    return f"status={error.code} reason={error.reason}"
