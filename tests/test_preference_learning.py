from __future__ import annotations

from datetime import UTC, datetime

import yaml

from app.database import Deal, Feedback, FeedbackType
from app.recommendation import PreferenceLearningEngine

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


def test_more_like_this_increases_brand_and_category_weights() -> None:
    engine = PreferenceLearningEngine(_preferences())

    updated = engine.apply_feedback(
        deal=_deal(),
        feedback=_feedback(FeedbackType.MORE_LIKE_THIS),
    )

    assert updated["preferred_brands"]["百利"] == 40
    assert updated["category_priorities"]["cat_food"] == 35


def test_less_like_this_decreases_brand_and_category_weights() -> None:
    engine = PreferenceLearningEngine(_preferences())

    updated = engine.apply_feedback(
        deal=_deal(),
        feedback=_feedback(FeedbackType.LESS_LIKE_THIS),
    )

    assert updated["preferred_brands"]["百利"] == 20
    assert updated["category_priorities"]["cat_food"] == 25


def test_bought_feedback_is_strong_positive_signal() -> None:
    engine = PreferenceLearningEngine(_preferences())

    updated = engine.apply_feedback(
        deal=_deal(),
        feedback=_feedback(FeedbackType.BOUGHT_FROM_THIS),
    )

    assert updated["preferred_brands"]["百利"] == 50
    assert updated["category_priorities"]["cat_food"] == 40


def test_already_have_stock_does_not_change_preferences() -> None:
    engine = PreferenceLearningEngine(_preferences())

    updated = engine.apply_feedback(
        deal=_deal(),
        feedback=_feedback(FeedbackType.ALREADY_HAVE_STOCK),
    )

    assert updated == _preferences()


def test_learning_clamps_weights_between_zero_and_one_hundred() -> None:
    engine = PreferenceLearningEngine(
        {
            "preferred_brands": {"百利": 95, "金素": 5},
            "category_priorities": {"cat_food": 95, "wet_food": 5},
        }
    )

    bought = engine.apply_feedback(deal=_deal(), feedback=_feedback(FeedbackType.BOUGHT_FROM_THIS))
    negative = engine.apply_feedback(
        deal=_deal(brand="金素", category="wet_food"),
        feedback=_feedback(FeedbackType.LESS_LIKE_THIS),
    )

    assert bought["preferred_brands"]["百利"] == 100
    assert bought["category_priorities"]["cat_food"] == 100
    assert negative["preferred_brands"]["金素"] == 0
    assert negative["category_priorities"]["wet_food"] == 0


def test_learning_can_save_preferences_to_yaml(tmp_path) -> None:
    path = tmp_path / "preferences.yaml"
    engine = PreferenceLearningEngine(_preferences())

    engine.apply_feedback(deal=_deal(), feedback=_feedback(FeedbackType.MORE_LIKE_THIS))
    engine.save(path)

    with path.open(encoding="utf-8") as file:
        saved = yaml.safe_load(file)

    assert saved["preferred_brands"]["百利"] == 40
    assert saved["category_priorities"]["cat_food"] == 35


def test_feedback_must_belong_to_deal_when_deal_id_is_known() -> None:
    engine = PreferenceLearningEngine(_preferences())

    try:
        engine.apply_feedback(
            deal=_deal(deal_id=1),
            feedback=_feedback(FeedbackType.MORE_LIKE_THIS, deal_id=2),
        )
    except ValueError as error:
        assert "does not belong" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def _preferences() -> dict[str, dict[str, int]]:
    return {
        "preferred_brands": {"百利": 30},
        "category_priorities": {"cat_food": 30},
    }


def _deal(
    *,
    deal_id: int | None = 1,
    brand: str = "百利",
    category: str = "cat_food",
) -> Deal:
    return Deal(
        id=deal_id,
        post_id=1,
        category=category,
        brand=brand,
        product_name="百利原始鸡",
        price=335,
        confidence_score=90,
        cat_score=5,
        is_duplicate=False,
        created_at=NOW,
    )


def _feedback(feedback_type: FeedbackType, *, deal_id: int = 1) -> Feedback:
    return Feedback(deal_id=deal_id, feedback_type=feedback_type, created_at=NOW)
