#!/usr/bin/env python3
"""하우투 정보 사이트 빌드 스크립트.

data/config.json + data/posts/*.json  ->  site/ (정적 HTML 전체)

글 JSON 형식:
{
  "kw": "포장이사 견적 받는 방법",
  "title": "포장이사 견적 받는 방법 비용 시기 알아보기",
  "slug": "moving-quote-how-to",
  "category": "moving",                # config.categories 의 slug
  "date": "2026-11-21",
  "desc": "메타 설명 120자 안팎(키워드 포함)",
  "url": "https://...",                # 링크 카드 주소(공식 사이트 또는 제휴 링크)
  "og_title": "...", "og_desc": "...", "og_host": "example.com",
  "aff": false,                        # true면 제휴 링크 고지 문구와 rel=sponsored
  "captions": ["01 설명", "02 설명", ... 16개],   # 선택
  "body": [
    "IMG1",                 # 대표 이미지 images/{slug}/01.jpg
    "P:문단",               # 일반 문단 (**굵게** 지원)
    "EM:강조 문단",          # 노란 배경 빨간 굵은 글씨
    "AD1", "AD2", "AD3",    # 광고 자리
    "G1" ~ "G5",            # 이미지 3장 묶음 (G1=02~04, G2=05~07 ... G5=14~16)
    "H2",                   # 제목과 같은 보라 h2 (H2:문구 로 다른 문구 가능)
    "H3:소제목",             # 본론 소제목(선택)
    "OG"                    # 링크 카드
  ]
}
H2 이전이 서론으로 계산된다. 기준: 전체 1,700자 / 서론 500자(띄어쓰기 제외), 서론 키워드 4회.
"""
import csv, glob, html, json, os, re, shutil
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
KST = timezone(timedelta(hours=9))

MIN_TOTAL, MIN_INTRO, MIN_KW = 1700, 500, 4
RESERVED = {"images", "about", "contact", "privacy", "assets"}

cfg = json.load(open(os.path.join(DATA, "config.json"), encoding="utf-8"))
DOMAIN = cfg["domain"].rstrip("/")
NAME = cfg["site_name"]
CATS = {c["slug"]: c["name"] for c in cfg["categories"]}
esc = lambda s: html.escape(str(s or ""), quote=True)


def inline(s):
    s = esc(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def nospace_len(s):
    return len(re.sub(r"\s", "", s))


def write(path, text):
    full = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------- 공통 틀
def head(title, desc, canonical, og_image=None, og_type="website", jsonld=None):
    img = og_image or f"{DOMAIN}/assets/og-default.png"
    ads = ""
    if cfg.get("ADSENSE_CLIENT"):
        ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={esc(cfg["ADSENSE_CLIENT"])}" '
               'crossorigin="anonymous"></script>')
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    return f"""<!doctype html>
<html lang="{cfg.get('lang','ko')}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{esc(NAME)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="{esc(NAME)}" href="{DOMAIN}/rss.xml">
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="/assets/favicon.png">
{ld}
{ads}
{cfg.get('HEAD_EXTRA','')}
</head>
<body>
<header class="top"><div class="wrap">
<a class="logo" href="/">{esc(NAME)}</a>
<nav>{''.join(f'<a href="/{s}/">{esc(n)}</a>' for s, n in CATS.items())}</nav>
</div></header>
<main class="wrap">
"""


def foot():
    year = datetime.now(KST).year
    return f"""</main>
<footer class="bottom"><div class="wrap">
<p><a href="/about/">소개</a> · <a href="/contact/">문의</a> · <a href="/privacy/">개인정보처리방침</a></p>
<p>© {year} {esc(NAME)}. 이 사이트의 글은 공식 사이트의 안내를 바탕으로 작성되며, 실제 내용은 각 기관·업체 사정에 따라 바뀔 수 있습니다.</p>
</div></footer>
</body></html>
"""


def ad_slot():
    return f'<div class="ad-slot">{cfg.get("AD","")}</div>'


# ---------------------------------------------------------------- 글 읽기
def load_posts():
    posts = []
    for fp in sorted(glob.glob(os.path.join(DATA, "posts", "*.json"))):
        p = json.load(open(fp, encoding="utf-8"))
        for k in ("kw", "title", "slug", "category", "date", "desc", "body"):
            if not p.get(k):
                raise SystemExit(f"{fp}: '{k}' 값이 없습니다")
        if p["category"] not in CATS:
            raise SystemExit(f"{fp}: 카테고리 '{p['category']}' 가 config에 없습니다")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p["slug"]):
            raise SystemExit(f"{fp}: slug는 영문 소문자·숫자·하이픈만 씁니다")
        posts.append(p)
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


def img_src(p, n):
    return f"/images/{p['slug']}/{n:02d}.jpg"


def caption(p, n):
    caps = p.get("captions") or []
    return caps[n - 1] if len(caps) >= n else ""


def figure(p, n, cls=""):
    cap = caption(p, n)
    return (f'<figure class="{cls}"><img src="{img_src(p, n)}" alt="{esc(p["kw"])}" loading="lazy" decoding="async">'
            + (f"<figcaption>{esc(cap)}</figcaption>" if cap else "") + "</figure>")


def link_card(p):
    if not p.get("url"):
        return ""
    rel = 'rel="sponsored noopener" ' if p.get("aff") else 'rel="noopener" '
    return f"""<a class="link-card" href="{esc(p['url'])}" {rel}target="_blank">
<span class="lc-host">{esc(p.get('og_host',''))}</span>
<strong class="lc-title">{esc(p.get('og_title') or p['url'])}</strong>
<span class="lc-desc">{esc(p.get('og_desc',''))}</span>
<span class="lc-go">바로가기 →</span></a>"""


def render_body(p):
    out, intro_text, all_text, seen_h2 = [], [], [], False
    for item in p["body"]:
        if item == "IMG1":
            out.append(figure(p, 1, "hero"))
        elif item.startswith("P:"):
            t = item[2:].strip()
            out.append(f"<p>{inline(t)}</p>")
            all_text.append(t); (intro_text if not seen_h2 else []).append(t)
        elif item.startswith("EM:"):
            t = item[3:].strip()
            out.append(f'<p class="em">{inline(t)}</p>')
            all_text.append(t); (intro_text if not seen_h2 else []).append(t)
        elif item in ("AD1", "AD2", "AD3"):
            out.append(ad_slot())
        elif re.fullmatch(r"G[1-5]", item):
            g = int(item[1]); start = 2 + (g - 1) * 3
            out.append('<div class="grid">' + "".join(figure(p, n) for n in range(start, start + 3)) + "</div>")
        elif item == "H2" or item.startswith("H2:"):
            seen_h2 = True
            out.append(f'<h2 class="h2">{esc(item[3:].strip() if item.startswith("H2:") else p["title"])}</h2>')
        elif item.startswith("H3:"):
            seen_h2 = True
            out.append(f"<h3>{esc(item[3:].strip())}</h3>")
        elif item == "OG":
            out.append(link_card(p))
        else:
            raise SystemExit(f"{p['slug']}: 알 수 없는 body 항목 '{item[:20]}'")
    intro = " ".join(intro_text); total = " ".join(all_text)
    stats = dict(total=nospace_len(total), intro=nospace_len(intro), kw=intro.count(p["kw"]))
    return "\n".join(out), stats


# ---------------------------------------------------------------- 페이지
def card(p):
    return f"""<a class="card" href="/{p['slug']}/">
<img src="{img_src(p, 1)}" alt="{esc(p['kw'])}" loading="lazy">
<div><span class="cat">{esc(CATS[p['category']])}</span>
<strong>{esc(p['title'])}</strong><p>{esc(p['desc'])}</p></div></a>"""


def post_page(p, posts):
    body, stats = render_body(p)
    url = f"{DOMAIN}/{p['slug']}/"
    related = [q for q in posts if q["category"] == p["category"] and q["slug"] != p["slug"]][:3]
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": p["title"],
          "description": p["desc"], "datePublished": p["date"], "dateModified": p.get("updated", p["date"]),
          "image": [DOMAIN + img_src(p, 1)], "mainEntityOfPage": url,
          "author": {"@type": "Organization", "name": NAME}, "publisher": {"@type": "Organization", "name": NAME}}
    notice = f'<p class="aff-notice">{esc(cfg["affiliate_notice"])}</p>' if p.get("aff") else ""
    rel_html = ""
    if related:
        rel_html = '<section class="related"><h3>함께 보면 좋은 글</h3><ul>' + "".join(
            f'<li><a href="/{q["slug"]}/">{esc(q["title"])}</a></li>' for q in related) + "</ul></section>"
    html_ = head(p["title"], p["desc"], url, DOMAIN + img_src(p, 1), "article", ld) + f"""
<article class="post">
<p class="crumb"><a href="/">홈</a> › <a href="/{p['category']}/">{esc(CATS[p['category']])}</a></p>
<h1>{esc(p['title'])}</h1>
<p class="meta">{esc(p['date'])} · {esc(CATS[p['category']])}</p>
{notice}
{body}
</article>
{rel_html}
""" + foot()
    write(f"{p['slug']}/index.html", html_)
    return stats


def list_page(path, title, desc, items, heading):
    url = f"{DOMAIN}/{path}"
    cards = "".join(card(p) for p in items) or '<p class="empty">곧 첫 글이 올라옵니다.</p>'
    write(f"{path}index.html", head(title, desc, url) + f"""
<section class="intro"><h1>{esc(heading)}</h1><p>{esc(desc)}</p></section>
<div class="cards">{cards}</div>
""" + foot())


def static_page(slug, title, paragraphs):
    url = f"{DOMAIN}/{slug}/"
    body = "".join(f"<h2>{esc(x[3:])}</h2>" if x.startswith("## ") else f"<p>{x}</p>" for x in paragraphs)
    write(f"{slug}/index.html", head(f"{title} | {NAME}", f"{NAME} {title}", url) +
          f'<article class="post page"><h1>{esc(title)}</h1>{body}</article>' + foot())


def static_pages():
    mail = esc(cfg["contact_email"]); n = esc(NAME)
    static_page("about", "소개", [
        f"{n}은 일상에서 자주 검색하지만 막상 찾으면 설명이 흩어져 있는 생활 정보를 한곳에 모아 정리하는 사이트입니다. 이사와 입주 준비, 청소와 살림, 자동차 관리, 스마트폰과 각종 앱 설정, 전입신고 같은 생활 행정까지 실제로 따라 할 수 있도록 순서대로 안내합니다.",
        "모든 글은 해당 기관이나 업체의 공식 홈페이지와 공식 도움말을 직접 확인한 뒤 작성합니다. 이용 화면을 단계별로 캡처해 함께 싣기 때문에 처음 해 보는 분도 화면을 보면서 그대로 진행할 수 있습니다.",
        "제도나 서비스 내용은 수시로 바뀔 수 있습니다. 글에 적힌 내용과 실제 화면이 다르다면 공식 사이트의 최신 안내를 따라 주시고, 문의 페이지로 알려 주시면 확인 후 바로 고치겠습니다.",
        "일부 글에는 관련 서비스로 연결되는 제휴 링크가 포함될 수 있으며, 이 경우 글 상단에 따로 표시합니다. 제휴 여부와 관계없이 글의 내용은 공식 안내와 사실을 기준으로 작성합니다.",
    ])
    static_page("contact", "문의", [
        f"{n}에 대한 문의, 글 내용 수정 요청, 제휴 제안은 아래 이메일로 보내 주세요. 보통 영업일 기준 2~3일 안에 답변드립니다.",
        f'이메일: <a href="mailto:{mail}">{mail}</a>',
        "글의 정보가 바뀌었거나 잘못된 부분을 발견하셨다면 글 주소와 함께 알려 주시면 빠르게 확인하겠습니다. 개인정보가 포함된 내용은 보내지 않으셔도 됩니다.",
    ])
    today = datetime.now(KST).strftime("%Y년 %m월 %d일")
    static_page("privacy", "개인정보처리방침", [
        f"{n}(이하 '사이트')은 이용자의 개인정보를 중요하게 생각하며, 「개인정보 보호법」 등 관련 법령을 지킵니다. 이 방침은 사이트가 어떤 정보를 어떻게 다루는지 안내합니다.",
        "## 1. 수집하는 정보",
        "사이트는 회원가입이나 댓글 기능이 없으며, 이용자가 직접 입력하는 개인정보를 수집하지 않습니다. 다만 이용자가 이메일로 문의하는 경우 답변을 위해 이메일 주소와 문의 내용을 받게 되며, 답변 완료 후 지체 없이 삭제합니다.",
        "## 2. 자동으로 수집되는 정보와 쿠키",
        "사이트 이용 과정에서 접속 기록, 브라우저 종류, 방문 페이지 같은 정보가 서버와 통계 도구에 의해 자동으로 기록될 수 있습니다. 이 정보는 개인을 식별하지 않는 형태로 사이트 개선과 방문 통계에만 사용합니다. 이용자는 브라우저 설정에서 쿠키 저장을 거부하거나 삭제할 수 있습니다.",
        "## 3. 광고(Google AdSense)",
        "사이트는 Google AdSense 광고를 게재할 수 있습니다. Google을 포함한 제3자 광고 업체는 쿠키를 사용해 이용자가 이 사이트나 다른 사이트를 방문한 기록을 바탕으로 광고를 보여 줄 수 있습니다. Google의 광고 쿠키 사용 방식은 "
        '<a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">Google 광고 정책</a>에서 확인할 수 있으며, '
        '<a href="https://adssettings.google.com" rel="noopener" target="_blank">Google 광고 설정</a>에서 맞춤 광고를 끌 수 있습니다.',
        "## 4. 제휴 링크",
        "일부 글에는 제휴 링크가 포함될 수 있습니다. 이용자가 링크를 통해 외부 사이트로 이동한 뒤 입력하는 정보는 해당 사이트의 개인정보처리방침에 따라 처리되며, 사이트는 그 정보를 받거나 보관하지 않습니다.",
        "## 5. 외부 링크",
        "사이트에 연결된 외부 사이트의 개인정보 처리에 대해서는 사이트가 책임지지 않으므로, 해당 사이트의 방침을 확인해 주세요.",
        "## 6. 문의",
        f'개인정보와 관련한 문의는 <a href="mailto:{mail}">{mail}</a>로 보내 주세요.',
        "## 7. 시행일",
        f"이 방침은 {today}부터 적용됩니다. 내용이 바뀌면 이 페이지에 알립니다.",
    ])
    write("404.html", head(f"페이지를 찾을 수 없습니다 | {NAME}", "요청한 페이지가 없습니다.", DOMAIN + "/404.html") +
          '<article class="post page"><h1>페이지를 찾을 수 없습니다</h1><p><a href="/">홈으로 돌아가기</a></p></article>' + foot())


def feeds(posts):
    now = datetime.now(KST).strftime("%Y-%m-%d")
    urls = [(f"{DOMAIN}/", now)] + [(f"{DOMAIN}/{s}/", now) for s in CATS] + \
           [(f"{DOMAIN}/{p['slug']}/", p.get("updated", p["date"])) for p in posts] + \
           [(f"{DOMAIN}/{s}/", now) for s in ("about", "contact", "privacy")]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
         "".join(f"<url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n"
    write("sitemap.xml", sm)

    def rfc822(d):
        return datetime.strptime(d, "%Y-%m-%d").replace(hour=9, tzinfo=KST).strftime("%a, %d %b %Y %H:%M:%S +0900")
    items = "".join(f"""<item><title>{esc(p['title'])}</title><link>{DOMAIN}/{p['slug']}/</link>
<guid>{DOMAIN}/{p['slug']}/</guid><pubDate>{rfc822(p['date'])}</pubDate><description>{esc(p['desc'])}</description></item>
""" for p in posts[:20])
    write("rss.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{esc(NAME)}</title><link>{DOMAIN}/</link>
<description>{esc(cfg['description'])}</description><language>ko</language>
{items}</channel></rss>
""")
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
    client = cfg.get("ADSENSE_CLIENT", "")
    ads_path = os.path.join(SITE, "ads.txt")
    if client:
        write("ads.txt", f"google.com, {client.replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n")
    elif os.path.exists(ads_path):
        os.remove(ads_path)


def clean_stale(posts):
    keep = RESERVED | set(CATS) | {p["slug"] for p in posts}
    for d in os.listdir(SITE):
        full = os.path.join(SITE, d)
        if os.path.isdir(full) and d not in keep and os.path.exists(os.path.join(full, "index.html")):
            shutil.rmtree(full)
            print(f"삭제: site/{d}/ (글 JSON 없음)")


def update_csv(posts):
    path = os.path.join(DATA, "posts.csv")
    header = ["날짜", "키워드", "제목", "slug", "카테고리", "URL", "월검색량", "경쟁", "비고"]
    rows = []
    if os.path.exists(path):
        rows = list(csv.reader(open(path, encoding="utf-8-sig")))[1:]
    have = {r[3] for r in rows if len(r) > 3}
    for p in sorted(posts, key=lambda p: (p["date"], p["slug"])):
        if p["slug"] not in have:
            rows.append([p["date"], p["kw"], p["title"], p["slug"], CATS[p["category"]],
                         f"{DOMAIN}/{p['slug']}/", p.get("volume", ""), p.get("competition", ""), p.get("note", "")])
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def main():
    os.makedirs(SITE, exist_ok=True)
    posts = load_posts()
    fails = 0
    for p in posts:
        s = post_page(p, posts)
        missing = [n for n in range(1, 17) if not os.path.exists(os.path.join(SITE, img_src(p, n).lstrip("/")))]
        ok = s["total"] >= MIN_TOTAL and s["intro"] >= MIN_INTRO and s["kw"] >= MIN_KW
        fails += (not ok)
        print(f"{p['slug']} total {s['total']} intro {s['intro']} kw_in_intro {s['kw']}"
              + ("" if ok else "  FAIL") + (f"  이미지 없음 {missing}" if missing else ""))
    list_page("", NAME, cfg["description"], posts[:20], NAME)
    for slug, name in CATS.items():
        list_page(f"{slug}/", f"{name} | {NAME}", f"{name} 관련 방법을 공식 안내와 실제 화면으로 정리한 글 모음입니다.",
                  [p for p in posts if p["category"] == slug], name)
    static_pages()
    feeds(posts)
    clean_stale(posts)
    update_csv(posts)
    print(f"완료: 글 {len(posts)}개, 기준 미달 {fails}개")


if __name__ == "__main__":
    main()
