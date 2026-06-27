from pathlib import Path

from app.database import Repository
from app.main import run
from app.settings import Settings, load_settings


def test_run_returns_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.crawler.douban.fetch_html", _empty_html)
    monkeypatch.delenv("CAT_DEAL_RADAR_SEND_TEST_EMAIL", raising=False)

    assert run(_settings(tmp_path)) == 0


def test_run_initializes_database(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.crawler.douban.fetch_html", _empty_html)
    monkeypatch.delenv("CAT_DEAL_RADAR_SEND_TEST_EMAIL", raising=False)

    result = run(_settings(tmp_path))

    assert result == 0
    with Repository(_settings(tmp_path).database_path) as repository:
        assert repository.list_posts() == []


def test_load_settings_reads_yaml(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        """
database:
  path: /tmp/cat.sqlite
douban:
  group_url: https://example.com/group
  tab_name: 闲车禁拼多多
""",
        encoding="utf-8",
    )

    settings = load_settings(settings_path)

    assert settings.database_path == Path("/tmp/cat.sqlite")
    assert settings.douban_group_url == "https://example.com/group"
    assert settings.douban_tab_name == "闲车禁拼多多"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "data" / "cat_deal_radar.sqlite",
        douban_group_url="https://example.com/group",
        douban_tab_name="闲车禁拼多多",
    )


def _empty_html(*args, **kwargs) -> str:
    return "<html></html>"
