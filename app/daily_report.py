from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog

from app.database import Repository
from app.notification import EmailConfig, EmailMessage, SmtpEmailSender
from app.settings import Settings, load_settings

logger = structlog.get_logger()
SHANGHAI = ZoneInfo("Asia/Shanghai")


def run(settings: Settings | None = None) -> int:
    settings = settings or load_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)

    with Repository(settings.database_path) as repository:
        repository.initialize()
        runs = repository.list_radar_runs_since(now - timedelta(days=1))

    sender = _email_sender_from_env(settings)
    if sender is None:
        logger.warning("daily_report_skipped_missing_email_configuration")
        return 0

    message = render_daily_report(runs=runs, now=now)
    sender.send(message)
    logger.info("daily_report_sent", run_count=len(runs))
    return 0


def render_daily_report(*, runs, now: datetime) -> EmailMessage:
    report_date = now.astimezone(SHANGHAI).strftime("%Y-%m-%d")
    run_count = len(runs)
    posts_seen = sum(run.posts_seen for run in runs)
    deals_created = sum(run.deals_created for run in runs)
    notifications_sent = sum(run.notifications_sent for run in runs)
    latest_run = (
        runs[0].finished_at.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
        if runs
        else "无"
    )
    expected_runs = 144

    subject = f"🐱猫车雷达日报 {report_date}：运行{run_count}次，推送{notifications_sent}条"
    text_body = f"""猫车雷达日报

日期：{report_date}
统计范围：过去 24 小时

运行概况
- 实际运行：{run_count} 次
- 理论上每 10 分钟应运行：{expected_runs} 次
- 最近一次运行：{latest_run}

处理结果
- 抓到帖子：{posts_seen}
- 生成 deal：{deals_created}
- 邮件推送：{notifications_sent}

说明
GitHub Actions 的定时任务不是严格准点；如果实际运行次数明显少于 144 次，
说明 GitHub 对定时任务做了延迟或合并。
"""
    html_body = f"""<!doctype html>
<html lang="zh-CN">
  <body>
    <h2>猫车雷达日报</h2>
    <p>日期：{report_date}<br>统计范围：过去 24 小时</p>
    <h3>运行概况</h3>
    <ul>
      <li>实际运行：{run_count} 次</li>
      <li>理论上每 10 分钟应运行：{expected_runs} 次</li>
      <li>最近一次运行：{latest_run}</li>
    </ul>
    <h3>处理结果</h3>
    <ul>
      <li>抓到帖子：{posts_seen}</li>
      <li>生成 deal：{deals_created}</li>
      <li>邮件推送：{notifications_sent}</li>
    </ul>
    <p>
      GitHub Actions 的定时任务不是严格准点；如果实际运行次数明显少于 144 次，
      说明 GitHub 对定时任务做了延迟或合并。
    </p>
  </body>
</html>
"""
    return EmailMessage(subject=subject, text_body=text_body, html_body=html_body)


def _email_sender_from_env(settings: Settings) -> SmtpEmailSender | None:
    username = os.environ.get(settings.email_username_env)
    password = os.environ.get(settings.email_password_env)
    sender = os.environ.get(settings.email_sender_env)
    recipient = os.environ.get(settings.email_recipient_env)
    if not all([username, password, sender, recipient]):
        return None

    return SmtpEmailSender(
        EmailConfig(
            smtp_host=settings.email_smtp_host,
            smtp_port=settings.email_smtp_port,
            username=username,
            password=password,
            sender=sender,
            recipient=recipient,
            use_tls=settings.email_use_tls,
        )
    )


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
