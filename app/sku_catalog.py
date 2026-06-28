from __future__ import annotations

from dataclasses import dataclass

from app.configuration.loader import SkuReference


@dataclass(frozen=True)
class SkuMatch:
    sku_key: str
    brand: str
    category: str
    product: str
    reference_price: float | None
    unit: str | None


class SkuCatalog:
    def __init__(self, skus: tuple[SkuReference, ...]) -> None:
        self._skus = skus

    def match(
        self,
        *,
        brand: str | None,
        category: str | None,
        text: str,
    ) -> SkuMatch | None:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return None

        candidates = [
            sku
            for sku in self._skus
            if (not brand or sku.brand == brand) and (not category or sku.category == category)
        ]
        matches = [
            (sku, _match_length(sku, normalized_text))
            for sku in candidates
            if _match_length(sku, normalized_text) > 0
        ]
        if not matches:
            return None

        sku = max(matches, key=lambda item: item[1])[0]
        return SkuMatch(
            sku_key=sku.sku_key,
            brand=sku.brand,
            category=sku.category,
            product=sku.product,
            reference_price=sku.reference_price,
            unit=sku.unit,
        )


def _match_length(sku: SkuReference, normalized_text: str) -> int:
    terms = (sku.product, *sku.aliases)
    return max(
        (
            len(normalized)
            for term in terms
            if (normalized := _normalize_text(term)) in normalized_text
        ),
        default=0,
    )


def _normalize_text(value: str) -> str:
    return (
        value.casefold()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace("!", "")
    )
