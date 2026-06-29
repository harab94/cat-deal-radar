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

    if (request.method !== "GET") {
      return htmlResponse("不支持的请求", "请从邮件里的反馈链接打开。", 405);
    }

    const dealId = (url.searchParams.get("deal_id") || "").trim();
    const action = (url.searchParams.get("action") || "").trim();

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
        inputs: { send_test_email: "false" },
      }),
    },
  );

  if (response.status !== 204) {
    const body = await response.text();
    throw new Error(`GitHub workflow dispatch failed: ${response.status} ${body.slice(0, 500)}`);
  }

  console.log("radar_workflow_dispatched", { repository, workflowId, ref });
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
