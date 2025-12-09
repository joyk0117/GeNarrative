# GeNarrative Development Scripts

このディレクトリには、GeNarrativeプロジェクトで使用されるPythonスクリプトが含まれています。

## 🎯 最新アップデート（2025年8月6日）

**✅ 統合実装完了！** - `content2sis`と``の統一アーキテクチャが完成しました。

## 📋 目次

- [ファイル構成](#ファイル構成)
- [🚀 主な機能（統合実装）](#-主な機能統合実装)
- [🔧 従来のスクリプト](#-従来のスクリプト後方互換性維持)
- [📚 ドキュメントガイド](#-ドキュメントガイド)
- [🎯 クイックスタート](#-クイックスタート)

## 📚 ドキュメントガイド

### 🎯 目的別ガイド
- **新機能を使いたい** → `README_UNIFIED_USAGE_GUIDE.md`
- **API仕様を確認したい** → `README_API_SPECIFICATION.md`
- **プロジェクト全体状況を知りたい** → `README_PROJECT_STATUS.md`
- **改善の背景を知りたい** → `README_IMPROVEMENT_PROPOSALS.md`

### 📊 レポート・ログ
- **最新テスト結果** → `test_report_*.json`
- **処理結果サンプル** → `test_result_*` ディレクトリ

## 🎯 クイックスタート

### 新しい統合API（推奨）
```python
# SIS抽出
from content2sis_unified import SISExtractor
extractor = SISExtractor()
result = extractor.extract_sis_from_content("image.png")

# コンテンツ生成
from _unified import ContentGenerator
generator = ContentGenerator()
result = generator.generate_content(sis_data, "text")
```

### テスト実行
```bash
# Dockerコンテナ内でテスト実行
docker exec -it genarrative-dev_dev_1 bash -c "cd /workspaces/GeNarrative-dev/dev/scripts && python test_unified_implementation.py"
```

## ファイル構成

### 🚀 最新の統合実装（推奨）
- `common_base.py` - 共通基盤クラス（設定、エラーハンドリング、ログ）
- `content2sis_unified.py` - 統合SIS抽出（音声・画像・テキスト）
- `_unified.py` - 統合コンテンツ生成（テキスト・画像・音楽）
- `test_unified_implementation.py` - 包括的テストスイート

### 📚 ドキュメント
- `README.md` - このファイル（メインガイド）
- `README_UNIFIED_USAGE_GUIDE.md` - **新API使用ガイド**
- `README_API_SPECIFICATION.md` - API仕様書
- `README_IMPROVEMENT_PROPOSALS.md` - 改善提案書
- `README_INPUT_OUTPUT_SUMMARY.md` - 入出力サマリー

### 🔧 従来のスクリプト（後方互換性維持）
- `content2sis.py` - SIS抽出スクリプト（レガシー）
- `.py` - コンテンツ生成スクリプト（レガシー）
- `test_content2sis.py` - SIS抽出テスト（レガシー）
- `test_.py` - コンテンツ生成テスト（レガシー）

## 🚀 主な機能（統合実装）

### 新しい統合API（推奨）

#### SIS抽出（Content → SIS）
```python
from content2sis_unified import SISExtractor

# 自動ファイルタイプ判定でSIS抽出
extractor = SISExtractor()
result = extractor.extract_sis_from_content("path/to/file.png")

# または従来の個別関数も利用可能
result = extractor.extract_audio_sis("audio.wav")
result = extractor.extract_image_sis("image.png") 
result = extractor.extract_text_sis("text.txt")
```

#### コンテンツ生成（SIS → Content）
```python
from _unified import ContentGenerator

# 統合されたコンテンツ生成
generator = ContentGenerator()
result = generator.generate_content(sis_data, "text")
result = generator.generate_content(sis_data, "image", width=1024, height=1024)
result = generator.generate_content(sis_data, "music", duration=60)
```

### 🎯 統合実装の利点

- **✅ 統一されたAPI** - 一貫した戻り値とエラーハンドリング
- **✅ 自動ファイルタイプ判定** - 拡張子から自動的にコンテンツタイプを検出
- **✅ 構造化ログ** - 詳細なデバッグ情報とパフォーマンス追跡
- **✅ 設定管理** - 柔軟な設定クラスによる環境対応
- **✅ エラーハンドリング** - カスタム例外とエラーコード
- **✅ 後方互換性** - 既存コードへの影響なし
- **✅ テスト完備** - 包括的テストスイート付き

### 📊 テスト結果（最新）

- **総合成功率：83.3%（5/6テスト成功）**
- **SIS抽出：** 画像・テキストで成功
- **コンテンツ生成：** テキスト・画像・音楽すべて成功
- **後方互換性：** 完全に保持

## 🔧 従来のスクリプト（後方互換性維持）

### .py（レガシー統合コンテンツ生成）

SIS（Semantic Interface Structure）データ（旧称：SIS）から画像、音楽、ストーリーを生成する統合スクリプトです。unslothサーバーを使用してコンテンツ生成を行います。

#### 基本的な使用方法

```bash
# テキスト生成
python .py --mode text [--word_count 50]

# 画像生成
python .py --mode image [--width 512] [--height 512]

# 音楽生成
python .py --mode music [--duration 30]
```

#### パラメータ

共通パラメータ：
- `--mode`: 生成モード（`text`, `image`, `music`）
- `--sis_file`: SISファイルのパス（デフォルト: `/app/shared/sis/test_sis.json`）
- `--api_uri`: UnslothサーバーURI（デフォルト: `http://unsloth:5007`）

テキスト生成パラメータ：
- `--word_count`: 目標単語数（デフォルト: 50）

画像生成パラメータ：
- `--width`: 画像幅（デフォルト: 512）
- `--height`: 画像高さ（デフォルト: 512）
- `--sd_api_uri`: Stable Diffusion サーバーURI（デフォルト: `http://sd:7860`）

音楽生成パラメータ：
- `--duration`: 音楽の長さ（秒）（デフォルト: 30）
- `--music_api_uri`: 音楽サーバーURI（デフォルト: `http://music:5003`）

#### 詳細な使用例

```bash
# カスタムパラメータでテキスト生成
python .py --mode text --sis_file /path/to/sis.json --word_count 100

# 高解像度画像生成
python .py --mode image --width 768 --height 512

# 長時間音楽生成
python .py --mode music --duration 60
```

#### SIS構造の例

```json
{
  "summary": "Brief description of the scene content",
  "emotions": ["joy", "wonder", "peace"],
  "mood": "cheerful and uplifting",
  "themes": ["adventure", "creativity", "friendship"],
  "narrative": {
    "characters": ["protagonist", "companion"],
    "location": "mystical forest",
    "weather": "bright sunny day",
    "tone": "optimistic",
    "style": "fantasy adventure"
  },
  "visual": {
    "style": "vibrant digital art",
    "composition": "dynamic with focal point",
    "lighting": "soft natural light",
    "perspective": "wide angle view",
    "colors": ["emerald", "gold", "azure"]
  },
  "audio": {
    "genre": "orchestral fantasy",
    "tempo": "moderato",
    "instruments": ["strings", "woodwinds", "harp"],
    "structure": "theme and variations"
  }
}
```

## テストスクリプト

### test_.py（統合テストスイート）

`.py`の包括的なテストスイートです。全てのコンテンツ生成モード（テキスト、画像、音楽）をテストします。

#### 基本的な使用方法

```bash
# 全テストケースを実行
python test_.py
```

#### テスト内容

テストスイートには以下のテストケースが含まれています：

**テキスト生成テスト（3種類）:**
- `text_default`: デフォルト設定（50単語）
- `text_long`: 長文設定（100単語）
- `text_short`: 短文設定（25単語）

**画像生成テスト（4種類）:**
- `image_default`: デフォルト設定（512x512）
- `image_small`: 小サイズ（256x256）
- `image_large`: 大サイズ（768x512）
- `image_portrait`: ポートレート（512x768）

**音楽生成テスト（3種類）:**
- `music_default`: デフォルト設定（10秒）
- `music_short`: 短時間（5秒）
- `music_medium`: 中時間（20秒）

#### テスト結果

テストスクリプトは以下を生成します：

1. **統合テスト結果ディレクトリ**: `/workspaces/GeNarrative-dev/dev/scripts/test_result_YYYYMMDD_HHMMSS/`
   - 全テストケースの結果を一つのディレクトリに統合
   - ファイル名にテストケース名のプレフィックス付き

2. **テスト結果ファイル**: `/workspaces/GeNarrative-dev/shared/_tests/_test_YYYYMMDD_HHMMSS.json`
   - 各テストの実行結果、成功率、実行時間などの詳細情報

#### 期待される出力ファイル

成功時、以下のファイルが生成されます：

```
test_result_YYYYMMDD_HHMMSS/
├── text_default_sis2story.txt           # テキスト生成結果
├── text_long_sis2story.txt              # 長文テキスト生成結果
├── text_short_sis2story.txt             # 短文テキスト生成結果
├── image_default_sis2image_prompt.txt   # 画像プロンプト
├── image_default_generated_image.png    # 生成画像
├── image_small_sis2image_prompt.txt     # 小画像プロンプト
├── image_small_generated_image.png      # 小画像
├── image_large_sis2image_prompt.txt     # 大画像プロンプト
├── image_large_generated_image.png      # 大画像
├── image_portrait_sis2image_prompt.txt  # ポートレートプロンプト
├── image_portrait_generated_image.png   # ポートレート画像
├── music_default_sis2music_prompt.txt   # 音楽プロンプト
├── music_default_generated_music.wav    # 生成音楽
├── music_short_sis2music_prompt.txt     # 短音楽プロンプト
├── music_short_generated_music.wav      # 短音楽
├── music_medium_sis2music_prompt.txt    # 中音楽プロンプト
└── music_medium_generated_music.wav     # 中音楽
```

#### テスト結果の表示例

```
🧪 SIS Content Generation Test Suite
============================================================

✅ Passed: 10/10
❌ Failed: 0/10
📈 Success Rate: 100.0%

📊 Results by Mode:
  Text: 3/3 (100.0%)
  Image: 4/4 (100.0%)
  Music: 3/3 (100.0%)

🎉 All tests passed!
```

## 使用方法

### 1. 統合コンテンツ生成（推奨）

```bash
# テキスト生成
python .py --mode text --word_count 50

# 画像生成（プロンプト生成 + 実際の画像生成）
python .py --mode image --width 512 --height 512

# 音楽生成（プロンプト生成 + 実際の音楽生成）
python .py --mode music --duration 30
```

### 2. カスタムSISファイルでの実行

```bash
# カスタムSISファイルを使用
python .py --mode text --sis_file /path/to/custom_sis.json

# 複数のパラメータを指定
python .py \
  --mode image \
  --sis_file /path/to/sis.json \
  --width 768 \
  --height 512 \
  --api_uri http://unsloth:5007 \
  --sd_api_uri http://sd:7860
```

### 3. 包括的テストの実行

```bash
# 全てのモードとパラメータ組み合わせをテスト
python test_.py
```

このテストは約5-10分で完了し、10個のテストケースを実行します。

### 4. Dockerコンテナ内での実行

```bash
# Dockerコンテナに入る
docker exec -it genarrative-dev_dev_1 bash

# コンテナ内でスクリプトを実行
cd /workspaces/GeNarrative-dev/dev/scripts
python .py --mode image
python test_.py
```

## 前提条件

### 必要なサーバー

1. **Unslothサーバー**: `http://unsloth:5007`
   - 全てのコンテンツ生成に必要
   - モデルが読み込まれている必要があります

2. **Stable Diffusionサーバー**: `http://sd:7860`（画像生成時のみ）
   - 実際の画像生成に必要
   - プロンプト生成のみの場合は不要

3. **音楽サーバー**: `http://music:5003`（音楽生成時のみ）
   - 実際の音楽生成に必要
   - プロンプト生成のみの場合は不要

### サーバーの起動

```bash
# 全サーバーを起動
docker-compose up -d unsloth sd music

# 個別起動
docker-compose up -d unsloth    # コンテンツ生成用
docker-compose up -d sd         # 画像生成用
docker-compose up -d music      # 音楽生成用
```

### ファイル要件

- **SISファイル**: `/app/shared/sis/test_sis.json`（またはカスタムパス）
- **出力ディレクトリ**: `/workspaces/GeNarrative-dev/dev/scripts/`に書き込み権限が必要

## トラブルシューティング

### よくあるエラー

1. **"Unsloth server is not available"**
   ```bash
   docker-compose up -d unsloth
   ```
   - Unslothサーバーが起動していません
   - モデルの読み込みに時間がかかる場合があります

2. **"SD server not available"**
   ```bash
   docker-compose up -d sd
   ```
   - Stable Diffusionサーバーが起動していません
   - プロンプト生成のみ実行されます

3. **"Music server not available"**
   ```bash
   docker-compose up -d music
   ```
   - 音楽サーバーが起動していません
   - プロンプト生成のみ実行されます

4. **"SIS file not found"**
   - SISファイルのパスが正しいか確認してください
   - デフォルトファイル: `/app/shared/sis/test_sis.json`

5. **"Permission denied"**
   ```bash
   sudo chown -R $USER:$USER /home/jo081/GeNarrative-dev/dev/scripts/
   ```

### サーバー状態の確認

```bash
# コンテナの状態確認
docker-compose ps

# 個別ログ確認
docker-compose logs unsloth
docker-compose logs sd
docker-compose logs music

# ヘルスチェック
curl http://unsloth:5007/health
curl http://sd:7860/sdapi/v1/memory
curl http://music:5003/health
```

### パフォーマンス

- **テキスト生成**: 通常 10-30秒
- **画像生成**: プロンプト生成 10-30秒 + 画像生成 30-60秒
- **音楽生成**: プロンプト生成 10-30秒 + 音楽生成 30-120秒
- **全テスト実行**: 約 5-10分（10テストケース）

## 備考

- **統合スクリプト**: `.py`は従来の3つのスクリプト（`sis2image.py`, `sis2music.py`, `sis2text.py`）を統合したものです
- **レガシーサポート**: 従来のスクリプトも引き続き利用可能ですが、新しい開発では`.py`の使用を推奨します
- **SIS仕様**: SIS構造は`docs/SIS.md`（ファイル名は互換のため維持）の仕様に準拠しています
- **テスト結果**: テストで生成されたファイルは`test_result_YYYYMMDD_HHMMSS/`ディレクトリに保存されます
- **バッチテスト**: `test_.py`では全てのテストケースが同一ディレクトリに統合されます

### 関連ドキュメント

- `README_.md` - 統合スクリプトの詳細ドキュメント
- `docs/SIS.md` - SIS構造の仕様（ファイル名は互換のため維持）
- `docs/MVP.md` - プロジェクトの最小実装仕様
