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
class SkuReference:
    sku_key: str
    brand: str
    category: str
    product: str
    aliases: tuple[str, ...]
    reference_price: float | None = None
    unit: str | None = None


@dataclass(frozen=True)
class DetectionConfig:
    brand_aliases: dict[str, list[str]]
    categories: dict[str, dict[str, list[str]]]
    skus: tuple[SkuReference, ...]
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
            logger.info(
                "feishu_detection_config_loaded",
                brand_count=len(config.brand_aliases),
                category_count=len(config.categories),
                sku_count=len(config.skus),
                deal_signal_count=len(config.deal_signals),
                expired_signal_count=len(config.expired_signals),
            )
            return config
        except Exception as error:
            logger.warning("feishu_detection_config_failed", error=str(error))
    else:
        logger.info(
            "feishu_detection_config_not_configured",
            missing_envs=_missing_required_feishu_env(settings),
        )

    logger.info("local_detection_config_loaded_without_brand_aliases")
    return _load_local_detection_config(
        brands_path=settings.brands_path,
        categories_path=settings.categories_path,
        skus_path=settings.skus_path,
        include_brand_aliases=False,
    )


def _load_local_detection_config(
    *,
    brands_path: Path,
    categories_path: Path,
    skus_path: Path,
    include_brand_aliases: bool = True,
) -> DetectionConfig:
    brand_aliases = {}
    if include_brand_aliases:
        with brands_path.open(encoding="utf-8") as file:
            brand_config = yaml.safe_load(file) or {}
            brand_aliases = brand_config.get("brand_aliases", {})
    with categories_path.open(encoding="utf-8") as file:
        categories = yaml.safe_load(file) or {}
    skus = _load_local_skus(skus_path)

    return DetectionConfig(
        brand_aliases=_normalize_brand_aliases(brand_aliases),
        categories=_normalize_categories(categories),
        skus=tuple(skus),
        deal_signals=DEAL_SIGNALS,
        expired_signals=EXPIRED_SIGNALS,
    )


def _feishu_config_from_env(settings: Settings) -> FeishuBaseConfig | None:
    values = {
        "app_id": _env_value(settings.feishu_app_id_env),
        "app_secret": _env_value(settings.feishu_app_secret_env),
        "base_token": _env_value(settings.feishu_base_token_env),
        "brands_table_id": _env_value(settings.feishu_brands_table_id_env),
        "categories_table_id": _env_value(settings.feishu_categories_table_id_env),
        "detection_rules_table_id": _env_value(settings.feishu_detection_rules_table_id_env),
        "skus_table_id": _env_value(settings.feishu_skus_table_id_env),
        "brand_candidates_table_id": _env_value(settings.feishu_brand_candidates_table_id_env),
    }
    optional_keys = {
        "detection_rules_table_id",
        "skus_table_id",
        "brand_candidates_table_id",
    }
    required_values = {key: value for key, value in values.items() if key not in optional_keys}
    if not all(required_values.values()):
        return None
    return FeishuBaseConfig(**values)  # type: ignore[arg-type]


def _missing_required_feishu_env(settings: Settings) -> tuple[str, ...]:
    required_envs = (
        settings.feishu_app_id_env,
        settings.feishu_app_secret_env,
        settings.feishu_base_token_env,
        settings.feishu_brands_table_id_env,
        settings.feishu_categories_table_id_env,
    )
    return tuple(name for name in required_envs if not _env_value(name))


def _env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip()


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


def _load_local_skus(path: Path) -> list[SkuReference]:
    if not path.exists():
        return []

    with path.open(encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    records = raw.get("skus", [])
    if not isinstance(records, list):
        return []

    skus: list[SkuReference] = []
    for record in records:
        if not isinstance(record, dict) or record.get("enabled", True) is False:
            continue
        sku = _sku_from_mapping(record)
        if sku.brand and sku.category and sku.product:
            skus.append(sku)
    return skus


def _sku_from_mapping(record: dict[str, Any]) -> SkuReference:
    brand = str(record.get("brand", "")).strip()
    category = str(record.get("category", "")).strip()
    product = str(record.get("product", "")).strip()
    sku_key = str(record.get("sku_key") or _sku_key(brand, category, product)).strip()
    aliases = tuple(str(alias).strip() for alias in record.get("aliases", []) or [] if alias)
    reference_price = _optional_float(record.get("reference_price"))
    unit = str(record.get("unit", "")).strip() or None
    return SkuReference(
        sku_key=sku_key,
        brand=brand,
        category=category,
        product=product,
        aliases=aliases,
        reference_price=reference_price,
        unit=unit,
    )


def _sku_key(brand: str, category: str, product: str) -> str:
    return "|".join(part for part in (brand, category, product) if part)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
