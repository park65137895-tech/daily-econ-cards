#!/usr/bin/env python3
"""블로그 글 -> 인스타그램 카드뉴스(5장) 자동 변환 스크립트.

구성:
  1장  : 표지 (오늘의 경제이슈)
  2~4장: 핵심 포인트 1개씩
  5장  : CTA (마지막 카드)

사용법:
  python blog_to_carousel.py --title "제목" --body-file body.txt --out carousel
  type body.txt | python blog_to_carousel.py --title "제목"

옵션:
  --cta "문구1|문구2"   5장 CTA 문구 (줄바꿈은 | 로 구분)
  --hashtags "#태그1 #태그2"  caption.txt 에 붙일 해시태그
"""
import argparse
import collections
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG = (250, 247, 242)
FG = (34, 34, 34)
ACCENT = (232, 93, 60)
MUTED = (125, 125, 125)
MARGIN = 90
TEXT_W = W - MARGIN * 2

BOLD_FONTS = [
    r"C:\Windows\Fonts\malgunbd.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]
REGULAR_FONTS = [
    r"C:\Windows\Fonts\malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

STOPWORDS = set(
    "이 그 저 것 수 등 및 를 을 이 가 은 는 에 의 와 과 도 로 으로 에서 하는 있는 있다 "
    "하다 합니다 입니다 그리고 하지만 때문 대한 위해 통해 the and of to a is in for".split()
)


def load_font(size, bold=False):
    for path in (BOLD_FONTS if bold else REGULAR_FONTS) + (REGULAR_FONTS if bold else []):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    print("경고: 한글 폰트를 찾지 못해 기본 폰트를 사용합니다 (한글이 깨질 수 있음).", file=sys.stderr)
    return ImageFont.load_default()


def clean_line(line):
    """마크다운 기호 제거."""
    line = re.sub(r"^\s*(#+|[-*>+]+|\d+[.)])\s*", "", line)
    line = re.sub(r"[*_`]+", "", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)  # [텍스트](링크) -> 텍스트
    return line.strip()


def split_sentences(body):
    sentences = []
    for line in body.splitlines():
        line = clean_line(line)
        if not line:
            continue
        sentences.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip())
    return sentences


def tokens(text):
    return [t for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", text) if t.lower() not in STOPWORDS]


def pick_points(body, n=3):
    """문장별 핵심 키워드 빈도 점수로 상위 n개 문장을 고르고, 본문 순서대로 정렬."""
    sentences = [s for s in split_sentences(body) if 15 <= len(s) <= 160]
    if len(sentences) < n:
        raise ValueError(
            f"핵심 문장이 {len(sentences)}개뿐입니다. 카드 {n}장을 채우려면 본문이 더 필요합니다."
        )
    freq = collections.Counter(tokens(body))

    def score(sentence):
        toks = set(tokens(sentence))
        if not toks:
            return 0.0
        return sum(freq[t] for t in toks) / (len(toks) ** 0.5)

    ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)[:n]
    return [sentences[i] for i in sorted(ranked)]


def shorten(text, limit=110):
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:") + "…"


def wrap(draw, text, font, max_w):
    """어절 단위 줄바꿈. 한 어절이 한 줄을 넘으면 글자 단위로 쪼갠다."""
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if draw.textlength(cand, font=font) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        while draw.textlength(word, font=font) > max_w:
            k = len(word)
            while k > 1 and draw.textlength(word[:k], font=font) > max_w:
                k -= 1
            lines.append(word[:k])
            word = word[k:]
        cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_lines(draw, lines, font, x, y, gap, fill=FG, align="left", max_w=TEXT_W):
    for line in lines:
        if align == "center":
            tw = draw.textlength(line, font=font)
            draw.text((x + (max_w - tw) / 2, y), line, font=font, fill=fill)
        else:
            draw.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def new_card(index, total):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 16], fill=ACCENT)
    small = load_font(34)
    draw.text((MARGIN, 80), f"{index:02d} / {total:02d}", font=small, fill=MUTED)
    return img, draw


def cover_card(title):
    img, draw = new_card(1, 5)
    font = load_font(104, bold=True)
    lines = wrap(draw, title, font, TEXT_W)
    block_h = len(lines) * (font.size + 20)
    y = max(260, (H - block_h) // 2 - 60)
    draw.rectangle([MARGIN, y - 60, MARGIN + 120, y - 48], fill=ACCENT)
    draw_lines(draw, lines, font, MARGIN, y, 20)
    return img


def point_card(index, point):
    img, draw = new_card(index, 5)
    label_font = load_font(44, bold=True)
    body_font = load_font(66)
    draw.text((MARGIN, 300), f"POINT {index - 1}", font=label_font, fill=ACCENT)
    lines = wrap(draw, shorten(point), body_font, TEXT_W)
    draw_lines(draw, lines, body_font, MARGIN, 400, 26)
    return img


def cta_card(cta_lines):
    img, draw = new_card(5, 5)
    head_font = load_font(84, bold=True)
    body_font = load_font(50)
    draw.text((MARGIN, 330), "이 글이 도움이 되셨다면", font=load_font(48), fill=MUTED)
    y = draw_lines(draw, wrap(draw, "다음 글도 함께 보세요", head_font, TEXT_W), head_font, MARGIN, 400, 20)
    y += 80
    for text in cta_lines:
        y = draw_lines(draw, wrap(draw, text, body_font, TEXT_W), body_font, MARGIN, y, 16, fill=ACCENT)
        y += 30
    return img


def main():
    ap = argparse.ArgumentParser(description="블로그 글 -> 인스타그램 카드뉴스(5장)")
    ap.add_argument("--title", required=True, help="블로그 글 제목")
    ap.add_argument("--body-file", help="본문 텍스트/마크다운 파일 (생략 시 표준입력)")
    ap.add_argument("--out", default="carousel", help="출력 폴더")
    ap.add_argument("--cta", default="저장해두고 다시 보세요|팔로우하고 다음 글도 받아보세요",
                    help="CTA 문구, 줄바꿈은 | 로 구분")
    ap.add_argument("--hashtags", default="", help="caption.txt 에 붙일 해시태그")
    args = ap.parse_args()

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    else:
        body = sys.stdin.read()
    if not body.strip():
        ap.error("본문이 비어 있습니다.")

    points = pick_points(body, n=3)
    cta_lines = [s.strip() for s in args.cta.split("|") if s.strip()]

    os.makedirs(args.out, exist_ok=True)
    cards = [cover_card(args.title)]
    cards += [point_card(i + 2, p) for i, p in enumerate(points)]
    cards.append(cta_card(cta_lines))

    for i, card in enumerate(cards, 1):
        path = os.path.join(args.out, f"card_{i}.png")
        card.save(path, "PNG")
        print(f"저장: {path}")

    caption = [args.title, ""] + [f"- {p}" for p in points] + ["", args.hashtags]
    with open(os.path.join(args.out, "caption.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(caption).strip() + "\n")
    print(f"저장: {os.path.join(args.out, 'caption.txt')}")


if __name__ == "__main__":
    main()
