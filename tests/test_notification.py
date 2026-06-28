from __future__ import annotations

from datetime import UTC, datetime
from email.header import decode_header, make_header
from pathlib import Path

import pytest

from app.database import Deal, Post, Repository
from app.notification import (
    DealDigestItem,
    EmailMessage,
    FeedbackLinks,
    NotificationService,
    render_deal_digest_email,
    render_deal_email,
)
from app.notification.email_sender import build_mime_message
from app.recommendation import RecommendationScore

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
FEEDBACK_LINKS = FeedbackLinks(
    more_like_this="https://example.com/more",
    less_like_this="https://example.com/less",
    bought="https://example.com/bought",
    already_have_stock="https://example.com/stock",
)


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / "cat_deal_radar.sqlite")
    repo.initialize()
    yield repo
    repo.close()


def test_render_deal_email_includes_priority_subject_and_feedback_links() -> None:
    message = render_deal_email(
        deal=_deal(deal_id=1),
        post=_post(post_id=1),
        recommendation=_recommendation(cat_score=5),
        feedback_links=FEEDBACK_LINKS,
    )

    assert message.subject == "🐱🐱🐱🐱🐱【必抢】百利原始鸡 335元"
    assert "preferred brand" in message.text_body
    assert "https://example.com/more" in message.text_body
    assert "打开豆瓣原帖" in message.html_body


def test_render_deal_email_escapes_html() -> None:
    message = render_deal_email(
        deal=_deal(deal_id=1, product_name="<script>bad</script>"),
        post=_post(post_id=1, title="<b>title</b>"),
        recommendation=_recommendation(cat_score=4),
        feedback_links=FEEDBACK_LINKS,
    )

    assert "<script>bad</script>" not in message.html_body
    assert "&lt;script&gt;bad&lt;/script&gt;" in message.html_body
    assert "&lt;b&gt;title&lt;/b&gt;" in message.html_body


def test_render_deal_digest_email_combines_multiple_deals() -> None:
    message = render_deal_digest_email(
        [
            DealDigestItem(
                deal=_deal(deal_id=1, product_name="百利原始鸡"),
                post=_post(post_id=1, title="闲置 百利原始鸡"),
                recommendation=_recommendation(cat_score=5),
                feedback_links=FEEDBACK_LINKS,
            ),
            DealDigestItem(
                deal=_deal(deal_id=2, product_name="小李子罐头"),
                post=_post(post_id=2, title="闲置 小李子罐头"),
                recommendation=_recommendation(cat_score=4),
                feedback_links=FEEDBACK_LINKS,
            ),
        ]
    )

    assert message.subject.startswith("🐱猫车雷达今日发现 2 条")
    assert "今日猫车合集" in message.html_body
    assert "百利原始鸡" in message.html_body
    assert "小李子罐头" in message.html_body


def test_mime_message_encodes_unicode_subject() -> None:
    message = render_deal_email(
        deal=_deal(deal_id=1),
        post=_post(post_id=1),
        recommendation=_recommendation(cat_score=5),
        feedback_links=FEEDBACK_LINKS,
    )

    mime_message = build_mime_message(
        message=message,
        sender="sender@example.com",
        recipient="recipient@example.com",
    )
    decoded_subject = str(make_header(decode_header(mime_message["Subject"])))

    assert decoded_subject == "🐱🐱🐱🐱🐱【必抢】百利原始鸡 335元"
    assert "=?utf-8?" in mime_message.as_string().casefold()


def test_notification_service_sends_email_and_records_notification(
    repository: Repository,
) -> None:
    post = repository.create_post(_post())
    deal = repository.create_deal(_deal(post_id=post.id))
    sender = FakeSender()
    service = NotificationService(repository=repository, sender=sender)

    notification = service.send_deal_notification(
        deal=deal,
        post=post,
        recommendation=_recommendation(cat_score=5),
        feedback_links=FEEDBACK_LINKS,
    )

    assert len(sender.sent_messages) == 1
    assert notification.email_sent is True
    assert notification.sent_at is not None
    assert repository.get_notification(notification.id) == notification


def test_notification_service_sends_one_digest_and_records_each_notification(
    repository: Repository,
) -> None:
    post_a = repository.create_post(_post("douban-a"))
    post_b = repository.create_post(_post("douban-b", title="小李子罐头"))
    deal_a = repository.create_deal(_deal(post_id=post_a.id, product_name="百利原始鸡"))
    deal_b = repository.create_deal(_deal(post_id=post_b.id, product_name="小李子罐头"))
    sender = FakeSender()
    service = NotificationService(repository=repository, sender=sender)

    notifications = service.send_deal_digest(
        items=[
            DealDigestItem(deal_a, post_a, _recommendation(cat_score=5), FEEDBACK_LINKS),
            DealDigestItem(deal_b, post_b, _recommendation(cat_score=4), FEEDBACK_LINKS),
        ]
    )

    assert len(sender.sent_messages) == 1
    assert len(notifications) == 2
    assert len(repository.list_notifications()) == 2


def test_notification_service_requires_persisted_deal(repository: Repository) -> None:
    service = NotificationService(repository=repository, sender=FakeSender())

    with pytest.raises(ValueError, match="without an id"):
        service.send_deal_notification(
            deal=_deal(deal_id=None),
            post=_post(post_id=1),
            recommendation=_recommendation(cat_score=5),
            feedback_links=FEEDBACK_LINKS,
        )


class FakeSender:
    def __init__(self) -> None:
        self.sent_messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent_messages.append(message)


def _post(
    douban_post_id: str = "123456789",
    *,
    post_id: int | None = None,
    title: str = "百利原始鸡 335",
) -> Post:
    return Post(
        id=post_id,
        douban_post_id=douban_post_id,
        title=title,
        content=title,
        url="https://www.douban.com/group/topic/123456789/",
        created_at=NOW,
        fetched_at=NOW,
    )


def _deal(
    *,
    deal_id: int | None = None,
    post_id: int | None = 1,
    product_name: str = "百利原始鸡",
) -> Deal:
    assert post_id is not None
    return Deal(
        id=deal_id,
        post_id=post_id,
        category="cat_food",
        brand="百利",
        product_name=product_name,
        price=335,
        confidence_score=90,
        cat_score=5,
        is_duplicate=False,
        created_at=NOW,
    )


def _recommendation(cat_score: int) -> RecommendationScore:
    return RecommendationScore(
        confidence_score=90,
        cat_score=cat_score,
        should_notify=True,
        reasons=("preferred brand", "26% below average price"),
    )
