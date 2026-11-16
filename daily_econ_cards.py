#!/usr/bin/env python3
"""매일의 경제 이슈 -> 인스타그램 카드뉴스 생성 스크립트.

입력: 하루치 이슈를 담은 JSON 파일 (형식은 issues_2026-11-16.json 참고)
출력: card_1.png ~ card_N.png, caption.txt

두 가지 모드:
  기본 (5장): 표지 / 이슈 3개 / 정리
  확장 (10장): JSON에 "ripples"(파급 효과 3개)와 "strategy"(대응 전략),
               "checklist"(다음에 볼 것)가 있으면 자동으로 10장 구성

  1장   : 표지 (날짜 + 이슈 3개 미리보기)
  2~4장 : 이슈 1개씩 (분류 태그, 제목, 핵심 수치, 요약, 출처)
  5~7장 : 이슈별 파급 효과 + 지켜볼 지표
  8장   : 대응 전략 (참여자 유형별 점검 포인트)
  9장   : 다음에 확인할 것 (체크리스트)
  10장  : 오늘 정리 + CTA

사용법:
  python daily_econ_cards.py --issues issues_2026-11-16.json --out out_econ_2026-11-16
"""
import argparse
import json
import os
import sys

from blog_to_carousel import (
    ACCENT, H, MARGIN, MUTED, TEXT_W,
    draw_lines, load_font, new_card, shorten, wrap,
)

ISSUE_COUNT = 3
DISCLAIMER = "정보 제공 목적의 요약이며, 특정 종목·자산의 매매를 권하지 않습니다."


def total_cards(data):
    return 10 if "ripples" in data else 5


def validate(data):
    issues = data.get("issues", [])
    if len(issues) != ISSUE_COUNT:
        raise ValueError(f"이슈는 정확히 {ISSUE_COUNT}개여야 합니다 (현재 {len(issues)}개).")
    for key in ("category", "headline", "summary", "key_number", "key_label"):
        for i, issue in enumerate(issues, 1):
            if not str(issue.get(key, "")).strip():
                raise ValueError(f"이슈 {i}의 '{key}' 값이 비어 있습니다.")
    if not data.get("date"):
        raise ValueError("'date' 값이 필요합니다 (예: 2026-11-16).")
    if "ripples" in data:
        if len(data["ripples"]) != ISSUE_COUNT:
            raise ValueError(f"'ripples'는 이슈와 같은 {ISSUE_COUNT}개여야 합니다.")
        for i, r in enumerate(data["ripples"], 1):
            if not r.get("effects") or not r.get("watch"):
                raise ValueError(f"파급 효과 {i}에 'effects'와 'watch'가 필요합니다.")
        if not data.get("strategy", {}).get("groups"):
            raise ValueError("'strategy.groups'가 필요합니다.")


def tag(draw, text):
    font = load_font(40, bold=True)
    label = f" {text} "
    tw = draw.textlength(label, font=font)
    draw.rectangle([MARGIN, 230, MARGIN + tw + 20, 294], fill=ACCENT)
    draw.text((MARGIN + 10, 238), label, font=font, fill=(255, 255, 255))


def cover_card(data, total):
    img, draw = new_card(1, total)
    title_font = load_font(104, bold=True)
    draw.text((MARGIN, 300), data["date"], font=load_font(48), fill=MUTED)
    y = draw_lines(draw, wrap(draw, "오늘의 경제 이슈", title_font, TEXT_W), title_font, MARGIN, 380, 20)
    y += 60
    list_font = load_font(46)
    for i, issue in enumerate(data["issues"], 1):
        draw.text((MARGIN, y), f"{i:02d}", font=load_font(46, bold=True), fill=ACCENT)
        lines = wrap(draw, shorten(issue["headline"], 60), list_font, TEXT_W - 110)
        y = draw_lines(draw, lines, list_font, MARGIN + 110, y, 12)
        y += 40
    return img


def issue_card(index, total, issue):
    img, draw = new_card(index, total)
    tag(draw, issue["category"])

    head_font = load_font(64, bold=True)
    y = draw_lines(draw, wrap(draw, shorten(issue["headline"], 90), head_font, TEXT_W), head_font, MARGIN, 340, 18)

    num_font = load_font(120, bold=True)
    draw.text((MARGIN, max(y + 60, 640)), issue["key_number"], font=num_font, fill=ACCENT)
    y = max(y + 60, 640) + 150
    draw.text((MARGIN, y), issue["key_label"], font=load_font(42), fill=MUTED)

    body_font = load_font(40)
    lines = wrap(draw, shorten(issue["summary"], 140), body_font, TEXT_W)[:4]
    draw_lines(draw, lines, body_font, MARGIN, y + 120, 16)

    source = issue.get("source", "")
    if source:
        draw.text((MARGIN, H - 150), f"출처: {source}", font=load_font(30), fill=MUTED)
    return img


def ripple_card(index, total, ripple):
    img, draw = new_card(index, total)
    tag(draw, "파급 효과")
    head_font = load_font(60, bold=True)
    y = draw_lines(draw, wrap(draw, shorten(ripple["title"], 60), head_font, TEXT_W), head_font, MARGIN, 340, 16)
    y += 60
    body = load_font(40)
    for eff in ripple["effects"]:
        y = draw_lines(draw, wrap(draw, f"• {eff}", body, TEXT_W), body, MARGIN, y, 14)
        y += 26
    watch_y = H - 330
    label_font = load_font(36, bold=True)
    draw.text((MARGIN, watch_y), "지켜볼 지표", font=label_font, fill=ACCENT)
    watch_font = load_font(38)
    draw_lines(draw, wrap(draw, ripple["watch"], watch_font, TEXT_W), watch_font, MARGIN, watch_y + 56, 12)
    draw.text((MARGIN, H - 120), "※ 해석은 참고용이며 결과를 보장하지 않습니다.", font=load_font(28), fill=MUTED)
    return img


def strategy_card(index, total, strategy):
    img, draw = new_card(index, total)
    tag(draw, "대응 전략")
    head_font = load_font(60, bold=True)
    y = draw_lines(draw, wrap(draw, strategy["headline"], head_font, TEXT_W), head_font, MARGIN, 340, 16)
    y += 50
    name_font = load_font(42, bold=True)
    body_font = load_font(36)
    for group in strategy["groups"]:
        y = draw_lines(draw, wrap(draw, group["name"], name_font, TEXT_W), name_font, MARGIN, y, 10, fill=ACCENT)
        y += 8
        for point in group["points"]:
            y = draw_lines(draw, wrap(draw, f"• {point}", body_font, TEXT_W - 20), body_font, MARGIN + 20, y, 10)
            y += 6
        y += 30
    return img


def checklist_card(index, total, checklist):
    img, draw = new_card(index, total)
    tag(draw, "체크리스트")
    head_font = load_font(60, bold=True)
    y = draw_lines(draw, wrap(draw, "다음에 확인할 것", head_font, TEXT_W), head_font, MARGIN, 340, 16)
    y += 60
    item_font = load_font(42)
    for i, item in enumerate(checklist, 1):
        draw.text((MARGIN, y), f"{i}.", font=load_font(42, bold=True), fill=ACCENT)
        y = draw_lines(draw, wrap(draw, item, item_font, TEXT_W - 80), item_font, MARGIN + 80, y, 12)
        y += 30
    return img


def outro_card(data, total):
    img, draw = new_card(total, total)
    outro = data.get("outro", {})
    head_font = load_font(84, bold=True)
    body_font = load_font(44)
    draw.text((MARGIN, 240), "오늘 정리", font=load_font(48), fill=MUTED)
    y = draw_lines(draw, wrap(draw, outro.get("headline", "오늘의 핵심"), head_font, TEXT_W),
                   head_font, MARGIN, 300, 18)
    y += 60
    for point in outro.get("points", []):
        y = draw_lines(draw, wrap(draw, f"• {point}", body_font, TEXT_W), body_font, MARGIN, y, 14)
        y += 26
    y += 60
    cta_font = load_font(42, bold=True)
    for text in data.get("cta", []):
        y = draw_lines(draw, wrap(draw, text, cta_font, TEXT_W), cta_font, MARGIN, y, 14, fill=ACCENT)
        y += 20
    draw.text((MARGIN, H - 120), DISCLAIMER, font=load_font(28), fill=MUTED)
    return img


def build_cards(data):
    total = total_cards(data)
    cards = [cover_card(data, total)]
    cards += [issue_card(i + 2, total, issue) for i, issue in enumerate(data["issues"])]
    if total == 10:
        cards += [ripple_card(i + 5, total, r) for i, r in enumerate(data["ripples"])]
        cards.append(strategy_card(8, total, data["strategy"]))
        cards.append(checklist_card(9, total, data.get("checklist", [])))
    cards.append(outro_card(data, total))
    return cards


def main():
    ap = argparse.ArgumentParser(description="매일의 경제 이슈 카드뉴스 생성 (5장 또는 10장)")
    ap.add_argument("--issues", required=True, help="하루치 이슈 JSON 파일")
    ap.add_argument("--out", default="econ_cards", help="출력 폴더")
    args = ap.parse_args()

    with open(args.issues, encoding="utf-8") as f:
        data = json.load(f)
    try:
        validate(data)
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    cards = build_cards(data)
    for i, card in enumerate(cards, 1):
        path = os.path.join(args.out, f"card_{i}.png")
        card.save(path, "PNG")
        print(f"저장: {path}")

    caption = [f"[{data['date']}] 오늘의 경제 이슈", ""]
    caption += [f"{i}. [{x['category']}] {x['headline']}" for i, x in enumerate(data["issues"], 1)]
    caption += ["", DISCLAIMER, "", data.get("hashtags", "")]
    path = os.path.join(args.out, "caption.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(caption).strip() + "\n")
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
