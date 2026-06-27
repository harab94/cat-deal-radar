from __future__ import annotations

import json
from pathlib import Path

from app.configuration.loader import load_rule_based_detector
from app.settings import Settings


def test_load_rule_based_detector_uses_local_yaml_when_feishu_is_not_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _clear_feishu_env(monkeypatch)

    detector = load_rule_based_detector(_settings(tmp_path))
    detected = detector.detect(title="闲车 百利原始鸡 335元")

    assert detected.is_deal is True
    assert detected.brand == "百利"


def test_load_rule_based_detector_can_read_feishu_base_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("FEISHU_BASE_TOKEN", "base_token")
    monkeypatch.setenv("FEISHU_BRANDS_TABLE_ID", "brands_table")
    monkeypatch.setenv("FEISHU_CATEGORIES_TABLE_ID", "categories_table")
    monkeypatch.setenv("FEISHU_DETECTION_RULES_TABLE_ID", "rules_table")
    monkeypatch.setattr("app.configuration.feishu_base.urlopen", _fake_urlopen)

    detector = load_rule_based_detector(_settings(tmp_path))
    detected = detector.detect(title="推荐 测试别名猫粮 88元")
    expired = detector.detect(title="推荐 已结束 测试别名猫粮 88元")

    assert detected.is_deal is True
    assert detected.brand == "测试品牌"
    assert detected.category == "cat_food"
    assert expired.is_deal is False
    assert "expired deal signal" in expired.reasons


def _fake_urlopen(request, timeout):
    url = request.full_url
    if "/tenant_access_token/internal" in url:
        return _Response({"code": 0, "tenant_access_token": "tenant_token"})
    if "/tables/brands_table/records" in url:
        return _Response(
            {
                "code": 0,
                "data": {
                    "has_more": False,
                    "items": [
                        {
                            "fields": {
                                "canonical_brand": "测试品牌",
                                "alias": "测试别名",
                                "enabled": True,
                            }
                        }
                    ],
                },
            }
        )
    if "/tables/categories_table/records" in url:
        return _Response(
            {
                "code": 0,
                "data": {
                    "has_more": False,
                    "items": [
                        {
                            "fields": {
                                "category_key": "cat_food",
                                "brand": "测试品牌",
                                "enabled": True,
                            }
                        }
                    ],
                },
            }
        )
    if "/tables/rules_table/records" in url:
        return _Response(
            {
                "code": 0,
                "data": {
                    "has_more": False,
                    "items": [
                        {
                            "fields": {
                                "rule_type": "deal_signal",
                                "keyword": "推荐",
                                "enabled": True,
                            }
                        },
                        {
                            "fields": {
                                "rule_type": "expired_signal",
                                "keyword": "已结束",
                                "enabled": True,
                            }
                        },
                    ],
                },
            }
        )
    raise AssertionError(f"Unexpected URL: {url}")


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "data" / "cat_deal_radar.sqlite",
        douban_group_url="https://example.com/group",
        douban_tab_name="闲车禁拼多多",
    )


def _clear_feishu_env(monkeypatch) -> None:
    for name in (
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_BASE_TOKEN",
        "FEISHU_BRANDS_TABLE_ID",
        "FEISHU_CATEGORIES_TABLE_ID",
        "FEISHU_DETECTION_RULES_TABLE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
