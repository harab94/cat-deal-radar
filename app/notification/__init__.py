"""Email notification support."""

from app.notification.email_sender import EmailConfig, SmtpEmailSender
from app.notification.service import NotificationService
from app.notification.templates import (
    DealDigestItem,
    EmailMessage,
    FeedbackLinks,
    render_deal_digest_email,
    render_deal_email,
)

__all__ = [
    "DealDigestItem",
    "EmailConfig",
    "EmailMessage",
    "FeedbackLinks",
    "NotificationService",
    "SmtpEmailSender",
    "render_deal_digest_email",
    "render_deal_email",
]
