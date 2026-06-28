from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.database import (
    Deal,
    Feedback,
    FeedbackType,
    Notification,
    Post,
    RadarRun,
    Repository,
)

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / "cat_deal_radar.sqlite")
    repo.initialize()
    yield repo
    repo.close()


def test_post_crud(repository: Repository) -> None:
    post = repository.create_post(_post("douban-1"))

    assert post.id is not None
    assert repository.get_post(post.id) == post
    assert repository.get_post_by_douban_id("douban-1") == post

    updated = replace(post, title="百利原始鸡好价")
    repository.update_post(updated)

    assert repository.get_post(post.id) == updated

    repository.delete_post(post.id)

    assert repository.get_post(post.id) is None


def test_duplicate_douban_post_id_is_rejected(repository: Repository) -> None:
    repository.create_post(_post("douban-1"))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        repository.create_post(_post("douban-1"))


def test_create_post_if_new_skips_existing_post(repository: Repository) -> None:
    post = repository.create_post_if_new(_post("douban-1"))
    duplicate = repository.create_post_if_new(_post("douban-1"))

    assert post is not None
    assert duplicate is None
    assert repository.list_posts() == [post]


def test_deal_crud(repository: Repository) -> None:
    post = repository.create_post(_post("douban-1"))
    deal = repository.create_deal(_deal(post.id))

    assert deal.id is not None
    assert repository.get_deal(deal.id) == deal
    assert repository.list_deals() == [deal]

    updated = replace(deal, price=329.0, is_duplicate=True)
    repository.update_deal(updated)

    assert repository.get_deal(deal.id) == updated

    repository.delete_deal(deal.id)

    assert repository.get_deal(deal.id) is None


def test_notification_crud(repository: Repository) -> None:
    post = repository.create_post(_post("douban-1"))
    deal = repository.create_deal(_deal(post.id))
    notification = repository.create_notification(Notification(deal.id, email_sent=False))

    assert notification.id is not None
    assert repository.get_notification(notification.id) == notification

    updated = replace(notification, email_sent=True, sent_at=NOW)
    repository.update_notification(updated)

    assert repository.get_notification(notification.id) == updated

    repository.delete_notification(notification.id)

    assert repository.get_notification(notification.id) is None


def test_radar_run_records_are_listed_by_finished_at(repository: Repository) -> None:
    older = repository.create_radar_run(
        RadarRun(
            started_at=NOW - timedelta(hours=2),
            finished_at=NOW - timedelta(hours=2),
            posts_seen=1,
            deals_created=0,
            notifications_sent=0,
        )
    )
    newer = repository.create_radar_run(
        RadarRun(
            started_at=NOW,
            finished_at=NOW,
            posts_seen=3,
            deals_created=2,
            notifications_sent=1,
        )
    )

    assert repository.latest_radar_run() == newer
    assert repository.list_radar_runs_since(NOW - timedelta(hours=1)) == [newer]
    assert repository.list_radar_runs_since(NOW - timedelta(hours=3)) == [newer, older]


def test_feedback_crud(repository: Repository) -> None:
    post = repository.create_post(_post("douban-1"))
    deal = repository.create_deal(_deal(post.id))
    feedback = repository.create_feedback(
        Feedback(
            deal_id=deal.id,
            feedback_type=FeedbackType.MORE_LIKE_THIS,
            created_at=NOW,
        )
    )

    assert feedback.id is not None
    assert repository.get_feedback(feedback.id) == feedback
    assert repository.list_feedback_for_deal(deal.id) == [feedback]

    updated = replace(feedback, feedback_type=FeedbackType.BOUGHT_FROM_THIS)
    repository.update_feedback(updated)

    assert repository.get_feedback(feedback.id) == updated

    repository.delete_feedback(feedback.id)

    assert repository.get_feedback(feedback.id) is None


def test_deleting_post_cascades_related_records(repository: Repository) -> None:
    post = repository.create_post(_post("douban-1"))
    deal = repository.create_deal(_deal(post.id))
    notification = repository.create_notification(
        Notification(deal.id, email_sent=True, sent_at=NOW)
    )
    feedback = repository.create_feedback(
        Feedback(deal.id, FeedbackType.ALREADY_HAVE_STOCK, created_at=NOW)
    )

    repository.delete_post(post.id)

    assert repository.get_deal(deal.id) is None
    assert repository.get_notification(notification.id) is None
    assert repository.get_feedback(feedback.id) is None


def _post(douban_post_id: str) -> Post:
    return Post(
        douban_post_id=douban_post_id,
        title="百利原始鸡 335",
        content="闲车，百利原始鸡，335 元",
        url=f"https://www.douban.com/group/topic/{douban_post_id}/",
        created_at=NOW,
        fetched_at=NOW,
    )


def _deal(post_id: int | None) -> Deal:
    assert post_id is not None
    return Deal(
        post_id=post_id,
        category="cat_food",
        brand="百利",
        product_name="百利原始鸡",
        price=335.0,
        confidence_score=92,
        cat_score=5,
        is_duplicate=False,
        created_at=NOW,
    )
