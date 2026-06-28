from __future__ import annotations

from urllib.parse import urlencode

from app.database import Deal, FeedbackType, Post
from app.notification import FeedbackLinks

ACTION_TO_FEEDBACK_TYPE = {
    "more": FeedbackType.MORE_LIKE_THIS,
    "less": FeedbackType.LESS_LIKE_THIS,
    "bought": FeedbackType.BOUGHT_FROM_THIS,
    "stock": FeedbackType.ALREADY_HAVE_STOCK,
}

FEEDBACK_TYPE_TO_ACTION = {
    feedback_type: action for action, feedback_type in ACTION_TO_FEEDBACK_TYPE.items()
}


def build_feedback_links(
    *,
    base_url: str,
    deal_id: int,
    deal: Deal | None = None,
    post: Post | None = None,
) -> FeedbackLinks:
    metadata = _feedback_metadata(deal=deal, post=post)
    return FeedbackLinks(
        more_like_this=_feedback_url(
            base_url,
            deal_id,
            FeedbackType.MORE_LIKE_THIS,
            metadata=metadata,
        ),
        less_like_this=_feedback_url(
            base_url,
            deal_id,
            FeedbackType.LESS_LIKE_THIS,
            metadata=metadata,
        ),
        bought=_feedback_url(
            base_url,
            deal_id,
            FeedbackType.BOUGHT_FROM_THIS,
            metadata=metadata,
        ),
        already_have_stock=_feedback_url(
            base_url,
            deal_id,
            FeedbackType.ALREADY_HAVE_STOCK,
            metadata=metadata,
        ),
    )


def feedback_type_from_action(action: str) -> FeedbackType:
    try:
        return ACTION_TO_FEEDBACK_TYPE[action]
    except KeyError as error:
        msg = f"Unknown feedback action: {action}"
        raise ValueError(msg) from error


def _feedback_url(
    base_url: str,
    deal_id: int,
    feedback_type: FeedbackType,
    *,
    metadata: dict[str, str],
) -> str:
    action = FEEDBACK_TYPE_TO_ACTION[feedback_type]
    separator = "&" if "?" in base_url else "?"
    params = {"deal_id": deal_id, "action": action, **metadata}
    return f"{base_url}{separator}{urlencode(params)}"


def _feedback_metadata(*, deal: Deal | None, post: Post | None) -> dict[str, str]:
    if deal is None:
        return {}

    metadata = {
        "brand": deal.brand,
        "category": deal.category,
        "title": deal.product_name,
    }
    if deal.price > 0:
        metadata["price"] = f"{deal.price:g}"
    if post is not None:
        metadata["douban_url"] = post.url
    return metadata
