from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from app.brand_candidates import report_brand_candidate
from app.brand_normalization import BrandNormalizer
from app.configuration import load_detection_config
from app.configuration.feishu_base import (
    FeishuBaseConfig,
    FeishuBrandCandidateWriter,
    FeishuFeedbackReader,
)
from app.crawler import DoubanCrawler, DoubanGroupConfig, SmzdmConfig, SmzdmCrawler
from app.database import Deal, Post, Repository
from app.deal_detector import analyze_comments
from app.feedback import build_feedback_links
from app.feedback_sync import sync_feedback_and_update_preferences
from app.notification import (
    DealDigestItem,
    EmailConfig,
    EmailMessage,
    FeishuWebhookConfig,
    FeishuWebhookSender,
    NotificationService,
    PriceContext,
    SmtpEmailSender,
)
from app.recommendation import (
    DuplicateHandler,
    PreferenceLearningEngine,
    RecommendationInput,
    RecommendationScore,
    RecommendationScorer,
)
from app.settings import Settings
from app.sku_catalog import SkuCatalog, SkuMatch

logger = structlog.get_logger()
UNKNOWN_BRAND = "未知品牌"


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
    posts.extend(_smzdm_posts(settings, repository))
    detection_config = load_detection_config(settings)
    detector = _detector_from_config(detection_config)
    sku_catalog = SkuCatalog(detection_config.skus)
    learning_engine = PreferenceLearningEngine.from_yaml(settings.preferences_path)
    feedback_reader = _feedback_reader_from_env(settings)
    if feedback_reader is not None:
        try:
            feedback_sync = sync_feedback_and_update_preferences(
                repository=repository,
                reader=feedback_reader,
                learning_engine=learning_engine,
            )
        except RuntimeError as error:
            logger.warning("feedback_sync_failed", error=str(error))
        else:
            if feedback_sync.preferences_updated:
                learning_engine.save(settings.preferences_path)
            logger.info(
                "feedback_sync_completed",
                records_seen=feedback_sync.records_seen,
                feedback_created=feedback_sync.feedback_created,
                preferences_updated=feedback_sync.preferences_updated,
            )
    scorer = RecommendationScorer(learning_engine.preferences)
    duplicate_handler = DuplicateHandler()
    sender = _notification_sender_from_env(settings)
    feedback_base_url = _feedback_base_url_from_env(settings)
    brand_candidate_reporter = _brand_candidate_reporter_from_env(settings)

    deals_created = 0
    notifications_sent = 0
    detection_diagnostics: list[dict[str, object]] = []
    notification_items: list[DealDigestItem] = []

    for post in posts:
        if repository.has_notification_for_post(
            _require(post.id, "post id")
        ) or repository.has_notification_for_post_title(post.title):
            continue

        rich_content = _rich_post_content(post)
        detected = detector.detect(title=post.title, content=rich_content)
        sku_match = sku_catalog.match(
            brand=detected.brand,
            category=detected.category,
            text=f"{post.title}\n{rich_content}",
        )
        if brand_candidate_reporter is not None:
            try:
                reported = report_brand_candidate(
                    repository=repository,
                    post=post,
                    category=detected.category,
                    brand=detected.brand,
                    reporter=brand_candidate_reporter,
                )
            except RuntimeError as error:
                logger.warning(
                    "brand_candidate_report_failed",
                    post_id=post.id,
                    title=post.title,
                    error=str(error),
                )
            else:
                if reported:
                    logger.info(
                        "brand_candidate_reported",
                        post_id=post.id,
                        title=post.title,
                        category=detected.category,
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
                brand=_deal_brand(detected.brand),
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
            brand=_deal_brand(detected.brand),
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
        try:
            service = NotificationService(repository=repository, sender=sender)
            notifications = service.send_deal_digest(items=notification_items)
        except RuntimeError as error:
            logger.warning(
                "notification_delivery_failed",
                error=str(error),
                deal_ids=[item.deal.id for item in notification_items],
            )
        else:
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


def _smzdm_posts(settings: Settings, repository: Repository) -> list[Post]:
    if not settings.smzdm_enabled or not settings.smzdm_search_urls:
        return []
    try:
        return SmzdmCrawler(
            SmzdmConfig(
                search_urls=settings.smzdm_search_urls,
                include_keywords=settings.smzdm_include_keywords,
            ),
            repository,
        ).run_once()
    except RuntimeError as error:
        logger.warning("smzdm_crawl_failed", error=str(error))
        return []


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


def _deal_brand(brand: str | None) -> str:
    return brand or UNKNOWN_BRAND


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


def _feishu_sender_from_env(settings: Settings) -> FeishuWebhookSender | None:
    webhook_url = os.environ.get(settings.feishu_bot_webhook_env)
    if not webhook_url:
        return None

    return FeishuWebhookSender(
        FeishuWebhookConfig(
            webhook_url=webhook_url,
            secret=os.environ.get(settings.feishu_bot_secret_env),
        )
    )


def _notification_sender_from_env(settings: Settings):
    senders = [
        sender
        for sender in (_email_sender_from_env(settings), _feishu_sender_from_env(settings))
        if sender is not None
    ]
    if not senders:
        return None
    if len(senders) == 1:
        return senders[0]
    return CompositeSender(tuple(senders))


def _feedback_base_url_from_env(settings: Settings) -> str | None:
    value = os.environ.get(settings.feedback_base_url_env)
    if value is None:
        return None

    feedback_base_url = value.strip()
    if not feedback_base_url:
        return None

    lower_url = feedback_base_url.casefold()
    if any(placeholder in lower_url for placeholder in ("example.com", "github.com")):
        logger.warning(
            "feedback_base_url_placeholder_ignored",
            feedback_base_url=feedback_base_url,
        )
        return None

    return feedback_base_url


def _brand_candidate_reporter_from_env(settings: Settings) -> FeishuBrandCandidateWriter | None:
    table_id = os.environ.get(settings.feishu_brand_candidates_table_id_env)
    app_id = os.environ.get(settings.feishu_app_id_env)
    app_secret = os.environ.get(settings.feishu_app_secret_env)
    base_token = os.environ.get(settings.feishu_base_token_env)
    if not all([table_id, app_id, app_secret, base_token]):
        return None

    return FeishuBrandCandidateWriter(
        FeishuBaseConfig(
            app_id=str(app_id),
            app_secret=str(app_secret),
            base_token=str(base_token),
            brands_table_id=os.environ.get(settings.feishu_brands_table_id_env, ""),
            categories_table_id=os.environ.get(settings.feishu_categories_table_id_env, ""),
            detection_rules_table_id=os.environ.get(
                settings.feishu_detection_rules_table_id_env,
                "",
            ),
            skus_table_id=os.environ.get(settings.feishu_skus_table_id_env),
            brand_candidates_table_id=str(table_id),
        )
    )


def _feedback_reader_from_env(settings: Settings) -> FeishuFeedbackReader | None:
    table_id = os.environ.get(settings.feishu_feedback_table_id_env)
    app_id = os.environ.get(settings.feishu_app_id_env)
    app_secret = os.environ.get(settings.feishu_app_secret_env)
    base_token = os.environ.get(settings.feishu_base_token_env)
    if not all([table_id, app_id, app_secret, base_token]):
        return None

    return FeishuFeedbackReader(
        FeishuBaseConfig(
            app_id=str(app_id),
            app_secret=str(app_secret),
            base_token=str(base_token),
            brands_table_id=os.environ.get(settings.feishu_brands_table_id_env, ""),
            categories_table_id=os.environ.get(settings.feishu_categories_table_id_env, ""),
            detection_rules_table_id=os.environ.get(
                settings.feishu_detection_rules_table_id_env,
                "",
            ),
            skus_table_id=os.environ.get(settings.feishu_skus_table_id_env),
            feedback_table_id=str(table_id),
        )
    )


class CompositeSender:
    def __init__(self, senders: tuple) -> None:
        self._senders = senders

    def send(self, message: EmailMessage) -> None:
        for sender in self._senders:
            sender.send(message)


def _send_test_email(settings: Settings, repository: Repository) -> int:
    sender = _notification_sender_from_env(settings)
    feedback_base_url = _feedback_base_url_from_env(settings)
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
