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


def test_rule_detector_uses_builtin_category_keywords_without_known_brand() -> None:
    detector = _detector()

    detected = detector.detect(title="【闲置】德金猫粮野猪45/斤，2斤包邮")

    assert detected.is_deal is True
    assert detected.brand is None
    assert detected.category == "cat_food"


def test_rule_detector_treats_kaiche_as_expired_in_douban_group() -> None:
    detector = _detector()

    detected = detector.detect(title="开车 自然光环全能系列10磅 263r")

    assert detected.is_deal is False
    assert detected.brand == "Halo"
    assert detected.category == "cat_food"
    assert detected.price == 263
    assert "expired deal signal" in detected.reasons


def test_rule_detector_treats_haoche_as_deal_signal() -> None:
    detector = _detector()

    detected = detector.detect(title="金素豪车350两袋")

    assert detected.is_deal is True
    assert detected.brand == "金素"
    assert detected.category == "cat_food"
    assert detected.price is None
    assert "deal signal keyword" in detected.reasons


def test_rule_detector_recognizes_daipai_with_category_keyword_without_known_brand() -> None:
    detector = _detector()

    detected = detector.detect(title="【代拍】美士罐头 6盒41")

    assert detected.is_deal is True
    assert detected.brand is None
    assert detected.category == "wet_food"
    assert "deal signal keyword" in detected.reasons


def test_rule_detector_treats_yichu_as_expired_and_reads_money_bag_price() -> None:
    detector = _detector()

    detected = detector.detect(title="【闲置】已出 💰200百利生鲜鸡冻干拼鸡肉猫粮")

    assert detected.is_deal is False
    assert detected.brand == "百利"
    assert detected.category == "cat_food"
    assert detected.price == 200
    assert "expired deal signal" in detected.reasons


def test_rule_detector_identifies_real_xianzhi_orijen_title() -> None:
    detector = _detector()

    detected = detector.detect(title="【闲置】渴望鱼🐟5.4kg效期27.01，330元")

    assert detected.is_deal is True
    assert detected.brand == "渴望"
    assert detected.category == "cat_food"
    assert detected.price == 330


def test_rule_detector_allows_xianzhi_post_without_price() -> None:
    detector = _detector()

    detected = detector.detect(title="【闲置】官旗出爱肯拿农场牧场猫粮")

    assert detected.is_deal is True
    assert detected.brand == "爱肯拿"
    assert detected.category == "cat_food"
    assert detected.price is None


def test_rule_detector_recognizes_common_typos_and_k9() -> None:
    detector = _detector()

    typo = detector.detect(title="【闲置】百里无谷鸡猫粮 200元")
    k9 = detector.detect(title="闲置k9罐头鸡肉羊心*2 88元")

    assert typo.brand == "百利"
    assert typo.category == "cat_food"
    assert typo.is_deal is True
    assert k9.brand == "K9 Natural"
    assert k9.category == "wet_food"
    assert k9.is_deal is True


def test_rule_detector_ignores_content_for_brand_to_avoid_sidebar_noise() -> None:
    detector = _detector()

    detected = detector.detect(
        title="【闲置】now 车前子壳粉",
        content="侧栏推荐 Halo 自然光环 263r 开车",
    )

    assert detected.is_deal is False
    assert detected.brand is None
    assert detected.category is None
    assert detected.price is None


def test_rule_detector_uses_detail_content_price_when_title_brand_is_known() -> None:
    detector = _detector()

    detected = detector.detect(
        title="【闲置】halo自然光环2.5kg未拆封",
        content="正文价格 210元，可自提",
    )

    assert detected.is_deal is True
    assert detected.brand == "Halo"
    assert detected.category == "cat_food"
    assert detected.price == 210


def test_extract_lowest_price_ignores_large_non_price_numbers() -> None:
    assert extract_lowest_price("2026 年 百利 335 元，凑单后 329元") == 329


def test_extract_lowest_price_ignores_weight_numbers() -> None:
    assert extract_lowest_price("自然光环全能系列10磅 263r") == 263


def test_extract_lowest_price_reads_xianzhi_shipping_price_not_dates_or_weights() -> None:
    text = """皇家英短成猫粮BS34【整袋加分装】大于6.5kg
适合12个月以上英短、蓝猫、银渐层等短毛猫

大袋的26年6月淘宝买的，4.5kg，正品有防伪码，日期新鲜，保质期很长

分装的是4月27日淘宝买的，抽真空分装的，每包200克左右，十包至少2kg

猫心脏有问题要换处方粮了，闲置出
320包邮
营山可自提"""

    assert extract_lowest_price(text) == 320


def test_extract_lowest_price_reads_common_plus_shipping_suffix() -> None:
    assert extract_lowest_price("【闲置】渴望八重守护5.4kg，540+u，效期27.7 深圳可自提") == 540


def test_extract_lowest_price_reads_main_post_after_topic_chrome_is_removed() -> None:
    text = (
        "Jarrow牛初乳，120粒装，100包邮，保质期至，27.5月 "
        "now辅酶Q10，60粒30毫克装，40包邮，保质期至28.8 打包-5"
    )

    assert extract_lowest_price(text) == 40


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
