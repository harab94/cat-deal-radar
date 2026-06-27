"""Recommendation scoring and duplicate handling."""

from app.recommendation.duplicate_handler import DuplicateDecision, DuplicateHandler
from app.recommendation.preference_learning import PreferenceLearningEngine
from app.recommendation.scoring import (
    RecommendationInput,
    RecommendationScore,
    RecommendationScorer,
)

__all__ = [
    "DuplicateDecision",
    "DuplicateHandler",
    "PreferenceLearningEngine",
    "RecommendationInput",
    "RecommendationScore",
    "RecommendationScorer",
]
