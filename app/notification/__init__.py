"""Email notification support."""

from app.notification.email_sender import EmailConfig, SmtpEmailSender
from app.notification.service import NotificationService
from app.notification.templates import EmailMessage, FeedbackLinks, render_deal_email

__all__ = [
    "EmailConfig",
    "EmailMessage",
    "FeedbackLinks",
    "NotificationService",
    "SmtpEmailSender",
    "render_deal_email",
]
