"""Crawler package for community deal sources."""

from app.crawler.douban import DoubanCrawler, DoubanGroupConfig
from app.crawler.parser import ParsedPost, parse_douban_group_posts

__all__ = [
    "DoubanCrawler",
    "DoubanGroupConfig",
    "ParsedPost",
    "parse_douban_group_posts",
]
