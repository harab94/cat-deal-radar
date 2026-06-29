from __future__ import annotations

import json

from app.notification import EmailMessage, FeishuWebhookConfig, FeishuWebhookSender


def test_feishu_webhook_sender_posts_text_message(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _Response({"code": 0, "msg": "success"})

    monkeypatch.setattr("app.notification.feishu_sender.urlopen", fake_urlopen)

    sender = FeishuWebhookSender(
        FeishuWebhookConfig(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test")
    )
    sender.send(EmailMessage(subject="猫车提醒", text_body="百利原始鸡 250 元", html_body=""))

    assert len(requests) == 1
    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "猫车提醒\n\n百利原始鸡 250 元"


def test_feishu_webhook_sender_adds_signature_when_secret_is_configured(
    monkeypatch,
) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _Response({"code": 0, "msg": "success"})

    monkeypatch.setattr("app.notification.feishu_sender.time.time", lambda: 1234567890)
    monkeypatch.setattr("app.notification.feishu_sender.urlopen", fake_urlopen)

    sender = FeishuWebhookSender(
        FeishuWebhookConfig(
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
            secret="secret",
        )
    )
    sender.send(EmailMessage(subject="猫车提醒", text_body="百利原始鸡 250 元", html_body=""))

    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload["timestamp"] == "1234567890"
    assert payload["sign"]


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")
