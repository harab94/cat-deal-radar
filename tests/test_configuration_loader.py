from __future__ import annotations

import json
from pathlib import Path

from app.configuration.loader import load_detection_config, load_rule_based_detector
from app.settings import Settings


def test_load_rule_based_detector_uses_local_yaml_when_feishu_is_not_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _clear_feishu_env(monkeypatch)

    detector = load_rule_based_detector(_settings(tmp_path))
    detected = detector.detect(title="闲车 未维护品牌猫粮 335元")

    assert detected.is_deal is True
    assert detected.brand is None
    assert detected.category == "cat_food"


def test_load_rule_based_detector_can_read_feishu_base_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", " cli_test\n")
    monkeypatch.setenv("FEISHU_APP_SECRET", " secret\n")
    monkeypatch.setenv("FEISHU_BASE_TOKEN", " base_token\n")
    monkeypatch.setenv("FEISHU_BRANDS_TABLE_ID", " brands_table\n")
    monkeypatch.setenv("FEISHU_CATEGORIES_TABLE_ID", " categories_table\n")
    monkeypatch.setenv("FEISHU_DETECTION_RULES_TABLE_ID", " rules_table\n")
    monkeypatch.setenv("FEISHU_SKUS_TABLE_ID", " skus_table\n")
    monkeypatch.setattr("app.configuration.feishu_base.urlopen", _fake_urlopen)

    detector = load_rule_based_detector(_settings(tmp_path))
    detected = detector.detect(title="推荐 测试别名猫粮 88元")
    expired = detector.detect(title="推荐 已结束 测试别名猫粮 88元")
    config = load_detection_config(_settings(tmp_path))

    assert detected.is_deal is True
    assert detected.brand == "测试品牌"
    assert detected.category == "cat_food"
    assert config.skus[0].sku_key == "测试品牌|cat_food|测试鸡肉"
    assert config.skus[0].reference_price == 100
    assert expired.is_deal is False
    assert "expired deal signal" in expired.reasons


def test_feishu_config_uses_local_rules_when_rules_table_is_not_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("FEISHU_BASE_TOKEN", "base_token")
    monkeypatch.setenv("FEISHU_BRANDS_TABLE_ID", "brands_table")
    monkeypatch.setenv("FEISHU_CATEGORIES_TABLE_ID", "categories_table")
    monkeypatch.delenv("FEISHU_DETECTION_RULES_TABLE_ID", raising=False)
    monkeypatch.setattr("app.configuration.feishu_base.urlopen", _fake_urlopen)

    detector = load_rule_based_detector(_settings(tmp_path))
    detected = detector.detect(title="测试别名豪车88元")
    expired = detector.detect(title="开车 测试别名猫粮 88元")
    config = load_detection_config(_settings(tmp_path))

    assert detected.is_deal is True
    assert detected.brand == "测试品牌"
    assert detected.category == "cat_food"
    assert "豪车" in config.deal_signals
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
                                "aliases": ["测试别名", {"text": "测试品牌猫粮"}],
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
    if "/tables/skus_table/records" in url:
        return _Response(
            {
                "code": 0,
                "data": {
                    "has_more": False,
                    "items": [
                        {
                            "fields": {
                                "sku_key": "测试品牌|cat_food|测试鸡肉",
                                "brand": "测试品牌",
                                "category": "cat_food",
                                "product": "测试鸡肉",
                                "aliases": ["测试别名猫粮"],
                                "reference_price": 100,
                                "unit": "包",
                                "enabled": True,
                            }
                        }
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
        "FEISHU_SKUS_TABLE_ID",
        "FEISHU_BRAND_CANDIDATES_TABLE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
