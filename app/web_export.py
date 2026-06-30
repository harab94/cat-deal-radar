from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_PATH = Path("data/latest-deals.json")


def export_latest_deals(
    *,
    database_path: Path,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    limit: int = 20,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = latest_deals_payload(database_path=database_path, limit=limit)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def latest_deals_payload(*, database_path: Path, limit: int = 20) -> dict[str, Any]:
    if not database_path.exists():
        return {
            "published_at": _now_iso(),
            "latest_run": None,
            "deals": [],
        }

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        latest_run = connection.execute(
            """
            SELECT finished_at, posts_seen, deals_created, notifications_sent
            FROM radar_runs
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        rows = connection.execute(
            """
            SELECT
              deals.id,
              deals.category,
              deals.brand,
              deals.product_name,
              deals.price,
              deals.confidence_score,
              deals.cat_score,
              deals.created_at,
              posts.title AS post_title,
              posts.url AS post_url
            FROM deals
            JOIN posts ON posts.id = deals.post_id
            WHERE deals.is_duplicate = 0
            ORDER BY deals.created_at DESC, deals.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return {
        "published_at": _now_iso(),
        "latest_run": dict(latest_run) if latest_run else None,
        "deals": [_deal_from_row(row) for row in rows],
    }


def main() -> None:
    from app.settings import load_settings

    settings = load_settings()
    export_latest_deals(database_path=settings.database_path)


def _deal_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "category": row["category"],
        "brand": row["brand"],
        "product_name": row["product_name"],
        "price": row["price"],
        "confidence_score": row["confidence_score"],
        "cat_score": row["cat_score"],
        "created_at": row["created_at"],
        "post_title": row["post_title"],
        "post_url": _public_douban_url(row["post_url"]),
    }


def _public_douban_url(url: str) -> str:
    marker = "https://www.douban.com/group/topic/"
    if url.startswith(marker):
        return "https://m.douban.com/group/topic/" + url.removeprefix(marker)
    return url


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    main()
