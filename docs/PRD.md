Cat Deal Radar MVP PRD v1.1

1. Product Overview

Product Name

Cat Deal Radar

Vision

Build a personal AI shopping agent for cat owners that monitors community deal posts, proactively recommends high-value cat product deals, and continuously learns user preferences through feedback.

MVP Goal

Help the user avoid missing limited-time deals from Douban while working during the day.

The product should:

* Monitor Douban automatically
* Filter valuable cat-related deals
* Send immediate email notifications
* Learn user preferences over time
* Minimize manual configuration

⸻

2. User Persona

Primary User

User Profile:

* Owns 2 cats
* Cats are 4–5 years old
* No special dietary requirements
* Prefers imported brands
* Will not purchase low-end domestic brands
* Frequently buys in bulk
* Price-sensitive but quality-first

Pain Point:

The user cannot continuously monitor Douban during work hours and often misses time-sensitive deals.

⸻

3. Supported Categories

P0 Categories (MVP)

Cat Food

Preferred brands:

* 爱肯拿 (Acana)
* 百利 (Instinct)
* 法米娜 (Farmina)
* 金素 (Solid Gold)
* Halo

Potential future brands:

* 渴望 (Orijen)
* GO! Solutions
* Nulo
* Open Farm
* Ziwi Peak
* K9 Natural
* Wellness CORE

⸻

Wet Food

Preferred brands:

* 金色交响乐
* 小李子
* MJamJam

⸻

Freeze-Dried Treats

Preferred brands:

* OP 三文鱼冻干
* 顽味鸡脖
* 顽味青花鱼

⸻

Cat Litter

Preferred products:

* Arm & Hammer
* 豆腐砂
* 木薯砂

⸻

Excluded Categories

Not included in MVP:

* Deworming products
* Supplements
* Inventory management

⸻

4. Data Source

MVP Scope

Platform:

Douban

Group:

爱猫生活

Tab:

闲车禁拼多多

Future expansion:

* More Douban groups
* 什么值得买
* Other community sources

⸻

5. Monitoring Frequency

The system shall check new posts:

Every 10 minutes.

Implementation:

GitHub Actions Cron:

*/10 * * * *

⸻

6. Deal Detection Logic

Stage 1: Source Filtering

Only process posts from:

闲车禁拼多多

⸻

Stage 2: Rule-Based Detection

Signals include:

* 团购
* 开车
* Price patterns
* Brand keywords
* Product keywords

⸻

Stage 3: LLM Verification

Expected output:

{
“is_deal”: true,
“category”: “cat_food”,
“brand”: “百利”,
“product_name”: “百利原始鸡”,
“price”: 335,
“confidence”: 92
}

⸻

7. Brand Normalization

The system must normalize different aliases into canonical brand names.

Example:

Solid Gold

↓

金素

Instinct

↓

百利

Acana

↓

爱肯拿

All recommendation logic must use canonical brand names.

Brand aliases should be stored in YAML files.

⸻

8. Recommendation System

The system uses two independent scores.

⸻

8.1 Deal Confidence Score

Factors:

* Post age
* Comment freshness
* Positive comments:
    * 还能买
    * 已上车
* Negative comments:
    * 没了
    * 无货

If comments conflict:

Still notify users, but lower confidence.

⸻

8.2 Personal Cat Score

Display:

🐱🐱🐱🐱🐱

Factors:

* Brand preference
* Category priority
* Purchase history
* User feedback
* Discount level

Deals below 3 cats should not trigger notifications.

⸻

9. Deal Threshold

Initial MVP Rule:

A deal is considered valuable if:

Current Price ≤ Historical Average × 80%

Equivalent:

At least 20% below average price.

Future versions may rely more heavily on AI-based personalization.

⸻

10. Email Notification

Delivery Method

Immediate email only.

No daily digest.

⸻

Email Subject

Example:

🐱🐱🐱🐱🐱【必抢】百利原始系列 335元

Users should be able to understand recommendation priority directly from the subject line.

⸻

Email Body

Sections:

⸻

Recommendation Reasons

Example:

✓ High-priority category

✓ Preferred imported brand

✓ 22% below average price

✓ Community confirms availability

⸻

Community Information

Post time:

15 minutes ago

Recent comments:

还能买

⸻

Quick Feedback

❤️ 多推类似

Meaning:

Increase brand/category preference.

⸻

🙈 少推类似

Meaning:

Decrease brand/category preference.

⸻

🛍️ 因为这次推荐下单了

Meaning:

The user purchased because of this recommendation.

This strengthens future recommendations.

⸻

📦 家里还有，下次再买

Meaning:

The user likes the recommendation but currently has enough stock.

This should NOT negatively impact preference learning.

⸻

Original Link

Direct Douban URL.

⸻

11. Preference Learning

The system should minimize manual configuration.

Initial brand preferences are only seeds.

Learning signals include:

* Purchase actions
* Positive feedback
* Negative feedback
* Click behavior
* Email engagement
* Price sensitivity feedback

⸻

12. Duplicate Handling

Default MVP behavior:

Within 24 hours:

If multiple posts refer to the same product:

* Keep the lowest price
* Send only one email

Future versions may allow user customization.

⸻

13. Technical Requirements

Language:

Python 3.12

Database:

SQLite

Deployment:

GitHub Actions

Package Manager:

uv

Email:

Gmail SMTP

AI:

OpenAI API

Configuration:

YAML

Testing:

pytest

Logging:

structlog

⸻

14. Non-Functional Requirements

Email delivery:

Within 2 minutes after deal detection.

Monthly infrastructure cost:

Less than $10.

Architecture principle:

Prefer simplicity over scalability.

Assume single-user usage.

Avoid overengineering.

⸻

15. Future Roadmap

V2:

* WeChat feedback agent
* Inventory management
* Multi-user support
* More deal sources
* Personalized price learning
* Full conversational shopping assistant

⸻

16. MVP Acceptance Criteria

The MVP is complete when:

✓ Monitor Douban every 10 minutes

✓ Detect cat-related deal posts

✓ Normalize brands correctly

✓ Generate personalized recommendations

✓ Send immediate emails

✓ Support four feedback actions

✓ Learn user preferences

✓ Persist data in SQLite

✓ Deploy successfully through GitHub Actions