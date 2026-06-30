from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.database import Post, Repository

CATEGORY_MARKERS = {
    "cat_food": ("猫粮", "主粮"),
    "wet_food": ("罐头", "餐包", "湿粮"),
    "freeze_dried": ("冻干",),
    "cat_litter": ("猫砂", "豆腐砂", "木薯砂"),
}

NOISE_WORDS = {
    "闲置",
    "闲车",
    "开车",
    "出",
    "求",
    "救救孩子",
    "官旗",
    "禁拼多多",
}


@dataclass(frozen=True)
class BrandCandidate:
    candidate_brand: str
    category: str
    post_title: str
    post_url: str
    source: str = "system_auto"
    status: str = "needs_review"
    note: str = "系统自动发现，需人工审核后再加入正式 Brands/Categories 表"


def candidate_from_post(
    *,
    title: str,
    category: str | None,
    brand: str | None,
) -> BrandCandidate | None:
    if brand is not None or category is None:
        return None

    candidate = _candidate_brand_from_title(title, category)
    if candidate is None:
        return None

    return BrandCandidate(
        candidate_brand=candidate,
        category=category,
        post_title=title,
        post_url="",
    )


def report_brand_candidate(
    *,
    repository: Repository,
    post: Post,
    category: str | None,
    brand: str | None,
    reporter,
) -> bool:
    candidate = candidate_from_post(title=post.title, category=category, brand=brand)
    if candidate is None or post.id is None:
        return False
    if repository.has_brand_candidate_report(
        post_id=post.id,
        candidate_brand=candidate.candidate_brand,
    ):
        return False

    reporter.report(
        BrandCandidate(
            candidate_brand=candidate.candidate_brand,
            category=candidate.category,
            post_title=post.title,
            post_url=post.url,
            source=candidate.source,
            status=candidate.status,
            note=candidate.note,
        )
    )
    repository.create_brand_candidate_report(
        post_id=post.id,
        candidate_brand=candidate.candidate_brand,
        category=candidate.category,
        reported_at=datetime.now(UTC),
    )
    return True


def _candidate_brand_from_title(title: str, category: str) -> str | None:
    markers = CATEGORY_MARKERS.get(category, ())
    if not markers:
        return None

    normalized = _strip_tags(title)
    for marker in markers:
        index = normalized.find(marker)
        if index <= 0:
            continue
        prefix = normalized[:index]
        candidate = _last_meaningful_token(prefix)
        if candidate:
            return candidate
    return None


def _strip_tags(value: str) -> str:
    return re.sub(r"【[^】]*】|\[[^\]]*\]", " ", value)


def _last_meaningful_token(value: str) -> str | None:
    tokens = re.split(r"[\s,，。；;:：|｜/、()（）]+", value)
    for token in reversed(tokens):
        cleaned = _clean_candidate(token)
        if cleaned:
            return cleaned
    return None


def _clean_candidate(value: str) -> str | None:
    cleaned = re.sub(r"^\d+(?:\.\d+)?|(?:\d+(?:\.\d+)?)$", "", value.strip())
    cleaned = re.sub(r"[^\w\u4e00-\u9fff&]+", "", cleaned)
    for word in NOISE_WORDS:
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.strip()
    if not 1 < len(cleaned) <= 24:
        return None
    if cleaned.isdigit():
        return None
    return cleaned
