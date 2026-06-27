from __future__ import annotations

from pathlib import Path

from app.database import Repository
from app.main import run
from app.pipeline import run_pipeline
from app.settings import Settings

HTML = """
<html>
  <body>
    <a href="/group/topic/123456789/" data-created-at="2026-06-27T12:00:00+08:00">
      闲车 百利原始鸡 335 元
    </a>
  </body>
</html>
"""


def test_pipeline_creates_deal_without_email_when_email_config_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_html)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 1
    assert result.notifications_sent == 0
    assert len(repository.list_deals()) == 1
    assert repository.list_notifications() == []


def test_main_run_executes_pipeline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_html)
    settings = _settings(tmp_path)

    result = run(settings)

    assert result == 0
    with Repository(settings.database_path) as repository:
        assert len(repository.list_posts()) == 1
        assert len(repository.list_deals()) == 1


def _fake_fetch_html(*args, **kwargs) -> str:
    return HTML


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "data" / "cat_deal_radar.sqlite",
        douban_group_url="https://www.douban.com/group/haixiuzu/",
        douban_tab_name="闲车禁拼多多",
    )
