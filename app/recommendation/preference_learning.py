from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.database import Deal, Feedback, FeedbackType

BRAND_ADJUSTMENTS = {
    FeedbackType.MORE_LIKE_THIS: 10,
    FeedbackType.LESS_LIKE_THIS: -10,
    FeedbackType.BOUGHT_FROM_THIS: 20,
    FeedbackType.ALREADY_HAVE_STOCK: 0,
}

CATEGORY_ADJUSTMENTS = {
    FeedbackType.MORE_LIKE_THIS: 5,
    FeedbackType.LESS_LIKE_THIS: -5,
    FeedbackType.BOUGHT_FROM_THIS: 10,
    FeedbackType.ALREADY_HAVE_STOCK: 0,
}


class PreferenceLearningEngine:
    def __init__(self, preferences: dict[str, Any]) -> None:
        self._preferences = deepcopy(preferences)

    @classmethod
    def from_yaml(cls, path: str | Path) -> PreferenceLearningEngine:
        with Path(path).open(encoding="utf-8") as file:
            return cls(yaml.safe_load(file) or {})

    @property
    def preferences(self) -> dict[str, Any]:
        return deepcopy(self._preferences)

    def apply_feedback(self, *, deal: Deal, feedback: Feedback) -> dict[str, Any]:
        if deal.id is not None and feedback.deal_id != deal.id:
            msg = "Feedback does not belong to the provided deal."
            raise ValueError(msg)

        brand_adjustment = BRAND_ADJUSTMENTS[feedback.feedback_type]
        category_adjustment = CATEGORY_ADJUSTMENTS[feedback.feedback_type]

        self._adjust("preferred_brands", deal.brand, brand_adjustment)
        self._adjust("category_priorities", deal.category, category_adjustment)
        return self.preferences

    def save(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8") as file:
            yaml.safe_dump(self._preferences, file, allow_unicode=True, sort_keys=False)

    def _adjust(self, section: str, key: str, delta: int) -> None:
        values = self._preferences.setdefault(section, {})
        current_value = int(values.get(key, 0))
        values[key] = _clamp(current_value + delta, minimum=0, maximum=100)


def _clamp(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
