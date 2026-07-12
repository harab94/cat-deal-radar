"""Crawler package for community deal sources."""

from app.crawler.douban import DoubanCrawler, DoubanGroupConfig
from app.crawler.parser import ParsedPost, parse_douban_group_posts
from app.crawler.smzdm import SmzdmConfig, SmzdmCrawler, SmzdmItem, parse_smzdm_items

__all__ = [
    "DoubanCrawler",
    "DoubanGroupConfig",
    "ParsedPost",
    "SmzdmConfig",
    "SmzdmCrawler",
    "SmzdmItem",
    "parse_douban_group_posts",
    "parse_smzdm_items",
]
