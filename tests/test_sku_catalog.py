from app.configuration.loader import SkuReference
from app.sku_catalog import SkuCatalog


def test_sku_catalog_does_not_guess_without_brand_or_category() -> None:
    catalog = SkuCatalog(
        (
            SkuReference(
                sku_key="小李子|wet_food|禽肉罐头",
                brand="小李子",
                category="wet_food",
                product="禽肉罐头",
                aliases=("小李子猫罐头",),
                reference_price=16,
                unit="罐",
            ),
        )
    )

    match = catalog.match(
        brand=None,
        category=None,
        text="【闲置】救救孩子，买成狗粮了。刚拆开的NG恩萃狗粮兔肉6kg小颗粒",
    )

    assert match is None


def test_sku_catalog_can_match_with_category_context() -> None:
    catalog = SkuCatalog(
        (
            SkuReference(
                sku_key="小李子|wet_food|禽肉罐头",
                brand="小李子",
                category="wet_food",
                product="禽肉罐头",
                aliases=("小李子猫罐头",),
                reference_price=16,
                unit="罐",
            ),
        )
    )

    match = catalog.match(
        brand=None,
        category="wet_food",
        text="【开车】小李子禽肉罐头200g 12.17r",
    )

    assert match is not None
    assert match.sku_key == "小李子|wet_food|禽肉罐头"
