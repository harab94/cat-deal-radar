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

- Replace the temporary `FEEDBACK_BASE_URL` placeholder with a real endpoint.
- Implement a lightweight public feedback receiver.
- Wire feedback links so clicks call the receiver and store feedback in SQLite or another durable store.
- Verify GitHub Actions can load detection config from Feishu Base secrets.

## Product Follow-Up

- Validate real Douban HTML parsing against the live page.
- Verify live Douban reply parsing against production logs.
- Add real historical average price data before relying on discount scoring in production.
