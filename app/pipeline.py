from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from app.crawler import DoubanCrawler, DoubanGroupConfig
from app.database import Deal, Repository
from app.deal_detector import RuleBasedDealDetector, analyze_comments
from app.feedback import build_feedback_links
from app.notification import EmailConfig, NotificationService, SmtpEmailSender
from app.recommendation import DuplicateHandler, RecommendationInput, RecommendationScorer
from app.settings import Settings

logger = structlog.get_logger()


@dataclass(frozen=True)
class PipelineResult:
    posts_seen: int
    deals_created: int
    notifications_sent: int


def run_pipeline(settings: Settings, repository: Repository) -> PipelineResult:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    repository.initialize()

    try:
        posts = DoubanCrawler(_douban_config(settings), repository).run_once()
    except RuntimeError as error:
        logger.warning(
            "douban_crawl_failed",
            error=str(error),
            cookie_configured=bool(os.environ.get(settings.douban_cookie_env)),
        )
        return PipelineResult(posts_seen=0, deals_created=0, notifications_sent=0)
    detector = RuleBasedDealDetector.from_config_files(
        brands_path=settings.brands_path,
        categories_path=settings.categories_path,
    )
    scorer = RecommendationScorer.from_yaml(settings.preferences_path)
    duplicate_handler = DuplicateHandler()
    sender = _email_sender_from_env(settings)
    feedback_base_url = os.environ.get(settings.feedback_base_url_env)

    deals_created = 0
    notifications_sent = 0

    for post in posts:
        detected = detector.detect(title=post.title, content=post.content)
        if not detected.is_deal:
            continue

        recommendation = scorer.score(
            RecommendationInput(
                category=_require(detected.category, "category"),
                brand=_require(detected.brand, "brand"),
                price=_require(detected.price, "price"),
                base_confidence=detected.confidence,
                comment_analysis=analyze_comments([]),
            )
        )
        if not recommendation.should_notify:
            continue

        candidate_deal = Deal(
            post_id=_require(post.id, "post id"),
            category=_require(detected.category, "category"),
            brand=_require(detected.brand, "brand"),
            product_name=_require(detected.product_name, "product name"),
            price=_require(detected.price, "price"),
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
            logger.info("notification_skipped_missing_configuration", deal_id=deal.id)
            continue

        feedback_links = build_feedback_links(
            base_url=feedback_base_url,
            deal_id=_require(deal.id, "deal id"),
        )
        NotificationService(repository=repository, sender=sender).send_deal_notification(
            deal=deal,
            post=post,
            recommendation=recommendation,
            feedback_links=feedback_links,
        )
        notifications_sent += 1

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


def _require[T](value: T | None, name: str) -> T:
    if value is None:
        msg = f"Missing required {name}."
        raise ValueError(msg)
    return value
