from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FeedbackType(StrEnum):
    MORE_LIKE_THIS = "MORE_LIKE_THIS"
    LESS_LIKE_THIS = "LESS_LIKE_THIS"
    BOUGHT_FROM_THIS = "BOUGHT_FROM_THIS"
    ALREADY_HAVE_STOCK = "ALREADY_HAVE_STOCK"


@dataclass(frozen=True)
class Post:
    douban_post_id: str
    title: str
    content: str
    url: str
    created_at: datetime
    fetched_at: datetime
    comments: tuple[str, ...] = ()
    id: int | None = None


@dataclass(frozen=True)
class Deal:
    post_id: int
    category: str
    brand: str
    product_name: str
    price: float
    confidence_score: int
    cat_score: int
    is_duplicate: bool
    created_at: datetime
    id: int | None = None


@dataclass(frozen=True)
class Notification:
    deal_id: int
    email_sent: bool
    sent_at: datetime | None = None
    id: int | None = None


@dataclass(frozen=True)
class Feedback:
    deal_id: int
    feedback_type: FeedbackType
    created_at: datetime
    id: int | None = None
