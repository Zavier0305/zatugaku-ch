"""
YouTube OAuth リフレッシュトークン取得(セットアップ時にローカルで1回だけ実行)
--------------------------------------------------------------------
GitHub Actions(無人・ブラウザなし)では認可フローを実行できないため、
自分のPC上で一度だけこのスクリプトを実行し、以降ずっと使えるリフレッシュ
トークンを取得する。取得したトークンはGitHub Secretsに登録する。

事前準備:
    1. Google Cloud ConsoleでOAuthクライアントID(種類: デスクトップアプリ)を作成
    2. ダウンロードしたJSONを client_secret.json としてこのフォルダに置く

使い方(自分のPCで):
    pip install google-auth-oauthlib
    python3 get_refresh_token.py
    → ブラウザが開くので、動画を投稿したいGoogleアカウントでログイン・許可する
    → ターミナルに refresh_token が表示されるので、GitHub Secretsの
      YOUTUBE_REFRESH_TOKEN に登録する
"""

import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client_secret.json")


def main():
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"[error] {CLIENT_SECRET_FILE} が見つかりません。")
        print("Google Cloud Consoleでデスクトップアプリ用OAuthクライアントIDを作成し、")
        print("ダウンロードしたJSONをこの名前でリポジトリ直下に置いてください。")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n=== 取得成功 ===")
    print(f"client_id     : {creds.client_id}")
    print(f"client_secret : {creds.client_secret}")
    print(f"refresh_token : {creds.refresh_token}")
    print("\n上記3つをGitHubリポジトリの Secrets に登録してください:")
    print("  YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN")
    print("\n※ client_secret.json はリポジトリにコミットしないこと(.gitignore済み)")


if __name__ == "__main__":
    main()
