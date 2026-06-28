from __future__ import annotations

import json

from app.notification import EmailMessage
from app.notification.wework_sender import WeWorkAppSender, WeWorkConfig


def test_wework_sender_gets_token_and_sends_markdown(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if "gettoken" in request.full_url:
            return _Response({"errcode": 0, "access_token": "token"})
        return _Response({"errcode": 0})

    monkeypatch.setattr("app.notification.wework_sender.urlopen", fake_urlopen)

    sender = WeWorkAppSender(
        WeWorkConfig(
            corp_id="corp-id",
            app_secret="secret",
            agent_id="1000002",
            to_user="Hairahan",
        )
    )
    sender.send(
        EmailMessage(
            subject="猫车提醒",
            text_body="多推类似：https://example.com",
            html_body="",
        )
    )

    assert len(requests) == 2
    payload = json.loads(requests[1].data.decode("utf-8"))
    assert payload["touser"] == "Hairahan"
    assert payload["agentid"] == 1000002
    assert payload["msgtype"] == "markdown"
    assert "猫车提醒" in payload["markdown"]["content"]
    assert "https://example.com" in payload["markdown"]["content"]


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")
