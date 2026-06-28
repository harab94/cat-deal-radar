from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.notification.templates import EmailMessage

WEWORK_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
MAX_MARKDOWN_LENGTH = 3500


@dataclass(frozen=True)
class WeWorkConfig:
    corp_id: str
    app_secret: str
    agent_id: str
    to_user: str


class WeWorkAppSender:
    def __init__(self, config: WeWorkConfig) -> None:
        self._config = config

    def send(self, message: EmailMessage) -> None:
        token = self._access_token()
        payload = {
            "touser": self._config.to_user,
            "msgtype": "markdown",
            "agentid": int(self._config.agent_id),
            "markdown": {"content": _markdown_content(message)},
            "safe": 0,
        }
        response = _request_json(
            "POST",
            f"{WEWORK_API_BASE}/message/send?{urlencode({'access_token': token})}",
            data=payload,
        )
        _raise_for_wework_error(response, "Failed to send WeWork message")

    def _access_token(self) -> str:
        params = urlencode(
            {
                "corpid": self._config.corp_id,
                "corpsecret": self._config.app_secret,
            }
        )
        response = _request_json(
            "GET",
            f"{WEWORK_API_BASE}/gettoken?{params}",
        )
        _raise_for_wework_error(response, "Failed to get WeWork access token")
        token = response.get("access_token")
        if not token:
            msg = f"WeWork access token missing: {response}"
            raise RuntimeError(msg)
        return str(token)


def _markdown_content(message: EmailMessage) -> str:
    content = f"## {message.subject}\n\n{message.text_body.strip()}"
    if len(content) <= MAX_MARKDOWN_LENGTH:
        return content
    return f"{content[: MAX_MARKDOWN_LENGTH - 20].rstrip()}\n\n...内容已截断"


def _request_json(
    method: str,
    url: str,
    *,
    data: dict | None = None,
) -> dict:
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method=method,
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _raise_for_wework_error(response: dict, message: str) -> None:
    if int(response.get("errcode", 0)) == 0:
        return
    msg = f"{message}: {response}"
    raise RuntimeError(msg)
