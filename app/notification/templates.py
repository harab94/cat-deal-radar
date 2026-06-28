from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import urlparse

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


@dataclass(frozen=True)
class PriceContext:
    sku_key: str
    product: str
    reference_price: float | None
    unit: str | None = None

    def discount_percent(self, current_price: float) -> float | None:
        if current_price <= 0 or self.reference_price is None or self.reference_price <= 0:
            return None
        return max(0.0, (self.reference_price - current_price) / self.reference_price * 100)


@dataclass(frozen=True)
class DealDigestItem:
    deal: Deal
    post: Post
    recommendation: RecommendationScore
    feedback_links: FeedbackLinks
    price_context: PriceContext | None = None


def render_deal_email(
    *,
    deal: Deal,
    post: Post,
    recommendation: RecommendationScore,
    feedback_links: FeedbackLinks,
    price_context: PriceContext | None = None,
) -> EmailMessage:
    cats = "🐱" * recommendation.cat_score
    priority_label = _priority_label(recommendation.cat_score)
    price_label = _price_label(deal.price)
    subject = f"{cats}{priority_label}{deal.product_name} {price_label}"
    reasons = recommendation.reasons or ("No reasons recorded",)
    text_body = _render_text_body(
        deal,
        post,
        recommendation,
        feedback_links,
        reasons,
        price_context,
    )
    html_body = _render_html_body(
        deal,
        post,
        recommendation,
        feedback_links,
        reasons,
        price_context,
    )
    return EmailMessage(subject=subject, text_body=text_body, html_body=html_body)


def render_deal_digest_email(items: list[DealDigestItem]) -> EmailMessage:
    if not items:
        msg = "Cannot render an empty deal digest."
        raise ValueError(msg)
    if len(items) == 1:
        item = items[0]
        return render_deal_email(
            deal=item.deal,
            post=item.post,
            recommendation=item.recommendation,
            feedback_links=item.feedback_links,
            price_context=item.price_context,
        )

    top_item = max(items, key=lambda item: item.recommendation.cat_score)
    subject = (
        f"🐱猫车雷达今日发现 {len(items)} 条："
        f"{top_item.deal.product_name} 等"
    )
    text_body = _render_digest_text_body(items)
    html_body = _render_digest_html_body(items)
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
    price_context: PriceContext | None,
) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in reasons)
    price_context_text = _price_context_text(deal.price, price_context)
    return f"""【推荐理由】
{reason_lines}

【社区信息】
商品：{deal.product_name}
品牌：{deal.brand}
品类：{deal.category}
价格：{_price_label(deal.price)}
{price_context_text}
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
    price_context: PriceContext | None,
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
    price_context_html = _price_context_html(deal.price, price_context)
    category_label = _category_label(deal.category)
    cats = "🐱" * recommendation.cat_score
    douban_url = _public_douban_url(post.url)
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
            {price_context_html}

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
                <a href="{escape(douban_url)}" style="color:#111; font-weight:700;">
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


def _render_digest_text_body(items: list[DealDigestItem]) -> str:
    sections = []
    for index, item in enumerate(items, start=1):
        priority_label = _priority_label(item.recommendation.cat_score)
        title = f"{index}. {priority_label} {item.deal.product_name}"
        sections.append(
            f"""【{title}】
品牌：{item.deal.brand}
品类：{item.deal.category}
价格：{_price_label(item.deal.price)}
{_price_context_text(item.deal.price, item.price_context)}
信心分：{item.recommendation.confidence_score}
原帖：{item.post.url}

快速反馈：
多推类似：{item.feedback_links.more_like_this}
少推类似：{item.feedback_links.less_like_this}
因为这次推荐下单了：{item.feedback_links.bought}
家里还有，下次再买：{item.feedback_links.already_have_stock}
"""
        )
    return "猫车雷达本轮发现\n\n" + "\n".join(sections)


def _render_digest_html_body(items: list[DealDigestItem]) -> str:
    cards = "".join(_digest_card(item, index) for index, item in enumerate(items, start=1))
    return f"""<!doctype html>
<html lang="zh-CN">
  <body style="margin:0; padding:0; background:#ffffff; color:#242424;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
      style="border-collapse:collapse; font-family: Arial, Helvetica, sans-serif;">
      <tr>
        <td style="padding: 36px 28px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
            style="max-width: 820px; margin: 0 auto; border-collapse: collapse;">
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
                      <div style="color: #777;">本轮发现 {len(items)} 条猫咪好价</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="font-family: Georgia, 'Times New Roman', serif;
                font-size: 58px; line-height: 0.96; font-weight: 700; letter-spacing: 0;
                padding-bottom: 24px;">
                今日猫车合集
              </td>
            </tr>
            <tr>
              <td style="border-top: 2px solid #222; padding-top: 26px;
                padding-bottom: 8px;">
                <div style="font-size: 14px; font-weight: 700; color: #666;
                  text-transform: uppercase; letter-spacing: 0.08em;">
                  DEAL HIGHLIGHTS
                </div>
              </td>
            </tr>
            {cards}
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _digest_card(item: DealDigestItem, index: int) -> str:
    deal = item.deal
    recommendation = item.recommendation
    post = item.post
    feedback_links = item.feedback_links
    cats = "🐱" * recommendation.cat_score
    priority_label = _priority_label(recommendation.cat_score)
    reasons = " · ".join(recommendation.reasons[:3]) or "推荐理由待补充"
    price_context_html = _price_context_html(deal.price, item.price_context, compact=True)
    douban_url = _public_douban_url(post.url)
    return f"""
            <tr>
              <td style="padding: 24px 0; border-bottom: 1px solid #e5e5e5;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                  style="border-collapse: collapse;">
                  <tr>
                    <td style="font-size: 14px; color: #777; padding-bottom: 10px;">
                      #{index} {escape(priority_label)} · {cats} ·
                      信心分 {recommendation.confidence_score}
                    </td>
                  </tr>
                  <tr>
                    <td style="font-size: 28px; line-height: 1.2; font-weight: 800;
                      padding-bottom: 10px;">
                      {escape(deal.product_name)}
                    </td>
                  </tr>
                  <tr>
                    <td style="font-size: 18px; line-height: 1.45; color: #666;
                      padding-bottom: 12px;">
                      {escape(deal.brand)} · {escape(_category_label(deal.category))} ·
                      <strong style="color:#111;">{escape(_price_label(deal.price))}</strong>
                    </td>
                  </tr>
                  {price_context_html}
                  <tr>
                    <td style="font-size: 16px; line-height: 1.5; color: #555;
                      padding-bottom: 16px;">
                      推荐理由：{escape(reasons)}
                    </td>
                  </tr>
                  <tr>
                    <td style="padding-bottom: 14px;">
                      {_button(feedback_links.more_like_this, "❤️ 多推")}
                      <span style="display:inline-block; width:8px;"></span>
                      {_button(feedback_links.less_like_this, "🙈 少推")}
                      <span style="display:inline-block; width:8px;"></span>
                      {_button(feedback_links.bought, "🛍️ 已下单")}
                      <span style="display:inline-block; width:8px;"></span>
                      {_button(feedback_links.already_have_stock, "📦 家里还有")}
                    </td>
                  </tr>
                  <tr>
                    <td style="font-size: 15px;">
                      <a href="{escape(douban_url)}" style="color:#111; font-weight:700;">
                        打开豆瓣原帖 →
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
"""


def _price_label(price: float) -> str:
    if price <= 0:
        return "价格未知"
    return f"{price:g}元"


def _public_douban_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc in {"www.douban.com", "douban.com"} and parsed.path.startswith(
        "/group/topic/"
    ):
        return f"https://m.douban.com{parsed.path}"
    return url


def _price_context_text(price: float, context: PriceContext | None) -> str:
    if context is None:
        return ""
    reference = "参考价未知"
    if context.reference_price is not None and context.reference_price > 0:
        unit = f"/{context.unit}" if context.unit else ""
        reference = f"参考价：{context.reference_price:g}元{unit}"
    discount = context.discount_percent(price)
    discount_label = f"，便宜约 {discount:.0f}%" if discount is not None else ""
    return f"SKU：{context.sku_key}\n{reference}{discount_label}"


def _price_context_html(
    price: float,
    context: PriceContext | None,
    *,
    compact: bool = False,
) -> str:
    if context is None:
        return ""
    discount = context.discount_percent(price)
    reference = "参考价未知"
    if context.reference_price is not None and context.reference_price > 0:
        unit = f"/{context.unit}" if context.unit else ""
        reference = f"参考价 {context.reference_price:g}元{unit}"
    discount_label = f"便宜约 {discount:.0f}%" if discount is not None else "折扣待判断"
    padding = "0 0 12px" if compact else "0 0 26px"
    font_size = "15px" if compact else "18px"
    return f"""
                  <tr>
                    <td style="padding: {padding};">
                      <span style="display:inline-block; padding: 8px 11px;
                        background:#fff3c4; border:1px solid #e8cf7a;
                        font-size:{font_size}; font-weight:700;">
                        {escape(reference)} · {escape(discount_label)}
                      </span>
                    </td>
                  </tr>
"""


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
