const ACTION_LABELS = {
  more: "多推类似",
  less: "少推类似",
  bought: "因为这次推荐下单了",
  stock: "家里还有，下次再买",
};

const ACTION_TYPES = {
  more: "MORE_LIKE_THIS",
  less: "LESS_LIKE_THIS",
  bought: "BOUGHT_FROM_THIS",
  stock: "ALREADY_HAVE_STOCK",
};

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(triggerRadarWorkflow(env));
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/wework/callback") {
      return handleWeWorkCallback(request, env, url);
    }

    if (request.method === "GET" && url.pathname === "/favicon.ico") {
      return new Response(null, { status: 204 });
    }

    const dealId = (url.searchParams.get("deal_id") || "").trim();
    const action = (url.searchParams.get("action") || "").trim();

    if (request.method === "GET" && url.pathname === "/deals.json") {
      return latestDealsJsonResponse(env);
    }

    if (
      request.method === "GET" &&
      (url.pathname === "/" || url.pathname === "/deals") &&
      !dealId &&
      !action
    ) {
      return latestDealsPageResponse(env, url);
    }

    if (request.method !== "GET") {
      return htmlResponse("不支持的请求", "请从邮件里的反馈链接打开。", 405);
    }

    if (!dealId || !ACTION_TYPES[action]) {
      return htmlResponse("反馈链接无效", "缺少 deal_id 或 action 参数。", 400);
    }

    if (!isPreviewMode(env)) {
      try {
        await writeFeedback(env, {
          dealId,
          action,
          brand: optionalParam(url, "brand"),
          category: optionalParam(url, "category"),
          doubanUrl: optionalParam(url, "douban_url"),
          feedbackType: ACTION_TYPES[action],
          price: optionalPrice(url),
          title: optionalParam(url, "title"),
          createdAt: Date.now(),
        });
      } catch (error) {
        console.error(error);
        return htmlResponse("记录失败", "飞书暂时没有收下这条反馈，请稍后再试。", 502);
      }
    }

    return htmlResponse(
      "已记录，谢谢",
      `这条反馈是：${ACTION_LABELS[action]}。之后推荐会按你的选择慢慢变聪明。`,
    );
  },
};

async function triggerRadarWorkflow(env) {
  const repository = env.GITHUB_REPOSITORY || "harab94/cat-deal-radar";
  const workflowId = env.GITHUB_WORKFLOW_ID || "radar.yml";
  const ref = env.GITHUB_REF || "main";

  if (!env.GITHUB_ACTIONS_TOKEN) {
    throw new Error("GITHUB_ACTIONS_TOKEN is required to dispatch the radar workflow");
  }

  const response = await fetch(
    `https://api.github.com/repos/${repository}/actions/workflows/${workflowId}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${env.GITHUB_ACTIONS_TOKEN}`,
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "cat-deal-radar-worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        ref,
      }),
    },
  );

  if (response.status !== 204) {
    const body = await response.text();
    throw new Error(`GitHub workflow dispatch failed: ${response.status} ${body.slice(0, 500)}`);
  }

  console.log("radar_workflow_dispatched", { repository, workflowId, ref });
}

async function latestDealsJsonResponse(env) {
  const payload = await fetchLatestDeals(env);
  return new Response(JSON.stringify(payload), {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

async function latestDealsPageResponse(env, url) {
  let payload;
  try {
    payload = await fetchLatestDeals(env);
  } catch (error) {
    console.error("latest_deals_fetch_failed", error);
    return htmlResponse("猫车雷达暂时不可用", "最新推荐列表读取失败，请稍后再打开。", 502);
  }

  return new Response(renderDealsPage(payload, url), {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "text/html; charset=utf-8",
    },
  });
}

async function fetchLatestDeals(env) {
  if (env.LATEST_DEALS_JSON) {
    return JSON.parse(env.LATEST_DEALS_JSON);
  }

  const repository = env.GITHUB_REPOSITORY || "harab94/cat-deal-radar";
  const ref = env.GITHUB_REF || "main";
  const apiUrl = `https://api.github.com/repos/${repository}/contents/data/latest-deals.json?ref=${encodeURIComponent(ref)}`;
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "cat-deal-radar-worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (env.GITHUB_ACTIONS_TOKEN) {
    headers.Authorization = `Bearer ${env.GITHUB_ACTIONS_TOKEN}`;
  }

  const response = await fetch(apiUrl, { headers });
  if (!response.ok) {
    if (isPreviewMode(env)) {
      console.warn("latest_deals_preview_fallback", {
        status: response.status,
        repository,
        ref,
      });
      return previewDealsPayload();
    }
    throw new Error(`GitHub contents fetch failed: ${response.status} ${await response.text()}`);
  }

  const data = await response.json();
  if (!data.content) {
    throw new Error("GitHub contents response did not include file content");
  }
  const bytes = Uint8Array.from(atob(data.content.replace(/\s/g, "")), (char) =>
    char.charCodeAt(0),
  );
  return JSON.parse(new TextDecoder().decode(bytes));
}

function previewDealsPayload() {
  return {
    published_at: new Date().toISOString(),
    latest_run: {
      posts_seen: 52,
      deals_created: 2,
      notifications_sent: 2,
    },
    deals: [
      {
        id: "preview-1",
        brand: "百利",
        category: "cat_food",
        product_name: "【闲置】两个百利高罐头16r",
        price: 16,
        confidence_score: 95,
        cat_score: 5,
        post_title: "【闲置】两个百利高罐头16r",
        post_url: "https://m.douban.com/group/topic/492326286/",
      },
      {
        id: "preview-2",
        brand: "爱肯拿",
        category: "cat_food",
        product_name: "【闲置】爱肯拿鱼分装",
        price: 16,
        confidence_score: 95,
        cat_score: 4,
        post_title: "【闲置】爱肯拿鱼分装",
        post_url: "https://m.douban.com/group/topic/492339306/",
      },
    ],
  };
}

function renderDealsPage(payload, url) {
  const deals = Array.isArray(payload.deals) ? payload.deals : [];
  const updatedAt = formatTime(payload.published_at);
  const run = payload.latest_run || {};
  const subtitle =
    deals.length > 0
      ? `直播流里有 ${deals.length} 条猫车`
      : "雷达巡航中，暂时没有新猫车";
  const cards = deals.map((deal, index) => renderDealCard(deal, index, url)).join("");
  const streamHint =
    deals.length > 5
      ? `<p class="stream-hint">先露出 5 条，继续下滑还有 ${deals.length - 5} 条猫车在队尾慢慢靠站。</p>`
      : "";
  const fingerprint = dealsFingerprint(payload);
  const emptyState =
    deals.length === 0
      ? `<section class="empty" aria-live="polite">
          <div class="empty-icon">🐾</div>
          <h2>今天还没有值得冲的车</h2>
          <p>页面会跟着雷达每 10 分钟刷新。发现新 deal 后，它会出现在这里。</p>
        </section>`
      : "";

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Cat Deal Radar</title>
    <style>
      :root {
        color-scheme: light;
        --page-bg: oklch(96% 0.035 305);
        --surface: oklch(100% 0 0);
        --surface-muted: oklch(96% 0.035 305);
        --ink: oklch(9% 0.015 280);
        --text-strong: var(--ink);
        --text: oklch(25% 0.035 280);
        --text-muted: oklch(43% 0.045 282);
        --text-soft: oklch(61% 0.036 282);
        --border: var(--ink);
        --yellow: oklch(91% 0.135 86);
        --lime: oklch(88% 0.18 126);
        --lavender: oklch(82% 0.12 292);
        --purple: oklch(55% 0.18 278);
        --pink: oklch(93% 0.055 345);
        --priority: var(--ink);
        --priority-bg: var(--yellow);
        --price: var(--ink);
        --price-bg: var(--lime);
        --ticket: var(--yellow);
        --ticket-ink: var(--ink);
        --clash: var(--purple);
        --clash-bg: var(--lavender);
        --feedback-hover: oklch(94% 0.045 345);
        --focus: var(--purple);
        --shadow: 6px 6px 0 var(--ink);
        --font-display: "Tsukushi A Round Gothic", "Hiragino Maru Gothic ProN", "Yuanti SC",
          "PingFang SC", sans-serif;
        --font-ui: "Hiragino Sans GB", "PingFang SC", "Avenir Next", sans-serif;
        --font-data: "DIN Alternate", "Avenir Next Condensed", "SF Mono", monospace;
        font-family: var(--font-ui);
        color: var(--text);
        background: var(--page-bg);
        font-size: 16px;
      }
      * { box-sizing: border-box; }
      html { scroll-behavior: smooth; }
      body {
        margin: 0;
        min-height: 100vh;
        background:
          linear-gradient(108deg, transparent 0 14%, oklch(100% 0 0 / 0.72) 14% 15%, transparent 15% 100%),
          linear-gradient(164deg, transparent 0 52%, oklch(59% 0.18 278 / 0.14) 52% 53.2%, transparent 53.2% 100%),
          repeating-linear-gradient(90deg, oklch(100% 0 0 / 0.38) 0 2px, transparent 2px 88px),
          linear-gradient(180deg, oklch(99% 0.018 315), var(--page-bg) 360px);
        font-kerning: normal;
        text-rendering: optimizeLegibility;
      }
      main {
        width: min(100%, 920px);
        margin: 0 auto;
        padding: 30px 20px 52px;
      }
      header {
        position: relative;
        min-height: 244px;
        padding: 8px 0 20px;
        isolation: isolate;
      }
      header::after {
        content: "";
        position: absolute;
        right: 4px;
        bottom: 18px;
        width: min(42vw, 320px);
        height: 74px;
        border: 3px solid var(--ink);
        border-radius: 8px;
        background:
          repeating-linear-gradient(135deg, oklch(100% 0 0 / 0.32) 0 9px, transparent 9px 18px),
          var(--clash-bg);
        box-shadow: var(--shadow);
        transform: rotate(-4deg);
        z-index: -1;
      }
      .update-bar {
        position: sticky;
        top: 12px;
        z-index: 2;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        width: min(100%, 520px);
        margin: 0 auto 18px;
        padding: 10px 12px 10px 14px;
        border: 3px solid var(--ink);
        border-radius: 8px;
        background: var(--price-bg);
        box-shadow: var(--shadow);
        color: var(--ink);
        font-size: 0.92rem;
        font-weight: 750;
      }
      .update-bar[hidden] {
        display: none;
      }
      .update-bar button {
        min-height: 36px;
        padding: 6px 12px;
        border: 2px solid var(--ink);
        border-radius: 999px;
        background: var(--yellow);
        color: var(--ink);
        font: inherit;
        cursor: pointer;
      }
      .update-bar button:focus-visible {
        outline: 3px solid var(--focus);
        outline-offset: 2px;
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 30px;
      }
      .logo {
        width: 52px;
        height: 52px;
        display: grid;
        place-items: center;
        border-radius: 8px;
        background:
          linear-gradient(145deg, var(--yellow), var(--lime) 58%, var(--lavender));
        border: 3px solid var(--ink);
        box-shadow: 4px 4px 0 var(--ink);
        font-size: 25px;
        transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
      }
      .brand:hover .logo {
        transform: rotate(-5deg) translateY(-1px);
      }
      .brand strong {
        display: block;
        font-family: var(--font-data);
        font-size: 0.98rem;
        font-weight: 900;
        letter-spacing: 0.04em;
        line-height: 1.25;
      }
      .brand span {
        display: block;
        color: var(--text-muted);
        font-size: 0.92rem;
        line-height: 1.35;
      }
      h1 {
        margin: 0;
        max-width: 9ch;
        font-family: var(--font-display);
        font-size: clamp(3rem, 10vw, 5rem);
        line-height: 0.94;
        font-weight: 900;
        letter-spacing: 0;
        text-wrap: balance;
        color: var(--text-strong);
        text-shadow: 3px 3px 0 oklch(82% 0.12 292 / 0.62);
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 18px;
        color: var(--text-muted);
        font-size: 0.875rem;
        line-height: 1.5;
      }
      .meta span {
        display: inline-flex;
        align-items: center;
        min-height: 32px;
        padding: 5px 11px;
        border: 2px solid var(--ink);
        border-radius: 8px;
        background: var(--surface);
        box-shadow: 3px 3px 0 var(--ink);
        font-family: var(--font-data);
      }
      .feed-header {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 18px;
        margin-top: 10px;
      }
      .section-title {
        margin: 0;
        width: fit-content;
        max-width: 100%;
        padding: 6px 13px 7px;
        border: 3px solid var(--ink);
        background: var(--purple);
        box-shadow: 5px 5px 0 var(--ink);
        color: oklch(100% 0 0);
        font-family: var(--font-display);
        font-size: 1.8rem;
        font-weight: 900;
        letter-spacing: 0;
      }
      .feed-note {
        max-width: 24ch;
        margin: 0;
        padding: 8px 10px;
        border: 2px solid var(--ink);
        border-radius: 8px;
        background: var(--yellow);
        box-shadow: 4px 4px 0 var(--ink);
        color: var(--ink);
        font-family: var(--font-data);
        font-size: 0.86rem;
        font-weight: 900;
        line-height: 1.45;
        text-align: right;
      }
      .stream-hint {
        margin: 6px 0 14px;
        color: var(--text-muted);
        font-size: 0.93rem;
        line-height: 1.6;
      }
      .deal-stream {
        max-height: min(72vh, 650px);
        margin-top: 16px;
        padding: 3px 8px 34px 0;
        overflow-y: auto;
        overscroll-behavior: contain;
        scroll-snap-type: y proximity;
        mask-image: linear-gradient(to bottom, transparent 0, #000 18px, #000 calc(100% - 34px), transparent 100%);
      }
      .deal {
        position: relative;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 10px 18px;
        min-height: 118px;
        margin-bottom: 12px;
        padding: 16px 18px;
        border: 3px solid var(--ink);
        border-radius: 8px;
        background:
          repeating-linear-gradient(135deg, oklch(100% 0 0 / 0.24) 0 10px, transparent 10px 20px),
          var(--surface);
        box-shadow: var(--shadow);
        scroll-snap-align: start;
        animation: deal-rise 540ms cubic-bezier(0.2, 0.92, 0.18, 1) both;
        animation-delay: calc(var(--index) * 52ms);
        transition:
          border-color 190ms cubic-bezier(0.22, 1, 0.36, 1),
          box-shadow 190ms cubic-bezier(0.22, 1, 0.36, 1),
          filter 190ms cubic-bezier(0.22, 1, 0.36, 1),
          opacity 190ms cubic-bezier(0.22, 1, 0.36, 1),
          transform 190ms cubic-bezier(0.22, 1, 0.36, 1);
      }
      .deal:nth-child(3n + 1) {
        background:
          repeating-linear-gradient(135deg, oklch(100% 0 0 / 0.22) 0 10px, transparent 10px 20px),
          var(--yellow);
      }
      .deal:nth-child(3n + 2) {
        background:
          repeating-linear-gradient(135deg, oklch(100% 0 0 / 0.18) 0 10px, transparent 10px 20px),
          var(--lavender);
      }
      .deal:nth-child(3n) {
        background:
          repeating-linear-gradient(135deg, oklch(100% 0 0 / 0.2) 0 10px, transparent 10px 20px),
          var(--lime);
      }
      .deal::before {
        content: "CAT";
        position: absolute;
        top: -12px;
        right: 18px;
        z-index: 1;
        padding: 4px 9px 5px;
        border: 2px solid var(--ink);
        border-radius: 999px;
        background: var(--surface);
        box-shadow: 3px 3px 0 var(--ink);
        color: var(--ink);
        font-family: var(--font-data);
        font-size: 0.72rem;
        font-weight: 900;
        line-height: 1;
        transform: rotate(3deg);
      }
      .deal::after {
        content: "";
        position: absolute;
        inset: 8px;
        border: 1px dashed oklch(9% 0.015 280 / 0.22);
        border-radius: 5px;
        pointer-events: none;
        opacity: 0.48;
        transition:
          border-color 190ms cubic-bezier(0.22, 1, 0.36, 1),
          opacity 190ms cubic-bezier(0.22, 1, 0.36, 1);
      }
      .deal-stream:has(.deal:hover) .deal:not(:hover),
      .deal-stream:has(.deal:focus-within) .deal:not(:focus-within) {
        opacity: 0.58;
        filter: saturate(0.38) brightness(1.05);
      }
      .deal:hover,
      .deal:focus-within {
        border-color: var(--focus);
        box-shadow:
          8px 8px 0 var(--ink),
          0 0 0 5px oklch(88% 0.18 126 / 0.28);
        filter: saturate(1.06) brightness(1.01);
        transform: translateY(-3px) rotate(-0.25deg);
      }
      .deal:hover::after,
      .deal:focus-within::after {
        border-color: oklch(9% 0.015 280 / 0.5);
        opacity: 0.92;
      }
      .rank {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        color: var(--text-muted);
        font-family: var(--font-data);
        font-size: 0.78rem;
        font-weight: 700;
        line-height: 1.5;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        min-height: 26px;
        padding: 3px 8px;
        border: 2px solid var(--ink);
        border-radius: 999px;
        color: var(--priority);
        background: var(--priority-bg);
      }
      .score {
        color: var(--text-muted);
      }
      .price-pill {
        align-self: start;
        min-width: 94px;
        padding: 11px 13px;
        border: 3px solid var(--ink);
        border-radius: 8px;
        background: var(--price-bg);
        box-shadow: 4px 4px 0 var(--ink);
        color: var(--price);
        font-family: var(--font-data);
        font-size: 1.08rem;
        font-weight: 850;
        text-align: center;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
        transition:
          border-color 190ms cubic-bezier(0.22, 1, 0.36, 1),
          box-shadow 190ms cubic-bezier(0.22, 1, 0.36, 1),
          transform 190ms cubic-bezier(0.22, 1, 0.36, 1);
      }
      .deal:hover .price-pill,
      .deal:focus-within .price-pill {
        border-color: var(--focus);
        box-shadow:
          5px 5px 0 var(--ink),
          0 0 0 4px oklch(88% 0.18 126 / 0.24);
        transform: rotate(1.2deg);
      }
      .missing-price .price-pill {
        border-color: var(--border);
        background: transparent;
        box-shadow: none;
        color: var(--text-soft);
        font-weight: 700;
      }
      .featured {
        min-height: 164px;
        border-color: var(--ink);
        background:
          repeating-linear-gradient(135deg, oklch(100% 0 0 / 0.24) 0 10px, transparent 10px 20px),
          linear-gradient(142deg, var(--ticket) 0 62%, var(--lime) 62% 79%, var(--lavender) 79% 100%);
        color: var(--ticket-ink);
        box-shadow:
          8px 8px 0 var(--ink);
        transform-origin: 50% 30%;
      }
      .featured::before {
        content: "TOP";
        background: var(--pink);
      }
      .deal-stream:has(.featured:hover) .deal:not(:hover),
      .deal-stream:has(.featured:focus-within) .deal:not(:focus-within) {
        opacity: 0.46;
      }
      .featured:hover,
      .featured:focus-within {
        border-color: var(--focus);
        box-shadow:
          10px 10px 0 var(--ink),
          0 0 0 6px oklch(88% 0.18 126 / 0.26);
      }
      .featured h2 {
        color: oklch(100% 0 0);
        font-size: 2rem;
      }
      .featured .rank,
      .featured .score,
      .featured .facts,
      .featured .post-title {
        color: oklch(32% 0.06 70);
      }
      .featured .badge {
        border-color: var(--ink);
        background: var(--purple);
        color: oklch(100% 0 0);
      }
      .featured .price-pill {
        border-color: var(--ink);
        background: var(--lime);
        color: var(--ink);
      }
      .featured a.button {
        border-color: var(--ink);
        background: var(--surface);
        color: var(--ticket-ink);
      }
      .featured a.source {
        color: var(--ink);
      }
      .deal h2 {
        grid-column: 1;
        margin: 5px 0 6px;
        width: fit-content;
        max-width: 100%;
        padding: 4px 10px 5px;
        border: 2px solid var(--ink);
        background: var(--purple);
        box-shadow: 4px 4px 0 var(--ink);
        color: oklch(100% 0 0);
        font-family: var(--font-display);
        font-size: 1.34rem;
        line-height: 1.22;
        font-weight: 900;
        letter-spacing: 0;
        text-wrap: balance;
      }
      .facts {
        margin: 0 0 5px;
        color: var(--text-muted);
        font-size: 0.9rem;
        line-height: 1.45;
      }
      .facts strong { color: var(--text-strong); }
      .post-title {
        max-width: 70ch;
        margin: 0 0 12px;
        color: var(--text-muted);
        font-size: 0.86rem;
        line-height: 1.5;
        text-wrap: pretty;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin-bottom: 10px;
      }
      a.button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 38px;
        padding: 7px 11px;
        border: 2px solid var(--ink);
        border-radius: 999px;
        color: var(--text-strong);
        background: var(--surface);
        box-shadow: 3px 3px 0 var(--ink);
        font-size: 0.86rem;
        font-weight: 750;
        text-decoration: none;
        transition:
          background-color 180ms ease,
          border-color 180ms ease,
          box-shadow 180ms ease,
          transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
      }
      a.button:hover {
        border-color: var(--priority);
        background: var(--feedback-hover);
        box-shadow:
          4px 4px 0 var(--ink),
          0 0 0 3px oklch(82% 0.12 292 / 0.25);
        transform: translateY(-1px) scale(1.015);
      }
      a.button:active {
        transform: translateY(0) scale(0.98);
      }
      a.button:focus-visible,
      a.source:focus-visible {
        outline: 3px solid var(--focus);
        outline-offset: 3px;
      }
      a.source {
        color: var(--text-strong);
        font-size: 0.9rem;
        font-weight: 750;
        text-decoration-thickness: 1.5px;
        text-underline-offset: 4px;
      }
      .empty {
        margin-top: 18px;
        padding: 28px 22px;
        border: 3px dashed var(--ink);
        border-radius: 8px;
        background: var(--surface);
        box-shadow: var(--shadow);
      }
      .empty-icon {
        width: 48px;
        height: 48px;
        display: grid;
        place-items: center;
        margin-bottom: 12px;
        border-radius: 50%;
        background: var(--price-bg);
        font-size: 26px;
      }
      .empty h2 {
        margin: 0 0 8px;
        font-size: 1.35rem;
      }
      .empty p {
        margin: 0;
        max-width: 48ch;
        color: var(--text-muted);
        font-size: 0.96rem;
        line-height: 1.7;
      }
      @keyframes deal-rise {
        from {
          opacity: 0;
          transform: translateY(16px) scale(0.985);
        }
        to {
          opacity: 1;
          transform: translateY(0) scale(1);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        html { scroll-behavior: auto; }
        .deal {
          animation: none;
        }
        a.button {
          transition: none;
        }
        .deal,
        .deal::after,
        .price-pill {
          transition: none;
        }
        a.button:hover,
        a.button:active,
        .deal:hover,
        .deal:focus-within,
        .deal:hover .price-pill,
        .deal:focus-within .price-pill {
          transform: none;
        }
      }
      @media (max-width: 720px) {
        h1 { font-size: 2.85rem; }
        .deal h2 { font-size: 1.18rem; }
        .deal-stream { max-height: min(74vh, 620px); }
        .deal {
          grid-template-columns: minmax(0, 1fr);
        }
        .price-pill {
          grid-row: 2;
          justify-self: start;
        }
      }
      @media (max-width: 560px) {
        main { padding: 20px 16px 44px; }
        header { padding-top: 14px; }
        .brand { margin-bottom: 20px; }
        .logo {
          width: 44px;
          height: 44px;
          font-size: 23px;
        }
        h1 { font-size: 2.45rem; }
        .deal h2 { font-size: 1.12rem; }
        .deal {
          min-height: 132px;
          padding: 14px;
          border-radius: 16px;
        }
        .actions {
          display: grid;
          grid-template-columns: 1fr 1fr;
        }
        a.button { justify-content: center; padding-inline: 10px; }
      }
      @media (max-width: 360px) {
        .actions { grid-template-columns: 1fr; }
        h1 { font-size: 2.12rem; }
      }
    </style>
  </head>
  <body>
    <main>
      <div class="update-bar" id="update-bar" hidden>
        <span>雷达发现新内容</span>
        <button type="button" onclick="location.reload()">刷新列表</button>
      </div>
      <header>
        <div class="brand">
          <div class="logo">🐱</div>
          <div>
            <strong>Cat Deal Radar</strong>
            <span>${escapeHtml(subtitle)}</span>
          </div>
        </div>
        <h1>今晚猫车到站</h1>
        <div class="meta">
          <span>每 10 分钟摸一圈豆瓣</span>
          <span>更新于 ${escapeHtml(updatedAt)}</span>
          <span>本轮看帖 ${escapeHtml(run.posts_seen ?? "-")}，新 deal ${escapeHtml(run.deals_created ?? "-")}</span>
        </div>
      </header>
      <div class="feed-header">
        <div class="section-title">猫车直播流</div>
        <p class="feed-note">像睡前翻小票一样，先看最值得打开的那张。</p>
      </div>
      ${streamHint}
      ${emptyState}
      <section class="deal-stream" aria-label="猫车直播流">
        ${cards}
      </section>
    </main>
    <script>
      (() => {
        const current = ${JSON.stringify(fingerprint)};
        const bar = document.getElementById("update-bar");
        async function checkForUpdates() {
          try {
            const response = await fetch("/deals.json", { cache: "no-store" });
            if (!response.ok) return;
            const payload = await response.json();
            const deals = Array.isArray(payload.deals) ? payload.deals : [];
            const next = [
              payload.published_at || "",
              ...deals.slice(0, 8).map((deal) => deal.id),
            ].join("|");
            if (next && next !== current) {
              bar.hidden = false;
            }
          } catch (_error) {
          }
        }
        window.setInterval(checkForUpdates, 10 * 60 * 1000);
      })();
    </script>
  </body>
</html>`;
}

function renderDealCard(deal, index, url, compact = false) {
  const cats = "🐱".repeat(Math.max(1, Math.min(5, Number(deal.cat_score) || 1)));
  const priority = priorityLabel(deal.cat_score);
  const price = priceLabel(deal.price);
  const hasPrice = hasKnownPrice(deal.price);
  const sourceUrl = deal.post_url || "#";
  const feedbackLinks = feedbackLinksForDeal(deal, url);
  const classes = [
    "deal",
    index === 0 ? "featured" : "",
    compact ? "compact" : "",
    hasPrice ? "has-price" : "missing-price",
  ]
    .filter(Boolean)
    .join(" ");
  return `<article class="${classes}" style="--index:${Math.min(index, 8)}">
        <div>
        <div class="rank">
          <span>#${index + 1}</span>
          <span class="badge">${escapeHtml(priority)}</span>
          <span aria-label="${escapeHtml(Number(deal.cat_score) || 0)} 猫推荐指数">${cats}</span>
          <span class="score">信心分 ${escapeHtml(deal.confidence_score ?? "-")}</span>
        </div>
        <h2>${escapeHtml(deal.product_name || "未命名猫车")}</h2>
        <p class="facts">${escapeHtml(deal.brand || "未知品牌")} · ${escapeHtml(categoryLabel(deal.category))}</p>
        <p class="post-title">原帖：${escapeHtml(deal.post_title || "无标题")}</p>
        <div class="actions">
          <a class="button" href="${escapeHtml(feedbackLinks.more)}" aria-label="多推类似：${escapeHtml(deal.product_name || "这条猫车")}">❤️ 多推</a>
          <a class="button" href="${escapeHtml(feedbackLinks.less)}" aria-label="少推类似：${escapeHtml(deal.product_name || "这条猫车")}">🙈 少推</a>
          <a class="button" href="${escapeHtml(feedbackLinks.bought)}" aria-label="记录已下单：${escapeHtml(deal.product_name || "这条猫车")}">🛍️ 已下单</a>
          <a class="button" href="${escapeHtml(feedbackLinks.stock)}" aria-label="记录家里还有库存：${escapeHtml(deal.product_name || "这条猫车")}">📦 家里还有</a>
        </div>
        <a class="source" href="${escapeHtml(sourceUrl)}">打开豆瓣原帖 →</a>
        </div>
        <div class="price-pill">${escapeHtml(price)}</div>
      </article>`;
}

function dealsFingerprint(payload) {
  const deals = Array.isArray(payload.deals) ? payload.deals : [];
  return [payload.published_at || "", ...deals.slice(0, 8).map((deal) => deal.id)].join("|");
}

function feedbackLinksForDeal(deal, url) {
  const base = `${url.origin}/`;
  return Object.fromEntries(
    Object.keys(ACTION_TYPES).map((action) => {
      const params = new URLSearchParams({
        deal_id: String(deal.id || ""),
        action,
        brand: deal.brand || "",
        category: deal.category || "",
        douban_url: deal.post_url || "",
        price: deal.price == null ? "" : String(deal.price),
        title: deal.product_name || "",
      });
      return [action, `${base}?${params}`];
    }),
  );
}

function priorityLabel(catScore) {
  const score = Number(catScore) || 0;
  if (score >= 5) return "【必抢】";
  if (score >= 4) return "【推荐】";
  return "【可看】";
}

function priceLabel(price) {
  const value = Number(price);
  if (!Number.isFinite(value) || value <= 0) return "价格未知";
  const label = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, "");
  return `${label}元`;
}

function hasKnownPrice(price) {
  const value = Number(price);
  return Number.isFinite(value) && value > 0;
}

function categoryLabel(category) {
  return (
    {
      cat_food: "猫粮",
      wet_food: "罐头/湿粮",
      freeze_dried: "冻干",
      cat_litter: "猫砂",
    }[category] || category || "未知品类"
  );
}

function formatTime(value) {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

async function handleWeWorkCallback(request, env, url) {
  try {
    if (request.method === "GET") {
      return await verifyWeWorkCallback(env, url);
    }
    if (request.method === "POST") {
      return await receiveWeWorkMessage(request, env, url);
    }
  } catch (error) {
    console.error("wework_callback_failed", error);
    return new Response("wework callback failed", { status: 400 });
  }
  return new Response("method not allowed", { status: 405 });
}

async function verifyWeWorkCallback(env, url) {
  const encryptedEcho = requiredParam(url, "echostr");
  await assertWeWorkSignature(env, url, encryptedEcho);
  const echo = await decryptWeWorkMessage(env, encryptedEcho);
  return new Response(echo.message, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

async function receiveWeWorkMessage(request, env, url) {
  const body = await request.text();
  const encryptedMessage = xmlValue(body, "Encrypt");
  if (!encryptedMessage) {
    return new Response("missing Encrypt", { status: 400 });
  }

  await assertWeWorkSignature(env, url, encryptedMessage);
  const decrypted = await decryptWeWorkMessage(env, encryptedMessage);
  const message = parseWeWorkXml(decrypted.message);
  const feedback = parseWeWorkFeedback(message.content || "");

  if (!feedback) {
    await sendWeWorkConfirmation(env, {
      toUser: message.fromUser,
      content: "我没看懂这条反馈。可以回复：多推 123、少推 123、买了 123、家里还有 123。",
    });
    return new Response("success");
  }

  try {
    await writeFeedback(env, {
      dealId: feedback.dealId,
      action: feedback.action,
      brand: null,
      category: null,
      doubanUrl: null,
      feedbackType: ACTION_TYPES[feedback.action],
      price: null,
      title: `企业微信回复：${message.content}`,
      createdAt: Date.now(),
    });
    await sendWeWorkConfirmation(env, {
      toUser: message.fromUser,
      content: `已记录：${ACTION_LABELS[feedback.action]}（deal ${feedback.dealId}）。`,
    });
  } catch (error) {
    console.error(error);
    await sendWeWorkConfirmation(env, {
      toUser: message.fromUser,
      content: "反馈写入飞书失败了，我这边没收下这条记录。",
    });
  }

  return new Response("success");
}

function parseWeWorkFeedback(content) {
  const text = content.trim();
  const dealId = text.match(/\b\d+\b/)?.[0] || "";
  if (!dealId) return null;

  const normalized = text.replace(/\s+/g, "");
  const action =
    matchAny(normalized, ["多推", "类似", "more"]) ||
    matchAny(normalized, ["少推", "不推", "less"]) ||
    matchAny(normalized, ["已下单", "下单", "买了", "bought"]) ||
    matchAny(normalized, ["家里还有", "还有", "库存", "stock"]);
  if (!action) return null;
  return { dealId, action };
}

function matchAny(text, keywords) {
  if (keywords.some((keyword) => text.includes(keyword))) {
    if (keywords.includes("more")) return "more";
    if (keywords.includes("less")) return "less";
    if (keywords.includes("bought")) return "bought";
    if (keywords.includes("stock")) return "stock";
  }
  return null;
}

async function sendWeWorkConfirmation(env, { toUser, content }) {
  if (!env.WEWORK_CORP_ID || !env.WEWORK_APP_SECRET || !env.WEWORK_AGENT_ID || !toUser) {
    return;
  }
  const token = await weworkAccessToken(env);
  const response = await fetch(
    `${weworkBaseUrl()}/message/send?access_token=${encodeURIComponent(token)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        touser: toUser,
        msgtype: "text",
        agentid: Number(env.WEWORK_AGENT_ID),
        text: { content },
        safe: 0,
      }),
    },
  );
  await assertWeWorkOk(response);
}

async function weworkAccessToken(env) {
  const response = await fetch(
    `${weworkBaseUrl()}/gettoken?${new URLSearchParams({
      corpid: env.WEWORK_CORP_ID,
      corpsecret: env.WEWORK_APP_SECRET,
    })}`,
  );
  const data = await assertWeWorkOk(response);
  if (!data.access_token) {
    throw new Error("WeWork access token missing");
  }
  return data.access_token;
}

async function assertWeWorkOk(response) {
  const data = await response.json();
  if (!response.ok || data.errcode !== 0) {
    throw new Error(`WeWork API error: ${response.status} ${JSON.stringify(data).slice(0, 500)}`);
  }
  return data;
}

async function assertWeWorkSignature(env, url, encryptedMessage) {
  const signature = requiredParam(url, "msg_signature");
  const timestamp = requiredParam(url, "timestamp");
  const nonce = requiredParam(url, "nonce");
  const expected = await sha1Hex(
    [env.WEWORK_CALLBACK_TOKEN, timestamp, nonce, encryptedMessage].sort().join(""),
  );
  if (signature !== expected) {
    throw new Error("Invalid WeWork callback signature");
  }
}

async function decryptWeWorkMessage(env, encryptedMessage) {
  const key = encodingAesKeyBytes(env.WEWORK_ENCODING_AES_KEY);
  const encryptedBytes = base64ToBytes(encryptedMessage);
  const cryptoKey = await crypto.subtle.importKey("raw", key, "AES-CBC", false, ["decrypt"]);
  const decrypted = new Uint8Array(
    await crypto.subtle.decrypt({ name: "AES-CBC", iv: key.slice(0, 16) }, cryptoKey, encryptedBytes),
  );
  const plain = removePkcs7Padding(decrypted);
  const messageLength = new DataView(plain.buffer, plain.byteOffset + 16, 4).getUint32(0);
  const messageStart = 20;
  const messageEnd = messageStart + messageLength;
  const message = new TextDecoder().decode(plain.slice(messageStart, messageEnd));
  const receiveId = new TextDecoder().decode(plain.slice(messageEnd));
  if (env.WEWORK_CORP_ID && receiveId && receiveId !== env.WEWORK_CORP_ID) {
    throw new Error("WeWork callback receive id mismatch");
  }
  return { message, receiveId };
}

function encodingAesKeyBytes(encodingAesKey) {
  if (!encodingAesKey || encodingAesKey.length !== 43) {
    throw new Error("WEWORK_ENCODING_AES_KEY must be 43 characters");
  }
  return base64ToBytes(`${encodingAesKey}=`);
}

function removePkcs7Padding(bytes) {
  const padding = bytes.at(-1);
  if (!padding || padding < 1 || padding > 32) {
    throw new Error("Invalid PKCS7 padding");
  }
  return bytes.slice(0, bytes.length - padding);
}

function parseWeWorkXml(xml) {
  return {
    fromUser: xmlValue(xml, "FromUserName"),
    toUser: xmlValue(xml, "ToUserName"),
    content: xmlValue(xml, "Content"),
    msgType: xmlValue(xml, "MsgType"),
  };
}

function xmlValue(xml, tag) {
  const match = xml.match(new RegExp(`<${tag}><!\\[CDATA\\[([\\s\\S]*?)\\]\\]></${tag}>`));
  return match?.[1] || "";
}

async function sha1Hex(value) {
  const digest = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function base64ToBytes(value) {
  return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
}

function requiredParam(url, name) {
  const value = (url.searchParams.get(name) || "").trim();
  if (!value) {
    throw new Error(`Missing ${name}`);
  }
  return value;
}

function isPreviewMode(env) {
  return env.FEEDBACK_PREVIEW_MODE === "1";
}

async function writeFeedback(env, feedback) {
  const token = await tenantAccessToken(env);
  const response = await fetch(
    `${feishuBaseUrl()}/bitable/v1/apps/${env.FEISHU_BASE_TOKEN}/tables/${env.FEISHU_FEEDBACK_TABLE_ID}/records`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json; charset=utf-8",
      },
      body: JSON.stringify({
        fields: compactFields({
          deal_id: feedback.dealId,
          action: feedback.action,
          brand: feedback.brand,
          category: feedback.category,
          douban_url: feedback.doubanUrl,
          price: feedback.price,
          title: feedback.title,
          created_at: feedback.createdAt,
        }),
      }),
    },
  );
  await assertFeishuOk(response);
}

function optionalParam(url, name) {
  return (url.searchParams.get(name) || "").trim() || null;
}

function optionalPrice(url) {
  const value = optionalParam(url, "price");
  if (!value) return null;
  const price = Number(value);
  return Number.isFinite(price) && price > 0 ? price : null;
}

function compactFields(fields) {
  return Object.fromEntries(Object.entries(fields).filter(([, value]) => value !== null));
}

async function tenantAccessToken(env) {
  const response = await fetch(`${feishuBaseUrl()}/auth/v3/tenant_access_token/internal`, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      app_id: env.FEISHU_APP_ID,
      app_secret: env.FEISHU_APP_SECRET,
    }),
  });
  const data = await assertFeishuOk(response);
  if (!data.tenant_access_token) {
    throw new Error("Feishu tenant token missing");
  }
  return data.tenant_access_token;
}

async function assertFeishuOk(response) {
  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (error) {
    throw new Error(`Feishu returned non-JSON response: ${response.status} ${text.slice(0, 200)}`);
  }

  if (!response.ok || data.code !== 0) {
    throw new Error(`Feishu API error: ${response.status} ${text.slice(0, 500)}`);
  }
  return data;
}

function feishuBaseUrl() {
  return "https://open.feishu.cn/open-apis";
}

function weworkBaseUrl() {
  return "https://qyapi.weixin.qq.com/cgi-bin";
}

function htmlResponse(title, message, status = 200) {
  return new Response(
    `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>${escapeHtml(title)}</title>
    <style>
      :root {
        color-scheme: light;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #252525;
        background: #f6f3ea;
      }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 24px;
      }
      main {
        width: min(100%, 440px);
        background: #fffaf0;
        border: 1px solid #e6d8bd;
        border-radius: 8px;
        padding: 28px;
        box-shadow: 0 12px 30px rgba(42, 34, 20, 0.12);
      }
      h1 {
        margin: 0 0 12px;
        font-size: 26px;
        line-height: 1.2;
      }
      p {
        margin: 0;
        font-size: 16px;
        line-height: 1.7;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>${escapeHtml(title)}</h1>
      <p>${escapeHtml(message)}</p>
    </main>
  </body>
</html>`,
    {
      status,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    },
  );
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
