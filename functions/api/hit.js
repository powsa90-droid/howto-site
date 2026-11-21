// 페이지 조회 1건 기록: 글 페이지의 스크립트가 navigator.sendBeacon('/api/hit', {...}) 으로 호출
import { ensureSchema, classify, deviceOf, BOT_RE, kstDay, sha256Hex, isAdmin } from "../../lib/common.js";

export async function onRequestPost({ request, env }) {
  const ok = new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
  try {
    if (!env.DB) return ok;
    const ua = request.headers.get("User-Agent") || "";
    if (!ua || BOT_RE.test(ua)) return ok;
    if (await isAdmin(request, env)) return ok;          // 관리자 본인 방문은 세지 않음

    let body = {};
    try { body = JSON.parse(await request.text()); } catch { return ok; }
    const path = String(body.p || "").slice(0, 300);
    if (!path.startsWith("/") || path.startsWith("/admin") || path.startsWith("/api")) return ok;

    const selfHost = new URL(request.url).hostname;
    const ref = classify(String(body.r || "").slice(0, 500), selfHost);
    const now = new Date();
    const day = kstDay(now);
    const ip = request.headers.get("CF-Connecting-IP") || "";
    // IP는 저장하지 않고, 날짜별로 바뀌는 익명 식별값만 저장
    const vid = (await sha256Hex(`${day}|${ip}|${ua}|${env.ADMIN_PASSWORD || "salt"}`)).slice(0, 16);

    await ensureSchema(env.DB);
    await env.DB.prepare(
      "INSERT INTO hits (ts, day, path, ref_group, ref_name, ref_host, keyword, device, country, vid) VALUES (?,?,?,?,?,?,?,?,?,?)"
    ).bind(now.getTime(), day, path, ref.group, ref.name, ref.host || null, ref.keyword || null,
           deviceOf(ua), (request.cf && request.cf.country) || null, vid).run();
  } catch (e) {
    // 통계 실패가 방문자에게 영향을 주지 않도록 조용히 무시
  }
  return ok;
}
