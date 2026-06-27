from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.crawler import DoubanCrawler, DoubanGroupConfig
from app.database import Deal, FeedbackType, Repository
from app.deal_detector import RuleBasedDealDetector, analyze_comments
from app.feedback import FeedbackHandler, build_feedback_links
from app.notification import EmailMessage, NotificationService
from app.recommendation import (
    DuplicateHandler,
    PreferenceLearningEngine,
    RecommendationInput,
    RecommendationScorer,
)

HTML = """
<html>
  <body>
    <a href="/group/topic/123456789/" data-created-at="2026-06-27T12:00:00+08:00">
      闲车 百利原始鸡 335 元
    </a>
  </body>
</html>
"""


def test_full_pipeline_from_post_to_feedback_and_learning(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_fetch_html(*args, **kwargs) -> str:
        return HTML

    monkeypatch.setattr("app.crawler.douban.fetch_html", fake_fetch_html)

    repository = Repository(tmp_path / "cat_deal_radar.sqlite")
    repository.initialize()

    crawler = DoubanCrawler(
        DoubanGroupConfig(
            group_url="https://www.douban.com/group/haixiuzu/",
            tab_name="闲车禁拼多多",
        ),
        repository,
    )
    posts = crawler.run_once()

    assert len(posts) == 1

    detector = RuleBasedDealDetector.from_config_files(
        brands_path="config/brands.yaml",
        categories_path="config/categories.yaml",
    )
    detected = detector.detect(title=posts[0].title, content=posts[0].content)

    assert detected.is_deal is True
    assert detected.brand == "百利"
    assert detected.category == "cat_food"
    assert detected.price == 335

    comments = analyze_comments(["还能买，我已上车"])
    recommendation = RecommendationScorer.from_yaml("config/preferences.yaml").score(
        RecommendationInput(
            category=detected.category,
            brand=detected.brand,
            price=detected.price,
            base_confidence=detected.confidence,
            historical_average_price=450,
            comment_analysis=comments,
        )
    )

    assert recommendation.should_notify is True
    assert recommendation.cat_score == 5

    candidate_deal = Deal(
        post_id=posts[0].id,
        category=detected.category,
        brand=detected.brand,
        product_name=detected.product_name,
        price=detected.price,
        confidence_score=recommendation.confidence_score,
        cat_score=recommendation.cat_score,
        is_duplicate=False,
        created_at=datetime.now(UTC),
    )
    duplicate_decision = DuplicateHandler().evaluate(candidate_deal, repository.list_deals())

    assert duplicate_decision.should_notify is True

    deal = repository.create_deal(candidate_deal)
    feedback_links = build_feedback_links(base_url="https://example.com/feedback", deal_id=deal.id)
    sender = FakeSender()
    notification = NotificationService(repository=repository, sender=sender).send_deal_notification(
        deal=deal,
        post=posts[0],
        recommendation=recommendation,
        feedback_links=feedback_links,
    )

    assert len(sender.sent_messages) == 1
    assert notification.email_sent is True
    assert "百利原始鸡" in sender.sent_messages[0].subject
    assert "action=bought" in sender.sent_messages[0].text_body

    feedback = FeedbackHandler(repository).handle(deal_id=deal.id, action="bought")

    assert feedback.feedback_type == FeedbackType.BOUGHT_FROM_THIS

    learning_engine = PreferenceLearningEngine.from_yaml("config/preferences.yaml")
    updated_preferences = learning_engine.apply_feedback(
        deal=deal,
        feedback=feedback,
    )

    assert updated_preferences["preferred_brands"]["百利"] == 50
    assert updated_preferences["category_priorities"]["cat_food"] == 40


class FakeSender:
    def __init__(self) -> None:
        self.sent_messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent_messages.append(message)
