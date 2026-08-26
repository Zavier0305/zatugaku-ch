# 雑学ch自動化パイプライン

一般雑学ショートch用の、毎日自動投稿パイプラインです。全体設計は別途まとめた
[設計図(ブループリント)](実装計画の詳細はチャットで共有したArtifactを参照)を参照してください。

## 現在の実装状況

8工程すべてのコードが揃いました。ただし**まだ実際にリポジトリへpushしてGitHub Actions上で
通しで動かした実績はありません**。特にYouTube投稿(工程06)は、ご自身のOAuth設定が終わってからでないと
動作確認できません。

| 工程 | 状態 |
|---|---|
| 01 ネタ収集(Wikipedia API) | ✅ 実装済み・実API確認済み |
| 02 台本生成(Claude API) | ✅ 実装済み・実API確認済み |
| 03 音声合成(VOICEVOX) | ✅ 実装済み(ロジックのみ確認。下記「動作確認について」参照) |
| 04 映像合成(テロップ・図解) | ✅ 実装済み・実サンプルで動作確認済み |
| 05 サムネイル生成 | ✅ 実装済み・実サンプルで動作確認済み(下記の要確認点あり) |
| 06 YouTube投稿(Data API v3) | ✅ 実装済み(コードのみ。要OAuth設定・未実機確認) |
| 07 定期実行 | ✅ GitHub Actionsで実装済み(毎日06:00 JST) |
| 08 異常検知 | ✅ 簡易実装(失敗時のジョブサマリー表示。GitHubの標準メール通知に依存) |

**このクラウド開発環境からは Wikipedia / YouTube / Docker Hub 系のAPIに直接アクセスできなかった**ため
(検証済み: 403 Forbidden、Docker Hubは接続自体が不可)、定期実行の場所として GitHub Actions を採用しています。
GitHub Actionsのサーバーには通常のインターネットアクセスがあります。

### 動作確認について(要確認)

工程01・02は本物のAPIで動作確認済みです。工程03(VOICEVOX)は、この開発環境から
Docker Hubに接続できずVOICEVOX ENGINEの実機を起動できなかったため、**ダミーサーバーで
スクリプトのロジック(話者解決・APIリクエスト形式・ファイル出力)のみ検証**しています。
実際の音声品質・GitHub Actions上でのDockerサービスコンテナ起動可否は、
`workflow_dispatch`で手動実行して確認してください。

## セットアップ手順

### 1. リポジトリを作成してこのフォルダを push する

GitHubで新しいリポジトリ(Public/Privateどちらでも可。Private推奨)を作成し、
このフォルダの中身をpushしてください。

```bash
cd zatsugaku-ch
git init
git add .
git commit -m "init: zatsugaku-ch automation pipeline"
git branch -M main
git remote add origin https://github.com/<あなたのユーザー名>/<リポジトリ名>.git
git push -u origin main
```

### 2. Anthropic APIキーを取得してSecretに登録する

台本生成にはAnthropic APIを使います。**Claude.aiのサブスクリプションとは別課金**の
APIキーが必要です。

1. https://console.anthropic.com でAPIキーを発行する
2. GitHubリポジトリの `Settings > Secrets and variables > Actions` で
   `New repository secret` を押す
3. Name: `ANTHROPIC_API_KEY` / Secret: 発行したキー を登録する

### 3. YouTube側のチャンネル開設とOAuth設定

1. YouTube Studioで新チャンネルを開設する(APIでは代行できない、手動の1回きりの作業)
2. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成し、
   「YouTube Data API v3」を有効化する
3. 「APIとサービス > 認証情報」で、OAuthクライアントID(種類: **デスクトップアプリ**)を作成し、
   JSONをダウンロードして `client_secret.json` という名前でこのフォルダ直下に置く
4. 自分のPC(ブラウザが開ける環境)で以下を実行:
   ```bash
   pip install google-auth-oauthlib
   python3 scripts/get_refresh_token.py
   ```
   ブラウザが開くので、動画を投稿したいアカウントでログイン・許可する
5. ターミナルに表示される `client_id` / `client_secret` / `refresh_token` を、
   GitHub Secretsに登録する: `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN`

**動画は既定で `private`(非公開)でアップロードされます。** 内容・音声・字幕すべてを
実際に確認できてから、`.github/workflows/daily-post.yml` 内のコメントを外して
`public` に切り替えてください(いきなり無人で公開するのはリスクが高いための安全策)。

### 4. Actionsを有効化して手動実行してみる

1. リポジトリの `Actions` タブを開く
2. 「雑学ch 毎日自動生成」ワークフローを選択し、`Run workflow` で手動実行
3. 成功すると、台本・音声・動画・サムネイルが生成され、YouTubeに`private`でアップロードされる
   (アップロード後のURLはActionsのログに出力される)
4. 生成物一式はActionsのアーティファクト(14日保存)からもダウンロードして確認できる

問題なければ、以降は毎日 06:00(JST)に自動実行されます。

## ローカルでの動作確認

APIキーを使わずにプロンプトだけ確認したい場合:

```bash
pip install -r requirements.txt
python3 scripts/fetch_trivia.py --count 3
python3 scripts/generate_script.py --dry-run
```

実際に生成する場合は `ANTHROPIC_API_KEY` を環境変数にセットしてから
`--dry-run` を外して実行してください。

## 次にやること

すべての工程のコードは揃いました。残っているのは「実際にGitHub Actions上で
通しで動かして検証する」ことだけです。特に以下は実機でないと確認できません。

1. VOICEVOXがDockerサービスコンテナとして正常に起動するか
2. 生成される音声・動画の品質(棒読み感、テロップの間の取り方など)
3. YouTube Shortsとして正しく認識されるか(1080x1920・3分以内のため理論上は該当するはず)
4. サムネイルがAPI経由でShortsに反映されるか(下記の要確認点)

## 工程05(サムネイル生成)の要確認点

2026年2月時点の一部情報源によれば、**YouTube Shortsのカスタムサムネイル設定は
スマートフォンアプリからのみ対応しており、YouTube Studio(PC)やAPIでは
対応していない可能性がある**([参考](https://www.samune-ai.jp/blog/youtube-shorts-samune-tsukurikata))。
これが事実だとすると、工程06でData APIの`thumbnails.set`を呼んでも
Shorts動画には反映されない可能性がある。工程06を実装する際に実際のAPI挙動を
確認し、反映されない場合は「動画の最初のフレームをサムネ画像と同じデザインにする」
方式に切り替える想定。

## 工程04(映像合成)について

このクラウド開発環境ではffmpeg・Noto Sans CJK JPフォントが揃っていたため、
実際に無音のテストWAV(45秒)を使って生成からmp4出力まで動作確認済みです
(1080x1920, h264/aac, テロップ14個, ぴったり45秒)。GitHub Actions(ubuntu-latest)
には日本語フォントが標準で入っていないため、ワークフロー内で
`apt-get install fonts-noto-cjk` を実行してから合成するようにしています。

## リポジトリ容量について(要確認)

音声・動画・サムネイルなどの生成物はgitにコミットせず、GitHub Actionsの
アーティファクト(14日で自動削除)として保存する設計にしています。理由は、
毎日バイナリファイルをコミットし続けるとリポジトリが際限なく肥大化するためです。
工程06(YouTube投稿)まで実装すれば、生成物はYouTubeに上がった後は破棄してよいので、
このままの方針で問題ない見込みですが、動画ファイルのサイズ次第では
Actionsのストレージ上限(無料枠)に触れる可能性があるため、運用しながら確認してください。

## ネタ元について

スクレイピングではなくWikipedia REST APIを使用しています。事実の要約(extract)は
そのまま読み上げず、Claudeが独自の言葉で台本に再構成する設計にしています
(YouTubeの量産型コンテンツポリシー対策と著作権対策を兼ねる)。
