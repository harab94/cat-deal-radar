from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.header import Header
from email.message import Message as MimeMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.notification.templates import EmailMessage


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    sender: str
    recipient: str
    use_tls: bool = True


class SmtpEmailSender:
    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, message: EmailMessage) -> None:
        mime_message = build_mime_message(
            message=message,
            sender=self._config.sender,
            recipient=self._config.recipient,
        )

        with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as smtp:
            if self._config.use_tls:
                smtp.starttls()
            smtp.login(self._config.username, self._config.password)
            smtp.send_message(mime_message)


def build_mime_message(
    *,
    message: EmailMessage,
    sender: str,
    recipient: str,
) -> MimeMessage:
    mime_message = MIMEMultipart("alternative")
    mime_message["Subject"] = Header(message.subject, "utf-8", maxlinelen=998)
    mime_message["From"] = sender
    mime_message["To"] = recipient
    mime_message.attach(MIMEText(message.text_body, "plain", "utf-8"))
    mime_message.attach(MIMEText(message.html_body, "html", "utf-8"))
    return mime_message
