from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from app.crawler.douban import DoubanCrawler, DoubanGroupConfig, fetch_html
from app.crawler.parser import (
    parse_douban_group_posts,
    parse_douban_topic_comments,
    parse_douban_topic_text,
)
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
          <a href="https://www.douban.com/group/topic/987654321/?_spm_id=test">
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

TOPIC_HTML = """
<html>
  <body>
    <div class="topic-content">
      Halo自然光环未拆封，价格 210元，可自提。
    </div>
    <div class="reply-content">还能买，我刚拍。</div>
    <div class="comment-content">好像涨价了。</div>
    <script>ignore me</script>
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
    assert posts[1].url == "https://www.douban.com/group/topic/987654321/"


def test_crawler_returns_visible_posts_without_duplicate_inserts(
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
) -> None:
    def fake_fetch_html(url, *args, **kwargs) -> str:
        if "/group/topic/" in url:
            return TOPIC_HTML
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
    assert len(second_run) == 2
    assert [post.id for post in second_run] == [post.id for post in first_run]
    assert [post.douban_post_id for post in repository.list_posts()] == ["987654321", "123456789"]
    assert all("价格 210元" in post.content for post in first_run)
    assert all(post.comments == ("还能买，我刚拍。", "好像涨价了。") for post in first_run)


def test_crawler_skips_posts_when_topic_detail_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
) -> None:
    def fake_fetch_html(url, *args, **kwargs) -> str:
        if "/group/topic/" in url:
            raise RuntimeError("Failed to fetch Douban page")
        return HTML

    monkeypatch.setattr("app.crawler.douban.fetch_html", fake_fetch_html)

    crawler = DoubanCrawler(
        DoubanGroupConfig(
            group_url="https://www.douban.com/group/haixiuzu/",
            tab_name="闲车禁拼多多",
        ),
        repository,
    )

    assert crawler.run_once() == []
    assert repository.list_posts() == []


def test_crawler_skips_unavailable_topic_pages(
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
) -> None:
    def fake_fetch_html(url, *args, **kwargs) -> str:
        if "/group/topic/" in url:
            return "<html><body>你没有权限访问这个页面。</body></html>"
        return HTML

    monkeypatch.setattr("app.crawler.douban.fetch_html", fake_fetch_html)

    crawler = DoubanCrawler(
        DoubanGroupConfig(
            group_url="https://www.douban.com/group/haixiuzu/",
            tab_name="闲车禁拼多多",
        ),
        repository,
    )

    assert crawler.run_once() == []
    assert repository.list_posts() == []


def test_parse_douban_topic_text_extracts_visible_text() -> None:
    assert parse_douban_topic_text(TOPIC_HTML) == "Halo自然光环未拆封，价格 210元，可自提。"


def test_parse_douban_topic_comments_extracts_reply_text() -> None:
    assert parse_douban_topic_comments(TOPIC_HTML) == ["还能买，我刚拍。", "好像涨价了。"]


def test_parse_douban_topic_text_ignores_sidebar_text() -> None:
    html = """
    <html>
      <body>
        <aside>自然光环 263r 开车</aside>
        <div id="link-report">正文只有爱肯拿 330元</div>
      </body>
    </html>
    """

    assert parse_douban_topic_text(html) == "正文只有爱肯拿 330元"


def test_parse_douban_topic_text_trims_related_topic_recommendations() -> None:
    html = """
    <html>
      <body>
        <div id="link-report">
          Jarrow牛初乳，120粒装，100包邮，保质期至，27.5月
          now辅酶Q10，60粒30毫克装，40包邮，保质期至28.8
          打包-5
          赞 转发 微信扫码 新浪微博 QQ好友 QQ空间 回复
          相关内容推荐
          闲车禁拼多多｜【开车】jarrow60粒220r，返利12r，到手208r
          闲车禁拼多多｜【开车】小李子罐头禽肉200g 12.17r
        </div>
      </body>
    </html>
    """

    text = parse_douban_topic_text(html)

    assert "100包邮" in text
    assert "40包邮" in text
    assert "12.17r" not in text
    assert "返利12r" not in text


def test_fetch_html_includes_http_error_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_urlopen(*args, **kwargs):
        raise HTTPError(
            url="https://www.douban.com/group/haixiuzu/",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=BytesIO("登录后可见".encode()),
        )

    monkeypatch.setattr("app.crawler.douban.urlopen", fail_urlopen)

    with pytest.raises(RuntimeError, match="status=403"):
        fetch_html(
            "https://www.douban.com/group/haixiuzu/",
            cookie="bid=test",
            user_agent="test-agent",
            timeout_seconds=1,
        )
