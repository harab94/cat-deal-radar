from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeEmailMessage

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
        mime_message = MimeEmailMessage()
        mime_message["Subject"] = message.subject
        mime_message["From"] = self._config.sender
        mime_message["To"] = self._config.recipient
        mime_message.set_content(message.text_body)
        mime_message.add_alternative(message.html_body, subtype="html")

        with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as smtp:
            if self._config.use_tls:
                smtp.starttls()
            smtp.login(self._config.username, self._config.password)
            smtp.send_message(mime_message)
