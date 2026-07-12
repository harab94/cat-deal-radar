from __future__ import annotations

from pathlib import Path

import pytest

from app.crawler.smzdm import SmzdmConfig, SmzdmCrawler, parse_smzdm_items
from app.database import Repository

HTML = """
<html>
  <body>
    <a href="https://www.smzdm.com/p/12345678/" title="京东 宠物猫粮低至88元">
      京东 宠物猫粮低至88元
    </a>
    <a href="https://post.smzdm.com/p/a123abc/">猫砂囤货攻略</a>
    <a href="https://www.smzdm.com/p/999/">手机壳9.9元</a>
    <a href="https://www.smzdm.com/p/12345678/">重复猫粮</a>
  </body>
</html>
"""

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>京东 美士猫粮 88元</title>
      <link>https://www.smzdm.com/p/888888/</link>
    </item>
    <item>
      <title>小米手机 1999元</title>
      <link>https://www.smzdm.com/p/999999/</link>
    </item>
    <item>
      <title>网易严选 全价冻干狗粮 1.9元</title>
      <link>https://www.smzdm.com/p/777777/</link>
    </item>
  </channel>
</rss>
"""


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / "cat_deal_radar.sqlite")
    repo.initialize()
    yield repo
    repo.close()


def test_parse_smzdm_items_filters_cat_related_links() -> None:
    items = parse_smzdm_items(
        HTML,
        base_url="https://search.smzdm.com/?s=%E7%8C%AB%E7%B2%AE",
        include_keywords=("猫", "猫粮", "猫砂"),
    )

    assert [item.item_id for item in items] == ["12345678", "a123abc"]
    assert items[0].title == "京东 宠物猫粮低至88元"
    assert items[0].url == "https://www.smzdm.com/p/12345678/"
    assert items[1].url == "https://post.smzdm.com/p/a123abc/"


def test_parse_smzdm_items_supports_official_rss() -> None:
    items = parse_smzdm_items(
        RSS,
        base_url="http://feed.smzdm.com",
        include_keywords=("猫", "猫粮", "猫砂"),
    )

    assert [(item.item_id, item.title) for item in items] == [
        ("888888", "京东 美士猫粮 88元")
    ]


def test_smzdm_crawler_saves_items_without_duplicate_inserts(
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
) -> None:
    monkeypatch.setattr("app.crawler.smzdm.fetch_html", lambda *args, **kwargs: HTML)

    crawler = SmzdmCrawler(
        SmzdmConfig(
            search_urls=("https://search.smzdm.com/?s=%E7%8C%AB%E7%B2%AE",),
            include_keywords=("猫", "猫粮", "猫砂"),
        ),
        repository,
    )

    first_run = crawler.run_once()
    second_run = crawler.run_once()

    assert len(first_run) == 2
    assert len(second_run) == 2
    assert [post.id for post in second_run] == [post.id for post in first_run]
    assert {post.douban_post_id for post in first_run} == {"smzdm:12345678", "smzdm:a123abc"}
