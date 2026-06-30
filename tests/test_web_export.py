from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.database import Deal, Post, RadarRun, Repository
from app.web_export import export_latest_deals, latest_deals_payload

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


def test_latest_deals_payload_returns_empty_list_when_database_missing(tmp_path: Path) -> None:
    payload = latest_deals_payload(database_path=tmp_path / "missing.sqlite")

    assert payload["latest_run"] is None
    assert payload["deals"] == []


def test_export_latest_deals_writes_recent_non_duplicate_deals(tmp_path: Path) -> None:
    database_path = tmp_path / "cat_deal_radar.sqlite"
    output_path = tmp_path / "latest-deals.json"
    repository = Repository(database_path)
    repository.initialize()
    old_post = repository.create_post(_post("old", title="旧猫粮"))
    new_post = repository.create_post(_post("new", title="新罐头"))
    duplicate_post = repository.create_post(_post("duplicate", title="重复猫砂"))
    repository.create_deal(_deal(old_post.id, product_name="旧猫粮", created_at=NOW))
    newest = repository.create_deal(
        _deal(
            new_post.id,
            product_name="新罐头",
            category="wet_food",
            created_at=NOW + timedelta(minutes=1),
        )
    )
    repository.create_deal(
        _deal(
            duplicate_post.id,
            product_name="重复猫砂",
            category="cat_litter",
            created_at=NOW + timedelta(minutes=2),
            is_duplicate=True,
        )
    )
    repository.create_radar_run(
        RadarRun(
            started_at=NOW,
            finished_at=NOW + timedelta(minutes=2),
            posts_seen=5,
            deals_created=2,
            notifications_sent=2,
        )
    )
    repository.close()

    export_latest_deals(database_path=database_path, output_path=output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["latest_run"]["posts_seen"] == 5
    assert [deal["product_name"] for deal in payload["deals"]] == ["新罐头", "旧猫粮"]
    assert payload["deals"][0]["id"] == newest.id
    assert payload["deals"][0]["category"] == "wet_food"
    assert payload["deals"][0]["post_url"] == "https://m.douban.com/group/topic/new/"


def _post(douban_post_id: str, *, title: str) -> Post:
    return Post(
        douban_post_id=douban_post_id,
        title=title,
        content=title,
        url=f"https://www.douban.com/group/topic/{douban_post_id}/",
        created_at=NOW,
        fetched_at=NOW,
    )


def _deal(
    post_id: int | None,
    *,
    product_name: str,
    category: str = "cat_food",
    created_at: datetime,
    is_duplicate: bool = False,
) -> Deal:
    assert post_id is not None
    return Deal(
        post_id=post_id,
        category=category,
        brand="百利",
        product_name=product_name,
        price=335.0,
        confidence_score=92,
        cat_score=5,
        is_duplicate=is_duplicate,
        created_at=created_at,
    )
