from __future__ import annotations

import structlog

from app.database import Repository
from app.pipeline import run_pipeline
from app.settings import Settings, load_settings

logger = structlog.get_logger()


def run(settings: Settings | None = None) -> int:
    settings = settings or load_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    with Repository(settings.database_path) as repository:
        result = run_pipeline(settings, repository)

    logger.info(
        "cat_deal_radar_finished",
        database_path=str(settings.database_path),
        douban_group_url=settings.douban_group_url,
        douban_tab_name=settings.douban_tab_name,
        posts_seen=result.posts_seen,
        deals_created=result.deals_created,
        notifications_sent=result.notifications_sent,
    )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
