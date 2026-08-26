"""
映像合成スクリプト(パイプライン工程04)
------------------------------------
台本テキスト(output/*_script.json)とナレーション音声(output/*_voice.wav)から、
実写素材なしのテロップ主体ショート動画(9:16, 1080x1920)を組み立てる。

作り方:
1. 台本を句読点で区切り、画面に収まる長さのテロップ単位に分割する
2. 各テロップの表示時間を、文字数に比例させてナレーション尺いっぱいに割り振る
3. Pillowでテロップごとに1枚の背景+テキスト画像(PNG)を描画する
   (フォーマット: フック型/クイズ型/比較型 で配色を変える)
4. ffmpegの concat demuxer で画像を尺どおりに連結し、音声を合成してmp4化する

必要なもの:
    ffmpeg (システムにインストール済みであること)
    Noto Sans CJK JP相当のフォント(GitHub Actions runnerではapt-getで導入する。
    daily-post.yml参照)

使い方:
    python3 compose_video.py
"""

import glob
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import wave

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

WIDTH, HEIGHT = 1080, 1920
MIN_CHUNK_SECONDS = 1.1  # 1テロップあたりの最短表示時間
MAX_CHUNK_CHARS = 24     # 1テロップに収める目安文字数(2行想定)

# フォーマットごとの配色(上→下グラデーション用の2色)
FORMAT_COLORS = {
    "フック型": ((255, 138, 76), (214, 62, 46)),   # 暖色: オレンジ→レッド
    "クイズ型": ((124, 92, 255), (58, 41, 158)),   # 紫系
    "比較型":   ((44, 168, 189), (21, 90, 138)),   # 青緑系
}
DEFAULT_COLORS = ((90, 98, 122), (32, 36, 48))

FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def find_latest_unrendered_pair():
    script_paths = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_script.json")))
    for path in reversed(script_paths):
        stem = path[: -len("_script.json")]
        wav_path = stem + "_voice.wav"
        video_path = stem + "_video.mp4"
        if os.path.exists(wav_path) and not os.path.exists(video_path):
            return path, wav_path, video_path
    return None, None, None


def get_wav_duration(wav_path):
    with wave.open(wav_path, "rb") as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)


def split_into_chunks(text, max_chars=MAX_CHUNK_CHARS):
    # まず句点で文単位に分割
    sentences = [s for s in text.replace("。", "。\n").split("\n") if s.strip()]

    chunks = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        # 長い文は読点や助詞の切れ目を優先しつつ、textwrapでmax_chars単位に分割
        pieces = [p for p in sentence.replace("、", "、\n").split("\n") if p]
        buf = ""
        for piece in pieces:
            if len(buf) + len(piece) <= max_chars:
                buf += piece
            else:
                if buf:
                    chunks.append(buf)
                # pieceそのものが長すぎる場合は強制的に折り返す
                if len(piece) > max_chars:
                    chunks.extend(textwrap.wrap(piece, max_chars))
                    buf = ""
                else:
                    buf = piece
        if buf:
            chunks.append(buf)

    return [c for c in chunks if c.strip()]


def allocate_durations(chunks, total_seconds):
    total_chars = sum(len(c) for c in chunks) or 1
    raw = [max(MIN_CHUNK_SECONDS, total_seconds * len(c) / total_chars) for c in chunks]

    # MIN_CHUNK_SECONDSで底上げした分、合計が尺を超えないよう比例縮小する
    scale = total_seconds / sum(raw)
    durations = [d * scale for d in raw]

    # 端数調整: 最後のチャンクで合計を厳密に一致させる
    diff = total_seconds - sum(durations)
    durations[-1] += diff
    return durations


def wrap_for_display(text, font, max_width):
    # 表示用に、実際の描画幅を見ながら折り返す(日本語は文字単位で改行してよい)
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


def render_frame(text, colors, out_path):
    top_color, bottom_color = colors
    img = Image.new("RGB", (WIDTH, HEIGHT), top_color)
    draw = ImageDraw.Draw(img)

    # 縦グラデーション背景
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    font = ImageFont.truetype(FONT_BOLD, 66, index=0)
    max_text_width = WIDTH - 160
    lines = wrap_for_display(text, font, max_text_width)

    line_height = 92
    block_height = line_height * len(lines)
    panel_pad_y = 60
    panel_top = (HEIGHT - block_height) // 2 - panel_pad_y
    panel_bottom = (HEIGHT + block_height) // 2 + panel_pad_y

    # 半透明パネル
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [60, panel_top, WIDTH - 60, panel_bottom], radius=32, fill=(10, 12, 18, 150)
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    y = (HEIGHT - block_height) // 2
    for line in lines:
        bbox = font.getbbox(line)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        # 縁取り(視認性確保)
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_height

    img.save(out_path)


def build_video(frame_specs, wav_path, out_path):
    with tempfile.TemporaryDirectory() as tmp:
        concat_path = os.path.join(tmp, "concat.txt")
        with open(concat_path, "w", encoding="utf-8") as f:
            for frame_path, duration in frame_specs:
                f.write(f"file '{frame_path}'\n")
                f.write(f"duration {duration:.3f}\n")
            # concat demuxerの仕様上、最後の画像をもう一度書く必要がある
            f.write(f"file '{frame_specs[-1][0]}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_path,
            "-i", wav_path,
            "-vf", "fps=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            "-shortest",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-2000:]}")


def main():
    script_path, wav_path, video_path = find_latest_unrendered_pair()
    if script_path is None:
        print("[error] 映像化すべき未処理の台本・音声のペアがありません", file=sys.stderr)
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    text = script_data["script"]
    format_name = script_data.get("format", "")
    colors = FORMAT_COLORS.get(format_name, DEFAULT_COLORS)

    total_seconds = get_wav_duration(wav_path)
    chunks = split_into_chunks(text)
    durations = allocate_durations(chunks, total_seconds)

    with tempfile.TemporaryDirectory() as frame_dir:
        frame_specs = []
        for i, (chunk, duration) in enumerate(zip(chunks, durations)):
            frame_path = os.path.join(frame_dir, f"frame_{i:03d}.png")
            render_frame(chunk, colors, frame_path)
            frame_specs.append((frame_path, duration))

        build_video(frame_specs, wav_path, video_path)

    print(f"[ok] 動画を生成しました: {video_path}")
    print(f"  テロップ数: {len(chunks)} / 尺: {total_seconds:.1f}秒 / フォーマット: {format_name}")


if __name__ == "__main__":
    main()
