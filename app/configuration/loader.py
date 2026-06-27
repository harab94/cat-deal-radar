from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import yaml

from app.brand_normalization import BrandNormalizer
from app.configuration.feishu_base import FeishuBaseConfig, FeishuBaseReader
from app.deal_detector import RuleBasedDealDetector
from app.deal_detector.keyword_rules import DEAL_SIGNALS, EXPIRED_SIGNALS
from app.settings import Settings

logger = structlog.get_logger()


@dataclass(frozen=True)
class DetectionConfig:
    brand_aliases: dict[str, list[str]]
    categories: dict[str, dict[str, list[str]]]
    deal_signals: tuple[str, ...]
    expired_signals: tuple[str, ...]


def load_rule_based_detector(settings: Settings) -> RuleBasedDealDetector:
    config = load_detection_config(settings)
    return RuleBasedDealDetector(
        brand_normalizer=BrandNormalizer.from_mapping(config.brand_aliases),
        category_config=config.categories,
        deal_signals=config.deal_signals,
        expired_signals=config.expired_signals,
    )


def load_detection_config(settings: Settings) -> DetectionConfig:
    feishu_config = _feishu_config_from_env(settings)
    if feishu_config is not None:
        try:
            config = FeishuBaseReader(feishu_config).load_detection_config()
            logger.info("feishu_detection_config_loaded")
            return config
        except Exception as error:
            logger.warning("feishu_detection_config_failed", error=str(error))

    logger.info("local_detection_config_loaded")
    return _load_local_detection_config(
        brands_path=settings.brands_path,
        categories_path=settings.categories_path,
    )


def _load_local_detection_config(*, brands_path: Path, categories_path: Path) -> DetectionConfig:
    with brands_path.open(encoding="utf-8") as file:
        brand_config = yaml.safe_load(file) or {}
        brand_aliases = brand_config.get("brand_aliases", {})
    with categories_path.open(encoding="utf-8") as file:
        categories = yaml.safe_load(file) or {}

    return DetectionConfig(
        brand_aliases=_normalize_brand_aliases(brand_aliases),
        categories=_normalize_categories(categories),
        deal_signals=DEAL_SIGNALS,
        expired_signals=EXPIRED_SIGNALS,
    )


def _feishu_config_from_env(settings: Settings) -> FeishuBaseConfig | None:
    values = {
        "app_id": os.environ.get(settings.feishu_app_id_env),
        "app_secret": os.environ.get(settings.feishu_app_secret_env),
        "base_token": os.environ.get(settings.feishu_base_token_env),
        "brands_table_id": os.environ.get(settings.feishu_brands_table_id_env),
        "categories_table_id": os.environ.get(settings.feishu_categories_table_id_env),
        "detection_rules_table_id": os.environ.get(
            settings.feishu_detection_rules_table_id_env
        ),
    }
    if not all(values.values()):
        return None
    return FeishuBaseConfig(**values)  # type: ignore[arg-type]


def _normalize_brand_aliases(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(canonical): [str(alias) for alias in aliases or []]
        for canonical, aliases in raw.items()
    }


def _normalize_categories(raw: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(raw, dict):
        return {}

    categories: dict[str, dict[str, list[str]]] = {}
    for category, config in raw.items():
        if not isinstance(config, dict):
            continue
        categories[str(category)] = {
            "brands": [str(value) for value in config.get("brands", []) or []],
            "keywords": [str(value) for value in config.get("keywords", []) or []],
        }
    return categories
