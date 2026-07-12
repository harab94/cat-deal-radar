from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.database import Deal, Feedback, FeedbackType, Post, Repository
from app.feedback_sync import ExternalFeedback, sync_feedback_and_update_preferences
from app.recommendation import PreferenceLearningEngine

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


def test_sync_feedback_creates_local_feedback_and_updates_preferences(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    deal = _stored_deal(repository)
    assert deal.id is not None
    engine = PreferenceLearningEngine(
        {"preferred_brands": {"百利": 30}, "category_priorities": {"cat_food": 30}}
    )

    result = sync_feedback_and_update_preferences(
        repository=repository,
        reader=_Reader([ExternalFeedback(deal_id=deal.id, action="bought", created_at=NOW)]),
        learning_engine=engine,
    )

    assert result.records_seen == 1
    assert result.feedback_created == 1
    assert result.preferences_updated is True
    assert repository.list_feedback_for_deal(deal.id) == [
        Feedback(
            id=1,
            deal_id=deal.id,
            feedback_type=FeedbackType.BOUGHT_FROM_THIS,
            created_at=NOW,
        )
    ]
    assert engine.preferences["preferred_brands"]["百利"] == 50
    assert engine.preferences["category_priorities"]["cat_food"] == 40


def test_sync_feedback_skips_duplicates(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    deal = _stored_deal(repository)
    assert deal.id is not None
    repository.create_feedback(
        Feedback(
            deal_id=deal.id,
            feedback_type=FeedbackType.MORE_LIKE_THIS,
            created_at=NOW,
        )
    )
    engine = PreferenceLearningEngine(
        {"preferred_brands": {"百利": 30}, "category_priorities": {"cat_food": 30}}
    )

    result = sync_feedback_and_update_preferences(
        repository=repository,
        reader=_Reader([ExternalFeedback(deal_id=deal.id, action="more", created_at=NOW)]),
        learning_engine=engine,
    )

    assert result.records_seen == 1
    assert result.feedback_created == 0
    assert result.preferences_updated is False
    assert engine.preferences["preferred_brands"]["百利"] == 30


def test_sync_feedback_skips_unknown_action_and_missing_deal(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _stored_deal(repository)
    engine = PreferenceLearningEngine(
        {"preferred_brands": {"百利": 30}, "category_priorities": {"cat_food": 30}}
    )

    result = sync_feedback_and_update_preferences(
        repository=repository,
        reader=_Reader(
            [
                ExternalFeedback(deal_id=1, action="wat", created_at=NOW),
                ExternalFeedback(deal_id=999, action="less", created_at=NOW),
            ]
        ),
        learning_engine=engine,
    )

    assert result.records_seen == 2
    assert result.feedback_created == 0
    assert repository.list_feedback() == []


class _Reader:
    def __init__(self, feedback: list[ExternalFeedback]) -> None:
        self._feedback = feedback

    def list_feedback(self) -> list[ExternalFeedback]:
        return self._feedback


def _repository(tmp_path: Path) -> Repository:
    repository = Repository(tmp_path / "cat_deal_radar.sqlite")
    repository.initialize()
    return repository


def _stored_deal(repository: Repository) -> Deal:
    post = repository.create_post(
        Post(
            douban_post_id="123456789",
            title="百利原始鸡 335",
            content="百利原始鸡 335",
            url="https://www.douban.com/group/topic/123456789/",
            created_at=NOW,
            fetched_at=NOW,
        )
    )
    return repository.create_deal(
        Deal(
            post_id=post.id,
            category="cat_food",
            brand="百利",
            product_name="百利原始鸡",
            price=335,
            confidence_score=90,
            cat_score=5,
            is_duplicate=False,
            created_at=NOW,
        )
    )
