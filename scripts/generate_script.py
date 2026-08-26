"""
台本生成スクリプト(パイプライン工程02)
------------------------------------
data/candidates.jsonl に溜まったネタ候補から未使用のものを1件選び、
Anthropic API(Claude)を使って、A-1テンプレ(フック→事実→着地)の
ショート動画台本に書き直す。

重要: 出典の事実(extract)をそのまま読み上げるのではなく、
Claudeに「独自の言葉で再構成する」よう明示的に指示している。
これはYouTubeの量産型コンテンツポリシー対策と著作権対策を兼ねる。

必要な環境変数:
    ANTHROPIC_API_KEY  … console.anthropic.com で発行するAPIキー
                          (Claudeサブスクリプションとは別課金)

使い方:
    python3 generate_script.py                # 実際にAPIを呼んで生成
    python3 generate_script.py --dry-run       # APIを呼ばずプロンプトのみ表示(動作確認用)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CANDIDATES_PATH = os.path.join(DATA_DIR, "candidates.jsonl")
SCRIPTED_TITLES_PATH = os.path.join(DATA_DIR, "scripted_titles.json")

JST = timezone(timedelta(hours=9))

# 曜日ごとのフォーマット・ローテーション(月曜=0)
FORMAT_ROTATION = {
    0: "フック型",  # 月
    1: "クイズ型",  # 火
    2: "比較型",    # 水
    3: "フック型",  # 木
    4: "クイズ型",  # 金
    5: "比較型",    # 土
    6: "フック型",  # 日
}

FORMAT_GUIDE = {
    "フック型": (
        "冒頭1文で『え、知らなかった』と思わせる意外な事実の予告から入り、"
        "その理由や背景を説明し、最後に一言で締める。"
    ),
    "クイズ型": (
        "冒頭で視聴者に問いを投げかけ(『〇〇なのはなぜでしょう?』)、"
        "数秒の間を意識させる一文を挟んでから答え合わせをし、最後に一言で締める。"
    ),
    "比較型": (
        "『AとBの違い、実は…』のように2つを対比する切り口で始め、"
        "違いの理由を説明し、最後に一言で締める。"
    ),
}

SYSTEM_PROMPT = """あなたはYouTubeショート動画(45〜60秒、ナレーション主体)の台本作家です。
以下のルールを厳守してください。

1. 出典として渡された文章は「事実の参考情報」であり、そのまま書き写してはいけません。
   自分の言葉で要点を再構成し、独自の切り口・言い回しで説明してください。
2. 台本は「フック→事実→着地」の3段構成。指定されたフォーマット(フック型/クイズ型/比較型)に沿うこと。
3. 話し言葉で、1文を短く。ナレーション読み上げ時間で45〜60秒(日本語で200〜260文字程度)に収める。
4. 誇張表現や真偽不明の断定は避け、出典の情報から逸脱しないこと。
5. 最後に、動画のタイトル案(20文字以内、続きが気になる言い回し)を1つ添える。

出力は以下のJSON形式のみ。説明文やコードブロックは付けないこと。
{
  "title": "動画タイトル案",
  "script": "台本本文(改行なしの1つの文字列)",
  "format": "使用したフォーマット名"
}
"""


def load_unscripted_candidate():
    if not os.path.exists(CANDIDATES_PATH):
        return None

    scripted_titles = set()
    if os.path.exists(SCRIPTED_TITLES_PATH):
        with open(SCRIPTED_TITLES_PATH, "r", encoding="utf-8") as f:
            scripted_titles = set(json.load(f))

    with open(CANDIDATES_PATH, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    for candidate in lines:
        if candidate["title"] not in scripted_titles:
            return candidate, scripted_titles

    return None, scripted_titles


def mark_scripted(title, scripted_titles):
    scripted_titles.add(title)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCRIPTED_TITLES_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(scripted_titles), f, ensure_ascii=False, indent=2)


def build_user_prompt(candidate, format_name):
    return (
        f"【フォーマット】{format_name}\n"
        f"【フォーマットの型】{FORMAT_GUIDE[format_name]}\n\n"
        f"【出典タイトル】{candidate['title']}\n"
        f"【出典の要約】{candidate['extract']}\n"
    )


def call_claude(system_prompt, user_prompt):
    import anthropic

    client = anthropic.Anthropic()  # 環境変数 ANTHROPIC_API_KEY を自動参照
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def main():
    parser = argparse.ArgumentParser(description="ネタ候補から台本を生成する")
    parser.add_argument("--dry-run", action="store_true", help="APIを呼ばずプロンプトのみ表示")
    args = parser.parse_args()

    candidate, scripted_titles = load_unscripted_candidate()
    if candidate is None:
        print("[error] 未使用のネタ候補がありません。先に fetch_trivia.py を実行してください", file=sys.stderr)
        sys.exit(1)

    weekday = datetime.now(JST).weekday()
    format_name = FORMAT_ROTATION[weekday]
    user_prompt = build_user_prompt(candidate, format_name)

    if args.dry_run:
        print("=== SYSTEM PROMPT ===")
        print(SYSTEM_PROMPT)
        print("=== USER PROMPT ===")
        print(user_prompt)
        print("[dry-run] ここでAPIは呼ばれていません")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[error] 環境変数 ANTHROPIC_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    raw_response = call_claude(SYSTEM_PROMPT, user_prompt)

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError:
        print("[error] Claudeの応答をJSONとして解釈できませんでした:", file=sys.stderr)
        print(raw_response, file=sys.stderr)
        sys.exit(1)

    result["source_title"] = candidate["title"]
    result["source_url"] = candidate.get("url")
    result["generated_at"] = datetime.now(JST).isoformat()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now(JST).strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"{date_str}_script.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    mark_scripted(candidate["title"], scripted_titles)

    print(f"[ok] 台本を生成しました: {out_path}")
    print(f"  タイトル案: {result.get('title')}")


if __name__ == "__main__":
    main()
