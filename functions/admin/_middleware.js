// /admin 이하 전체를 비밀번호로 보호한다. 비밀번호는 Cloudflare Pages 환경 변수 ADMIN_PASSWORD(비밀)로 설정.
import { isAdmin, checkPassword, makeToken, COOKIE } from "../../lib/common.js";

const page = (msg = "", noPw = false) => `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>관리자 로그인 | 생활노트</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f4fb;font-family:"Pretendard Variable",Pretendard,sans-serif;color:#1d1b2e}
.box{width:min(380px,92vw);background:#fff;border:1px solid #e9e6f3;border-radius:20px;padding:34px 30px;box-shadow:0 10px 40px rgba(60,30,150,.1)}
.mark{display:inline-grid;place-items:center;width:46px;height:46px;border-radius:14px;background:linear-gradient(90deg,#6d4bea,#e0479e);color:#fff;font-weight:800;font-size:20px}
h1{font-size:22px;margin:14px 0 4px}p{margin:0 0 20px;color:#6b6880;font-size:14px}
input{width:100%;padding:13px 16px;border:1px solid #e9e6f3;border-radius:12px;font:inherit;font-size:16px;outline:none;background:#f8f7fd}
input:focus{border-color:#6d4bea}button{width:100%;margin-top:12px;padding:13px;border:0;border-radius:12px;background:#1d1b2e;color:#fff;font:inherit;font-weight:700;font-size:16px;cursor:pointer}
button:hover{background:#6d4bea}.err{color:#d10000;font-size:14px;margin:10px 0 0}a{color:#6b6880;font-size:13px}
</style></head><body><form class="box" method="post" action="/admin/login">
<span class="mark">생</span><h1>관리자 로그인</h1><p>생활노트 관리자 전용 공간입니다.</p>
${noPw ? '<p class="err">관리자 비밀번호가 아직 설정되지 않았습니다. Cloudflare Pages 설정에서 ADMIN_PASSWORD를 추가해 주세요.</p>'
       : '<input type="password" name="pw" placeholder="비밀번호" autocomplete="current-password" required autofocus><button type="submit">로그인</button>'}
${msg ? `<p class="err">${msg}</p>` : ""}
<p style="margin:18px 0 0"><a href="/">← 사이트로 돌아가기</a></p></form></body></html>`;

const html = (body, status = 200, headers = {}) =>
  new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", ...headers } });

export async function onRequest(ctx) {
  const { request, env, next } = ctx;
  const url = new URL(request.url);

  if (url.pathname === "/admin/logout") {
    return new Response(null, { status: 302, headers: { Location: "/admin/", "Set-Cookie": `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict` } });
  }
  if (url.pathname === "/admin/login" && request.method === "POST") {
    const form = await request.formData().catch(() => null);
    const pw = form ? form.get("pw") : "";
    if (!checkPassword(pw, env)) {
      await new Promise(r => setTimeout(r, 1000));       // 비밀번호 대입 공격을 늦춤
      return html(page("비밀번호가 맞지 않습니다.", !env.ADMIN_PASSWORD), 401);
    }
    const tok = await makeToken(env.ADMIN_PASSWORD);
    return new Response(null, { status: 302, headers: {
      Location: "/admin/", "Cache-Control": "no-store",
      "Set-Cookie": `${COOKIE}=${tok}; Path=/; Max-Age=${30 * 86400}; HttpOnly; Secure; SameSite=Strict` } });
  }
  if (!(await isAdmin(request, env))) return html(page("", !env.ADMIN_PASSWORD), env.ADMIN_PASSWORD ? 200 : 503);

  const res = await next();
  const out = new Response(res.body, res);
  out.headers.set("Cache-Control", "no-store");
  out.headers.set("X-Robots-Tag", "noindex, nofollow");
  return out;
}
