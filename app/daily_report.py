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
    run_health = _run_health_label(run_count, expected_runs)
    html_body = f"""<!doctype html>
<html lang="zh-CN">
  <body style="margin:0; padding:0; background:#ffffff; color:#242424;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
      style="border-collapse:collapse; font-family: Arial, Helvetica, sans-serif;">
      <tr>
        <td style="padding: 36px 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
            style="max-width: 760px; margin: 0 auto; border-collapse: collapse;">
            <tr>
              <td style="padding-bottom: 28px;">
                <table role="presentation" cellspacing="0" cellpadding="0"
                  style="border-collapse: collapse;">
                  <tr>
                    <td style="width: 52px; height: 52px; border-radius: 50%;
                      background: #fff3c4; text-align: center; font-size: 28px;">
                      🐱
                    </td>
                    <td style="padding-left: 14px; font-size: 18px; line-height: 1.4;">
                      <div style="font-weight: 700;">Cat Deal Radar</div>
                      <div style="color: #777;">每日运行摘要 · {report_date}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="font-family: Georgia, 'Times New Roman', serif;
                font-size: 58px; line-height: 0.96; font-weight: 700; letter-spacing: 0;
                padding-bottom: 24px;">
                猫车雷达日报
              </td>
            </tr>
            <tr>
              <td style="border-top: 2px solid #222; padding-top: 26px;
                padding-bottom: 26px;">
                <div style="font-size: 14px; font-weight: 700; color: #666;
                  text-transform: uppercase; letter-spacing: 0.08em;">
                  TODAY'S RADAR CHECK
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding-bottom: 24px;">
                <h1 style="margin:0; font-size: 34px; line-height: 1.18;">
                  过去 24 小时运行 {run_count} 次，推送 {notifications_sent} 条
                </h1>
                <p style="margin: 12px 0 0; font-size: 20px; line-height: 1.45;
                  color: #666;">
                  最近一次运行：{latest_run} · 状态：{run_health}
                </p>
              </td>
            </tr>

            <tr>
              <td style="padding: 20px 0; border-top: 1px solid #e5e5e5;
                border-bottom: 1px solid #e5e5e5;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                  style="border-collapse: collapse;">
                  <tr>
                    {_metric_cell("实际运行", f"{run_count} 次")}
                    {_metric_cell("抓到帖子", str(posts_seen))}
                    {_metric_cell("邮件推送", str(notifications_sent))}
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding-top: 26px;">
                <h2 style="margin: 0 0 12px; font-size: 22px;">运行说明</h2>
                <p style="margin:0; font-size: 17px; line-height: 1.6; color:#555;">
                  理论上每 10 分钟应运行 {expected_runs} 次。GitHub Actions 的定时任务
                  不是严格准点；如果实际运行次数明显少于 {expected_runs} 次，
                  说明 GitHub 对定时任务做了延迟或合并。
                </p>
              </td>
            </tr>

            <tr>
              <td style="padding-top: 24px; font-size: 16px; color:#666;">
                生成 deal：{deals_created} · 统计范围：过去 24 小时
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return EmailMessage(subject=subject, text_body=text_body, html_body=html_body)


def _run_health_label(run_count: int, expected_runs: int) -> str:
    if run_count >= expected_runs * 0.8:
        return "稳定"
    if run_count >= expected_runs * 0.3:
        return "有延迟"
    return "运行偏少"


def _metric_cell(label: str, value: str) -> str:
    return f"""<td style="width: 33.33%; padding-right: 14px;">
      <div style="font-size: 13px; color: #777; padding-bottom: 8px;">{label}</div>
      <div style="font-size: 30px; font-weight: 800; line-height: 1;">{value}</div>
    </td>"""


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
