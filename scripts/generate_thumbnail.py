"""
サムネイル生成スクリプト(パイプライン工程05)
------------------------------------
台本のタイトル案(output/*_script.json の "title")から、
ショート動画用サムネイル(1080x1920, 9:16)を生成する。

サイズはYouTube Shorts用カスタムサムネイルの推奨サイズ(1080x1920)に合わせている。

【要確認】2026年2月時点の情報では、Shorts用カスタムサムネイルの設定は
スマートフォンアプリからのみ対応しており、YouTube Studio(PC)やAPI経由では
対応していない可能性がある。工程06(YouTube投稿)を実装する際に、
Data APIのthumbnails.setがShorts動画に対して実際に反映されるか要検証。
反映されない場合、この工程05で作った画像は「投稿時に自動設定される表紙」
ではなく「手動で使う候補」または「動画内の最初のフレームをこのデザインにする」
形に設計変更が必要。

使い方:
    python3 generate_thumbnail.py
"""

import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

WIDTH, HEIGHT = 1080, 1920

FORMAT_COLORS = {
    "フック型": ((255, 138, 76), (214, 62, 46)),
    "クイズ型": ((124, 92, 255), (58, 41, 158)),
    "比較型":   ((44, 168, 189), (21, 90, 138)),
}
DEFAULT_COLORS = ((90, 98, 122), (32, 36, 48))

FORMAT_BADGE = {
    "フック型": "実は…",
    "クイズ型": "クイズ",
    "比較型": "徹底比較",
}

FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def find_latest_script_without_thumbnail():
    script_paths = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_script.json")))
    for path in reversed(script_paths):
        stem = path[: -len("_script.json")]
        thumb_path = stem + "_thumbnail.png"
        if not os.path.exists(thumb_path):
            return path, thumb_path
    return None, None


def wrap_for_display(text, font, max_width):
    lines, current = [], ""
    for ch in text:
        trial = current + ch
        bbox = font.getbbox(trial)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def draw_outlined_text(draw, xy, text, font, fill, outline_fill, outline_width=5):
    x, y = xy
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline_fill)
    draw.text((x, y), text, font=font, fill=fill)


def render_thumbnail(title, format_name, out_path):
    colors = FORMAT_COLORS.get(format_name, DEFAULT_COLORS)
    top_color, bottom_color = colors

    img = Image.new("RGB", (WIDTH, HEIGHT), top_color)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # バッジ(フォーマット名)
    badge_text = FORMAT_BADGE.get(format_name, "雑学")
    badge_font = ImageFont.truetype(FONT_BOLD, 54, index=0)
    bbox = badge_font.getbbox(badge_text)
    badge_w, badge_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    badge_pad_x, badge_pad_y = 36, 20
    badge_top = 120
    draw.rounded_rectangle(
        [80, badge_top, 80 + badge_w + badge_pad_x * 2, badge_top + badge_h + badge_pad_y * 2],
        radius=18,
        fill=(255, 255, 255),
    )
    draw.text((80 + badge_pad_x, badge_top + badge_pad_y - bbox[1]), badge_text, font=badge_font, fill=top_color)

    # メインタイトル(大きめ・太字・縁取り)
    title_font = ImageFont.truetype(FONT_BOLD, 108, index=0)
    max_width = WIDTH - 140
    lines = wrap_for_display(title, title_font, max_width)

    line_height = 150
    block_height = line_height * len(lines)
    y = (HEIGHT - block_height) // 2

    for line in lines:
        bbox = title_font.getbbox(line)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        draw_outlined_text(draw, (x, y), line, title_font, fill=(255, 255, 255), outline_fill=(0, 0, 0), outline_width=6)
        y += line_height

    img.save(out_path)


def main():
    script_path, thumb_path = find_latest_script_without_thumbnail()
    if script_path is None:
        print("[error] サムネイル化すべき未処理の台本がありません", file=sys.stderr)
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    title = script_data.get("title", "")
    format_name = script_data.get("format", "")

    render_thumbnail(title, format_name, thumb_path)

    print(f"[ok] サムネイルを生成しました: {thumb_path}")


if __name__ == "__main__":
    main()
