from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.database import Deal, Notification, Post, Repository
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

MULTI_DEAL_HTML = """
<html>
  <body>
    <a href="/group/topic/123456789/" data-created-at="2026-06-27T12:00:00+08:00">
      闲车 百利原始鸡 250 元
    </a>
    <a href="/group/topic/223456789/" data-created-at="2026-06-27T12:03:00+08:00">
      闲置 k9罐头鸡肉羊心*2
    </a>
  </body>
</html>
"""

PRICELESS_HTML = """
<html>
  <body>
    <a href="/group/topic/223456789/" data-created-at="2026-06-27T12:00:00+08:00">
      闲置 ve猪肉粒
    </a>
  </body>
</html>
"""

UNKNOWN_BRAND_HTML = """
<html>
  <body>
    <a href="/group/topic/323456789/" data-created-at="2026-06-27T12:00:00+08:00">
      【闲置】德金猫粮野猪45/斤，2斤包邮
    </a>
  </body>
</html>
"""

REFERENCE_PRICE_HTML = """
<html>
  <body>
    <a href="/group/topic/123456789/" data-created-at="2026-06-27T12:00:00+08:00">
      闲车 百利原始鸡 335 元
    </a>
  </body>
</html>
"""

DISCOUNTED_HTML = """
<html>
  <body>
    <a href="/group/topic/123456789/" data-created-at="2026-06-27T12:00:00+08:00">
      闲车 百利原始鸡 250 元
    </a>
  </body>
</html>
"""

TOPIC_DETAIL_HTML = """
<html>
  <body>
    <div class="topic-content">
      闲车 百利原始鸡 250 元，还有货。
    </div>
    <div class="reply-content">还能买。</div>
  </body>
</html>
"""

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


def test_pipeline_creates_deal_without_email_when_email_config_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_discounted_html)
    _clear_notification_env(monkeypatch)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 1
    assert result.notifications_sent == 0
    assert len(repository.list_deals()) == 1
    assert repository.list_notifications() == []


def test_pipeline_creates_deal_when_title_price_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "app.crawler.douban.fetch_html",
        lambda *args, **kwargs: PRICELESS_HTML,
    )
    _clear_notification_env(monkeypatch)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 1
    assert result.notifications_sent == 0
    deal = repository.list_deals()[0]
    assert deal.product_name == "闲置 ve猪肉粒"
    assert deal.price == 0


def test_pipeline_sends_one_email_for_multiple_deals(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setattr("app.crawler.douban.fetch_html", lambda *args, **kwargs: MULTI_DEAL_HTML)
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_send)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 2
    assert result.deals_created == 2
    assert result.notifications_sent == 2
    assert len(sent_subjects) == 1
    assert sent_subjects[0].startswith("🐱猫车雷达今日发现 2 条")
    assert len(repository.list_notifications()) == 2


def test_pipeline_can_send_feishu_notification_without_email(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_discounted_html)
    _clear_email_env(monkeypatch)
    _clear_wework_env(monkeypatch)
    monkeypatch.setenv("FEISHU_BOT_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/test")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.feishu_sender.FeishuWebhookSender.send", fake_send)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 1
    assert result.notifications_sent == 1
    assert sent_subjects == ["🐱🐱🐱🐱🐱【必抢】闲车 百利原始鸡 250 元 250元"]
    assert len(repository.list_notifications()) == 1


def test_pipeline_sends_email_and_feishu_when_both_are_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    email_subjects: list[str] = []
    feishu_subjects: list[str] = []

    def fake_email_send(self, message) -> None:
        email_subjects.append(message.subject)

    def fake_feishu_send(self, message) -> None:
        feishu_subjects.append(message.subject)

    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_discounted_html)
    _clear_wework_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEISHU_BOT_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/test")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_email_send)
    monkeypatch.setattr("app.notification.feishu_sender.FeishuWebhookSender.send", fake_feishu_send)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 1
    assert result.notifications_sent == 1
    assert email_subjects == ["🐱🐱🐱🐱🐱【必抢】闲车 百利原始鸡 250 元 250元"]
    assert feishu_subjects == email_subjects


def test_pipeline_does_not_notify_when_price_matches_reference(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setattr(
        "app.crawler.douban.fetch_html",
        lambda *args, **kwargs: REFERENCE_PRICE_HTML,
    )
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_send)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 0
    assert result.notifications_sent == 0
    assert sent_subjects == []
    assert repository.list_notifications() == []


def test_pipeline_reports_unknown_brand_candidate_once(
    monkeypatch,
    tmp_path: Path,
) -> None:
    reporter = _Reporter()
    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_unknown_brand_html)
    monkeypatch.setattr(
        "app.pipeline._brand_candidate_reporter_from_env",
        lambda settings: reporter,
    )
    _clear_notification_env(monkeypatch)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    first = run_pipeline(settings, repository)
    second = run_pipeline(settings, repository)

    assert first.posts_seen == 1
    assert second.posts_seen == 1
    assert first.deals_created == 0
    assert second.deals_created == 0
    assert [candidate.candidate_brand for candidate in reporter.candidates] == ["德金"]


def test_pipeline_keeps_run_successful_when_notification_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fail_send(self, message) -> None:
        raise RuntimeError("WeWork IP rejected")

    monkeypatch.setattr("app.crawler.douban.fetch_html", lambda *args, **kwargs: MULTI_DEAL_HTML)
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fail_send)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 2
    assert result.deals_created == 2
    assert result.notifications_sent == 0
    notifications = repository.list_notifications()
    assert len(notifications) == 2
    assert all(notification.email_sent is False for notification in notifications)


def test_main_run_executes_pipeline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_discounted_html)
    _clear_notification_env(monkeypatch)
    settings = _settings(tmp_path)

    result = run(settings)

    assert result == 0
    with Repository(settings.database_path) as repository:
        assert len(repository.list_posts()) == 1
        assert len(repository.list_deals()) == 1


def test_pipeline_handles_douban_fetch_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fail_fetch(*args, **kwargs) -> str:
        raise RuntimeError("Failed to fetch Douban page")

    monkeypatch.setattr("app.crawler.douban.fetch_html", fail_fetch)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 0
    assert result.deals_created == 0
    assert result.notifications_sent == 0


def test_pipeline_can_send_fake_deal_email(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setenv("CAT_DEAL_RADAR_SEND_TEST_EMAIL", "true")
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_send)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 0
    assert result.deals_created == 1
    assert result.notifications_sent == 1
    assert sent_subjects == ["🐱🐱🐱🐱🐱【必抢】测试邮件：百利原始鸡 335元"]
    assert len(repository.list_notifications()) == 1


def test_pipeline_does_not_send_notification_with_placeholder_feedback_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_discounted_html)
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://feedback.example.com")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_send)
    settings = _settings(tmp_path)
    repository = Repository(settings.database_path)

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 1
    assert result.notifications_sent == 0
    assert sent_subjects == []


def test_pipeline_does_not_notify_same_post_twice_even_if_deal_name_changes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_html)
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_send)
    settings = _settings(tmp_path)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    repository = Repository(settings.database_path)
    repository.initialize()
    post = repository.create_post(
        _post_for_existing_notification("123456789", title="旧标题 百利鸡")
    )
    deal = repository.create_deal(
        _deal_for_existing_notification(post_id=post.id, product_name="旧识别 百利鸡")
    )
    repository.create_notification(_notification_for_existing_notification(deal_id=deal.id))

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 0
    assert result.notifications_sent == 0
    assert sent_subjects == []


def test_pipeline_does_not_notify_same_product_same_price_twice_without_notification_record(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_discounted_html)
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_send)
    settings = _settings(tmp_path)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    repository = Repository(settings.database_path)
    repository.initialize()
    post = repository.create_post(
        _post_for_existing_notification("existing-post", title="旧标题 百利鸡")
    )
    repository.create_deal(
        _deal_for_existing_notification(
            post_id=post.id,
            product_name="闲车 百利原始鸡 250 元",
            price=250,
        )
    )

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 0
    assert result.notifications_sent == 0
    assert sent_subjects == []


def test_pipeline_does_not_notify_same_title_with_new_post_id(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sent_subjects: list[str] = []

    def fake_send(self, message) -> None:
        sent_subjects.append(message.subject)

    monkeypatch.setattr("app.crawler.douban.fetch_html", _fake_fetch_discounted_html)
    _clear_wework_env(monkeypatch)
    _clear_feishu_bot_env(monkeypatch)
    monkeypatch.setenv("GMAIL_USERNAME", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("DEAL_NOTIFICATION_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("FEEDBACK_BASE_URL", "https://cat-deal-radar.hairihanb.workers.dev")
    monkeypatch.setattr("app.notification.email_sender.SmtpEmailSender.send", fake_send)
    settings = _settings(tmp_path)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    repository = Repository(settings.database_path)
    repository.initialize()
    post = repository.create_post(
        _post_for_existing_notification("old-post-id", title="闲车 百利原始鸡 250 元")
    )
    deal = repository.create_deal(
        _deal_for_existing_notification(
            post_id=post.id,
            product_name="闲车 百利原始鸡 250 元",
            price=250,
        )
    )
    repository.create_notification(_notification_for_existing_notification(deal_id=deal.id))

    result = run_pipeline(settings, repository)

    assert result.posts_seen == 1
    assert result.deals_created == 0
    assert result.notifications_sent == 0
    assert sent_subjects == []


def _fake_fetch_html(*args, **kwargs) -> str:
    url = str(args[0]) if args else ""
    if "/group/topic/" in url:
        return TOPIC_DETAIL_HTML
    return HTML


def _fake_fetch_discounted_html(*args, **kwargs) -> str:
    url = str(args[0]) if args else ""
    if "/group/topic/" in url:
        return TOPIC_DETAIL_HTML
    return DISCOUNTED_HTML


def _fake_fetch_unknown_brand_html(*args, **kwargs) -> str:
    url = str(args[0]) if args else ""
    if "/group/topic/" in url:
        return "【闲置】德金猫粮野猪45/斤，2斤包邮"
    return UNKNOWN_BRAND_HTML


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "data" / "cat_deal_radar.sqlite",
        douban_group_url="https://www.douban.com/group/haixiuzu/",
        douban_tab_name="闲车禁拼多多",
    )


def _post_for_existing_notification(douban_post_id: str, *, title: str) -> Post:
    return Post(
        douban_post_id=douban_post_id,
        title=title,
        content=title,
        url=f"https://www.douban.com/group/topic/{douban_post_id}/",
        created_at=NOW,
        fetched_at=NOW,
    )


def _deal_for_existing_notification(
    *,
    post_id: int | None,
    product_name: str,
    price: float = 335,
) -> Deal:
    assert post_id is not None
    return Deal(
        post_id=post_id,
        category="cat_food",
        brand="百利",
        product_name=product_name,
        price=price,
        confidence_score=90,
        cat_score=5,
        is_duplicate=False,
        created_at=NOW,
    )


def _notification_for_existing_notification(*, deal_id: int | None) -> Notification:
    assert deal_id is not None
    return Notification(deal_id=deal_id, email_sent=True, sent_at=NOW)


def _clear_notification_env(monkeypatch) -> None:
    for name in (
        "GMAIL_USERNAME",
        "GMAIL_APP_PASSWORD",
        "GMAIL_SENDER",
        "DEAL_NOTIFICATION_RECIPIENT",
        "FEEDBACK_BASE_URL",
        "CAT_DEAL_RADAR_SEND_TEST_EMAIL",
        "FEISHU_BOT_WEBHOOK",
        "FEISHU_BOT_SECRET",
        "FEISHU_BRAND_CANDIDATES_TABLE_ID",
        "WEWORK_CORP_ID",
        "WEWORK_AGENT_ID",
        "WEWORK_APP_SECRET",
        "WEWORK_TO_USER",
    ):
        monkeypatch.delenv(name, raising=False)


def _clear_email_env(monkeypatch) -> None:
    for name in (
        "GMAIL_USERNAME",
        "GMAIL_APP_PASSWORD",
        "GMAIL_SENDER",
        "DEAL_NOTIFICATION_RECIPIENT",
    ):
        monkeypatch.delenv(name, raising=False)


def _clear_wework_env(monkeypatch) -> None:
    for name in (
        "WEWORK_CORP_ID",
        "WEWORK_AGENT_ID",
        "WEWORK_APP_SECRET",
        "WEWORK_TO_USER",
    ):
        monkeypatch.delenv(name, raising=False)


def _clear_feishu_bot_env(monkeypatch) -> None:
    for name in (
        "FEISHU_BOT_WEBHOOK",
        "FEISHU_BOT_SECRET",
        "FEISHU_BRAND_CANDIDATES_TABLE_ID",
    ):
        monkeypatch.delenv(name, raising=False)


class _Reporter:
    def __init__(self) -> None:
        self.candidates = []

    def report(self, candidate) -> None:
        self.candidates.append(candidate)
