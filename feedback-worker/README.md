# Cat Deal Radar Feedback Worker

This Cloudflare Worker receives email feedback clicks and writes them to the
Feishu Base `Feedback` table.

## Required Feishu Permission

The Feishu app must have app identity permission for Base records:

- `base:record:create`

If config loading also uses the same app, it also needs:

- `base:record:retrieve`

## Secrets

Set these Worker secrets:

```bash
npx wrangler secret put FEISHU_APP_ID
npx wrangler secret put FEISHU_APP_SECRET
npx wrangler secret put FEISHU_BASE_TOKEN
npx wrangler secret put FEISHU_FEEDBACK_TABLE_ID
npx wrangler secret put WEWORK_CORP_ID
npx wrangler secret put WEWORK_AGENT_ID
npx wrangler secret put WEWORK_APP_SECRET
npx wrangler secret put WEWORK_CALLBACK_TOKEN
npx wrangler secret put WEWORK_ENCODING_AES_KEY
```

Current values:

```text
FEISHU_BASE_TOKEN=NAUZbxujCaO9ycsrsX8c5ChLnZg
FEISHU_FEEDBACK_TABLE_ID=tblMHSAXVv6GXqU8
```

## Deploy

```bash
cd feedback-worker
npx wrangler deploy
```

After deployment, set the GitHub repository secret:

```text
FEEDBACK_BASE_URL=https://<your-worker-domain>
```

Email links will call:

```text
https://<your-worker-domain>?deal_id=<id>&action=more
https://<your-worker-domain>?deal_id=<id>&action=less
https://<your-worker-domain>?deal_id=<id>&action=bought
https://<your-worker-domain>?deal_id=<id>&action=stock
```

## WeWork App Callback

The same Worker can receive direct replies from a WeWork custom app.

Configure the WeWork app callback URL as:

```text
https://<your-worker-domain>/wework/callback
```

Set these Worker secrets to the same values configured in WeWork:

```text
WEWORK_CALLBACK_TOKEN=<the Token from the WeWork callback settings>
WEWORK_ENCODING_AES_KEY=<the EncodingAESKey from the WeWork callback settings>
```

Supported direct reply formats:

```text
多推 123
少推 123
买了 123
家里还有 123
```

The number is the `deal_id` shown in feedback links. The Worker decrypts the
WeWork callback, writes the feedback to Feishu, then sends a short confirmation
back to the user through the WeWork app.

## Local Preview

Create `feedback-worker/.dev.vars` for local preview:

```text
FEEDBACK_PREVIEW_MODE=1
```

Then run:

```bash
cd feedback-worker
npx wrangler dev --local --port 8787
```

Open:

```text
http://localhost:8787/?deal_id=preview-1&action=more
```
