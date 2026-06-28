# Cat Deal Radar TODO

## Production Verification

- Re-run GitHub Actions after pushing the latest fixes.
- Confirm the `Cat Deal Radar` workflow turns green.
- Check workflow logs for `douban_crawl_failed`.
- If `douban_crawl_failed` appears, debug Douban access separately:
  - Verify `DOUBAN_COOKIE` is fresh and copied from a logged-in browser session.
  - Confirm `douban.group_url` points to the actual `爱猫生活 / 闲车禁拼多多` page.
  - Current target URL: `https://www.douban.com/group/656297/?tab=42899`
  - Check whether Douban blocks GitHub Actions runners.
  - Consider running the crawler locally or from a trusted machine if GitHub runner access is blocked.

## Notification Verification

- Confirm Gmail SMTP secrets are valid:
  - `GMAIL_USERNAME`
  - `GMAIL_APP_PASSWORD`
  - `GMAIL_SENDER`
  - `DEAL_NOTIFICATION_RECIPIENT`
- Send one real notification after Douban crawling succeeds.
- If Gmail rejects credentials, regenerate a Gmail app password.

## Feedback Follow-Up

- Verify GitHub Actions uses the Cloudflare Worker `FEEDBACK_BASE_URL`, not a GitHub URL.
- Add `FEISHU_SKUS_TABLE_ID=tblBcUnMsghjbgR0` to GitHub Actions secrets.
- Make feedback learning consume Feishu feedback records automatically:
  - 多推类似：brand/category/SKU 加权
  - 少推类似：brand/category/SKU 降权
  - 已下单：强加权
  - 家里还有：短期减少同类推送，不长期降权

## Product Follow-Up

- Validate real Douban HTML parsing against the live page.
- Verify live Douban reply parsing against production logs.
- Expand the Feishu `SKUs` table beyond the first seeded SKUs.
- Add LLM second-pass verification for brand/category matches with missing price or ambiguous product.
- Consider moving scheduling from GitHub Actions cron to Cloudflare Cron if 10-minute runs remain unreliable.
