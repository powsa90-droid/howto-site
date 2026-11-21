#!/usr/bin/env python3
"""하우투 정보 사이트 빌드 스크립트 (블로그형 레이아웃).

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
    "H2",                   # 제목과 같은 그라데이션 h2 (H2:문구 로 다른 문구 가능)
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
RESERVED = {"images", "about", "contact", "privacy", "assets", "search"}

cfg = json.load(open(os.path.join(DATA, "config.json"), encoding="utf-8"))
DOMAIN = cfg["domain"].rstrip("/")
NAME = cfg["site_name"]
CATS = {c["slug"]: c["name"] for c in cfg["categories"]}
ICONS = {"moving": "📦", "cleaning": "🧽", "car": "🚗", "phone-it": "📱", "life-admin": "🏛️"}
esc = lambda s: html.escape(str(s or ""), quote=True)
POSTS = []          # load_posts() 후 채움 (사이드바·티커에서 사용)
BUILD_V = datetime.now(KST).strftime("%Y%m%d%H%M")


def inline(s):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(s))


def nospace_len(s):
    return len(re.sub(r"\s", "", s))


def write(path, text):
    full = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def img_src(p, n):
    return f"/images/{p['slug']}/{n:02d}.jpg"


def read_min(p):
    txt = " ".join(x.split(":", 1)[1] for x in p["body"] if x.startswith(("P:", "EM:")))
    return max(1, round(nospace_len(txt) / 500))


def kdate(d):
    y, m, dd = d.split("-")
    return f"{y}. {int(m)}. {int(dd)}."


# ---------------------------------------------------------------- 공통 틀
ICON_SEARCH = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'
ICON_MOON = '<svg class="i-moon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
ICON_SUN = '<svg class="i-sun" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
ICON_MENU = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'
SPARK = '<svg class="spark" viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M12 2c.6 4.6 3.4 7.4 8 8-4.6.6-7.4 3.4-8 8-.6-4.6-3.4-7.4-8-8 4.6-.6 7.4-3.4 8-8z"/></svg>'


def head(title, desc, canonical, og_image=None, og_type="website", jsonld=None, active=""):
    img = og_image or f"{DOMAIN}/assets/og-default.png"
    ads = ""
    if cfg.get("ADSENSE_CLIENT"):
        ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={esc(cfg["ADSENSE_CLIENT"])}" '
               'crossorigin="anonymous"></script>')
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    nav = "".join(f'<a href="/{s}/"{" class=on" if s == active else ""}>{esc(n)}</a>' for s, n in CATS.items())
    ticker = "".join(f'<a href="/{p["slug"]}/"><b>{kdate(p["date"])}</b> {esc(p["title"])}</a>' for p in POSTS[:8])
    ticker_html = (f'<div class="ticker"><div class="wrap ticker-in"><span class="ticker-tag"><i></i>최신 글</span>'
                   f'<div class="ticker-track"><div class="ticker-move">{ticker}{ticker}</div></div></div></div>') if POSTS else ""
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
<meta name="theme-color" content="#6d4bea">
<link rel="alternate" type="application/rss+xml" title="{esc(NAME)}" href="{DOMAIN}/rss.xml">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="/style.css?v={BUILD_V}">
<link rel="icon" href="/assets/favicon.png">
<script>try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}</script>
{ld}
{ads}
{cfg.get('HEAD_EXTRA','')}
</head>
<body>
<div class="topbar"><div class="wrap topbar-in">
<span class="today" id="today"></span>
<span class="topmsg">✨ 생활 속 방법을 실제 화면과 함께 쉽게 정리합니다</span>
</div></div>
<header class="header"><div class="wrap header-in">
<a class="logo" href="/"><span class="logo-mark">생</span>{esc(NAME)}</a>
<nav class="nav" id="nav">{nav}</nav>
<div class="tools">
<a class="icon-btn" href="/search/" aria-label="검색">{ICON_SEARCH}</a>
<button class="theme-btn" id="themeBtn" type="button" aria-label="다크 모드 전환">{ICON_SUN}{ICON_MOON}<span class="knob"></span></button>
<button class="icon-btn menu-btn" id="menuBtn" type="button" aria-label="메뉴">{ICON_MENU}</button>
</div>
</div></header>
{ticker_html}
<main class="wrap main">
"""


def foot():
    year = datetime.now(KST).year
    cats = "".join(f'<li><a href="/{s}/">{ICONS.get(s,"")} {esc(n)}</a></li>' for s, n in CATS.items())
    return f"""</main>
<footer class="footer"><div class="wrap footer-grid">
<div><a class="logo" href="/"><span class="logo-mark">생</span>{esc(NAME)}</a>
<p>{esc(cfg['description'])}</p></div>
<div><h4>카테고리</h4><ul>{cats}</ul></div>
<div><h4>사이트 안내</h4><ul><li><a href="/about/">소개</a></li><li><a href="/contact/">문의</a></li><li><a href="/privacy/">개인정보처리방침</a></li><li><a href="/rss.xml">RSS</a></li></ul></div>
</div>
<div class="wrap copy">© {year} {esc(NAME)}. 글의 내용은 공식 안내를 바탕으로 작성되며, 실제 내용은 각 기관·업체 사정에 따라 바뀔 수 있습니다.</div>
</footer>
<script>
(function(){{
var d=new Date(),w='일월화수목금토'[d.getDay()];
var el=document.getElementById('today');if(el)el.textContent=d.getFullYear()+'년 '+(d.getMonth()+1)+'월 '+d.getDate()+'일 ('+w+')';
var b=document.getElementById('themeBtn');if(b)b.onclick=function(){{var r=document.documentElement,n=r.dataset.theme==='dark'?'light':'dark';r.dataset.theme=n;try{{localStorage.setItem('theme',n)}}catch(e){{}}}};
var m=document.getElementById('menuBtn');if(m)m.onclick=function(){{document.getElementById('nav').classList.toggle('open')}};
}})();
</script>
</body></html>
"""


def ad_slot(extra=""):
    return f'<div class="ad-slot{extra}">{cfg.get("AD","")}</div>'


# ---------------------------------------------------------------- 사이드바
def sidebar():
    counts = {s: sum(1 for p in POSTS if p["category"] == s) for s in CATS}
    recent = "".join(
        f'<li><a href="/{p["slug"]}/"><img src="{img_src(p,1)}" alt="{esc(p["kw"])}" loading="lazy">'
        f'<span><strong>{esc(p["title"])}</strong><small>{kdate(p["date"])}</small></span></a></li>' for p in POSTS[:5])
    cats = "".join(f'<li><a href="/{s}/"><span>{ICONS.get(s,"")} {esc(n)}</span><em>{counts[s]}</em></a></li>' for s, n in CATS.items())
    return f"""<aside class="sidebar">
<section class="widget author">
<div class="author-top"><span class="avatar">생</span><div><strong>{esc(NAME)}</strong><small>생활 정보 정리 노트</small></div></div>
<p>안녕하세요, {esc(NAME)}입니다. 이사·청소·자동차·스마트폰·생활 행정까지 막상 하려면 헷갈리는 일들을 공식 안내와 실제 화면으로 차근차근 정리합니다.</p>
<ul class="promise"><li><span>✔</span>공식 사이트에서 직접 확인한 내용</li><li><span>✔</span>단계별 실제 화면 캡처</li><li><span>✔</span>바뀐 정보는 빠르게 수정</li></ul>
<a class="btn" href="/contact/">문의하기</a>
</section>
<section class="widget"><h3>{SPARK}검색</h3>
<form class="side-search" action="/search/" method="get"><input name="q" type="search" placeholder="찾는 방법을 입력하세요" aria-label="검색어"><button type="submit" aria-label="검색">{ICON_SEARCH}</button></form>
</section>
{f'<section class="widget"><h3>{SPARK}최근 글</h3><ul class="recent">{recent}</ul></section>' if recent else ''}
<section class="widget"><h3>{SPARK}카테고리</h3><ul class="cat-list">{cats}</ul></section>
{ad_slot(" side-ad")}
</aside>"""


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
<span class="lc-host">🔗 {esc(p.get('og_host',''))}</span>
<strong class="lc-title">{esc(p.get('og_title') or p['url'])}</strong>
<span class="lc-desc">{esc(p.get('og_desc',''))}</span>
<span class="lc-go">바로가기 →</span></a>"""


def render_body(p):
    out, intro_text, all_text, seen_h2 = [], [], [], False
    for item in p["body"]:
        if item == "IMG1":
            out.append(figure(p, 1, "hero-img"))
        elif item.startswith("P:") or item.startswith("EM:"):
            em = item.startswith("EM:")
            t = item.split(":", 1)[1].strip()
            out.append(f'<p class="em">{inline(t)}</p>' if em else f"<p>{inline(t)}</p>")
            all_text.append(t)
            if not seen_h2:
                intro_text.append(t)
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


# ---------------------------------------------------------------- 카드
def meta_line(p):
    return f'<span class="m-date">{kdate(p["date"])}</span><span class="m-dot"></span><span>{read_min(p)}분 읽기</span>'


def badge(p, cls="badge"):
    return f'<a class="{cls}" href="/{p["category"]}/">{ICONS.get(p["category"],"")} {esc(CATS[p["category"]])}</a>'


def card(p):
    return f"""<article class="card">
<a class="card-img" href="/{p['slug']}/"><img src="{img_src(p, 1)}" alt="{esc(p['kw'])}" loading="lazy"></a>
<div class="card-body">{badge(p)}
<h3><a href="/{p['slug']}/">{esc(p['title'])}</a></h3>
<p>{esc(p['desc'])}</p>
<div class="meta">{meta_line(p)}</div></div>
</article>"""


def hero(posts):
    if not posts:
        return f"""<section class="hero hero-empty"><div>
<span class="badge light">{esc(NAME)}</span>
<h1>생활 속 방법,<br>화면 보면서 쉽게 따라 하세요</h1>
<p>{esc(cfg['description'])}</p></div></section>"""
    main, side = posts[0], posts[1:4]
    sides = "".join(f"""<a class="hero-side" href="/{p['slug']}/"><img src="{img_src(p,1)}" alt="{esc(p['kw'])}">
<span><small>{esc(CATS[p['category']])}</small><strong>{esc(p['title'])}</strong></span></a>""" for p in side)
    return f"""<section class="hero{' hero-solo' if not side else ''}">
<a class="hero-main" href="/{main['slug']}/">
<img src="{img_src(main,1)}" alt="{esc(main['kw'])}">
<div class="hero-over"><span class="badge light">{ICONS.get(main['category'],'')} {esc(CATS[main['category']])}</span>
<h2>{esc(main['title'])}</h2><p>{esc(main['desc'])}</p><div class="meta light">{meta_line(main)}</div></div></a>
{f'<div class="hero-list">{sides}</div>' if side else ''}
</section>"""


def cat_chips(active=""):
    chips = f'<a href="/"{" class=on" if not active else ""}>전체</a>' + "".join(
        f'<a href="/{s}/"{" class=on" if s == active else ""}>{ICONS.get(s,"")} {esc(n)}</a>' for s, n in CATS.items())
    return f'<div class="chips">{chips}</div>'


# ---------------------------------------------------------------- 페이지
def post_page(p, posts):
    body, stats = render_body(p)
    url = f"{DOMAIN}/{p['slug']}/"
    related = [q for q in posts if q["category"] == p["category"] and q["slug"] != p["slug"]][:3]
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": p["title"],
          "description": p["desc"], "datePublished": p["date"], "dateModified": p.get("updated", p["date"]),
          "image": [DOMAIN + img_src(p, 1)], "mainEntityOfPage": url,
          "author": {"@type": "Organization", "name": NAME}, "publisher": {"@type": "Organization", "name": NAME}}
    crumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "홈", "item": DOMAIN + "/"},
        {"@type": "ListItem", "position": 2, "name": CATS[p["category"]], "item": f"{DOMAIN}/{p['category']}/"},
        {"@type": "ListItem", "position": 3, "name": p["title"], "item": url}]}
    notice = f'<p class="aff-notice">ⓘ {esc(cfg["affiliate_notice"])}</p>' if p.get("aff") else ""
    rel_html = ""
    if related:
        rel_html = '<section class="related"><h3>' + SPARK + '함께 보면 좋은 글</h3><div class="rel-grid">' + "".join(
            f'<a href="/{q["slug"]}/"><img src="{img_src(q,1)}" alt="{esc(q["kw"])}" loading="lazy"><strong>{esc(q["title"])}</strong></a>'
            for q in related) + "</div></section>"
    html_ = head(p["title"], p["desc"], url, DOMAIN + img_src(p, 1), "article", [ld, crumb], p["category"]) + f"""
<div class="layout">
<div class="content">
<article class="post box">
<nav class="crumb"><a href="/">홈</a><span>›</span><a href="/{p['category']}/">{esc(CATS[p['category']])}</a></nav>
{badge(p)}
<h1>{esc(p['title'])}</h1>
<div class="meta post-meta"><span class="by"><span class="avatar sm">생</span>{esc(NAME)}</span><span class="m-dot"></span>{meta_line(p)}</div>
{notice}
<div class="post-body">
{body}
</div>
</article>
{rel_html}
</div>
{sidebar()}
</div>
""" + foot()
    write(f"{p['slug']}/index.html", html_)
    return stats


def home_page(posts):
    latest = posts[:20]
    cards = "".join(card(p) for p in latest) or '<p class="empty box">곧 첫 글이 올라옵니다. 조금만 기다려 주세요!</p>'
    write("index.html", head(NAME, cfg["description"], f"{DOMAIN}/") + f"""
{hero(posts)}
<div class="layout">
<div class="content">
<div class="sec-head"><h2>{SPARK}최신 글</h2>{cat_chips()}</div>
<div class="cards">{cards}</div>
</div>
{sidebar()}
</div>
""" + foot())


def cat_page(slug, name, items):
    url = f"{DOMAIN}/{slug}/"
    desc = f"{name} 관련 방법을 공식 안내와 실제 화면으로 정리한 글 모음입니다."
    cards = "".join(card(p) for p in items) or '<p class="empty box">이 카테고리의 첫 글을 준비하고 있습니다.</p>'
    write(f"{slug}/index.html", head(f"{name} | {NAME}", desc, url, active=slug) + f"""
<section class="cat-hero box"><span class="cat-icon">{ICONS.get(slug,'')}</span><div><h1>{esc(name)}</h1><p>{esc(desc)} 지금까지 {len(items)}개의 글이 있습니다.</p></div></section>
<div class="layout">
<div class="content">
<div class="sec-head">{cat_chips(slug)}</div>
<div class="cards">{cards}</div>
</div>
{sidebar()}
</div>
""" + foot())


def static_page(slug, title, paragraphs):
    url = f"{DOMAIN}/{slug}/"
    body = "".join(f"<h2>{esc(x[3:])}</h2>" if x.startswith("## ") else f"<p>{x}</p>" for x in paragraphs)
    write(f"{slug}/index.html", head(f"{title} | {NAME}", f"{NAME} {title}", url) +
          f'<div class="layout"><div class="content"><article class="post box page"><h1>{esc(title)}</h1><div class="post-body">{body}</div></article></div>{sidebar()}</div>' + foot())


def search_page():
    write("search/index.html", head(f"검색 | {NAME}", f"{NAME} 글 검색", f"{DOMAIN}/search/") + f"""
<div class="layout"><div class="content">
<section class="box search-box"><h1>{SPARK}글 검색</h1>
<form class="side-search big" action="/search/" method="get"><input id="q" name="q" type="search" placeholder="예: 이사 견적, 전입신고, 중고폰" aria-label="검색어" autofocus><button type="submit" aria-label="검색">{ICON_SEARCH}</button></form>
<p class="search-info" id="info"></p></section>
<div class="cards" id="results"></div>
</div>{sidebar()}</div>
<script>
(async function(){{
var q=new URLSearchParams(location.search).get('q')||'';document.getElementById('q').value=q;
var info=document.getElementById('info'),box=document.getElementById('results');
if(!q.trim()){{info.textContent='찾고 싶은 방법을 입력해 보세요.';return;}}
var list=[];try{{list=await fetch('/search.json').then(function(r){{return r.json()}})}}catch(e){{}}
var words=q.toLowerCase().split(/\\s+/).filter(Boolean);
var hit=list.filter(function(p){{var t=(p.t+' '+p.k+' '+p.d+' '+p.c).toLowerCase();return words.every(function(w){{return t.indexOf(w)>-1}})}});
info.textContent='"'+q+'" 검색 결과 '+hit.length+'개';
box.innerHTML=hit.map(function(p){{var e=function(s){{var d=document.createElement('div');d.textContent=s;return d.innerHTML}};
return '<article class="card"><a class="card-img" href="'+p.u+'"><img src="'+p.i+'" alt="'+e(p.k)+'" loading="lazy"></a><div class="card-body"><span class="badge">'+e(p.c)+'</span><h3><a href="'+p.u+'">'+e(p.t)+'</a></h3><p>'+e(p.d)+'</p><div class="meta"><span>'+e(p.dt)+'</span></div></div></article>'}}).join('');
}})();
</script>
""" + foot())
    idx = [{"t": p["title"], "k": p["kw"], "d": p["desc"], "c": CATS[p["category"]], "u": f"/{p['slug']}/",
            "i": img_src(p, 1), "dt": kdate(p["date"])} for p in POSTS]
    write("search.json", json.dumps(idx, ensure_ascii=False))


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
    today = cfg.get("privacy_date") or datetime.now(KST).strftime("%Y년 %m월 %d일")
    static_page("privacy", "개인정보처리방침", [
        f"{n}(이하 '사이트')은 이용자의 개인정보를 중요하게 생각하며, 「개인정보 보호법」 등 관련 법령을 지킵니다. 이 방침은 사이트가 어떤 정보를 어떻게 다루는지 안내합니다.",
        "## 1. 수집하는 정보",
        "사이트는 회원가입이나 댓글 기능이 없으며, 이용자가 직접 입력하는 개인정보를 수집하지 않습니다. 다만 이용자가 이메일로 문의하는 경우 답변을 위해 이메일 주소와 문의 내용을 받게 되며, 답변 완료 후 지체 없이 삭제합니다.",
        "## 2. 자동으로 수집되는 정보와 쿠키",
        "사이트 이용 과정에서 접속 기록, 브라우저 종류, 방문 페이지 같은 정보가 서버와 통계 도구에 의해 자동으로 기록될 수 있습니다. 이 정보는 개인을 식별하지 않는 형태로 사이트 개선과 방문 통계에만 사용합니다. 화면 밝기(다크 모드) 설정은 이용자의 브라우저에만 저장됩니다. 이용자는 브라우저 설정에서 쿠키 저장을 거부하거나 삭제할 수 있습니다.",
        "## 3. 광고(Google AdSense)",
        "사이트는 Google AdSense 광고를 게재할 수 있습니다. Google을 포함한 제3자 광고 업체는 쿠키를 사용해 이용자가 이 사이트나 다른 사이트를 방문한 기록을 바탕으로 광고를 보여 줄 수 있습니다. Google의 광고 쿠키 사용 방식은 "
        '<a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">Google 광고 정책</a>에서 확인할 수 있으며, '
        '<a href="https://adssettings.google.com" rel="noopener" target="_blank">Google 광고 설정</a>에서 맞춤 광고를 끌 수 있습니다.',
        "## 4. 제휴 링크",
        "일부 글에는 제휴 링크가 포함될 수 있습니다. 이용자가 링크를 통해 외부 사이트로 이동한 뒤 입력하는 정보는 해당 사이트의 개인정보처리방침에 따라 처리되며, 사이트는 그 정보를 받거나 보관하지 않습니다.",
        "## 5. 외부 링크와 글꼴",
        "사이트에 연결된 외부 사이트의 개인정보 처리에 대해서는 사이트가 책임지지 않으므로, 해당 사이트의 방침을 확인해 주세요. 사이트는 화면 표시를 위해 외부 글꼴 서비스(jsDelivr)를 사용하며, 이 과정에서 접속 정보가 해당 서비스에 전달될 수 있습니다.",
        "## 6. 문의",
        f'개인정보와 관련한 문의는 <a href="mailto:{mail}">{mail}</a>로 보내 주세요.',
        "## 7. 시행일",
        f"이 방침은 {today}부터 적용됩니다. 내용이 바뀌면 이 페이지에 알립니다.",
    ])
    write("404.html", head(f"페이지를 찾을 수 없습니다 | {NAME}", "요청한 페이지가 없습니다.", DOMAIN + "/404.html") +
          '<section class="box notfound"><h1>404</h1><p>요청하신 페이지를 찾을 수 없습니다.</p><a class="btn" href="/">홈으로 돌아가기</a></section>' + foot())


def feeds(posts):
    now = datetime.now(KST).strftime("%Y-%m-%d")
    last = posts[0]["date"] if posts else now
    urls = [(f"{DOMAIN}/", last)] + [(f"{DOMAIN}/{s}/", last) for s in CATS] + \
           [(f"{DOMAIN}/{p['slug']}/", p.get("updated", p["date"])) for p in posts] + \
           [(f"{DOMAIN}/{s}/", cfg.get("static_date", now)) for s in ("about", "contact", "privacy")]
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
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /search/\n\nSitemap: {DOMAIN}/sitemap.xml\n")
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
    global POSTS
    os.makedirs(SITE, exist_ok=True)
    posts = POSTS = load_posts()
    fails = 0
    for p in posts:
        s = post_page(p, posts)
        missing = [n for n in range(1, 17) if not os.path.exists(os.path.join(SITE, img_src(p, n).lstrip("/")))]
        ok = s["total"] >= MIN_TOTAL and s["intro"] >= MIN_INTRO and s["kw"] >= MIN_KW
        fails += (not ok)
        print(f"{p['slug']} total {s['total']} intro {s['intro']} kw_in_intro {s['kw']}"
              + ("" if ok else "  FAIL") + (f"  이미지 없음 {missing}" if missing else ""))
    home_page(posts)
    for slug, name in CATS.items():
        cat_page(slug, name, [p for p in posts if p["category"] == slug])
    static_pages()
    search_page()
    feeds(posts)
    clean_stale(posts)
    update_csv(posts)
    print(f"완료: 글 {len(posts)}개, 기준 미달 {fails}개")


if __name__ == "__main__":
    main()
