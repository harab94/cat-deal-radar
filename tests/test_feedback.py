from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app.database import Deal, FeedbackType, Post, Repository
from app.feedback import FeedbackHandler, build_feedback_links
from app.feedback.links import feedback_type_from_action

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / "cat_deal_radar.sqlite")
    repo.initialize()
    yield repo
    repo.close()


def test_build_feedback_links_uses_deal_id_and_action() -> None:
    links = build_feedback_links(base_url="https://example.com/feedback", deal_id=42)

    assert links.more_like_this == "https://example.com/feedback?deal_id=42&action=more"
    assert links.less_like_this == "https://example.com/feedback?deal_id=42&action=less"
    assert links.bought == "https://example.com/feedback?deal_id=42&action=bought"
    assert links.already_have_stock == "https://example.com/feedback?deal_id=42&action=stock"


def test_build_feedback_links_preserves_existing_query_string() -> None:
    links = build_feedback_links(base_url="https://example.com/feedback?token=abc", deal_id=42)

    assert links.more_like_this == "https://example.com/feedback?token=abc&deal_id=42&action=more"


def test_build_feedback_links_can_include_deal_metadata() -> None:
    post = _post()
    deal = _deal(post_id=1)

    links = build_feedback_links(
        base_url="https://example.com/feedback",
        deal_id=42,
        deal=deal,
        post=post,
    )
    params = parse_qs(urlparse(links.more_like_this).query)

    assert params["deal_id"] == ["42"]
    assert params["action"] == ["more"]
    assert params["brand"] == ["百利"]
    assert params["category"] == ["cat_food"]
    assert params["price"] == ["335"]
    assert params["title"] == ["百利原始鸡"]
    assert params["douban_url"] == ["https://www.douban.com/group/topic/123456789/"]


@pytest.mark.parametrize(
    ("action", "feedback_type"),
    [
        ("more", FeedbackType.MORE_LIKE_THIS),
        ("less", FeedbackType.LESS_LIKE_THIS),
        ("bought", FeedbackType.BOUGHT_FROM_THIS),
        ("stock", FeedbackType.ALREADY_HAVE_STOCK),
    ],
)
def test_feedback_type_from_action(action: str, feedback_type: FeedbackType) -> None:
    assert feedback_type_from_action(action) == feedback_type


def test_feedback_type_from_action_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unknown feedback action"):
        feedback_type_from_action("wat")


def test_feedback_handler_stores_feedback(repository: Repository) -> None:
    post = repository.create_post(_post())
    deal = repository.create_deal(_deal(post.id))
    handler = FeedbackHandler(repository)

    feedback = handler.handle(deal_id=deal.id, action="bought")

    assert feedback.feedback_type == FeedbackType.BOUGHT_FROM_THIS
    assert repository.list_feedback_for_deal(deal.id) == [feedback]


def _post() -> Post:
    return Post(
        douban_post_id="123456789",
        title="百利原始鸡 335",
        content="百利原始鸡 335",
        url="https://www.douban.com/group/topic/123456789/",
        created_at=NOW,
        fetched_at=NOW,
    )


def _deal(post_id: int | None) -> Deal:
    assert post_id is not None
    return Deal(
        post_id=post_id,
        category="cat_food",
        brand="百利",
        product_name="百利原始鸡",
        price=335,
        confidence_score=90,
        cat_score=5,
        is_duplicate=False,
        created_at=NOW,
    )
