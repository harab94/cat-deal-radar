from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from app.database import Deal, Notification, Post, Repository
from app.notification.templates import (
    DealDigestItem,
    EmailMessage,
    FeedbackLinks,
    PriceContext,
    render_deal_digest_email,
    render_deal_email,
)
from app.recommendation import RecommendationScore


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class NotificationService:
    def __init__(self, *, repository: Repository, sender: EmailSender) -> None:
        self._repository = repository
        self._sender = sender

    def send_deal_notification(
        self,
        *,
        deal: Deal,
        post: Post,
        recommendation: RecommendationScore,
        feedback_links: FeedbackLinks,
        price_context: PriceContext | None = None,
    ) -> Notification:
        message = render_deal_email(
            deal=deal,
            post=post,
            recommendation=recommendation,
            feedback_links=feedback_links,
            price_context=price_context,
        )
        notification = self._repository.create_notification(
            Notification(deal_id=_require_deal_id(deal), email_sent=False)
        )
        self._sender.send(message)
        return self._repository.update_notification(
            Notification(
                id=notification.id,
                deal_id=notification.deal_id,
                email_sent=True,
                sent_at=datetime.now(UTC),
            )
        )

    def send_deal_digest(self, *, items: list[DealDigestItem]) -> list[Notification]:
        message = render_deal_digest_email(items)
        notifications = [
            self._repository.create_notification(
                Notification(deal_id=_require_deal_id(item.deal), email_sent=False)
            )
            for item in items
        ]
        self._sender.send(message)
        sent_at = datetime.now(UTC)
        return [
            self._repository.update_notification(
                Notification(
                    id=notification.id,
                    deal_id=notification.deal_id,
                    email_sent=True,
                    sent_at=sent_at,
                )
            )
            for notification in notifications
        ]


def _require_deal_id(deal: Deal) -> int:
    if deal.id is None:
        msg = "Cannot send a notification for a deal without an id."
        raise ValueError(msg)
    return deal.id
