from app.deal_detector import (
    RuleBasedDealDetector,
    analyze_comments,
    parse_llm_classification,
)
from app.deal_detector.keyword_rules import extract_lowest_price


def test_rule_detector_identifies_supported_cat_food_deal() -> None:
    detector = _detector()

    detected = detector.detect(title="闲车：百利原始鸡 335 元，还能买")

    assert detected.is_deal is True
    assert detected.category == "cat_food"
    assert detected.brand == "百利"
    assert detected.price == 335
    assert detected.confidence >= 90


def test_rule_detector_rejects_known_brand_without_deal_signal() -> None:
    detector = _detector()

    detected = detector.detect(title="百利原始鸡日常讨论")

    assert detected.is_deal is False
    assert detected.brand == "百利"
    assert detected.category == "cat_food"
    assert detected.price is None


def test_rule_detector_uses_category_keywords_for_cat_litter() -> None:
    detector = _detector()

    detected = detector.detect(title="闲车 铁锤猫砂 89 元")

    assert detected.is_deal is True
    assert detected.category == "cat_litter"
    assert detected.brand == "Arm & Hammer"
    assert detected.price == 89


def test_rule_detector_treats_kaiche_as_expired_in_douban_group() -> None:
    detector = _detector()

    detected = detector.detect(title="开车 百利原始鸡 335 元")

    assert detected.is_deal is False
    assert detected.brand == "百利"
    assert "expired deal signal" in detected.reasons


def test_extract_lowest_price_ignores_large_non_price_numbers() -> None:
    assert extract_lowest_price("2026 年 百利 335 元，凑单后 329") == 329


def test_analyze_comments_scores_availability_signals() -> None:
    analysis = analyze_comments(["还能买，我已上车", "没了，好像无货"])

    assert analysis.positive_count == 1
    assert analysis.negative_count == 1
    assert analysis.confidence_adjustment == -5
    assert analysis.has_conflict is True


def test_parse_llm_classification_accepts_json_fence() -> None:
    parsed = parse_llm_classification(
        """
        ```json
        {
          "is_deal": true,
          "category": "cat_food",
          "brand": "百利",
          "product_name": "百利原始鸡",
          "price": 335,
          "confidence": 92
        }
        ```
        """
    )

    assert parsed.is_deal is True
    assert parsed.category == "cat_food"
    assert parsed.brand == "百利"
    assert parsed.product_name == "百利原始鸡"
    assert parsed.price == 335
    assert parsed.confidence == 92


def test_parse_llm_classification_clamps_confidence() -> None:
    parsed = parse_llm_classification('{"is_deal": false, "confidence": 140}')

    assert parsed.is_deal is False
    assert parsed.confidence == 100


def _detector() -> RuleBasedDealDetector:
    return RuleBasedDealDetector.from_config_files(
        brands_path="config/brands.yaml",
        categories_path="config/categories.yaml",
    )
