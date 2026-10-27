// Cloudflare Worker: hyinventory GitHub 저장 프록시
// - GitHub 토큰은 Worker의 비밀값(GITHUB_TOKEN)에만 보관. 브라우저/공개 저장소에는 없음.
// - data.json 한 파일의 읽기(GET)/저장(PUT)만 중계.

const REPO = "poodingcake-hue/hyinventory";
const FILE = "data.json";
const ALLOWED_ORIGINS = ["https://poodingcake-hue.github.io"];
const MAX_BODY_BYTES = 3 * 1024 * 1024;

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = ALLOWED_ORIGINS.includes(origin);
    const cors = {
      "Access-Control-Allow-Origin": allowed ? origin : ALLOWED_ORIGINS[0],
      "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin",
    };
    const json = (obj, status) =>
      new Response(JSON.stringify(obj), { status, headers: { ...cors, "Content-Type": "application/json" } });

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (origin && !allowed) return json({ message: "forbidden origin" }, 403);
    if (request.method !== "GET" && request.method !== "PUT") return json({ message: "method not allowed" }, 405);
    if (!env.GITHUB_TOKEN) return json({ message: "server token is not configured" }, 500);

    const init = {
      method: request.method,
      headers: {
        "Authorization": `token ${env.GITHUB_TOKEN}`,
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "hyinventory-proxy",
      },
    };
    if (request.method === "PUT") {
      const body = await request.text();
      if (body.length > MAX_BODY_BYTES) return json({ message: "payload too large" }, 413);
      init.headers["Content-Type"] = "application/json";
      init.body = body;
    }

    const res = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE}`, init);
    return new Response(res.body, {
      status: res.status,
      headers: { ...cors, "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  },
};
