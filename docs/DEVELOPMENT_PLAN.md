Cat Deal Radar Development Plan v1.0

Development Principles

Build incrementally.

Complete one task at a time.

Every task must include:

* Implementation
* Unit tests
* Documentation updates
* Manual verification instructions

Do not start the next task until the current task is confirmed.

⸻

Task 0: Project Bootstrap

Goal:

Initialize the project structure.

Requirements:

* Python 3.12
* uv package manager
* Ruff
* Pytest
* Structlog
* Type hints

Deliverables:

app/
tests/
config/
prompts/
docs/
.github/workflows/

Acceptance Criteria:

✓ Project runs locally

✓ Tests pass

✓ Ruff passes

⸻

Task 1: Database Layer

Goal:

Build SQLite data models and repository layer.

Tables:

* posts
* deals
* notifications
* feedback

Requirements:

* Repository pattern
* No ORM overengineering
* Clear type definitions

Acceptance Criteria:

✓ CRUD operations work

✓ Unit tests pass

⸻

Task 2: Brand Normalization Engine

Goal:

Normalize all product brands into canonical names.

Files:

config/brands.yaml

Examples:

Solid Gold

↓

金素

Instinct

↓

百利

Acana

↓

爱肯拿

Acceptance Criteria:

✓ Alias matching works

✓ Unit tests cover all known brands

⸻

Task 3: Douban Crawler

Goal:

Fetch latest posts from:

爱猫生活

↓

闲车禁拼多多

Requirements:

* Fetch latest posts
* Store raw data
* Prevent duplicate inserts

Acceptance Criteria:

✓ New posts are saved into SQLite

✓ Duplicate handling works

⸻

Task 4: Deal Detection Pipeline

Goal:

Identify whether a post contains a valid deal.

Pipeline:

Rule Engine

↓

LLM Verification

↓

Comment Analysis

Deliverables:

* keyword_rules.py
* llm_classifier.py
* comment_analyzer.py

Acceptance Criteria:

✓ Detect deal posts correctly

✓ Extract brand, category, and price

⸻

Task 5: Recommendation Engine

Goal:

Generate:

Deal Confidence

Personal Cat Score

Deliverables:

* confidence scoring
* recommendation scoring
* duplicate handling

Rules:

Default:

24-hour duplicate merge.

Keep lowest price only.

Acceptance Criteria:

✓ Cat score generation works

✓ Duplicate logic works

⸻

Task 6: Email Notification System

Goal:

Send immediate email notifications.

Requirements:

Subject example:

🐱🐱🐱🐱🐱【必抢】百利335元

Body includes:

* Recommendation reasons
* Community information
* Feedback links
* Original post URL

Acceptance Criteria:

✓ Emails send successfully

✓ HTML formatting works

⸻

Task 7: Feedback System

Goal:

Implement first-layer feedback.

Actions:

❤️ More Like This

🙈 Less Like This

🛍️ Bought Because Of This Recommendation

📦 Already Have Enough Stock

Requirements:

* Store feedback in SQLite
* Update recommendation weights

Acceptance Criteria:

✓ Feedback links work

✓ Database updates correctly

⸻

Task 8: Preference Learning Engine

Goal:

Continuously learn user preferences.

Learning signals:

* Purchase behavior
* Positive feedback
* Negative feedback
* Click behavior

Requirements:

Avoid hard-coded thresholds.

Use adaptive preference weights.

Acceptance Criteria:

✓ User preferences evolve correctly

⸻

Task 9: GitHub Actions Deployment

Goal:

Deploy the system automatically.

Trigger:

Cloudflare Cron every 10 minutes dispatches the GitHub Actions workflow.

Workflow:

checkout

↓

install uv

↓

run tests

↓

run application

↓

send emails

Acceptance Criteria:

✓ GitHub Actions runs successfully

✓ Scheduled execution works

⸻

Task 10: End-to-End Testing

Goal:

Validate complete user journey.

Scenario:

Douban Post

↓

Deal Detection

↓

Recommendation

↓

Email

↓

User Feedback

↓

Preference Learning

Acceptance Criteria:

✓ Full pipeline works

✓ No manual intervention required

⸻

Final Definition of Done

The MVP is complete when:

✓ Monitors Douban every 10 minutes

✓ Detects valid deals

✓ Normalizes brands

✓ Sends immediate emails

✓ Supports feedback actions

✓ Learns user preferences

✓ Uses SQLite

✓ Runs on GitHub Actions

✓ Passes all tests
