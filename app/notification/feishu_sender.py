from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen

from app.notification.templates import EmailMessage

MAX_TEXT_LENGTH = 3500


@dataclass(frozen=True)
class FeishuWebhookConfig:
    webhook_url: str
    secret: str | None = None


class FeishuWebhookSender:
    def __init__(self, config: FeishuWebhookConfig) -> None:
        self._config = config

    def send(self, message: EmailMessage) -> None:
        payload: dict[str, object] = {
            "msg_type": "text",
            "content": {"text": _text_content(message)},
        }
        if self._config.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = _signature(timestamp, self._config.secret)

        response = _request_json(self._config.webhook_url, payload)
        _raise_for_feishu_error(response)


def _text_content(message: EmailMessage) -> str:
    content = f"{message.subject}\n\n{message.text_body.strip()}"
    if len(content) <= MAX_TEXT_LENGTH:
        return content
    return f"{content[: MAX_TEXT_LENGTH - 20].rstrip()}\n\n...内容已截断"


def _signature(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode()
    digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _request_json(url: str, data: dict[str, object]) -> dict:
    request = Request(
        url,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _raise_for_feishu_error(response: dict) -> None:
    code = int(response.get("code", response.get("StatusCode", 0)))
    if code == 0:
        return
    msg = f"Failed to send Feishu message: {response}"
    raise RuntimeError(msg)
