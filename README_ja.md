# GeNarrative

> ※ 本リポジトリは実験用のプロダクトであり、現在も開発・検証中です。仕様や挙動は予告なく変更される可能性があります。

## 🌟 概要 (Overview)
GeNarrative はローカル環境で動作するマルチモーダル創作支援アシスタントです。
台本・イラスト・音声・BGM を組み合わせ、オフラインでオリジナルの物語体験を作れます。
**SIS（Semantic Interface Structure）** という「意味の中間表現」を介して、生成 → 再生成 → 比較 → 編集を回せることを重視しています。
各機能は Docker で分離され、プライバシー・再現性・拡張性を重視しています。

- 想定入力例: 台本、子どもの手描きイラスト
- 想定出力例: ナレーション付きマルチメディア物語 (HTML / MP4)
- 目的: **完成品アプリ**ではなく、生成パイプラインを **観測・再現・比較**できる状態を作る

## 何が新しいか
### 1) SIS：意味の中間表現を“表に出す”
GeNarrative は、作品やシーンの意味情報を **SIS** としてJSON化し、
- 意味（SIS）を固定したまま **モデル/パラメータだけ差し替え**
- 生成条件を残して **再現性を確保**
- 抽出が不完全でも **人手で編集・補正**
を可能にします。

### 2) ローカル & 分離構成：差し替えと比較がしやすい
UIが各サービスのREST APIをオーケストレーションし、成果物を `shared/` に集約します。
これにより、LLM / 画像生成 / TTS / 音楽生成を **モジュール単位で比較**できます。

## 🏗️ アーキテクチャ / 技術スタック
GeNarrative はマイクロサービス構成です。UI が各サービスの REST API をオーケストレーションし、共有ストレージで成果物を受け渡します。

| コンポーネント | 技術 | 既定ポート | 説明 |
|---|---|---|---|
| 統合 UI | Flask + Swiper.js | 5000 | 一体型フロント/バックエンド、ワークフロー実行 |
| 画像生成 | Stable Diffusion (AUTOMATIC1111) | 7860 | イラスト・画像生成 |
| 音声合成 | Coqui TTS | 5002 | ナレーション音声生成 |
| 音楽生成 | MusicGen (Meta AudioCraft) | 5003 | 背景音楽・効果音生成 |
| LLM ランタイム | Ollama | 11434 | テキスト生成、SIS 変換補助 |

- 内部ネットワーク: Docker ブリッジネットワーク
- 共有ストレージ: `shared/`（各サービスで共用）
- 既定ポートは `docker-compose.yml` を優先

## 🧩 SIS (Semantic Interface Structure)

- GeNarrative では、マルチモーダル生成の共通フォーマットとして **SIS (Semantic Interface Structure)** を利用しています。
- SIS をハブにして、台本や画像 から SIS を生成し、SIS から台本・イラスト・BGM などを統一的に生成・管理できます。
- 生成物から SIS を再抽出して、検索や評価（整合性チェック）に回すことも想定しています。
- 詳細な仕様は `docs/SIS.md` を参照してください。

## 📁 ディレクトリ構成
```text
GeNarrative-dev/
├── docker-compose.yml      # 全サービス定義
├── requirements.txt        # 共通 Python 依存
├── docs/                   # ドキュメント
├── sd/                     # 画像生成 (Stable Diffusion WebUI)
├── tts/                    # 音声合成 (Coqui TTS)
├── music/                  # 音楽生成 (MusicGen)
├── ui/                     # UI + Flask 統合サーバ
└── shared/                 # 共有データ領域
```

## 🔧 技術的課題と解決

| 課題 | 解決策 |
|---|---|
| マルチモーダル生成の制御 | 統一スキーマ（SIS）の考案と各モーダル向けメタプロンプト作成 |
| ライブラリの負荷・資源競合 | 各機能をコンテナ分離し負荷を局所化 |
| ローカル GPU での動作 | 量子化モデル・軽量モデルの利用 |
| 統合出力 | HTML＋Swiper.js または MP4 によるマルチメディア出力 |

## 🚀 クイックスタート (Windows/PowerShell)

事前に Docker をインストールしてください（GPU 利用のため、NVIDIA 環境が必要）。

- セットアップ時間の目安: 初回インストール〜起動まで 30 分以上
- 必要な空きディスク容量: 100GB 以上

```powershell
git clone https://github.com/joyk0117/GeNarrative-dev.git
cd GeNarrative-dev
docker compose up -d
```

起動後、ブラウザで `http://127.0.0.1:5000/` にアクセスして利用を開始します。

### サービス状態確認
```powershell
# すべてのサービス一覧
docker compose ps

# 個別ログ確認
docker compose logs ui      # UI サーバ
docker compose logs music   # 音楽生成サーバ
docker compose logs tts     # 音声合成サーバ
docker compose logs sd      # 画像生成サーバ
docker compose logs ollama  # テキスト生成サーバ
```

### アクセス
- 統合 UI: http://localhost:5000
- 画像生成 (A1111): http://localhost:7860
- LLM API (Ollama): http://localhost:11434

詳細なポートは `docker-compose.yml` を参照してください。

## 🛠️ トラブルシューティング（Windows）

### GPU / CUDA
- `nvidia-smi` で GPU 状態を確認（WSL2 上や対応環境で実行）
- Docker で GPU を使う場合は NVIDIA Container Toolkit 相当のセットアップが必要

### ポート競合
```powershell
# ポート使用確認（例: 5000）
netstat -ano | Select-String ":5000"

# PID を確認後、対象プロセスを停止
Get-Process -Id <PID>
Stop-Process -Id <PID> -Force
```

### API 接続・ネットワーク
```powershell
# コンテナ間疎通確認（例）
docker compose exec ui ping -c 1 music
docker compose exec ui ping -c 1 tts

# ログ確認
docker compose logs ui
docker compose logs music
docker compose logs tts
```

## ✅ 再現性チェック
- `docker compose up -d` で全サービス起動
- `docker compose logs` で各サービスのログ取得
- 生成物は `shared/` 以下に保存（各モジュールによりサブディレクトリが異なります）
- 主要エンドポイント（既定）:
	- http://localhost:5000 (UI)
	- http://localhost:7860 (画像)
	- http://localhost:5002 (TTS)
	- http://localhost:5003 (音楽)
	- http://localhost:11434 (Ollama)

## 📚 ドキュメント / 参照
- 構造化仕様（SIS）: `docs/SIS.md`
- UI/API 詳細: `ui/README.md`, `ui/API_REFERENCE.md`
- TTS 詳細: `tts/README.md`

## 🎯 今後の予定 (Roadmap)
- ストーリー全体の自動生成
- 多言語対応の強化
- 外部のAIサービスとの連携
- 段階的モダナイズ（フロントエンド: Flask → Vue.js、バックエンド: Flask → FastAPI）
- ファインチューニング(Image: LoRA, LLM: Unsloth)

## 📜 ライセンス
MIT License  
Copyright (c) 2025 Yuki Jo
注意: 本リポジトリにはオーケストレーション用のコードのみが含まれます。
Ollama、AUTOMATIC1111、Coqui TTS、MusicGen などのサードパーティ製モデル／ツール／その他のアセットは別途取得する必要があり、それぞれのライセンスに従ってご利用ください。
