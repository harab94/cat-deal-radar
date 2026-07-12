# Cat Deal Radar

Cat Deal Radar is a lightweight personal tool that monitors cat product deal posts,
scores them against personal preferences, and sends timely email notifications.

## Current Phase

Task 10: end-to-end testing.

## Database

The database layer uses Python's built-in SQLite support and small repository
methods instead of an ORM.

Implemented tables:

- `posts`
- `deals`
- `notifications`
- `feedback`

## Brand Normalization

Brand aliases live in `config/brands.yaml`. The normalizer returns canonical
brand names so later deal detection and recommendation logic never has to rely
on raw post text.

Current behavior:

- exact alias normalization
- brand lookup inside post text
- case-insensitive English matching
- whitespace, hyphen, underscore, and exclamation mark tolerance
- longest alias match first

## Douban Crawler

The Douban crawler is split into:

- `app/crawler/parser.py` for extracting topic links from group HTML
- `app/crawler/douban.py` for fetching the group page and saving new posts

Crawler settings live in `config/settings.yaml`. If Douban requires a logged-in
session, set the cookie value in the environment variable named by
`douban.cookie_env`.

Manual verification for a real run should confirm:

- `douban.group_url` points to the correct `爱猫生活 / 闲车禁拼多多` page
- `DOUBAN_COOKIE` is set if the page is not public
- new topics are inserted into SQLite
- repeated runs do not insert duplicate `douban_post_id` values

## Deal Detection

The first deal detection layer is local and deterministic:

- keyword deal signals such as `闲车`, `团购`, `补货`, and `好价`
- `开车` is treated as an expired-deal signal for this Douban group
- brand normalization through `config/brands.yaml`
- category mapping through `config/categories.yaml`
- simple price extraction
- comment availability signals such as `还能买`, `已上车`, `没了`, and `无货`

The LLM classifier module currently parses the required JSON response shape.
The real OpenAI API call is intentionally left as the next integration step so
local tests do not require network access or API keys.

## Recommendation

Recommendation scoring is split into:

- deal confidence score, adjusted by comment availability signals
- personal cat score, based on brand preference, category priority, discount,
  purchase history, and feedback counts
- duplicate handling, using a 24-hour same-brand same-product window and
  notifying only when a new duplicate has the lowest price

Personal seed weights live in `config/preferences.yaml`. Deals below 3 cats do
not trigger notifications.

## Email Notifications

Email notification support includes:

- subject lines with cat score, priority label, product name, and price
- plain text and HTML bodies
- recommendation reasons
- community/post information
- quick feedback links
- original Douban URL
- SMTP delivery with TLS
- notification records in SQLite after successful send

Gmail settings live in `config/settings.yaml` and are read from environment
variables:

- `GMAIL_USERNAME`
- `GMAIL_APP_PASSWORD`
- `GMAIL_SENDER`
- `DEAL_NOTIFICATION_RECIPIENT`

## Feedback

Feedback links are generated from `FEEDBACK_BASE_URL` and include:

- `action=more` for `MORE_LIKE_THIS`
- `action=less` for `LESS_LIKE_THIS`
- `action=bought` for `BOUGHT_FROM_THIS`
- `action=stock` for `ALREADY_HAVE_STOCK`

The production feedback endpoint lives in `feedback-worker/`. It shows a small
confirmation page and writes each click to the Feishu Base `Feedback` table.
`ALREADY_HAVE_STOCK` means the user likes the recommendation but does not need
to buy right now, so preference learning should not treat it as negative
feedback.

## Preference Learning

Preference learning updates YAML-style preference weights from feedback:

- `MORE_LIKE_THIS`: brand +10, category +5
- `LESS_LIKE_THIS`: brand -10, category -5
- `BOUGHT_FROM_THIS`: brand +20, category +10
- `ALREADY_HAVE_STOCK`: no preference change

Weights are clamped from 0 to 100. The engine can return updated preferences in
memory or save them back to a YAML file.

## GitHub Actions

The project has two workflows:

- `CI`: runs on push and pull request
- `Cat Deal Radar`: can be started manually with `workflow_dispatch`

Cloudflare Cron triggers the feedback Worker every 10 minutes. The Worker
dispatches the `Cat Deal Radar` workflow, which installs dependencies, runs
tests, runs Ruff, then starts the radar entrypoint.

After a successful radar run, the workflow commits `data/cat_deal_radar.sqlite`
back to the repository when the database changed. This lets scheduled runs
remember which Douban posts and notifications were already processed.

When starting the workflow manually, set `send_test_email` to `true` to send a
fake deal email and verify Gmail delivery without waiting for a real Douban deal.

`python -m app.main` now executes one pipeline run:

1. initialize SQLite
2. fetch and save new Douban posts
3. detect supported deals
4. score recommendations
5. apply duplicate policy
6. create deal records
7. send email notifications when email and feedback configuration are present

If email or feedback configuration is missing, the run still records eligible
deals and skips notification safely.

Configure these repository secrets before enabling the full production run:

- `DOUBAN_COOKIE`
- `GMAIL_USERNAME`
- `GMAIL_APP_PASSWORD`
- `GMAIL_SENDER`
- `DEAL_NOTIFICATION_RECIPIENT`
- `FEEDBACK_BASE_URL`
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_BASE_TOKEN`
- `FEISHU_BRANDS_TABLE_ID`
- `FEISHU_CATEGORIES_TABLE_ID`
- `FEISHU_DETECTION_RULES_TABLE_ID` (optional, overrides local deal/expired signals)
- `FEISHU_BRAND_CANDIDATES_TABLE_ID` (optional, for unknown brand review)

When the required Feishu secrets are present, brand and category config is
loaded from Feishu Base. If `FEISHU_DETECTION_RULES_TABLE_ID` is not configured,
deal and expired signals use the local code defaults.

When Feishu is unavailable, the app does not use the local fallback brand list
for known-brand decisions. It still uses local deal/expired signals and category
keywords, so new or unknown brands can be detected when the title contains a
supported category keyword such as `猫粮`, `罐头`, `冻干`, or `猫砂`.

Unknown brand candidates can be written to a separate Feishu Base table for
manual review. Create a table with these fields:

- `candidate_brand`
- `category`
- `post_title`
- `post_url`
- `source`
- `status`
- `note`

Rows created by the radar use `source=system_auto` and `status=needs_review`.
Review this table regularly before adding approved values to the main Brands
and Categories tables.

Current Feishu Base:

- URL: `https://my.feishu.cn/base/NAUZbxujCaO9ycsrsX8c5ChLnZg`
- `FEISHU_BASE_TOKEN`: `NAUZbxujCaO9ycsrsX8c5ChLnZg`
- `FEISHU_BRANDS_TABLE_ID`: `tblmYQwlJbG1QRlk`
- `FEISHU_CATEGORIES_TABLE_ID`: `tblLnyp0oYvyGOWU`
- `FEISHU_DETECTION_RULES_TABLE_ID`: `tblsKTQon5wTiSmt`

## End-to-End Testing

The local end-to-end test covers the complete MVP journey with fake external
services:

1. parse a Douban-like HTML page
2. save new posts into SQLite
3. detect a supported deal
4. score recommendation confidence and cat score
5. handle duplicate policy
6. generate feedback links
7. render and send an email through a fake sender
8. record notification state
9. store user feedback
10. update learned preferences

Real Douban and Gmail verification still requires repository secrets and a live
manual run.

Outstanding production follow-ups live in `docs/TODO.md`.

Manual verification for the current phase:

```bash
UV_CACHE_DIR=.uv-cache .venv/bin/uv run pytest
UV_CACHE_DIR=.uv-cache .venv/bin/uv run ruff check .
```

## Local Checks

```bash
uv sync
uv run pytest
uv run ruff check .
uv run cat-deal-radar
```

## Principles

- Keep the project single-user and low-maintenance.
- Prefer SQLite, YAML, GitHub Actions, and email.
- Use tests, type hints, Ruff, and structured logging.
