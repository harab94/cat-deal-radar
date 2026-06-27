from datetime import UTC, datetime, timedelta

from app.database import Deal
from app.deal_detector import CommentAnalysis
from app.recommendation import DuplicateHandler, RecommendationInput, RecommendationScorer

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


def test_recommendation_scores_preferred_discounted_food_as_five_cats() -> None:
    score = _scorer().score(
        RecommendationInput(
            category="cat_food",
            brand="百利",
            price=335,
            base_confidence=85,
            historical_average_price=450,
            comment_analysis=CommentAnalysis(
                positive_count=1,
                negative_count=0,
                confidence_adjustment=5,
                has_conflict=False,
            ),
        )
    )

    assert score.cat_score == 5
    assert score.should_notify is True
    assert score.confidence_score == 90
    assert "preferred brand" in score.reasons
    assert "26% below average price" in score.reasons


def test_recommendation_below_three_cats_does_not_notify() -> None:
    score = _scorer().score(
        RecommendationInput(
            category="cat_litter",
            brand="Unknown",
            price=120,
            base_confidence=70,
        )
    )

    assert score.cat_score == 2
    assert score.should_notify is False


def test_negative_comments_lower_confidence_but_do_not_hide_score() -> None:
    score = _scorer().score(
        RecommendationInput(
            category="cat_food",
            brand="百利",
            price=335,
            base_confidence=90,
            comment_analysis=CommentAnalysis(
                positive_count=1,
                negative_count=1,
                confidence_adjustment=-5,
                has_conflict=True,
            ),
        )
    )

    assert score.confidence_score == 85
    assert score.cat_score >= 3
    assert score.should_notify is True


def test_duplicate_handler_allows_first_matching_deal() -> None:
    candidate = _deal(price=335)

    decision = DuplicateHandler().evaluate(candidate, [])

    assert decision.is_duplicate is False
    assert decision.should_notify is True


def test_duplicate_handler_suppresses_higher_price_duplicate_inside_window() -> None:
    existing = _deal(deal_id=1, price=335)
    candidate = _deal(price=350)

    decision = DuplicateHandler().evaluate(candidate, [existing])

    assert decision.is_duplicate is True
    assert decision.should_notify is False


def test_duplicate_handler_notifies_lower_price_duplicate_inside_window() -> None:
    existing = _deal(deal_id=1, price=335)
    candidate = _deal(price=329)

    decision = DuplicateHandler().evaluate(candidate, [existing])

    assert decision.is_duplicate is False
    assert decision.should_notify is True
    assert decision.superseded_deal_id == 1


def test_duplicate_handler_ignores_matches_outside_window() -> None:
    existing = _deal(deal_id=1, price=335, created_at=NOW - timedelta(hours=25))
    candidate = _deal(price=350)

    decision = DuplicateHandler().evaluate(candidate, [existing])

    assert decision.is_duplicate is False
    assert decision.should_notify is True


def _scorer() -> RecommendationScorer:
    return RecommendationScorer.from_yaml("config/preferences.yaml")


def _deal(
    *,
    deal_id: int | None = None,
    price: float,
    created_at: datetime = NOW,
) -> Deal:
    return Deal(
        id=deal_id,
        post_id=1,
        category="cat_food",
        brand="百利",
        product_name="百利原始鸡",
        price=price,
        confidence_score=90,
        cat_score=5,
        is_duplicate=False,
        created_at=created_at,
    )
