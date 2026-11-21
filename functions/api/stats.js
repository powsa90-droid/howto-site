// 관리자 통계 데이터 (로그인한 관리자만)
// GET /api/stats?unit=day|week|month&end=YYYY-MM-DD&from=YYYY-MM-DD&to=YYYY-MM-DD
import { ensureSchema, isAdmin, json, kstDay, addDays } from "../../lib/common.js";

const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

function periods(unit, end) {
  // 그래프에 쓸 구간 목록 (오래된 것 → 최근)
  const out = [];
  if (unit === "week") {
    // 월요일 시작 주, 12주
    const d = new Date(end + "T00:00:00Z");
    const mon = addDays(end, -((d.getUTCDay() + 6) % 7));
    for (let i = 11; i >= 0; i--) {
      const s = addDays(mon, -7 * i);
      out.push({ from: s, to: addDays(s, 6), label: s.slice(5).replace("-", ".") + "~" });
    }
  } else if (unit === "month") {
    let [y, m] = end.split("-").map(Number);
    const list = [];
    for (let i = 0; i < 12; i++) {
      const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
      list.unshift({ from: `${y}-${String(m).padStart(2, "0")}-01`, to: `${y}-${String(m).padStart(2, "0")}-${last}`, label: `${m}월` });
      if (--m === 0) { m = 12; y--; }
    }
    out.push(...list);
  } else {
    for (let i = 20; i >= 0; i--) {
      const s = addDays(end, -i);
      out.push({ from: s, to: s, label: String(Number(s.slice(8))) });
    }
  }
  return out;
}

export async function onRequestGet({ request, env }) {
  if (!(await isAdmin(request, env))) return json({ error: "unauthorized" }, 401);
  if (!env.DB) return json({ error: "no_db" }, 500);
  await ensureSchema(env.DB);
  const db = env.DB;
  const q = new URL(request.url).searchParams;
  const today = kstDay();
  const unit = ["day", "week", "month"].includes(q.get("unit")) ? q.get("unit") : "day";
  const end = DAY_RE.test(q.get("end") || "") ? q.get("end") : today;
  const ps = periods(unit, end);
  const from = DAY_RE.test(q.get("from") || "") ? q.get("from") : ps[ps.length - 1].from;
  const to = DAY_RE.test(q.get("to") || "") ? q.get("to") : ps[ps.length - 1].to;
  const yday = addDays(today, -1);

  const [sumDay, total, series, refs, devices, pages, keywords, others] = await db.batch([
    db.prepare("SELECT day, COUNT(*) v, COUNT(DISTINCT vid) u FROM hits WHERE day IN (?, ?) GROUP BY day").bind(today, yday),
    db.prepare("SELECT (SELECT COUNT(*) FROM hits) v, (SELECT COUNT(*) FROM (SELECT DISTINCT day, vid FROM hits)) u"),
    db.prepare("SELECT day, COUNT(*) v, COUNT(DISTINCT vid) u FROM hits WHERE day BETWEEN ? AND ? GROUP BY day").bind(ps[0].from, ps[ps.length - 1].to),
    db.prepare("SELECT ref_group g, ref_name n, COUNT(*) c FROM hits WHERE day BETWEEN ? AND ? GROUP BY g, n").bind(from, to),
    db.prepare("SELECT device d, COUNT(*) c FROM hits WHERE day BETWEEN ? AND ? GROUP BY d").bind(from, to),
    db.prepare("SELECT path p, COUNT(*) c FROM hits WHERE day BETWEEN ? AND ? GROUP BY p ORDER BY c DESC LIMIT 20").bind(from, to),
    db.prepare("SELECT keyword k, COUNT(*) c FROM hits WHERE keyword IS NOT NULL AND keyword <> '' AND day BETWEEN ? AND ? GROUP BY k ORDER BY c DESC LIMIT 30").bind(from, to),
    db.prepare("SELECT ref_host h, COUNT(*) c FROM hits WHERE ref_name = '기타 유입' AND day BETWEEN ? AND ? GROUP BY h ORDER BY c DESC LIMIT 30").bind(from, to),
  ]);

  const byDay = Object.fromEntries((series.results || []).map(r => [r.day, r]));
  const seriesOut = ps.map(p => {
    let v = 0, u = 0;
    for (let d = p.from; d <= p.to; d = addDays(d, 1)) {
      if (byDay[d]) { v += byDay[d].v; u += byDay[d].u; }
    }
    return { ...p, views: v, visitors: u };
  });
  const sd = Object.fromEntries((sumDay.results || []).map(r => [r.day, r]));
  const t = (total.results || [])[0] || { v: 0, u: 0 };

  return json({
    today, unit, end, from, to,
    summary: {
      todayViews: sd[today]?.v || 0, ydayViews: sd[yday]?.v || 0, totalViews: t.v || 0,
      todayVisitors: sd[today]?.u || 0, ydayVisitors: sd[yday]?.u || 0, totalVisitors: t.u || 0,
    },
    series: seriesOut,
    refs: refs.results || [],
    devices: devices.results || [],
    pages: pages.results || [],
    keywords: keywords.results || [],
    others: others.results || [],
  });
}
