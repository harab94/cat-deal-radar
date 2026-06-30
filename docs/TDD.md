Cat Deal Radar MVP Technical Design Document (TDD) v1.0

1. Technical Goals

The system should:

* Monitor Douban every 10 minutes
* Detect cat-related deals
* Normalize brands and products
* Generate personalized recommendations
* Send immediate email notifications
* Record user feedback
* Continuously learn user preferences

⸻

2. Tech Stack

Language:

Python 3.12

⸻

Database:

SQLite

⸻

Deployment:

GitHub Actions

⸻

Package Manager:

uv

⸻

LLM:

OpenAI API

Model:

gpt-5.5-mini

⸻

Email:

Gmail SMTP

⸻

Configuration:

YAML

⸻

Testing:

pytest

⸻

Logging:

structlog

⸻

3. Project Structure

cat-deal-radar/
├── app/
│
├── crawler/
│   ├── douban.py
│   └── parser.py
│
├── deal_detector/
│   ├── keyword_rules.py
│   ├── llm_classifier.py
│   └── comment_analyzer.py
│
├── recommendation/
│   ├── scoring.py
│   ├── preference_learning.py
│   └── duplicate_handler.py
│
├── notification/
│   ├── email_sender.py
│   └── templates.py
│
├── feedback/
│   ├── handlers.py
│   └── api.py
│
├── database/
│   ├── models.py
│   ├── migrations.py
│   └── repository.py
│
├── config/
│   ├── brands.yaml
│   ├── categories.yaml
│   └── settings.yaml
│
├── prompts/
│   ├── classify_deal.md
│   ├── normalize_brand.md
│   └── recommendation.md
│
└── main.py

⸻

4. Brand Normalization Engine

Purpose:

Convert all brand aliases into canonical names.

Example:

brand_aliases:
  爱肯拿:
    - Acana
    - acana
  百利:
    - Instinct
    - instinct
    - 百利原始
  法米娜:
    - Farmina
  金素:
    - Solid Gold
    - solidgold
  Halo:
    - halo
  顽味:
    - 顽味鸡脖
    - 顽味青花鱼
  MJamJam:
    - mjamjam

Business logic should always use:

canonical_brand_name

instead of raw text.

⸻

5. Category Mapping

cat_food:
  brands:
    - 爱肯拿
    - 百利
    - 法米娜
    - 金素
    - Halo
wet_food:
  brands:
    - 金色交响乐
    - 小李子
    - MJamJam
freeze_dried:
  brands:
    - OP
    - 顽味
cat_litter:
  keywords:
    - 铁锤
    - 豆腐砂
    - 木薯砂

⸻

6. Database Design

⸻

posts

id
douban_post_id
title
content
url
created_at
fetched_at

⸻

deals

id
post_id
category
brand
product_name
price
confidence_score
cat_score
is_duplicate
created_at

⸻

notifications

id
deal_id
email_sent
sent_at

⸻

feedback

id
deal_id
feedback_type
created_at

Allowed values:

MORE_LIKE_THIS
LESS_LIKE_THIS
BOUGHT_FROM_THIS
ALREADY_HAVE_STOCK

⸻

7. Deal Detection Pipeline

Douban
↓
Fetch latest posts
↓
Keyword filter
↓
Brand normalization
↓
LLM classification
↓
Comment analysis
↓
Deal confidence
↓
Recommendation score
↓
Duplicate handling
↓
Email

⸻

8. LLM Prompt Design

⸻

classify_deal.md

Output format:

{
  "is_deal": true,
  "category": "cat_food",
  "brand": "百利",
  "product_name": "百利原始鸡",
  "price": 335,
  "confidence": 92
}

⸻

normalize_brand.md

Input:

solidgold

Output:

{
  "canonical_brand":"金素"
}

⸻

recommendation.md

Output:

{
  "cat_score":5,
  "reasons":[
    "High priority category",
    "User preference brand",
    "20% below average price"
  ]
}

⸻

9. Duplicate Strategy

Default MVP behavior:

24 hours
↓
Same brand
↓
Same product
↓
Keep lowest price
↓
Only one email

Future setting:

duplicate_policy:
  merge:
    true
  window:
    24h

⸻

10. Email Template

Subject:

🐱🐱🐱🐱🐱【必抢】百利原始系列 335元

⸻

Body:

━━━━━━━━━━
【推荐理由】
✓ 高优先级商品
✓ 低于平均价22%
✓ 评论区确认还能买
━━━━━━━━━━
【社区信息】
发帖时间：
15分钟前
最新评论：
还能买
━━━━━━━━━━
❤️ 多推类似
🙈 少推类似
🛍️ 因为这次推荐下单了
📦 家里还有，下次再买
━━━━━━━━━━
原帖链接：
...

⸻

11. Preference Learning Engine

Initial preferences are seeds only.

Learning sources:

Purchase feedback
Positive feedback
Negative feedback
Click behavior
Email open rate

⸻

Weight update example:

MORE_LIKE_THIS:
brand_score += 10
LESS_LIKE_THIS:
brand_score -= 10
BOUGHT_FROM_THIS:
brand_score += 20
ALREADY_HAVE_STOCK:
no change

⸻

12. Cloudflare Cron + GitHub Actions

Schedule:

cron:
*/10 * * * *

Workflow:

Cloudflare Worker scheduled event
↓
workflow_dispatch
↓
checkout
↓
install uv
↓
install dependencies
↓
run main.py
↓
send emails

⸻

13. Development Phases

⸻

Phase 1:

Douban crawler

⸻

Phase 2:

Brand normalization

⸻

Phase 3:

LLM deal detection

⸻

Phase 4:

Email notifications

⸻

Phase 5:

Feedback system

⸻

Phase 6:

Preference learning

⸻

14. Testing Strategy

Unit tests:

Brand normalization
Duplicate detection
Recommendation scoring
Feedback handling

⸻

Integration tests:

Douban fetch
Email sending
SQLite persistence

⸻

15. MVP Definition

The MVP is complete when:

✓ Runs automatically every 10 minutes

✓ Detects deal posts

✓ Normalizes brands

✓ Sends email notifications

✓ Supports feedback actions

✓ Learns user preferences

✓ Persists data in SQLite

✓ Deploys successfully on GitHub Actions
