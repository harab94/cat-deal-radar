from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.database import Deal


@dataclass(frozen=True)
class DuplicateDecision:
    is_duplicate: bool
    should_notify: bool
    superseded_deal_id: int | None = None


class DuplicateHandler:
    def __init__(self, *, window_hours: int = 24) -> None:
        self._window = timedelta(hours=window_hours)

    def evaluate(self, candidate: Deal, existing_deals: list[Deal]) -> DuplicateDecision:
        matches = [
            deal
            for deal in existing_deals
            if _same_product(candidate, deal)
            and _within_window(candidate.created_at, deal.created_at, self._window)
        ]
        if not matches:
            return DuplicateDecision(is_duplicate=False, should_notify=True)

        if _unknown_price(candidate.price):
            return DuplicateDecision(is_duplicate=True, should_notify=False)

        known_price_matches = [deal for deal in matches if not _unknown_price(deal.price)]
        if not known_price_matches:
            return DuplicateDecision(is_duplicate=False, should_notify=True)

        lowest_existing = min(known_price_matches, key=lambda deal: deal.price)
        if candidate.price < lowest_existing.price:
            return DuplicateDecision(
                is_duplicate=False,
                should_notify=True,
                superseded_deal_id=lowest_existing.id,
            )
        return DuplicateDecision(is_duplicate=True, should_notify=False)


def _same_product(left: Deal, right: Deal) -> bool:
    return (
        left.brand == right.brand
        and left.category == right.category
        and _normalize_product_name(left.product_name)
        == _normalize_product_name(right.product_name)
    )


def _unknown_price(price: float) -> bool:
    return price <= 0


def _normalize_product_name(value: str) -> str:
    return value.casefold().replace(" ", "").replace("-", "").replace("_", "")


def _within_window(left: datetime, right: datetime, window: timedelta) -> bool:
    return abs(left - right) <= window
