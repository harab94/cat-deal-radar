from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMDealClassification:
    is_deal: bool
    category: str | None
    brand: str | None
    product_name: str | None
    price: float | None
    confidence: int


def parse_llm_classification(raw_response: str) -> LLMDealClassification:
    data = json.loads(_strip_markdown_fence(raw_response))
    if not isinstance(data, dict):
        msg = "LLM classification response must be a JSON object."
        raise ValueError(msg)

    return LLMDealClassification(
        is_deal=bool(data.get("is_deal", False)),
        category=_optional_str(data.get("category")),
        brand=_optional_str(data.get("brand")),
        product_name=_optional_str(data.get("product_name")),
        price=_optional_float(data.get("price")),
        confidence=_bounded_int(data.get("confidence", 0), minimum=0, maximum=100),
    )


def _strip_markdown_fence(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))
