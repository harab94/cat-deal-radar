from __future__ import annotations

from dataclasses import dataclass
from html import escape

from app.database import Deal, Post
from app.recommendation import RecommendationScore


@dataclass(frozen=True)
class FeedbackLinks:
    more_like_this: str
    less_like_this: str
    bought: str
    already_have_stock: str


@dataclass(frozen=True)
class EmailMessage:
    subject: str
    text_body: str
    html_body: str


def render_deal_email(
    *,
    deal: Deal,
    post: Post,
    recommendation: RecommendationScore,
    feedback_links: FeedbackLinks,
) -> EmailMessage:
    cats = "🐱" * recommendation.cat_score
    priority_label = _priority_label(recommendation.cat_score)
    price_label = _price_label(deal.price)
    subject = f"{cats}{priority_label}{deal.product_name} {price_label}"
    reasons = recommendation.reasons or ("No reasons recorded",)
    text_body = _render_text_body(deal, post, recommendation, feedback_links, reasons)
    html_body = _render_html_body(deal, post, recommendation, feedback_links, reasons)
    return EmailMessage(subject=subject, text_body=text_body, html_body=html_body)


def _priority_label(cat_score: int) -> str:
    if cat_score >= 5:
        return "【必抢】"
    if cat_score >= 4:
        return "【推荐】"
    return "【可看】"


def _render_text_body(
    deal: Deal,
    post: Post,
    recommendation: RecommendationScore,
    feedback_links: FeedbackLinks,
    reasons: tuple[str, ...],
) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in reasons)
    return f"""【推荐理由】
{reason_lines}

【社区信息】
商品：{deal.product_name}
品牌：{deal.brand}
品类：{deal.category}
价格：{_price_label(deal.price)}
信心分：{recommendation.confidence_score}
原帖标题：{post.title}

【快速反馈】
多推类似：{feedback_links.more_like_this}
少推类似：{feedback_links.less_like_this}
因为这次推荐下单了：{feedback_links.bought}
家里还有，下次再买：{feedback_links.already_have_stock}

原帖链接：
{post.url}
"""


def _render_html_body(
    deal: Deal,
    post: Post,
    recommendation: RecommendationScore,
    feedback_links: FeedbackLinks,
    reasons: tuple[str, ...],
) -> str:
    reason_items = "".join(
        f"""
        <tr>
          <td style="padding: 8px 0; font-size: 16px; line-height: 1.5;">
            <span style="color: #f59e0b;">✦</span>
            {escape(reason)}
          </td>
        </tr>
        """
        for reason in reasons
    )
    priority_label = _priority_label(recommendation.cat_score)
    price_label = _price_label(deal.price)
    category_label = _category_label(deal.category)
    cats = "🐱" * recommendation.cat_score
    return f"""<!doctype html>
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
                      <div style="color: #777;">为 Hara 发现猫咪好价</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="font-family: Georgia, 'Times New Roman', serif;
                font-size: 58px; line-height: 0.96; font-weight: 700; letter-spacing: 0;
                padding-bottom: 24px;">
                今日猫车提醒
              </td>
            </tr>
            <tr>
              <td style="border-top: 2px solid #222; padding-top: 26px;
                padding-bottom: 28px;">
                <div style="font-size: 14px; font-weight: 700; color: #666;
                  text-transform: uppercase; letter-spacing: 0.08em;">
                  DEAL HIGHLIGHT
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding-bottom: 20px;">
                <span style="display: inline-block; padding: 7px 12px;
                  border: 1px solid #222; border-radius: 999px; font-weight: 700;
                  font-size: 14px;">
                  {escape(priority_label)}
                </span>
                <span style="display: inline-block; margin-left: 8px; color: #777;
                  font-size: 15px;">
                  {cats} · 信心分 {recommendation.confidence_score}
                </span>
              </td>
            </tr>

            <tr>
              <td style="padding-bottom: 10px;">
                <h1 style="margin: 0; font-size: 36px; line-height: 1.16;
                  font-weight: 800;">
                  {escape(deal.product_name)}
                </h1>
              </td>
            </tr>
            <tr>
              <td style="font-size: 24px; line-height: 1.3; color: #666;
                padding-bottom: 26px;">
                {escape(deal.brand)} · {escape(category_label)} ·
                <strong style="color: #111;">{escape(price_label)}</strong>
              </td>
            </tr>

            <tr>
              <td style="padding: 22px 0; border-top: 1px solid #e5e5e5;
                border-bottom: 1px solid #e5e5e5;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                  style="border-collapse: collapse;">
                  <tr>
                    <td style="font-size: 13px; color: #777; padding-bottom: 6px;">
                      原帖标题
                    </td>
                  </tr>
                  <tr>
                    <td style="font-size: 18px; line-height: 1.5; font-weight: 700;">
                      {escape(post.title)}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding-top: 28px;">
                <h2 style="margin: 0 0 12px; font-size: 22px;">推荐理由</h2>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                  style="border-collapse: collapse;">
                  {reason_items}
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding-top: 30px;">
                <table role="presentation" cellspacing="0" cellpadding="0"
                  style="border-collapse: collapse;">
                  <tr>
                    <td style="padding: 0 10px 12px 0;">
                      {_button(feedback_links.more_like_this, "❤️ 多推类似")}
                    </td>
                    <td style="padding: 0 10px 12px 0;">
                      {_button(feedback_links.less_like_this, "🙈 少推类似")}
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 0 10px 12px 0;">
                      {_button(feedback_links.bought, "🛍️ 已下单")}
                    </td>
                    <td style="padding: 0 10px 12px 0;">
                      {_button(feedback_links.already_have_stock, "📦 家里还有")}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding-top: 18px; font-size: 16px;">
                <a href="{escape(post.url)}" style="color:#111; font-weight:700;">
                  打开豆瓣原帖 →
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _price_label(price: float) -> str:
    if price <= 0:
        return "价格未知"
    return f"{price:g}元"


def _category_label(category: str) -> str:
    labels = {
        "cat_food": "猫粮",
        "wet_food": "罐头/湿粮",
        "freeze_dried": "冻干",
        "cat_litter": "猫砂",
    }
    return labels.get(category, category)


def _button(url: str, label: str) -> str:
    return (
        f'<a href="{escape(url)}" style="display:inline-block; padding:12px 16px; '
        "border:1px solid #222; border-radius:999px; color:#111; "
        'font-weight:700; text-decoration:none; font-size:15px;">'
        f"{escape(label)}</a>"
    )
