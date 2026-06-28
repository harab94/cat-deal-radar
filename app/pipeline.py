from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from app.brand_normalization import BrandNormalizer
from app.configuration import load_detection_config
from app.crawler import DoubanCrawler, DoubanGroupConfig
from app.database import Deal, Post, Repository
from app.deal_detector import analyze_comments
from app.feedback import build_feedback_links
from app.notification import (
    DealDigestItem,
    EmailConfig,
    EmailMessage,
    NotificationService,
    PriceContext,
    SmtpEmailSender,
    WeWorkAppSender,
    WeWorkConfig,
)
from app.recommendation import (
    DuplicateHandler,
    RecommendationInput,
    RecommendationScore,
    RecommendationScorer,
)
from app.settings import Settings
from app.sku_catalog import SkuCatalog, SkuMatch

logger = structlog.get_logger()


@dataclass(frozen=True)
class PipelineResult:
    posts_seen: int
    deals_created: int
    notifications_sent: int


def run_pipeline(settings: Settings, repository: Repository) -> PipelineResult:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    repository.initialize()

    if _send_test_email_enabled():
        notifications_sent = _send_test_email(settings, repository)
        return PipelineResult(
            posts_seen=0,
            deals_created=1 if notifications_sent else 0,
            notifications_sent=notifications_sent,
        )

    try:
        posts = DoubanCrawler(_douban_config(settings), repository).run_once()
    except RuntimeError as error:
        logger.warning(
            "douban_crawl_failed",
            error=str(error),
            cookie_configured=bool(os.environ.get(settings.douban_cookie_env)),
        )
        return PipelineResult(posts_seen=0, deals_created=0, notifications_sent=0)
    detection_config = load_detection_config(settings)
    detector = _detector_from_config(detection_config)
    sku_catalog = SkuCatalog(detection_config.skus)
    scorer = RecommendationScorer.from_yaml(settings.preferences_path)
    duplicate_handler = DuplicateHandler()
    sender = _notification_sender_from_env(settings)
    feedback_base_url = os.environ.get(settings.feedback_base_url_env)

    deals_created = 0
    notifications_sent = 0
    detection_diagnostics: list[dict[str, object]] = []
    notification_items: list[DealDigestItem] = []

    for post in posts:
        rich_content = _rich_post_content(post)
        detected = detector.detect(title=post.title, content=rich_content)
        sku_match = sku_catalog.match(
            brand=detected.brand,
            category=detected.category,
            text=f"{post.title}\n{rich_content}",
        )
        if not detected.is_deal:
            detection_diagnostics.append(
                {
                    "title": post.title,
                    "brand": detected.brand,
                    "category": detected.category,
                    "price": detected.price,
                    "sku": sku_match.sku_key if sku_match else None,
                    "comment_count": len(post.comments),
                    "reasons": detected.reasons,
                }
            )
            continue

        reference_price = sku_match.reference_price if sku_match else None
        recommendation = scorer.score(
            RecommendationInput(
                category=_require(detected.category, "category"),
                brand=_require(detected.brand, "brand"),
                price=detected.price or 0,
                base_confidence=detected.confidence,
                historical_average_price=reference_price,
                comment_analysis=analyze_comments(list(post.comments)),
            )
        )
        if not recommendation.should_notify:
            continue

        candidate_deal = Deal(
            post_id=_require(post.id, "post id"),
            category=_require(detected.category, "category"),
            brand=_require(detected.brand, "brand"),
            product_name=_require(detected.product_name, "product name"),
            price=detected.price or 0,
            confidence_score=recommendation.confidence_score,
            cat_score=recommendation.cat_score,
            is_duplicate=False,
            created_at=datetime.now(UTC),
        )
        duplicate_decision = duplicate_handler.evaluate(candidate_deal, repository.list_deals())
        if not duplicate_decision.should_notify:
            continue

        deal = repository.create_deal(candidate_deal)
        deals_created += 1

        if sender is None or feedback_base_url is None:
            logger.info(
                "notification_skipped_missing_configuration",
                deal_id=deal.id,
            )
            continue

        notification_items.append(
            DealDigestItem(
                deal=deal,
                post=post,
                recommendation=recommendation,
                price_context=_price_context_from_sku_match(sku_match),
                feedback_links=build_feedback_links(
                    base_url=feedback_base_url,
                    deal_id=_require(deal.id, "deal id"),
                    deal=deal,
                    post=post,
                ),
            )
        )

    if notification_items and sender is not None:
        if feedback_base_url and "github.com" in feedback_base_url.casefold():
            logger.warning(
                "feedback_base_url_points_to_github",
                feedback_base_url=feedback_base_url,
            )
        notifications = NotificationService(repository=repository, sender=sender).send_deal_digest(
            items=notification_items,
        )
        notifications_sent = len(notifications)

    if deals_created == 0 and posts:
        logger.info(
            "deal_detection_summary",
            posts_seen=len(posts),
            brand_matches=sum(1 for item in detection_diagnostics if item["brand"]),
            category_matches=sum(1 for item in detection_diagnostics if item["category"]),
            price_matches=sum(1 for item in detection_diagnostics if item["price"] is not None),
            sample=detection_diagnostics[:10],
        )

    return PipelineResult(
        posts_seen=len(posts),
        deals_created=deals_created,
        notifications_sent=notifications_sent,
    )


def _douban_config(settings: Settings) -> DoubanGroupConfig:
    return DoubanGroupConfig(
        group_url=settings.douban_group_url,
        tab_name=settings.douban_tab_name,
        cookie=os.environ.get(settings.douban_cookie_env),
    )


def _detector_from_config(detection_config):
    from app.deal_detector import RuleBasedDealDetector

    return RuleBasedDealDetector(
        brand_normalizer=BrandNormalizer.from_mapping(detection_config.brand_aliases),
        category_config=detection_config.categories,
        deal_signals=detection_config.deal_signals,
        expired_signals=detection_config.expired_signals,
    )


def _rich_post_content(post: Post) -> str:
    return "\n".join(part for part in (post.content, *post.comments) if part)


def _price_context_from_sku_match(match: SkuMatch | None) -> PriceContext | None:
    if match is None:
        return None
    return PriceContext(
        sku_key=match.sku_key,
        product=match.product,
        reference_price=match.reference_price,
        unit=match.unit,
    )


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


def _wework_sender_from_env(settings: Settings) -> WeWorkAppSender | None:
    corp_id = os.environ.get(settings.wework_corp_id_env)
    agent_id = os.environ.get(settings.wework_agent_id_env)
    app_secret = os.environ.get(settings.wework_app_secret_env)
    to_user = os.environ.get(settings.wework_to_user_env)
    if not all([corp_id, agent_id, app_secret, to_user]):
        return None

    return WeWorkAppSender(
        WeWorkConfig(
            corp_id=_require(corp_id, "WeWork corp id"),
            agent_id=_require(agent_id, "WeWork agent id"),
            app_secret=_require(app_secret, "WeWork app secret"),
            to_user=_require(to_user, "WeWork to user"),
        )
    )


def _notification_sender_from_env(settings: Settings):
    senders = [
        sender
        for sender in (_email_sender_from_env(settings), _wework_sender_from_env(settings))
        if sender is not None
    ]
    if not senders:
        return None
    if len(senders) == 1:
        return senders[0]
    return CompositeSender(tuple(senders))


class CompositeSender:
    def __init__(self, senders: tuple) -> None:
        self._senders = senders

    def send(self, message: EmailMessage) -> None:
        for sender in self._senders:
            sender.send(message)


def _send_test_email(settings: Settings, repository: Repository) -> int:
    sender = _notification_sender_from_env(settings)
    feedback_base_url = os.environ.get(settings.feedback_base_url_env)
    if sender is None or feedback_base_url is None:
        logger.warning("test_email_skipped_missing_configuration")
        return 0

    post = repository.create_post_if_new(
        _test_post(),
    ) or _require(
        repository.get_post_by_douban_id("test-email"),
        "test post",
    )
    deal = repository.create_deal(
        Deal(
            post_id=_require(post.id, "post id"),
            category="cat_food",
            brand="百利",
            product_name="测试邮件：百利原始鸡",
            price=335,
            confidence_score=95,
            cat_score=5,
            is_duplicate=False,
            created_at=datetime.now(UTC),
        )
    )
    NotificationService(repository=repository, sender=sender).send_deal_notification(
        deal=deal,
        post=post,
        recommendation=RecommendationScore(
            confidence_score=95,
            cat_score=5,
            should_notify=True,
            reasons=("test email", "Gmail delivery verification"),
        ),
        feedback_links=build_feedback_links(
            base_url=feedback_base_url,
            deal_id=_require(deal.id, "deal id"),
            deal=deal,
            post=post,
        ),
        price_context=PriceContext(
            sku_key="百利|cat_food|原始鸡",
            product="原始鸡",
            reference_price=335,
            unit="包",
        ),
    )
    logger.info("test_email_sent", deal_id=deal.id)
    return 1


def _test_post():
    return Post(
        douban_post_id="test-email",
        title="测试邮件：百利原始鸡 335 元",
        content="这是一封用于验证 Gmail SMTP 投递的测试邮件。",
        url="https://github.com/harab94/cat-deal-radar",
        created_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
    )


def _send_test_email_enabled() -> bool:
    return os.environ.get("CAT_DEAL_RADAR_SEND_TEST_EMAIL", "").casefold() in {"1", "true", "yes"}


def _require[T](value: T | None, name: str) -> T:
    if value is None:
        msg = f"Missing required {name}."
        raise ValueError(msg)
    return value
