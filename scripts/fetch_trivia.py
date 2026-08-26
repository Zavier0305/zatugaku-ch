"""
ネタ収集スクリプト(パイプライン工程01)
------------------------------------
Wikipedia日本語版の「ランダム記事」APIから雑学の種になりそうな記事を取得し、
過去に使用済みの記事と重複しないものだけを候補としてストックする。

なぜスクレイピングではなくWikipedia APIか:
- 汎用サイトのスクレイピングは利用規約違反・著作権侵害のリスクを個別に確認する
  必要があるが、Wikipedia REST APIは公式に提供されたAPIであり、
  CC BY-SA 4.0 / GFDLの下で再利用が明確に許可されている。
- 「事実の要約を抽出し、台本は独自の言葉で書き直す」という前提であれば、
  事実(アイデア)自体には著作権が及ばないため、法的リスクが小さい。

使い方:
    python3 fetch_trivia.py --count 5

出力:
    data/candidates.jsonl に新しい候補を追記する(1行1候補のJSON)
    data/used_titles.json に使用済みタイトルを記録し、重複取得を避ける
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

WIKI_RANDOM_API = "https://ja.wikipedia.org/api/rest_v1/page/random/summary"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CANDIDATES_PATH = os.path.join(DATA_DIR, "candidates.jsonl")
USED_TITLES_PATH = os.path.join(DATA_DIR, "used_titles.json")

USER_AGENT = "zatsugaku-ch-bot/0.1 (personal project; contact: chuo-2024007@edu-g.gsn.ed.jp)"

# 雑学として弱い・扱いにくい記事を弾く簡易フィルタ
MIN_EXTRACT_LENGTH = 80  # 短すぎる=情報量が少ない
EXCLUDE_TITLE_KEYWORDS = [
    "年", "月", "曖昧さ回避", "一覧", "Wikipedia:", "Portal:", "Category:",
]


def load_used_titles():
    if not os.path.exists(USED_TITLES_PATH):
        return set()
    with open(USED_TITLES_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_used_titles(titles):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USED_TITLES_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(titles), f, ensure_ascii=False, indent=2)


def fetch_random_summary():
    req = urllib.request.Request(WIKI_RANDOM_API, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode("utf-8"))


def is_usable(article, used_titles):
    title = article.get("title", "")
    extract = article.get("extract", "")

    if title in used_titles:
        return False
    if len(extract) < MIN_EXTRACT_LENGTH:
        return False
    if any(kw in title for kw in EXCLUDE_TITLE_KEYWORDS):
        return False
    if article.get("type") == "disambiguation":
        return False
    return True


def collect(count, max_attempts=50):
    used_titles = load_used_titles()
    collected = []
    attempts = 0

    while len(collected) < count and attempts < max_attempts:
        attempts += 1
        try:
            article = fetch_random_summary()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"[warn] fetch failed (attempt {attempts}): {e}", file=sys.stderr)
            time.sleep(1)
            continue

        if not is_usable(article, used_titles):
            continue

        candidate = {
            "title": article.get("title"),
            "extract": article.get("extract"),
            "url": article.get("content_urls", {}).get("desktop", {}).get("page"),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00", time.localtime()),
        }
        collected.append(candidate)
        used_titles.add(candidate["title"])
        time.sleep(0.3)  # 連続リクエストの間隔をあける

    return collected, used_titles


def append_candidates(candidates):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CANDIDATES_PATH, "a", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Wikipediaから雑学ネタ候補を収集する")
    parser.add_argument("--count", type=int, default=5, help="収集する候補数(既定: 5)")
    args = parser.parse_args()

    candidates, used_titles = collect(args.count)

    if not candidates:
        print("[error] 候補を1件も取得できませんでした", file=sys.stderr)
        sys.exit(1)

    append_candidates(candidates)
    save_used_titles(used_titles)

    print(f"[ok] {len(candidates)}件の新規候補を取得しました")
    for c in candidates:
        print(f"  - {c['title']}")


if __name__ == "__main__":
    main()
