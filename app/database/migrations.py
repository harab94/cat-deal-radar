from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    douban_post_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    product_name TEXT NOT NULL,
    price REAL NOT NULL,
    confidence_score INTEGER NOT NULL,
    cat_score INTEGER NOT NULL,
    is_duplicate INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL,
    email_sent INTEGER NOT NULL DEFAULT 0,
    sent_at TEXT,
    FOREIGN KEY (deal_id) REFERENCES deals (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS radar_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    posts_seen INTEGER NOT NULL,
    deals_created INTEGER NOT NULL,
    notifications_sent INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL CHECK (
        feedback_type IN (
            'MORE_LIKE_THIS',
            'LESS_LIKE_THIS',
            'BOUGHT_FROM_THIS',
            'ALREADY_HAVE_STOCK'
        )
    ),
    created_at TEXT NOT NULL,
    FOREIGN KEY (deal_id) REFERENCES deals (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS brand_candidate_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    candidate_brand TEXT NOT NULL,
    category TEXT NOT NULL,
    reported_at TEXT NOT NULL,
    UNIQUE (post_id, candidate_brand),
    FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deals_post_id ON deals (post_id);
CREATE INDEX IF NOT EXISTS idx_notifications_deal_id ON notifications (deal_id);
CREATE INDEX IF NOT EXISTS idx_radar_runs_finished_at ON radar_runs (finished_at);
CREATE INDEX IF NOT EXISTS idx_feedback_deal_id ON feedback (deal_id);
CREATE INDEX IF NOT EXISTS idx_brand_candidate_reports_post_id
    ON brand_candidate_reports (post_id);
"""
