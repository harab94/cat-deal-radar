from __future__ import annotations

from dataclasses import dataclass

POSITIVE_COMMENT_SIGNALS = ("还能买", "已上车", "有货", "可买", "刚买")
NEGATIVE_COMMENT_SIGNALS = ("没了", "无货", "下架", "涨价", "车走了", "买不到")


@dataclass(frozen=True)
class CommentAnalysis:
    positive_count: int
    negative_count: int
    confidence_adjustment: int
    has_conflict: bool


def analyze_comments(comments: list[str]) -> CommentAnalysis:
    positive_count = sum(_contains_any(comment, POSITIVE_COMMENT_SIGNALS) for comment in comments)
    negative_count = sum(_contains_any(comment, NEGATIVE_COMMENT_SIGNALS) for comment in comments)

    confidence_adjustment = positive_count * 5 - negative_count * 10
    return CommentAnalysis(
        positive_count=positive_count,
        negative_count=negative_count,
        confidence_adjustment=confidence_adjustment,
        has_conflict=positive_count > 0 and negative_count > 0,
    )


def _contains_any(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)
