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
  async fetch(request, env) {
    if (request.method !== "GET") {
      return htmlResponse("不支持的请求", "请从邮件里的反馈链接打开。", 405);
    }

    const url = new URL(request.url);
    const dealId = (url.searchParams.get("deal_id") || "").trim();
    const action = (url.searchParams.get("action") || "").trim();

    if (!dealId || !ACTION_TYPES[action]) {
      return htmlResponse("反馈链接无效", "缺少 deal_id 或 action 参数。", 400);
    }

    try {
      await writeFeedback(env, {
        dealId,
        action,
        feedbackType: ACTION_TYPES[action],
        createdAt: new Date().toISOString(),
      });
    } catch (error) {
      console.error(error);
      return htmlResponse("记录失败", "飞书暂时没有收下这条反馈，请稍后再试。", 502);
    }

    return htmlResponse(
      "已记录，谢谢",
      `这条反馈是：${ACTION_LABELS[action]}。之后推荐会按你的选择慢慢变聪明。`,
    );
  },
};

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
        fields: {
          deal_id: feedback.dealId,
          action: feedback.action,
          created_at: feedback.createdAt,
        },
      }),
    },
  );
  await assertFeishuOk(response);
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
