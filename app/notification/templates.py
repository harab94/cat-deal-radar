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
    reason_items = "".join(f"<li>{escape(reason)}</li>" for reason in reasons)
    return f"""<!doctype html>
<html lang="zh-CN">
  <body>
    <h2>{escape(deal.product_name)} {escape(_price_label(deal.price))}</h2>
    <h3>推荐理由</h3>
    <ul>{reason_items}</ul>
    <h3>社区信息</h3>
    <p>
      品牌：{escape(deal.brand)}<br>
      品类：{escape(deal.category)}<br>
      信心分：{recommendation.confidence_score}<br>
      原帖标题：{escape(post.title)}
    </p>
    <h3>快速反馈</h3>
    <p>
      <a href="{escape(feedback_links.more_like_this)}">❤️ 多推类似</a><br>
      <a href="{escape(feedback_links.less_like_this)}">🙈 少推类似</a><br>
      <a href="{escape(feedback_links.bought)}">🛍️ 因为这次推荐下单了</a><br>
      <a href="{escape(feedback_links.already_have_stock)}">📦 家里还有，下次再买</a>
    </p>
    <p><a href="{escape(post.url)}">打开豆瓣原帖</a></p>
  </body>
</html>
"""


def _price_label(price: float) -> str:
    if price <= 0:
        return "价格未知"
    return f"{price:g}元"
