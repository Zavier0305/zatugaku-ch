"""
YouTube投稿スクリプト(パイプライン工程06)
------------------------------------
output/*_video.mp4 と対応する台本(タイトル・出典)から、YouTube Data API v3で
動画をアップロードする。サムネイルも合わせて設定を試みる(工程05の要確認点参照)。

必要な環境変数:
    YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
        … get_refresh_token.py で事前に1回だけ取得し、GitHub Secretsに登録

任意の環境変数:
    YOUTUBE_PRIVACY_STATUS … 既定 "private"(安全側のデフォルト。動作に自信が
                              持てたら "public" に変更する)
    YOUTUBE_CATEGORY_ID    … 既定 "27"(教育)

使い方:
    python3 upload_video.py                # 実際にアップロード
    python3 upload_video.py --dry-run       # メタデータのみ表示、APIは呼ばない
"""

import argparse
import glob
import json
import os
import sys

DATA_DIR_NAME = "output"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, DATA_DIR_NAME)

PRIVACY_STATUS = os.environ.get("YOUTUBE_PRIVACY_STATUS", "private")
CATEGORY_ID = os.environ.get("YOUTUBE_CATEGORY_ID", "27")  # 27 = 教育

FORMAT_HASHTAGS = {
    "フック型": "#雑学 #豆知識 #shorts",
    "クイズ型": "#雑学クイズ #豆知識 #shorts",
    "比較型": "#雑学 #比較 #shorts",
}


def find_latest_unuploaded_set():
    script_paths = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_script.json")))
    for path in reversed(script_paths):
        stem = path[: -len("_script.json")]
        video_path = stem + "_video.mp4"
        thumb_path = stem + "_thumbnail.png"
        uploaded_marker = stem + "_uploaded.json"
        if os.path.exists(video_path) and not os.path.exists(uploaded_marker):
            return path, video_path, thumb_path, uploaded_marker
    return None, None, None, None


def build_metadata(script_data):
    format_name = script_data.get("format", "")
    hashtags = FORMAT_HASHTAGS.get(format_name, "#雑学 #shorts")

    description = (
        f"{script_data.get('script', '')}\n\n"
        f"{hashtags}\n\n"
        "※本編は出典情報をもとに独自に再構成したオリジナル解説です。"
    )

    return {
        "snippet": {
            "title": script_data.get("title", "雑学ショート"),
            "description": description,
            "tags": ["雑学", "豆知識", "shorts", format_name],
            "categoryId": CATEGORY_ID,
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,  # 子供向けではないと自己申告。内容に応じて要確認
        },
    }


def upload(video_path, thumb_path, metadata):
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )

    youtube = build("youtube", "v3", credentials=creds)

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=metadata, media_body=media)
    response = request.execute()
    video_id = response["id"]

    print(f"[ok] アップロード完了: https://youtu.be/{video_id}")

    if thumb_path and os.path.exists(thumb_path):
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumb_path)).execute()
            print("[ok] サムネイルを設定しました")
        except Exception as e:  # noqa: BLE001 — Shorts非対応の可能性があるため握りつぶして継続
            print(f"[warn] サムネイル設定に失敗しました(Shorts未対応の可能性): {e}", file=sys.stderr)

    return video_id


def main():
    parser = argparse.ArgumentParser(description="動画をYouTubeにアップロードする")
    parser.add_argument("--dry-run", action="store_true", help="APIを呼ばずメタデータのみ表示")
    args = parser.parse_args()

    script_path, video_path, thumb_path, marker_path = find_latest_unuploaded_set()
    if script_path is None:
        print("[error] アップロードすべき未処理の動画がありません", file=sys.stderr)
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    metadata = build_metadata(script_data)

    if args.dry_run:
        print("=== アップロードされるメタデータ(dry-run) ===")
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        print(f"動画ファイル: {video_path}")
        print(f"サムネイル: {thumb_path}")
        return

    required_env = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [k for k in required_env if not os.environ.get(k)]
    if missing:
        print(f"[error] 環境変数が不足しています: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    video_id = upload(video_path, thumb_path, metadata)

    with open(marker_path, "w", encoding="utf-8") as f:
        json.dump({"video_id": video_id, "url": f"https://youtu.be/{video_id}"}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
