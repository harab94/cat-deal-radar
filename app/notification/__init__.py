"""Email notification support."""

from app.notification.email_sender import EmailConfig, SmtpEmailSender
from app.notification.feishu_sender import FeishuWebhookConfig, FeishuWebhookSender
from app.notification.service import NotificationService
from app.notification.templates import (
    DealDigestItem,
    EmailMessage,
    FeedbackLinks,
    PriceContext,
    render_deal_digest_email,
    render_deal_email,
)
from app.notification.wework_sender import WeWorkAppSender, WeWorkConfig

__all__ = [
    "DealDigestItem",
    "EmailConfig",
    "EmailMessage",
    "FeishuWebhookConfig",
    "FeishuWebhookSender",
    "FeedbackLinks",
    "PriceContext",
    "NotificationService",
    "SmtpEmailSender",
    "WeWorkAppSender",
    "WeWorkConfig",
    "render_deal_digest_email",
    "render_deal_email",
]
