from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.deal_detector import CommentAnalysis


@dataclass(frozen=True)
class RecommendationInput:
    category: str
    brand: str
    price: float
    base_confidence: int
    comment_analysis: CommentAnalysis | None = None
    historical_average_price: float | None = None
    purchase_count: int = 0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0


@dataclass(frozen=True)
class RecommendationScore:
    confidence_score: int
    cat_score: int
    should_notify: bool
    reasons: tuple[str, ...]


class RecommendationScorer:
    def __init__(self, preferences: dict[str, Any]) -> None:
        self._preferences = preferences

    @classmethod
    def from_yaml(cls, path: str | Path) -> RecommendationScorer:
        with Path(path).open(encoding="utf-8") as file:
            return cls(yaml.safe_load(file) or {})

    def score(self, recommendation: RecommendationInput) -> RecommendationScore:
        reasons: list[str] = []
        confidence = recommendation.base_confidence
        if recommendation.comment_analysis is not None:
            confidence += recommendation.comment_analysis.confidence_adjustment
            if recommendation.comment_analysis.positive_count:
                reasons.append("community confirms availability")
            if recommendation.comment_analysis.negative_count:
                reasons.append("community reports risk")

        points = 0
        category_points = self._category_points(recommendation.category)
        brand_points = self._brand_points(recommendation.brand)
        points += category_points + brand_points

        if category_points:
            reasons.append("high priority category")
        if brand_points:
            reasons.append("preferred brand")
        if recommendation.base_confidence >= 80:
            points += 10
            reasons.append("strong title match")

        discount = _discount_percent(recommendation.price, recommendation.historical_average_price)
        if discount is not None:
            discount_points = _discount_points(discount)
            points += discount_points
            if discount >= 20:
                reasons.append(f"{discount:.0f}% below average price")

        points += min(recommendation.purchase_count * 5, 15)
        points += min(recommendation.positive_feedback_count * 5, 15)
        points -= min(recommendation.negative_feedback_count * 10, 30)

        cat_score = _cat_score(points)
        return RecommendationScore(
            confidence_score=_clamp(confidence, 0, 100),
            cat_score=cat_score,
            should_notify=cat_score >= 3,
            reasons=tuple(reasons),
        )

    def _category_points(self, category: str) -> int:
        priorities = self._preferences.get("category_priorities", {})
        return int(priorities.get(category, 0))

    def _brand_points(self, brand: str) -> int:
        preferred_brands = self._preferences.get("preferred_brands", {})
        return int(preferred_brands.get(brand, 0))


def _discount_percent(price: float, historical_average_price: float | None) -> float | None:
    if price <= 0 or historical_average_price is None or historical_average_price <= 0:
        return None
    return max(0.0, (historical_average_price - price) / historical_average_price * 100)


def _discount_points(discount_percent: float) -> int:
    if discount_percent >= 30:
        return 30
    if discount_percent >= 20:
        return 20
    if discount_percent >= 10:
        return 10
    return 0


def _cat_score(points: int) -> int:
    if points >= 70:
        return 5
    if points >= 50:
        return 4
    if points >= 30:
        return 3
    if points >= 15:
        return 2
    return 1


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
