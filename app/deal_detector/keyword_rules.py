from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.brand_normalization import BrandNormalizer

DEAL_SIGNALS = ("团购", "闲车", "好价", "补货", "凑单")
EXPIRED_SIGNALS = ("开车", "已开车", "车走了")
PRICE_PATTERN = re.compile(r"(?:¥|￥)?\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB)?")


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
    ) -> None:
        self._brand_normalizer = brand_normalizer
        self._category_config = category_config

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
        text = f"{title}\n{content}".strip()
        brand = self._brand_normalizer.find_in_text(text)
        category = self._category_for_text(text, brand)
        price = extract_lowest_price(text)
        reasons = _reasons(text, brand, category, price)
        is_deal = bool(
            brand
            and category
            and price is not None
            and _has_deal_signal(text)
            and not _has_expired_signal(text)
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
            for keyword in config.get("keywords", []):
                if str(keyword).casefold() in normalized_text:
                    return str(category)
        return None


def extract_lowest_price(text: str) -> float | None:
    prices = [
        float(match.group(1))
        for match in PRICE_PATTERN.finditer(text)
        if _looks_like_price(float(match.group(1)))
    ]
    return min(prices) if prices else None


def _looks_like_price(value: float) -> bool:
    return 1 <= value <= 5000


def _has_deal_signal(text: str) -> bool:
    return any(signal in text for signal in DEAL_SIGNALS)


def _has_expired_signal(text: str) -> bool:
    return any(signal in text for signal in EXPIRED_SIGNALS)


def _reasons(
    text: str,
    brand: str | None,
    category: str | None,
    price: float | None,
) -> list[str]:
    reasons: list[str] = []
    if _has_deal_signal(text):
        reasons.append("deal signal keyword")
    if _has_expired_signal(text):
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
