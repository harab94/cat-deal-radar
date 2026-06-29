from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from app.database.migrations import SCHEMA_SQL
from app.database.models import Deal, Feedback, FeedbackType, Notification, Post, RadarRun


class Repository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = database_path
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> Repository:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def connect(self) -> sqlite3.Connection:
        if self._connection is None:
            connection = sqlite3.connect(self.database_path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            self._connection = connection
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def initialize(self) -> None:
        self.connect().executescript(SCHEMA_SQL)
        self.connect().commit()

    def create_post(self, post: Post) -> Post:
        cursor = self.connect().execute(
            """
            INSERT INTO posts (douban_post_id, title, content, url, created_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                post.douban_post_id,
                post.title,
                post.content,
                post.url,
                _to_db_time(post.created_at),
                _to_db_time(post.fetched_at),
            ),
        )
        self.connect().commit()
        return Post(
            id=cursor.lastrowid,
            douban_post_id=post.douban_post_id,
            title=post.title,
            content=post.content,
            url=post.url,
            created_at=post.created_at,
            fetched_at=post.fetched_at,
            comments=post.comments,
        )

    def create_post_if_new(self, post: Post) -> Post | None:
        if self.get_post_by_douban_id(post.douban_post_id) is not None:
            return None
        return self.create_post(post)

    def get_post(self, post_id: int) -> Post | None:
        row = self.connect().execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return _post_from_row(row) if row else None

    def get_post_by_douban_id(self, douban_post_id: str) -> Post | None:
        row = self.connect().execute(
            "SELECT * FROM posts WHERE douban_post_id = ?", (douban_post_id,)
        ).fetchone()
        return _post_from_row(row) if row else None

    def list_posts(self) -> list[Post]:
        rows = self.connect().execute("SELECT * FROM posts ORDER BY created_at DESC, id DESC")
        return [_post_from_row(row) for row in rows]

    def update_post(self, post: Post) -> Post:
        _require_id(post.id, "post")
        self.connect().execute(
            """
            UPDATE posts
            SET douban_post_id = ?, title = ?, content = ?, url = ?, created_at = ?, fetched_at = ?
            WHERE id = ?
            """,
            (
                post.douban_post_id,
                post.title,
                post.content,
                post.url,
                _to_db_time(post.created_at),
                _to_db_time(post.fetched_at),
                post.id,
            ),
        )
        self.connect().commit()
        return post

    def delete_post(self, post_id: int) -> None:
        self.connect().execute("DELETE FROM posts WHERE id = ?", (post_id,))
        self.connect().commit()

    def create_deal(self, deal: Deal) -> Deal:
        cursor = self.connect().execute(
            """
            INSERT INTO deals (
                post_id, category, brand, product_name, price, confidence_score, cat_score,
                is_duplicate, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deal.post_id,
                deal.category,
                deal.brand,
                deal.product_name,
                deal.price,
                deal.confidence_score,
                deal.cat_score,
                int(deal.is_duplicate),
                _to_db_time(deal.created_at),
            ),
        )
        self.connect().commit()
        return Deal(
            id=cursor.lastrowid,
            post_id=deal.post_id,
            category=deal.category,
            brand=deal.brand,
            product_name=deal.product_name,
            price=deal.price,
            confidence_score=deal.confidence_score,
            cat_score=deal.cat_score,
            is_duplicate=deal.is_duplicate,
            created_at=deal.created_at,
        )

    def get_deal(self, deal_id: int) -> Deal | None:
        row = self.connect().execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        return _deal_from_row(row) if row else None

    def list_deals(self) -> list[Deal]:
        rows = self.connect().execute("SELECT * FROM deals ORDER BY created_at DESC, id DESC")
        return [_deal_from_row(row) for row in rows]

    def update_deal(self, deal: Deal) -> Deal:
        _require_id(deal.id, "deal")
        self.connect().execute(
            """
            UPDATE deals
            SET post_id = ?, category = ?, brand = ?, product_name = ?, price = ?,
                confidence_score = ?, cat_score = ?, is_duplicate = ?, created_at = ?
            WHERE id = ?
            """,
            (
                deal.post_id,
                deal.category,
                deal.brand,
                deal.product_name,
                deal.price,
                deal.confidence_score,
                deal.cat_score,
                int(deal.is_duplicate),
                _to_db_time(deal.created_at),
                deal.id,
            ),
        )
        self.connect().commit()
        return deal

    def delete_deal(self, deal_id: int) -> None:
        self.connect().execute("DELETE FROM deals WHERE id = ?", (deal_id,))
        self.connect().commit()

    def create_notification(self, notification: Notification) -> Notification:
        cursor = self.connect().execute(
            """
            INSERT INTO notifications (deal_id, email_sent, sent_at)
            VALUES (?, ?, ?)
            """,
            (
                notification.deal_id,
                int(notification.email_sent),
                _to_optional_db_time(notification.sent_at),
            ),
        )
        self.connect().commit()
        return Notification(
            id=cursor.lastrowid,
            deal_id=notification.deal_id,
            email_sent=notification.email_sent,
            sent_at=notification.sent_at,
        )

    def get_notification(self, notification_id: int) -> Notification | None:
        row = self.connect().execute(
            "SELECT * FROM notifications WHERE id = ?", (notification_id,)
        ).fetchone()
        return _notification_from_row(row) if row else None

    def list_notifications(self) -> list[Notification]:
        rows = self.connect().execute("SELECT * FROM notifications ORDER BY id DESC")
        return [_notification_from_row(row) for row in rows]

    def has_notification_for_post(self, post_id: int) -> bool:
        row = self.connect().execute(
            """
            SELECT 1
            FROM notifications
            JOIN deals ON deals.id = notifications.deal_id
            WHERE deals.post_id = ?
            LIMIT 1
            """,
            (post_id,),
        ).fetchone()
        return row is not None

    def has_notification_for_post_title(self, title: str) -> bool:
        row = self.connect().execute(
            """
            SELECT 1
            FROM notifications
            JOIN deals ON deals.id = notifications.deal_id
            JOIN posts ON posts.id = deals.post_id
            WHERE posts.title = ?
            LIMIT 1
            """,
            (title,),
        ).fetchone()
        return row is not None

    def update_notification(self, notification: Notification) -> Notification:
        _require_id(notification.id, "notification")
        self.connect().execute(
            """
            UPDATE notifications
            SET deal_id = ?, email_sent = ?, sent_at = ?
            WHERE id = ?
            """,
            (
                notification.deal_id,
                int(notification.email_sent),
                _to_optional_db_time(notification.sent_at),
                notification.id,
            ),
        )
        self.connect().commit()
        return notification

    def delete_notification(self, notification_id: int) -> None:
        self.connect().execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
        self.connect().commit()

    def create_radar_run(self, radar_run: RadarRun) -> RadarRun:
        cursor = self.connect().execute(
            """
            INSERT INTO radar_runs (
                started_at, finished_at, posts_seen, deals_created, notifications_sent
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                _to_db_time(radar_run.started_at),
                _to_db_time(radar_run.finished_at),
                radar_run.posts_seen,
                radar_run.deals_created,
                radar_run.notifications_sent,
            ),
        )
        self.connect().commit()
        return RadarRun(
            id=cursor.lastrowid,
            started_at=radar_run.started_at,
            finished_at=radar_run.finished_at,
            posts_seen=radar_run.posts_seen,
            deals_created=radar_run.deals_created,
            notifications_sent=radar_run.notifications_sent,
        )

    def list_radar_runs_since(self, since: datetime) -> list[RadarRun]:
        rows = self.connect().execute(
            """
            SELECT * FROM radar_runs
            WHERE finished_at >= ?
            ORDER BY finished_at DESC, id DESC
            """,
            (_to_db_time(since),),
        )
        return [_radar_run_from_row(row) for row in rows]

    def latest_radar_run(self) -> RadarRun | None:
        row = self.connect().execute(
            "SELECT * FROM radar_runs ORDER BY finished_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return _radar_run_from_row(row) if row else None

    def create_feedback(self, feedback: Feedback) -> Feedback:
        cursor = self.connect().execute(
            """
            INSERT INTO feedback (deal_id, feedback_type, created_at)
            VALUES (?, ?, ?)
            """,
            (feedback.deal_id, feedback.feedback_type.value, _to_db_time(feedback.created_at)),
        )
        self.connect().commit()
        return Feedback(
            id=cursor.lastrowid,
            deal_id=feedback.deal_id,
            feedback_type=feedback.feedback_type,
            created_at=feedback.created_at,
        )

    def get_feedback(self, feedback_id: int) -> Feedback | None:
        row = self.connect().execute(
            "SELECT * FROM feedback WHERE id = ?", (feedback_id,)
        ).fetchone()
        return _feedback_from_row(row) if row else None

    def list_feedback(self) -> list[Feedback]:
        rows = self.connect().execute("SELECT * FROM feedback ORDER BY created_at DESC, id DESC")
        return [_feedback_from_row(row) for row in rows]

    def list_feedback_for_deal(self, deal_id: int) -> list[Feedback]:
        rows = self.connect().execute(
            "SELECT * FROM feedback WHERE deal_id = ? ORDER BY created_at DESC, id DESC",
            (deal_id,),
        )
        return [_feedback_from_row(row) for row in rows]

    def update_feedback(self, feedback: Feedback) -> Feedback:
        _require_id(feedback.id, "feedback")
        self.connect().execute(
            """
            UPDATE feedback
            SET deal_id = ?, feedback_type = ?, created_at = ?
            WHERE id = ?
            """,
            (
                feedback.deal_id,
                feedback.feedback_type.value,
                _to_db_time(feedback.created_at),
                feedback.id,
            ),
        )
        self.connect().commit()
        return feedback

    def delete_feedback(self, feedback_id: int) -> None:
        self.connect().execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
        self.connect().commit()


def _require_id(value: int | None, model_name: str) -> None:
    if value is None:
        msg = f"Cannot update {model_name} without an id."
        raise ValueError(msg)


def _to_db_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _to_optional_db_time(value: datetime | None) -> str | None:
    return _to_db_time(value) if value is not None else None


def _from_db_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _post_from_row(row: sqlite3.Row) -> Post:
    return Post(
        id=row["id"],
        douban_post_id=row["douban_post_id"],
        title=row["title"],
        content=row["content"],
        url=row["url"],
        created_at=_from_db_time(row["created_at"]),
        fetched_at=_from_db_time(row["fetched_at"]),
    )


def _deal_from_row(row: sqlite3.Row) -> Deal:
    return Deal(
        id=row["id"],
        post_id=row["post_id"],
        category=row["category"],
        brand=row["brand"],
        product_name=row["product_name"],
        price=row["price"],
        confidence_score=row["confidence_score"],
        cat_score=row["cat_score"],
        is_duplicate=bool(row["is_duplicate"]),
        created_at=_from_db_time(row["created_at"]),
    )


def _notification_from_row(row: sqlite3.Row) -> Notification:
    sent_at = row["sent_at"]
    return Notification(
        id=row["id"],
        deal_id=row["deal_id"],
        email_sent=bool(row["email_sent"]),
        sent_at=_from_db_time(sent_at) if sent_at else None,
    )


def _radar_run_from_row(row: sqlite3.Row) -> RadarRun:
    return RadarRun(
        id=row["id"],
        started_at=_from_db_time(row["started_at"]),
        finished_at=_from_db_time(row["finished_at"]),
        posts_seen=row["posts_seen"],
        deals_created=row["deals_created"],
        notifications_sent=row["notifications_sent"],
    )


def _feedback_from_row(row: sqlite3.Row) -> Feedback:
    return Feedback(
        id=row["id"],
        deal_id=row["deal_id"],
        feedback_type=FeedbackType(row["feedback_type"]),
        created_at=_from_db_time(row["created_at"]),
    )
