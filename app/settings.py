from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Settings:
    database_path: Path
    douban_group_url: str
    douban_tab_name: str
    douban_cookie_env: str = "DOUBAN_COOKIE"
    brands_path: Path = Path("config/brands.yaml")
    categories_path: Path = Path("config/categories.yaml")
    skus_path: Path = Path("config/skus.yaml")
    preferences_path: Path = Path("config/preferences.yaml")
    feedback_base_url_env: str = "FEEDBACK_BASE_URL"
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username_env: str = "GMAIL_USERNAME"
    email_password_env: str = "GMAIL_APP_PASSWORD"
    email_sender_env: str = "GMAIL_SENDER"
    email_recipient_env: str = "DEAL_NOTIFICATION_RECIPIENT"
    email_use_tls: bool = True
    feishu_app_id_env: str = "FEISHU_APP_ID"
    feishu_app_secret_env: str = "FEISHU_APP_SECRET"
    feishu_base_token_env: str = "FEISHU_BASE_TOKEN"
    feishu_brands_table_id_env: str = "FEISHU_BRANDS_TABLE_ID"
    feishu_categories_table_id_env: str = "FEISHU_CATEGORIES_TABLE_ID"
    feishu_detection_rules_table_id_env: str = "FEISHU_DETECTION_RULES_TABLE_ID"
    feishu_skus_table_id_env: str = "FEISHU_SKUS_TABLE_ID"


def load_settings(path: str | Path = "config/settings.yaml") -> Settings:
    with Path(path).open(encoding="utf-8") as file:
        raw_settings = yaml.safe_load(file) or {}

    database_path = Path(
        _nested(raw_settings, "database", "path", default="data/cat_deal_radar.sqlite")
    )
    return Settings(
        database_path=database_path,
        douban_group_url=str(_nested(raw_settings, "douban", "group_url", default="")),
        douban_tab_name=str(_nested(raw_settings, "douban", "tab_name", default="")),
        douban_cookie_env=str(
            _nested(raw_settings, "douban", "cookie_env", default="DOUBAN_COOKIE")
        ),
        brands_path=Path(
            _nested(raw_settings, "config", "brands_path", default="config/brands.yaml")
        ),
        categories_path=Path(
            _nested(raw_settings, "config", "categories_path", default="config/categories.yaml")
        ),
        skus_path=Path(_nested(raw_settings, "config", "skus_path", default="config/skus.yaml")),
        preferences_path=Path(
            _nested(raw_settings, "config", "preferences_path", default="config/preferences.yaml")
        ),
        feedback_base_url_env=str(
            _nested(raw_settings, "feedback", "base_url_env", default="FEEDBACK_BASE_URL")
        ),
        email_smtp_host=str(_nested(raw_settings, "email", "smtp_host", default="smtp.gmail.com")),
        email_smtp_port=int(_nested(raw_settings, "email", "smtp_port", default="587")),
        email_username_env=str(
            _nested(raw_settings, "email", "username_env", default="GMAIL_USERNAME")
        ),
        email_password_env=str(
            _nested(raw_settings, "email", "password_env", default="GMAIL_APP_PASSWORD")
        ),
        email_sender_env=str(_nested(raw_settings, "email", "sender_env", default="GMAIL_SENDER")),
        email_recipient_env=str(
            _nested(
                raw_settings,
                "email",
                "recipient_env",
                default="DEAL_NOTIFICATION_RECIPIENT",
            )
        ),
        email_use_tls=_nested_bool(raw_settings, "email", "use_tls", default=True),
        feishu_app_id_env=str(
            _nested(raw_settings, "feishu", "app_id_env", default="FEISHU_APP_ID")
        ),
        feishu_app_secret_env=str(
            _nested(raw_settings, "feishu", "app_secret_env", default="FEISHU_APP_SECRET")
        ),
        feishu_base_token_env=str(
            _nested(raw_settings, "feishu", "base_token_env", default="FEISHU_BASE_TOKEN")
        ),
        feishu_brands_table_id_env=str(
            _nested(
                raw_settings,
                "feishu",
                "brands_table_id_env",
                default="FEISHU_BRANDS_TABLE_ID",
            )
        ),
        feishu_categories_table_id_env=str(
            _nested(
                raw_settings,
                "feishu",
                "categories_table_id_env",
                default="FEISHU_CATEGORIES_TABLE_ID",
            )
        ),
        feishu_detection_rules_table_id_env=str(
            _nested(
                raw_settings,
                "feishu",
                "detection_rules_table_id_env",
                default="FEISHU_DETECTION_RULES_TABLE_ID",
            )
        ),
        feishu_skus_table_id_env=str(
            _nested(
                raw_settings,
                "feishu",
                "skus_table_id_env",
                default="FEISHU_SKUS_TABLE_ID",
            )
        ),
    )


def _nested(settings: dict[str, Any], section: str, key: str, *, default: str) -> str:
    section_values = settings.get(section, {})
    if not isinstance(section_values, dict):
        return default
    return str(section_values.get(key, default))


def _nested_bool(settings: dict[str, Any], section: str, key: str, *, default: bool) -> bool:
    section_values = settings.get(section, {})
    if not isinstance(section_values, dict):
        return default
    value = section_values.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).casefold() in {"1", "true", "yes", "on"}
