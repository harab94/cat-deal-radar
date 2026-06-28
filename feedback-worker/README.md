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
