from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


@dataclass(frozen=True)
class FeishuBaseConfig:
    app_id: str
    app_secret: str
    base_token: str
    brands_table_id: str
    categories_table_id: str
    detection_rules_table_id: str


class FeishuBaseReader:
    def __init__(self, config: FeishuBaseConfig) -> None:
        self._config = config

    def load_detection_config(self):
        from app.configuration.loader import DetectionConfig

        token = self._tenant_access_token()
        brand_records = self._list_records(token, self._config.brands_table_id)
        category_records = self._list_records(token, self._config.categories_table_id)
        rule_records = self._list_records(token, self._config.detection_rules_table_id)

        deal_signals, expired_signals = _rules_from_records(rule_records)
        return DetectionConfig(
            brand_aliases=_brand_aliases_from_records(brand_records),
            categories=_categories_from_records(category_records),
            deal_signals=deal_signals,
            expired_signals=expired_signals,
        )

    def _tenant_access_token(self) -> str:
        response = _request_json(
            "POST",
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            data={
                "app_id": self._config.app_id,
                "app_secret": self._config.app_secret,
            },
        )
        token = response.get("tenant_access_token")
        if not token:
            msg = f"Failed to get Feishu tenant token: {response}"
            raise RuntimeError(msg)
        return str(token)

    def _list_records(self, token: str, table_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params = {"page_size": "100"}
            if page_token:
                params["page_token"] = page_token
            response = _request_json(
                "GET",
                (
                    f"{FEISHU_API_BASE}/bitable/v1/apps/{self._config.base_token}"
                    f"/tables/{table_id}/records?{urlencode(params)}"
                ),
                token=token,
            )
            data = response.get("data", {})
            if not isinstance(data, dict):
                msg = f"Unexpected Feishu record response: {response}"
                raise RuntimeError(msg)

            records.extend(data.get("items", []) or [])
            if not data.get("has_more"):
                return records
            page_token = str(data.get("page_token", ""))


def _brand_aliases_from_records(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for record in records:
        fields = _fields(record)
        if not _enabled(fields):
            continue
        canonical = _cell_text(fields.get("canonical_brand"))
        alias = _cell_text(fields.get("alias"))
        if canonical and alias:
            aliases.setdefault(canonical, []).append(alias)
    return aliases


def _categories_from_records(records: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    categories: dict[str, dict[str, list[str]]] = {}
    for record in records:
        fields = _fields(record)
        if not _enabled(fields):
            continue
        category = _cell_text(fields.get("category_key"))
        if not category:
            continue
        config = categories.setdefault(category, {"brands": [], "keywords": []})
        brand = _cell_text(fields.get("brand"))
        keyword = _cell_text(fields.get("keyword"))
        if brand:
            config["brands"].append(brand)
        if keyword:
            config["keywords"].append(keyword)
    return categories


def _rules_from_records(records: list[dict[str, Any]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    deal_signals: list[str] = []
    expired_signals: list[str] = []
    for record in records:
        fields = _fields(record)
        if not _enabled(fields):
            continue
        rule_type = _cell_text(fields.get("rule_type"))
        keyword = _cell_text(fields.get("keyword"))
        if rule_type == "deal_signal" and keyword:
            deal_signals.append(keyword)
        if rule_type == "expired_signal" and keyword:
            expired_signals.append(keyword)
    return tuple(deal_signals), tuple(expired_signals)


def _request_json(
    method: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    body = None if data is None else json.dumps(data).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = _http_error_detail(error)
        msg = f"Feishu API request failed: {method} {_safe_url(url)} ({detail})"
        raise RuntimeError(msg) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        msg = f"Feishu API request failed: {error}"
        raise RuntimeError(msg) from error

    if result.get("code", 0) != 0:
        msg = f"Feishu API returned error: {result}"
        raise RuntimeError(msg)
    return result


def _fields(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("fields", {})
    return fields if isinstance(fields, dict) else {}


def _enabled(fields: dict[str, Any]) -> bool:
    value = fields.get("enabled", True)
    return value is not False


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "".join(_cell_text(item) for item in value).strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("name") or "").strip()
    return str(value).strip()


def _http_error_detail(error: HTTPError) -> str:
    body = error.read(500).decode("utf-8", errors="replace").replace("\n", " ")
    if body:
        return f"status={error.code} reason={error.reason} body={body[:300]}"
    return f"status={error.code} reason={error.reason}"


def _safe_url(url: str) -> str:
    return url.split("?")[0]
