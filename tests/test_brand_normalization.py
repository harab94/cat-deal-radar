from pathlib import Path

import pytest

from app.brand_normalization import BrandNormalizer

CONFIG_PATH = Path("config/brands.yaml")


@pytest.fixture
def normalizer() -> BrandNormalizer:
    return BrandNormalizer.from_yaml(CONFIG_PATH)


@pytest.mark.parametrize(
    ("raw_brand", "canonical_name"),
    [
        ("Acana", "爱肯拿"),
        ("ACANA", "爱肯拿"),
        ("Instinct", "百利"),
        ("百利原始鸡", "百利"),
        ("Farmina", "法米娜"),
        ("Solid Gold", "金素"),
        ("solid-gold", "金素"),
        ("halo", "Halo"),
        ("金色交响乐", "金色交响乐"),
        ("小李子", "小李子"),
        ("OP 三文鱼冻干", "OP"),
        ("顽味青花鱼", "顽味"),
        ("mjamjam", "MJamJam"),
        ("Arm & Hammer", "Arm & Hammer"),
        ("铁锤", "Arm & Hammer"),
    ],
)
def test_normalize_known_brand_aliases(
    normalizer: BrandNormalizer,
    raw_brand: str,
    canonical_name: str,
) -> None:
    assert normalizer.normalize(raw_brand) == canonical_name


@pytest.mark.parametrize(
    ("post_text", "canonical_name"),
    [
        ("闲车：百利原始鸡 335 元，还能买", "百利"),
        ("Acana 大包好价，适合囤货", "爱肯拿"),
        ("solid gold 今天有车", "金素"),
        ("OP 三文鱼冻干补货", "OP"),
        ("铁锤猫砂双十一价", "Arm & Hammer"),
    ],
)
def test_find_brand_in_post_text(
    normalizer: BrandNormalizer,
    post_text: str,
    canonical_name: str,
) -> None:
    assert normalizer.find_in_text(post_text) == canonical_name


def test_unknown_brand_returns_none(normalizer: BrandNormalizer) -> None:
    assert normalizer.normalize("不认识的牌子") is None
    assert normalizer.find_in_text("今天没有任何已知品牌") is None


def test_canonical_names_include_all_seed_brands(normalizer: BrandNormalizer) -> None:
    assert {
        "爱肯拿",
        "百利",
        "法米娜",
        "金素",
        "Halo",
        "金色交响乐",
        "小李子",
        "MJamJam",
        "OP",
        "顽味",
        "Arm & Hammer",
    }.issubset(normalizer.canonical_names)
