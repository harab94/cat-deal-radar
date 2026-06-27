from __future__ import annotations

from datetime import UTC, datetime

from app.database import Feedback, Repository
from app.feedback.links import feedback_type_from_action


class FeedbackHandler:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def handle(self, *, deal_id: int, action: str) -> Feedback:
        feedback_type = feedback_type_from_action(action)
        return self._repository.create_feedback(
            Feedback(
                deal_id=deal_id,
                feedback_type=feedback_type,
                created_at=datetime.now(UTC),
            )
        )
