from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import structlog

from app.database import Feedback, FeedbackType, Repository
from app.feedback.links import feedback_type_from_action
from app.recommendation import PreferenceLearningEngine

logger = structlog.get_logger()


@dataclass(frozen=True)
class ExternalFeedback:
    deal_id: int
    action: str
    created_at: datetime


@dataclass(frozen=True)
class FeedbackSyncResult:
    records_seen: int
    feedback_created: int
    preferences_updated: bool


class FeedbackReader(Protocol):
    def list_feedback(self) -> list[ExternalFeedback]:
        pass


def sync_feedback_and_update_preferences(
    *,
    repository: Repository,
    reader: FeedbackReader,
    learning_engine: PreferenceLearningEngine,
) -> FeedbackSyncResult:
    external_feedback = reader.list_feedback()
    existing_keys = _existing_feedback_keys(repository)
    created_feedback: list[Feedback] = []

    for item in external_feedback:
        feedback_type = _feedback_type(item.action)
        if feedback_type is None:
            continue
        created_at = _normalized_datetime(item.created_at)
        key = (item.deal_id, feedback_type, created_at)
        if key in existing_keys:
            continue
        deal = repository.get_deal(item.deal_id)
        if deal is None:
            logger.info("feedback_sync_skipped_missing_deal", deal_id=item.deal_id)
            continue

        feedback = repository.create_feedback(
            Feedback(
                deal_id=item.deal_id,
                feedback_type=feedback_type,
                created_at=created_at,
            )
        )
        existing_keys.add(key)
        created_feedback.append(feedback)
        learning_engine.apply_feedback(deal=deal, feedback=feedback)

    return FeedbackSyncResult(
        records_seen=len(external_feedback),
        feedback_created=len(created_feedback),
        preferences_updated=bool(created_feedback),
    )


def _existing_feedback_keys(repository: Repository) -> set[tuple[int, FeedbackType, datetime]]:
    return {
        (feedback.deal_id, feedback.feedback_type, _normalized_datetime(feedback.created_at))
        for feedback in repository.list_feedback()
    }


def _feedback_type(action: str) -> FeedbackType | None:
    try:
        return feedback_type_from_action(action)
    except ValueError:
        try:
            return FeedbackType(action)
        except ValueError:
            logger.info("feedback_sync_skipped_unknown_action", action=action)
            return None


def _normalized_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
