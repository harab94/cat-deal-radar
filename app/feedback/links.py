from __future__ import annotations

from urllib.parse import urlencode

from app.database import FeedbackType
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


def build_feedback_links(*, base_url: str, deal_id: int) -> FeedbackLinks:
    return FeedbackLinks(
        more_like_this=_feedback_url(base_url, deal_id, FeedbackType.MORE_LIKE_THIS),
        less_like_this=_feedback_url(base_url, deal_id, FeedbackType.LESS_LIKE_THIS),
        bought=_feedback_url(base_url, deal_id, FeedbackType.BOUGHT_FROM_THIS),
        already_have_stock=_feedback_url(base_url, deal_id, FeedbackType.ALREADY_HAVE_STOCK),
    )


def feedback_type_from_action(action: str) -> FeedbackType:
    try:
        return ACTION_TO_FEEDBACK_TYPE[action]
    except KeyError as error:
        msg = f"Unknown feedback action: {action}"
        raise ValueError(msg) from error


def _feedback_url(base_url: str, deal_id: int, feedback_type: FeedbackType) -> str:
    action = FEEDBACK_TYPE_TO_ACTION[feedback_type]
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'deal_id': deal_id, 'action': action})}"
