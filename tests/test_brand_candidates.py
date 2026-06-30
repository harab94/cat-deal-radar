from datetime import UTC, datetime
from pathlib import Path

from app.brand_candidates import candidate_from_post, report_brand_candidate
from app.database import Post, Repository


def test_candidate_from_post_extracts_unknown_brand_before_category_marker() -> None:
    candidate = candidate_from_post(
        title="【闲置】德金猫粮野猪45/斤，2斤包邮",
        category="cat_food",
        brand=None,
    )

    assert candidate is not None
    assert candidate.candidate_brand == "德金"
    assert candidate.category == "cat_food"
    assert candidate.source == "system_auto"
    assert candidate.status == "needs_review"


def test_candidate_from_post_ignores_known_brand() -> None:
    assert (
        candidate_from_post(
            title="【闲置】百利猫粮 200元",
            category="cat_food",
            brand="百利",
        )
        is None
    )


def test_report_brand_candidate_writes_once_per_post_and_candidate(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "radar.sqlite")
    repository.initialize()
    post = repository.create_post(
        Post(
            douban_post_id="brand-candidate",
            title="【闲置】德金猫粮野猪45/斤，2斤包邮",
            content="【闲置】德金猫粮野猪45/斤，2斤包邮",
            url="https://www.douban.com/group/topic/brand-candidate/",
            created_at=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
        )
    )
    reporter = _Reporter()

    first = report_brand_candidate(
        repository=repository,
        post=post,
        category="cat_food",
        brand=None,
        reporter=reporter,
    )
    second = report_brand_candidate(
        repository=repository,
        post=post,
        category="cat_food",
        brand=None,
        reporter=reporter,
    )

    assert first is True
    assert second is False
    assert [candidate.candidate_brand for candidate in reporter.candidates] == ["德金"]


class _Reporter:
    def __init__(self) -> None:
        self.candidates = []

    def report(self, candidate) -> None:
        self.candidates.append(candidate)
