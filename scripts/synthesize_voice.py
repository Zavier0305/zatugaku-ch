"""
音声合成スクリプト(パイプライン工程03)
------------------------------------
output/YYYY-MM-DD_script.json の台本テキストを、VOICEVOX ENGINEのHTTP APIで
ナレーション音声(WAV)に変換する。

前提: VOICEVOX ENGINEがローカルで起動していること(既定: http://127.0.0.1:50021)。
GitHub Actions上ではDockerサービスコンテナとして起動する(daily-post.yml参照)。

話者IDはハードコードせず、/speakers から名前で検索して解決する。
理由: バージョンやビルドによってIDが変わる場合があるため、
名前指定の方が壊れにくい。

必要な環境変数(任意):
    VOICEVOX_URL      … 既定 http://127.0.0.1:50021
    VOICEVOX_SPEAKER   … 話者名の部分一致(既定 "ずんだもん")
    VOICEVOX_STYLE     … スタイル名の部分一致(既定 "ノーマル")

使い方:
    python3 synthesize_voice.py                 # 最新の未合成の台本を処理
    python3 synthesize_voice.py --list-speakers  # 利用可能な話者一覧を表示して終了
"""

import argparse
import glob
import json
import os
import sys
import urllib.request
import urllib.parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
SPEAKER_NAME = os.environ.get("VOICEVOX_SPEAKER", "ずんだもん")
STYLE_NAME = os.environ.get("VOICEVOX_STYLE", "ノーマル")


def http_post_json(url, params=None, json_body=None, timeout=30):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else b""
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def http_get_json(url, timeout=15):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def resolve_speaker_id():
    speakers = http_get_json(f"{VOICEVOX_URL}/speakers")
    for speaker in speakers:
        if SPEAKER_NAME not in speaker.get("name", ""):
            continue
        for style in speaker.get("styles", []):
            if STYLE_NAME in style.get("name", ""):
                return style["id"], speaker["name"], style["name"]
    # フォールバック: 話者名だけ一致すれば先頭スタイルを使う
    for speaker in speakers:
        if SPEAKER_NAME in speaker.get("name", ""):
            style = speaker["styles"][0]
            return style["id"], speaker["name"], style["name"]

    available = ", ".join(s["name"] for s in speakers)
    raise RuntimeError(
        f"話者「{SPEAKER_NAME}」が見つかりませんでした。利用可能な話者: {available}"
    )


def find_latest_script_without_audio():
    script_paths = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_script.json")))
    for path in reversed(script_paths):
        wav_path = path.replace("_script.json", "_voice.wav")
        if not os.path.exists(wav_path):
            return path, wav_path
    return None, None


def synthesize(text, speaker_id):
    query = http_post_json(f"{VOICEVOX_URL}/audio_query", params={"speaker": speaker_id, "text": text})

    url = f"{VOICEVOX_URL}/synthesis?{urllib.parse.urlencode({'speaker': speaker_id})}"
    req = urllib.request.Request(
        url,
        data=json.dumps(query).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return res.read()  # WAVバイナリ


def main():
    parser = argparse.ArgumentParser(description="台本をVOICEVOXでナレーション音声化する")
    parser.add_argument("--list-speakers", action="store_true", help="利用可能な話者一覧を表示して終了")
    args = parser.parse_args()

    if args.list_speakers:
        speakers = http_get_json(f"{VOICEVOX_URL}/speakers")
        for speaker in speakers:
            styles = ", ".join(f"{s['name']}(id={s['id']})" for s in speaker["styles"])
            print(f"{speaker['name']}: {styles}")
        return

    script_path, wav_path = find_latest_script_without_audio()
    if script_path is None:
        print("[error] 音声化すべき未処理の台本がありません。先に generate_script.py を実行してください", file=sys.stderr)
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    text = script_data["script"]

    try:
        speaker_id, speaker_name, style_name = resolve_speaker_id()
    except (urllib.error.URLError, RuntimeError) as e:
        print(f"[error] VOICEVOXへの接続または話者解決に失敗しました: {e}", file=sys.stderr)
        print(f"  VOICEVOX_URL={VOICEVOX_URL} が起動しているか確認してください", file=sys.stderr)
        sys.exit(1)

    wav_bytes = synthesize(text, speaker_id)

    with open(wav_path, "wb") as f:
        f.write(wav_bytes)

    print(f"[ok] 音声を生成しました: {wav_path}")
    print(f"  話者: {speaker_name}({style_name})")


if __name__ == "__main__":
    main()
