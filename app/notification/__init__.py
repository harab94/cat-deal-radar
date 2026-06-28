"""Email notification support."""

from app.notification.email_sender import EmailConfig, SmtpEmailSender
from app.notification.service import NotificationService
from app.notification.templates import (
    DealDigestItem,
    EmailMessage,
    FeedbackLinks,
    PriceContext,
    render_deal_digest_email,
    render_deal_email,
)

__all__ = [
    "DealDigestItem",
    "EmailConfig",
    "EmailMessage",
    "FeedbackLinks",
    "PriceContext",
    "NotificationService",
    "SmtpEmailSender",
    "render_deal_digest_email",
    "render_deal_email",
]
