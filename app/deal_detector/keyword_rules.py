from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.brand_normalization import BrandNormalizer

DEAL_SIGNALS = ("团购", "闲车", "闲置", "好价", "补货", "凑单")
EXPIRED_SIGNALS = ("开车", "已开车", "车走了", "已出", "出掉", "已售", "售出", "卖掉")
DEFAULT_CATEGORY_KEYWORDS = {
    "cat_food": ("猫粮", "主粮"),
    "wet_food": ("罐头", "餐包", "湿粮"),
    "freeze_dried": ("冻干",),
    "cat_litter": ("猫砂", "豆腐砂", "木薯砂"),
}
PRICE_PATTERN = re.compile(
    r"(?:¥|￥|💰)\s*(\d+(?:\.\d+)?)"
    r"|(\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB)"
    r"|(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*[rR](?![A-Za-z])"
    r"|(?<!\d)(\d+(?:\.\d+)?)\s*(?:包邮|\+u|\+U|自提|出)"
)
WEIGHT_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:kg|KG|公斤|克|g|G|斤|磅)")


@dataclass(frozen=True)
class DetectedDeal:
    is_deal: bool
    category: str | None
    brand: str | None
    product_name: str | None
    price: float | None
    confidence: int
    reasons: tuple[str, ...]


class RuleBasedDealDetector:
    def __init__(
        self,
        *,
        brand_normalizer: BrandNormalizer,
        category_config: dict[str, Any],
        deal_signals: tuple[str, ...] = DEAL_SIGNALS,
        expired_signals: tuple[str, ...] = EXPIRED_SIGNALS,
    ) -> None:
        self._brand_normalizer = brand_normalizer
        self._category_config = category_config
        self._deal_signals = deal_signals
        self._expired_signals = expired_signals

    @classmethod
    def from_config_files(
        cls,
        *,
        brands_path: str | Path,
        categories_path: str | Path,
    ) -> RuleBasedDealDetector:
        with Path(categories_path).open(encoding="utf-8") as file:
            category_config = yaml.safe_load(file) or {}
        return cls(
            brand_normalizer=BrandNormalizer.from_yaml(brands_path),
            category_config=category_config,
        )

    def detect(self, *, title: str, content: str = "") -> DetectedDeal:
        title_text = title.strip()
        brand = self._brand_normalizer.find_in_text(title_text)
        category = self._category_for_text(title_text, brand)
        price = extract_lowest_price(title_text)
        if price is None and brand and category:
            price = extract_lowest_price(content)
        reasons = _reasons(
            title_text,
            brand,
            category,
            price,
            deal_signals=self._deal_signals,
            expired_signals=self._expired_signals,
        )
        is_deal = bool(
            brand
            and category
            and _has_any_signal(title_text, self._deal_signals)
            and not _has_any_signal(title_text, self._expired_signals)
        )

        return DetectedDeal(
            is_deal=is_deal,
            category=category,
            brand=brand,
            product_name=title.strip() or None,
            price=price,
            confidence=_confidence(reasons, is_deal),
            reasons=tuple(reasons),
        )

    def _category_for_text(self, text: str, brand: str | None) -> str | None:
        if brand:
            for category, config in self._category_config.items():
                if brand in config.get("brands", []):
                    return str(category)

        normalized_text = text.casefold()
        for category, config in self._category_config.items():
            keywords = (
                *config.get("keywords", []),
                *DEFAULT_CATEGORY_KEYWORDS.get(category, ()),
            )
            for keyword in keywords:
                if str(keyword).casefold() in normalized_text:
                    return str(category)
        return None


def extract_lowest_price(text: str) -> float | None:
    text_without_weights = WEIGHT_PATTERN.sub(" ", text)
    prices = []
    for match in PRICE_PATTERN.finditer(text_without_weights):
        raw_price = next(group for group in match.groups() if group is not None)
        price = float(raw_price)
        if _looks_like_price(price):
            prices.append(price)
    return min(prices) if prices else None


def _looks_like_price(value: float) -> bool:
    return 1 <= value <= 5000


def _reasons(
    text: str,
    brand: str | None,
    category: str | None,
    price: float | None,
    *,
    deal_signals: tuple[str, ...] = DEAL_SIGNALS,
    expired_signals: tuple[str, ...] = EXPIRED_SIGNALS,
) -> list[str]:
    reasons: list[str] = []
    if _has_any_signal(text, deal_signals):
        reasons.append("deal signal keyword")
    if _has_any_signal(text, expired_signals):
        reasons.append("expired deal signal")
    if brand:
        reasons.append("known brand")
    if category:
        reasons.append("supported category")
    if price is not None:
        reasons.append("price found")
    return reasons


def _confidence(reasons: list[str], is_deal: bool) -> int:
    if not is_deal:
        return min(len(reasons) * 20, 60)
    return min(60 + len(reasons) * 10, 95)


def _has_any_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)
