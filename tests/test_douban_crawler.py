from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.crawler.douban import DoubanCrawler, DoubanGroupConfig
from app.crawler.parser import parse_douban_group_posts
from app.database import Repository

HTML = """
<html>
  <body>
    <table>
      <tr>
        <td class="title">
          <a href="/group/topic/123456789/" data-created-at="2026-06-27T01:20:00+08:00">
            百利原始鸡 335 元
          </a>
        </td>
      </tr>
      <tr>
        <td class="title">
          <a href="https://www.douban.com/group/topic/987654321/">
            OP 三文鱼冻干补货
          </a>
        </td>
      </tr>
      <tr>
        <td class="title">
          <a href="/group/topic/123456789/">重复链接不应重复解析</a>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / "cat_deal_radar.sqlite")
    repo.initialize()
    yield repo
    repo.close()


def test_parse_douban_group_posts_extracts_topics() -> None:
    posts = parse_douban_group_posts(HTML, base_url="https://www.douban.com/group/haixiuzu/")

    assert len(posts) == 2
    assert posts[0].douban_post_id == "123456789"
    assert posts[0].title == "百利原始鸡 335 元"
    assert posts[0].url == "https://www.douban.com/group/topic/123456789/"
    assert posts[0].created_at == datetime(2026, 6, 26, 17, 20, tzinfo=UTC)
    assert posts[1].douban_post_id == "987654321"
    assert posts[1].title == "OP 三文鱼冻干补货"


def test_crawler_saves_new_posts_and_skips_duplicates(
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
) -> None:
    def fake_fetch_html(*args, **kwargs) -> str:
        return HTML

    monkeypatch.setattr("app.crawler.douban.fetch_html", fake_fetch_html)

    crawler = DoubanCrawler(
        DoubanGroupConfig(
            group_url="https://www.douban.com/group/haixiuzu/",
            tab_name="闲车禁拼多多",
        ),
        repository,
    )

    first_run = crawler.run_once()
    second_run = crawler.run_once()

    assert len(first_run) == 2
    assert second_run == []
    assert [post.douban_post_id for post in repository.list_posts()] == ["987654321", "123456789"]
