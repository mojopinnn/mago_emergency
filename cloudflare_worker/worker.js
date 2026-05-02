/**
 * MAGO Emergency - Cloudflare Worker
 *
 * 역할:
 *   1. ShotGrid AMI 웹훅을 집 서버로 중계
 *   2. 집 서버가 꺼져 있으면 → KV 대기열에 저장
 *   3. 집 서버가 켜지면 → /worker/pending 을 호출해 대기열 처리
 *
 * 환경변수 (wrangler secret 으로 설정):
 *   HOME_SERVER_URL  : 집 서버 주소 (예: https://xxx.devtunnels.ms)
 *   RELAY_SECRET     : 워커 ↔ 집 서버 인증 토큰 (임의 문자열)
 *
 * KV 바인딩:
 *   MAGO_KV          : KV namespace
 */

const TIMEOUT_MS   = 4000;
const QUEUE_PREFIX = "pending_";
const QUEUE_TTL    = 86400; // 24시간

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 집 서버가 대기열 목록을 가져가는 엔드포인트
    if (request.method === "GET" && url.pathname === "/worker/pending") {
      return handleGetPending(request, env);
    }

    // 처리 완료된 대기열 항목 삭제
    if (request.method === "DELETE" && url.pathname.startsWith("/worker/pending/")) {
      const key = url.pathname.slice("/worker/pending/".length);
      return handleDeletePending(request, env, key);
    }

    // ShotGrid AMI 웹훅 수신 및 중계
    if (request.method === "POST" && url.pathname === "/sg_webhook") {
      return handleWebhook(request, env, ctx);
    }

    return new Response("Not Found", { status: 404 });
  },
};


// ── ShotGrid AMI 중계 ──────────────────────────────────────────

async function handleWebhook(request, env, ctx) {
  const formData = await request.formData();
  const formEntries = {};
  for (const [k, v] of formData.entries()) {
    formEntries[k] = v;
  }

  const homeUrl = `${env.HOME_SERVER_URL}/sg_webhook`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const newForm = new FormData();
    for (const [k, v] of Object.entries(formEntries)) {
      newForm.append(k, v);
    }

    const response = await fetch(homeUrl, {
      method: "POST",
      body: newForm,
      signal: controller.signal,
      headers: { "X-Relay-Secret": env.RELAY_SECRET || "" },
    });

    clearTimeout(timer);

    const text = await response.text();
    return new Response(text, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });

  } catch (err) {
    clearTimeout(timer);

    // 집 서버 오프라인 → KV 대기열에 저장
    const queueKey = `${QUEUE_PREFIX}${Date.now()}`;
    await env.MAGO_KV.put(
      queueKey,
      JSON.stringify({ formData: formEntries, timestamp: Date.now() }),
      { expirationTtl: QUEUE_TTL }
    );

    console.log(`[MAGO] 집 서버 오프라인 → 대기열 저장: ${queueKey}`);

    // ShotGrid에는 200 반환 (에러 표시 방지)
    return new Response(
      JSON.stringify({ ok: true, status: "queued", key: queueKey }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }
}


// ── 대기열 조회 ─────────────────────────────────────────────────

async function handleGetPending(request, env) {
  const secret = request.headers.get("X-Relay-Secret");
  if (env.RELAY_SECRET && secret !== env.RELAY_SECRET) {
    return new Response("Unauthorized", { status: 401 });
  }

  const list = await env.MAGO_KV.list({ prefix: QUEUE_PREFIX });
  const items = [];

  for (const key of list.keys) {
    const value = await env.MAGO_KV.get(key.name);
    if (value) {
      items.push({ key: key.name, data: JSON.parse(value) });
    }
  }

  return new Response(JSON.stringify({ items }), {
    headers: { "Content-Type": "application/json" },
  });
}


// ── 대기열 항목 삭제 ─────────────────────────────────────────────

async function handleDeletePending(request, env, key) {
  const secret = request.headers.get("X-Relay-Secret");
  if (env.RELAY_SECRET && secret !== env.RELAY_SECRET) {
    return new Response("Unauthorized", { status: 401 });
  }

  await env.MAGO_KV.delete(key);
  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
}
