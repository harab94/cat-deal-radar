from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.daily_report import render_daily_report
from app.database import RadarRun

NOW = datetime(2026, 6, 28, 1, 0, tzinfo=UTC)


def test_render_daily_report_summarizes_recent_runs() -> None:
    message = render_daily_report(
        runs=[
            RadarRun(
                started_at=NOW - timedelta(minutes=10),
                finished_at=NOW - timedelta(minutes=9),
                posts_seen=55,
                deals_created=2,
                notifications_sent=2,
            ),
            RadarRun(
                started_at=NOW - timedelta(minutes=20),
                finished_at=NOW - timedelta(minutes=19),
                posts_seen=54,
                deals_created=1,
                notifications_sent=1,
            ),
        ],
        now=NOW,
    )

    assert message.subject == "🐱猫车雷达日报 2026-06-28：运行2次，推送3条"
    assert "实际运行：2 次" in message.text_body
    assert "距离最近一次运行：9 分钟前" in message.text_body
    assert "抓到帖子：109" in message.text_body
    assert "生成 deal：3" in message.text_body
    assert "邮件推送：3" in message.text_body


def test_render_daily_report_warns_when_radar_has_not_run_recently() -> None:
    message = render_daily_report(
        runs=[
            RadarRun(
                started_at=NOW - timedelta(hours=2),
                finished_at=NOW - timedelta(hours=2),
                posts_seen=55,
                deals_created=0,
                notifications_sent=0,
            ),
        ],
        now=NOW,
    )

    assert message.subject.startswith("⚠️猫车雷达日报")
    assert "告警：超过 30 分钟未运行" in message.text_body
