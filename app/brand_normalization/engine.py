from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class _AliasRule:
    canonical_name: str
    alias: str
    normalized_alias: str


class BrandNormalizer:
    def __init__(self, alias_rules: list[_AliasRule]) -> None:
        self._alias_rules = sorted(
            alias_rules,
            key=lambda rule: len(rule.normalized_alias),
            reverse=True,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> BrandNormalizer:
        with Path(path).open(encoding="utf-8") as file:
            raw_config = yaml.safe_load(file) or {}

        brand_aliases = raw_config.get("brand_aliases", {})
        return cls.from_mapping(brand_aliases)

    @classmethod
    def from_mapping(cls, brand_aliases: dict[str, Any]) -> BrandNormalizer:
        if not isinstance(brand_aliases, dict):
            msg = "brands.yaml must contain a mapping named brand_aliases."
            raise ValueError(msg)

        rules: list[_AliasRule] = []
        for canonical_name, aliases in brand_aliases.items():
            rules.extend(_rules_for_brand(str(canonical_name), aliases))
        return cls(rules)

    def normalize(self, raw_brand: str) -> str | None:
        normalized_input = _normalize_text(raw_brand)
        if not normalized_input:
            return None

        for rule in self._alias_rules:
            if normalized_input == rule.normalized_alias:
                return rule.canonical_name
        return None

    def find_in_text(self, text: str) -> str | None:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return None

        for rule in self._alias_rules:
            if rule.normalized_alias in normalized_text:
                return rule.canonical_name
        return None

    @property
    def canonical_names(self) -> set[str]:
        return {rule.canonical_name for rule in self._alias_rules}


def _rules_for_brand(canonical_name: str, aliases: Any) -> list[_AliasRule]:
    if aliases is None:
        aliases = []
    if not isinstance(aliases, list):
        msg = f"Aliases for {canonical_name} must be a list."
        raise ValueError(msg)

    raw_aliases = [canonical_name, *[str(alias) for alias in aliases]]
    return [
        _AliasRule(
            canonical_name=canonical_name,
            alias=alias,
            normalized_alias=_normalize_text(alias),
        )
        for alias in raw_aliases
        if _normalize_text(alias)
    ]


def _normalize_text(value: str) -> str:
    return (
        value.casefold()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace("!", "")
    )
