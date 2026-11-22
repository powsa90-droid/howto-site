#!/usr/bin/env python3
"""생활노트 대표 이미지(썸네일) 만들기 — 마스킹테이프 메모카드 스타일.

사용법:
  python3 thumb.py OUT.jpg --tag "정부24로 5분" --main "전입신고" --sub "온라인 신청법" \
      --desc "세대주 확인부터 처리 결과 확인까지"
  --tag  : 맨 위 작은 문구(선택)
  --main : 큰 글씨 1줄, 보라색 (핵심 키워드)
  --sub  : 큰 글씨 2줄째, 검정
  --desc : 아래 작은 설명(선택, 길면 자동 줄바꿈, 최대 2줄)
"""
import argparse, glob
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--tag", default="")
ap.add_argument("--main", required=True)
ap.add_argument("--sub", default="")
ap.add_argument("--desc", default="")
a = ap.parse_args()

K = 2                      # 2배로 그린 뒤 줄여서 부드럽게
S = 800 * K
BG = (240, 235, 255)       # 연보라 배경
DOT = (221, 212, 250)
CARD = (255, 255, 255)
INK = (29, 27, 46)
PURPLE = (109, 75, 234)
SHADOW = (45, 31, 143)
GRAY = (110, 106, 128)

def font(weight, size):
    fp = glob.glob(f"/usr/share/fonts/**/NotoSansCJK-{weight}.ttc", recursive=True)[0]
    return ImageFont.truetype(fp, size, index=1)   # index 1 = 한국어

im = Image.new("RGB", (S, S), BG)
d = ImageDraw.Draw(im)

# 배경 점무늬
for y in range(30 * K, S, 40 * K):
    for x in range(30 * K, S, 40 * K):
        r = 3 * K
        d.ellipse([x - r, y - r, x + r, y + r], fill=DOT)

# 카드 + 각진 그림자
L, T, R, B = 92 * K, 118 * K, 708 * K, 700 * K
d.rounded_rectangle([L + 14 * K, T + 16 * K, R + 14 * K, B + 16 * K], radius=34 * K, fill=SHADOW)
d.rounded_rectangle([L, T, R, B], radius=34 * K, fill=CARD, outline=INK, width=5 * K)

# 마스킹테이프(살짝 기울어진 반투명 띠)
tape = Image.new("RGBA", (230 * K, 60 * K), (224, 71, 158, 120))
td = ImageDraw.Draw(tape)
for x in range(0, tape.width, 18 * K):     # 테이프 결
    td.line([(x, 0), (x + 30 * K, tape.height)], fill=(255, 255, 255, 22), width=5 * K)
tape = tape.rotate(-6, expand=True, resample=Image.BICUBIC)
im.paste(tape, (S // 2 - tape.width // 2, T - 38 * K), tape)
d = ImageDraw.Draw(im)

cx = S // 2
inner = (R - L) - 110 * K      # 글자가 들어갈 최대 폭

def fit(text, weight, start, minimum):
    s = start
    while s > minimum and d.textlength(text, font=font(weight, s)) > inner:
        s -= 4 * K
    return font(weight, s), s

# --- 블록 크기를 먼저 재고, 카드 안(배지 자리 제외)에 세로 가운데 정렬 ---
blocks = []   # (높이, 그리는 함수)
if a.tag:
    ft = font("Bold", 32 * K)
    def draw_tag(y, f=ft):
        w = d.textlength(a.tag, font=f); pad = 22 * K
        d.rounded_rectangle([cx - w / 2 - pad, y, cx + w / 2 + pad, y + 56 * K], radius=28 * K, fill=(239, 234, 255))
        d.text((cx, y + 28 * K), a.tag, font=f, fill=PURPLE, anchor="mm")
    blocks.append((56 * K, draw_tag)); blocks.append((26 * K, None))
f1, s1 = fit(a.main, "Black", 118 * K, 64 * K)
blocks.append((int(s1 * 1.16), lambda y, f=f1, s=s1: d.text((cx, y + s * 0.58), a.main, font=f, fill=PURPLE, anchor="mm")))
if a.sub:
    f2, s2 = fit(a.sub, "Black", 96 * K, 56 * K)
    blocks.append((int(s2 * 1.18), lambda y, f=f2, s=s2: d.text((cx, y + s * 0.59), a.sub, font=f, fill=INK, anchor="mm")))
def draw_div(y):
    yy = y + 14 * K
    for x in range(L + 80 * K, R - 80 * K, 22 * K):
        d.line([(x, yy), (x + 10 * K, yy)], fill=(200, 196, 214), width=3 * K)
    dm = 9 * K
    d.polygon([(cx, yy - dm), (cx + dm, yy), (cx, yy + dm), (cx - dm, yy)], fill=PURPLE)
blocks.append((18 * K, None)); blocks.append((28 * K, draw_div))
if a.desc:
    f3 = font("Medium", 29 * K)
    lines, cur = [], ""
    for wd in a.desc.split():
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=f3) <= inner - 30 * K: cur = t
        else: lines.append(cur); cur = wd
    lines.append(cur); lines = lines[:2]
    def draw_desc(y, f=f3, ls=lines):
        for i, ln in enumerate(ls):
            d.text((cx, y + 21 * K + i * 42 * K), ln, font=f, fill=GRAY, anchor="mm")
    blocks.append((18 * K, None)); blocks.append((42 * K * len(lines), draw_desc))

top_, bot_ = T + 44 * K, B - 92 * K
total = sum(h for h, _ in blocks)
y = top_ + max(0, (bot_ - top_ - total) // 2)
for h, fn in blocks:
    if fn: fn(y)
    y += h

# 오른쪽 아래 사이트 표시
fm = font("Black", 22 * K)
bx, by = R - 46 * K, B - 40 * K
label = "생활노트"
lw = d.textlength(label, font=fm)
d.rounded_rectangle([bx - lw - 50 * K, by - 18 * K, bx, by + 18 * K], radius=18 * K, fill=INK)
d.rounded_rectangle([bx - lw - 44 * K, by - 12 * K, bx - lw - 20 * K, by + 12 * K], radius=6 * K, fill=PURPLE)
d.text((bx - 14 * K, by), label, font=fm, fill=(255, 255, 255), anchor="rm")

im = im.resize((800, 800), Image.LANCZOS)
im.save(a.out, quality=92)
