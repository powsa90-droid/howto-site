// 방문 통계·관리자 공통 함수 (Cloudflare Pages Functions에서 import)

export const COOKIE = "sn_admin";
const enc = new TextEncoder();

// ---------------------------------------------------------------- 날짜(KST)
export function kstDay(d = new Date()) {
  return new Date(d.getTime() + 9 * 3600e3).toISOString().slice(0, 10);
}
export function addDays(day, n) {
  const t = new Date(day + "T00:00:00Z");
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------- 해시·서명
async function hmacHex(secret, msg) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(msg));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("");
}
export async function sha256Hex(msg) {
  const h = await crypto.subtle.digest("SHA-256", enc.encode(msg));
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, "0")).join("");
}
function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

// ---------------------------------------------------------------- 관리자 쿠키
export async function makeToken(secret, days = 30) {
  const exp = Date.now() + days * 864e5;
  return `${exp}.${await hmacHex(secret, "admin|" + exp)}`;
}
export function getCookie(request, name) {
  const c = request.headers.get("Cookie") || "";
  const m = c.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[1]) : "";
}
export async function isAdmin(request, env) {
  const secret = env.ADMIN_PASSWORD;
  if (!secret) return false;
  const tok = getCookie(request, COOKIE);
  const [exp, sig] = tok.split(".");
  if (!exp || !sig || Number(exp) < Date.now()) return false;
  return safeEqual(sig, await hmacHex(secret, "admin|" + exp));
}
export function checkPassword(input, env) {
  return !!env.ADMIN_PASSWORD && typeof input === "string" && safeEqual(input, env.ADMIN_PASSWORD);
}

// ---------------------------------------------------------------- DB
let ready = false;
export async function ensureSchema(db) {
  if (ready) return;
  await db.batch([
    db.prepare(`CREATE TABLE IF NOT EXISTS hits (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts INTEGER NOT NULL, day TEXT NOT NULL, path TEXT NOT NULL,
      ref_group TEXT NOT NULL, ref_name TEXT NOT NULL, ref_host TEXT, keyword TEXT,
      device TEXT NOT NULL, country TEXT, vid TEXT NOT NULL)`),
    db.prepare("CREATE INDEX IF NOT EXISTS idx_hits_day ON hits(day)"),
    db.prepare("CREATE INDEX IF NOT EXISTS idx_hits_day_vid ON hits(day, vid)"),
  ]);
  ready = true;
}

// ---------------------------------------------------------------- 유입 경로 분류
const SEARCH = [
  [/(^|\.)google\./, "구글 검색"], [/(^|\.)naver\.com$/, "네이버 검색"], [/(^|\.)daum\.net$/, "다음 검색"],
  [/(^|\.)bing\.com$/, "빙 검색"], [/(^|\.)zum\.com$/, "줌 검색"], [/(^|\.)yahoo\./, "야후 검색"],
  [/(duckduckgo\.com|baidu\.com|yandex\.|ecosia\.org|naver\.me)$/, "기타 검색"],
];
const SNS = [
  [/(^|\.)kakao(talk)?\.(com|co\.kr)$|^talk\.kakao|^k\.kakaocdn/, "카카오톡"], [/story\.kakao\.com$/, "카카오스토리"],
  [/(^|\.)(facebook\.com|fb\.com|fb\.me)$/, "페이스북"], [/(^|\.)(twitter\.com|x\.com|t\.co)$/, "트위터(X)"],
  [/(^|\.)(youtube\.com|youtu\.be)$/, "유튜브"], [/(^|\.)instagram\.com$/, "인스타그램"],
  [/(^|\.)(threads\.net|band\.us|pinterest\.|linkedin\.com|reddit\.com)/, "기타 SNS"],
];
export function classify(ref, selfHost) {
  if (!ref) return { group: "기타", name: "직접 유입", host: "", keyword: "" };
  let u;
  try { u = new URL(ref); } catch { return { group: "기타", name: "직접 유입", host: "", keyword: "" }; }
  const host = u.hostname.replace(/^www\.|^m\./, "").toLowerCase();
  if (selfHost && (host === selfHost.replace(/^www\./, "") || u.hostname === selfHost))
    return { group: "내부", name: "사이트 내 이동", host: "", keyword: "" };
  // 카카오스토리를 카카오톡보다 먼저 확인
  if (/story\.kakao\.com$/.test(host)) return { group: "SNS", name: "카카오스토리", host, keyword: "" };
  for (const [re, name] of SEARCH) {
    if (re.test(host)) {
      // 네이버는 검색이 아닌 서비스(블로그·카페)에서 온 경우 기타로
      if (name === "네이버 검색" && !/search\.naver\.com$/.test(u.hostname) && !u.searchParams.get("query"))
        return { group: "기타", name: "기타 유입", host, keyword: "" };
      const kw = (u.searchParams.get("query") || u.searchParams.get("q") || u.searchParams.get("p") || "").trim().slice(0, 80);
      return { group: "검색", name, host, keyword: kw };
    }
  }
  for (const [re, name] of SNS) if (re.test(host)) return { group: "SNS", name, host, keyword: "" };
  return { group: "기타", name: "기타 유입", host, keyword: "" };
}

export function deviceOf(ua) {
  return /Mobi|Android|iPhone|iPod|iPad|Windows Phone/i.test(ua || "") ? "모바일" : "PC";
}
export const BOT_RE = /bot|crawl|spider|slurp|headless|lighthouse|pagespeed|preview|facebookexternalhit|bingpreview|python|curl|wget|httpclient|monitor|uptime|scrapy|phantom|selenium|puppeteer|playwright/i;

export const json = (data, status = 200, extra = {}) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra } });
