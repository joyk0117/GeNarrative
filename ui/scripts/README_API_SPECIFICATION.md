# API仕様書: GeNarrative統合実装

## 概要
このドキュメントは統合実装（`content2sis_unified.py`と`_unified.py`）および従来の`content2sis.py`と`.py`の関数の入出力仕様を整理したものです。

## 🚀 統合実装API（推奨）

### Content2SIS Unified (content2sis_unified.py)

#### SISExtractor クラス

##### 1. extract_sis_from_content()
ファイルタイプを自動判定してSISを抽出する統合メソッド

**入力パラメータ:**
```python
content_path: str                    # コンテンツファイルパス
content_type: str = None             # 'audio'|'image'|'text'|None（自動判定）
config: APIConfig = None             # API設定オブジェクト
```

**戻り値:**
```python
ProcessingResult = {
    'success': bool,                 # 成功/失敗フラグ
    'data': Dict | None,             # SIS構造データ
    'error': str | None,             # エラーメッセージ
    'error_code': str | None,        # エラーコード
    'metadata': {                    # メタデータ
        'processing_time': float,    # 処理時間（秒）
        'timestamp': str,            # 処理時刻（ISO形式）
        'function_name': str,        # 呼び出し関数名
        'content_type': str          # 検出されたコンテンツタイプ
    },
    'debug_info': {                  # デバッグ情報
        'raw_response': str,         # API生レスポンス
        'api_status': Dict           # API状態情報
    }
}
```

##### 2. 個別抽出メソッド（後方互換性）
```python
extract_audio_sis(audio_path: str, config: APIConfig = None) -> ProcessingResult
extract_image_sis(image_path: str, config: APIConfig = None) -> ProcessingResult
extract_text_sis(text_path: str, config: APIConfig = None) -> ProcessingResult
```

### SIS2Content Unified (_unified.py)

#### ContentGenerator クラス

##### 1. generate_content()
SISデータから指定タイプのコンテンツを生成する統合メソッド

**入力パラメータ:**
```python
sis_data: Dict[str, Any]            # SIS構造データ
content_type: str                   # 'text'|'image'|'music'
config: ProcessingConfig = None     # 処理設定オブジェクト
**kwargs                            # 追加パラメータ
```

**戻り値:**
```python
ProcessingResult = {
    'success': bool,                # 成功/失敗フラグ
    'data': {                       # 生成結果データ
        'content': str,             # 生成されたコンテンツ
        'output_path': str,         # 保存先パス
        'content_type': str,        # コンテンツタイプ
        'additional_result': Dict   # 追加生成結果（画像・音楽時）
    },
    'error': str | None,            # エラーメッセージ
    'error_code': str | None,       # エラーコード
    'metadata': {                   # メタデータ
        'processing_time': float,   # 処理時間（秒）
        'timestamp': str,           # 処理時刻
        'function_name': str        # 呼び出し関数名
    }
}
```

### 設定クラス

#### APIConfig
```python
@dataclass
class APIConfig:
    unsloth_uri: str = "http://unsloth:5006"
    sd_uri: str = "http://sd:7860"
    music_uri: str = "http://music:5003"
    model_name: str = "unsloth/gemma-3n-E4B-it"
    timeout: int = 300
```

#### ProcessingConfig  
```python
@dataclass
class ProcessingConfig:
    output_dir: str = "/workspaces/GeNarrative-dev/dev/scripts"
    save_debug_info: bool = False
    auto_save_sis: bool = True
    use_timestamp: bool = True
    image_width: int = 1024
    image_height: int = 768
    music_duration: int = 30
    text_word_count: int = 50
```

### カスタム例外

```python
class GeNarrativeError(Exception): pass
class ServerConnectionError(GeNarrativeError): pass
class ModelNotLoadedError(GeNarrativeError): pass
class ContentTypeError(GeNarrativeError): pass
class FileNotFoundError(GeNarrativeError): pass
class ValidationError(GeNarrativeError): pass
```

---

## 📚 従来のAPI（後方互換性維持）

### Content2SIS Functions (content2sis.py)

### 1. audio2SIS()
音声ファイルからSIS (Semantic Interface Structure; 旧称SIS)を抽出

**入力パラメータ:**
```python
audio_path: str = "/app/shared/music_0264b049.wav"
api_uri: str = "http://unsloth:5007"
model_name: str = "unsloth/gemma-3n-E4B-it"
```

**戻り値:**
```python
Dict[str, Any] = {
    'success': bool,              # 成功/失敗フラグ
    'sis_data': Dict | None,      # SIS構造データ
    'extraction_time': str | None, # 抽出時刻 (ISO format)
    'error': str | None,          # エラーメッセージ
    'raw_response': str | None    # API生レスポンス（デバッグ用）
}
```

### 1.1. speech2text()
音声ファイルからテキストを抽出（音声認識・要約）

**入力パラメータ:**
```python
audio_path: str                   # 音声ファイルのパス
api_uri: str = "http://unsloth:5007"  # UnslothサーバーのURI
model_name: str = "unsloth/gemma-3n-E4B-it"  # 使用するモデル名
```

**戻り値:**
```python
Dict[str, Any] = {
    'success': bool,                 # 成功/失敗フラグ
    'extracted_text': str | None,    # 抽出されたテキスト
    'audio_file': str,               # 処理した音声ファイルパス
    'file_size': int,                # ファイルサイズ（バイト）
    'extraction_time': str,          # 抽出時刻 (ISO format)
    'prompt_used': str,              # 使用されたプロンプト ("What is this audio about?")
    'error': str | None              # エラーメッセージ
}
```

**機能:**
- 音声ファイル (MP3, WAV, M4A, FLAC) をアップロード
- Unsloth multimodal APIで音声内容を分析
- "What is this audio about?" プロンプトで要約テキストを生成
- 音声の内容、話者の発言、音楽の説明などを自然言語で出力

**使用例:**
```python
from content2sis_unified import speech2text

# 基本的な使用方法
result = speech2text("/path/to/audio.mp3")
if result['success']:
    print(f"音声内容: {result['extracted_text']}")
else:
    print(f"エラー: {result['error']}")

# カスタムサーバーでの使用
result = speech2text(
    "/path/to/audio.wav",
    api_uri="http://localhost:5007"
)
```

**SIS構造データ (`sis_data`):**
```python
{
    "summary": str,                    # 音声コンテンツの簡潔な説明
    "emotions": List[str],             # 感情リスト
    "mood": str,                       # 全体的なムード
    "themes": List[str],               # テーマリスト
    "narrative": {
        "characters": List[str],       # 含意されるキャラクター
        "location": str,               # 設定・環境
        "weather": str,                # 天候・大気条件
        "tone": str,                   # ナラティブトーン
        "style": str                   # ナラティブスタイル
    },
    "visual": {
        "style": str,                  # 視覚スタイル
        "composition": str,            # シーン構成
        "lighting": str,               # 照明ムード
        "perspective": str,            # 視点
        "colors": List[str]            # 色彩リスト
    },
    "audio": {
        "genre": str,                  # 音楽ジャンル
        "tempo": str,                  # テンポ・リズム
        "instruments": List[str],      # 楽器リスト
        "structure": str,              # 音楽構造
        "dynamics": str,               # 音量・強度変化
        "harmony": str,                # ハーモニー内容
        "melody": str                  # メロディー特性
    },
    "extraction_time": str             # 抽出時刻 (ISO format)
}
```

### 2. image2SIS()
画像ファイルからSISを抽出

**入力パラメータ:**
```python
image_path: str = "/app/shared/image/story_image_20250726_094413.png"
api_uri: str = "http://unsloth:5007"
model_name: str = "unsloth/gemma-3n-E4B-it"
```

**戻り値:**
```python
Dict[str, Any] = {
    'success': bool,              # 成功/失敗フラグ
    'sis_data': Dict | None,      # SIS構造データ (同じ構造)
    'extraction_time': str | None, # 抽出時刻
    'error': str | None,          # エラーメッセージ
    'raw_response': str | None    # API生レスポンス
}
```

### 3. text2SIS()
テキストファイルからSISを抽出

**入力パラメータ:**
```python
text_path: str = "/app/shared/text/text_20250804_230132.txt"
api_uri: str = "http://unsloth:5007"
model_name: str = "unsloth/gemma-3n-E4B-it"
```

**戻り値:**
```python
Dict[str, Any] = {
    'success': bool,              # 成功/失敗フラグ
    'sis_data': Dict | None,      # SIS構造データ (同じ構造)
    'extraction_time': str | None, # 抽出時刻
    'error': str | None,          # エラーメッセージ
    'raw_response': str | None    # API生レスポンス
}
```

### 4. ユーティリティ関数

#### save_sis_to_file()
```python
save_sis_to_file(sis_data: Dict[str, Any], output_path: str) -> bool
```

#### json2jsonl()
```python
json2jsonl(json_file_path: str, jsonl_file_path: str = None) -> bool
```

### 5. 統合エントリーポイント関数

#### extract_sis_from_content()
```python
extract_sis_from_content(
    content_path: str,
    content_type: str = None,
    api_config: Optional[APIConfig] = None,
    processing_config: Optional[ProcessingConfig] = None,
    logger: Optional[StructuredLogger] = None
) -> Dict[str, Any]
```

#### speech2text()
```python
speech2text(
    audio_path: str,
    api_uri: str = "http://unsloth:5007",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]
```

---

## SIS2Content Functions (.py)

### 1. generate_content_with_unsloth()
SISデータからコンテンツ（テキスト/画像/音楽）を生成

**入力パラメータ:**
```python
sis_data: Dict[str, Any]         # SIS構造データ
api_uri: str                     # Unsloth API URI
content_type: str                # "image" | "music" | "text"
**kwargs: Dict                   # 追加パラメータ
```

**kwargs詳細:**
```python
# 画像生成用
width: int = 1024
height: int = 768
sd_api_uri: str = "http://sd:7860"

# 音楽生成用
duration: int = 30
music_api_uri: str = "http://music:5003"

# テキスト生成用
word_count: int = 50

# 共通
custom_timestamp: str = None      # カスタムタイムスタンプ
test_case_name: str = ""         # テストケース名
```

**戻り値:**
```python
Dict[str, Any] = {
    'success': bool,                    # 成功/失敗フラグ
    'generated_text': str,              # 生成されたプロンプト/テキスト
    'output_path': str,                 # 保存先パス
    'generation_time': float,           # 生成時間（秒）
    'content_type': str,                # コンテンツタイプ
    'image_result': Dict | None,        # 画像生成結果（画像モード時）
    'music_result': Dict | None,        # 音楽生成結果（音楽モード時）
    'error': str | None                 # エラーメッセージ
}
```

### 2. 個別コンテンツ生成関数

#### generate_image_with_sd()
Stable Diffusionで実際の画像を生成

**入力パラメータ:**
```python
image_prompt: str                # 画像生成プロンプト
sd_api_uri: str                  # Stable Diffusion API URI
width: int = 1024                # 画像幅
height: int = 768                # 画像高さ
```

**戻り値:**
```python
Dict[str, Any] = {
    'success': bool,                # 成功/失敗フラグ
    'image_path': str,              # 画像ファイルパス
    'image_filename': str,          # 画像ファイル名
    'image_size': int,              # ファイルサイズ（バイト）
    'generation_time': float,       # 生成時間（秒）
    'error': str | None             # エラーメッセージ
}
```

#### generate_music_with_server()
MusicGenで実際の音楽を生成

**入力パラメータ:**
```python
music_prompt: str                # 音楽生成プロンプト
music_api_uri: str               # Music API URI
duration: int = 30               # 音楽の長さ（秒）
```

**戻り値:**
```python
Dict[str, Any] = {
    'success': bool,                # 成功/失敗フラグ
    'music_path': str,              # 音楽ファイルパス
    'music_filename': str,          # 音楽ファイル名
    'music_size': int,              # ファイルサイズ（バイト）
    'sample_rate': int,             # サンプルレート
    'generation_time': float,       # 生成時間（秒）
    'error': str | None             # エラーメッセージ
}
```

### 3. プロンプト作成関数

#### create_image_prompt()
```python
create_image_prompt(sis_data: Dict[str, Any], width: int, height: int) -> str
```

#### create_music_prompt()
```python
create_music_prompt(sis_data: Dict[str, Any], duration: int) -> str
```

#### create_text_prompt()
```python
create_text_prompt(sis_data: Dict[str, Any], word_count: int) -> str
```

### 4. サーバーチェック関数

#### check_unsloth_server()
```python
check_unsloth_server(api_uri: str) -> Tuple[bool, bool]
# Returns: (server_ok, model_loaded)
```

#### check_sd_server()
```python
check_sd_server(sd_api_uri: str) -> bool
```

#### check_music_server()
```python
check_music_server(music_api_uri: str) -> bool
```

#### load_sis_data()
```python
load_sis_data(sis_file_path: str) -> Dict[str, Any] | None
```

---

## データフロー

### 1. Content → SIS
```
Audio/Image/Text File → content2sis.py → SIS JSON Structure (concept)
```

### 2. SIS → Content
```
SIS JSON Structure → .py → Generated Content (Text/Image/Music)
```

### 3. 完全なパイプライン
```
Input Content → SIS → Output Content
     ↓           ↓         ↓
  原始データ → 構造化データ → 生成コンテンツ
```

---

## エラーハンドリング

### 共通エラータイプ
- `FileNotFoundError`: ファイルが見つからない
- `ConnectionError`: サーバー接続エラー
- `TimeoutError`: タイムアウトエラー
- `ValidationError`: 入力データ検証エラー
- `JSONDecodeError`: JSON解析エラー

### エラーレスポンス形式
```python
{
    'success': False,
    'error': "エラーの詳細説明",
    'sis_data': None,        # content2sis.py（キー名は互換のため維持）
    'generated_text': None,  # .py
    'raw_response': str      # デバッグ用（オプション）
}
```

---

## 🚀 統合実装の使用例

### Content2SIS統合使用例（コードはcontent2sisのまま）
```python
from content2sis_unified import SISExtractor
from common_base import APIConfig

# 基本的な使用（自動ファイルタイプ判定）
extractor = SISExtractor()
result = extractor.extract_sis_from_content("/path/to/image.png")

if result.success:
    sis_data = result.data
    print(f"SIS抽出成功: {sis_data['summary']}")
    print(f"処理時間: {result.metadata['processing_time']:.2f}秒")
else:
    print(f"エラー [{result.error_code}]: {result.error}")

# カスタム設定での使用
config = APIConfig(
    unsloth_uri="http://custom-unsloth:5007",
    timeout=600
)
result = extractor.extract_sis_from_content(
    "/path/to/audio.wav",
    content_type="audio",  # 明示的指定
    config=config
)
```

### SIS2Content統合使用例（コードはのまま）
```python
from _unified import ContentGenerator
from common_base import ProcessingConfig

# 基本的なテキスト生成
generator = ContentGenerator()
result = generator.generate_content(sis_data, "text")

if result.success:
    print(f"生成されたテキスト: {result.data['content']}")
    print(f"保存先: {result.data['output_path']}")
else:
    print(f"エラー: {result.error}")

# カスタム設定での画像生成
config = ProcessingConfig(
    output_dir="/custom/output/dir",
    image_width=1024,
    image_height=768,
    save_debug_info=True
)
result = generator.generate_content(
    sis_data, 
    "image",
    config=config
)

# 生成された画像の確認
if result.success and result.data.get('additional_result'):
    image_info = result.data['additional_result']
    print(f"画像ファイル: {image_info['image_path']}")
    print(f"ファイルサイズ: {image_info['image_size']} bytes")
```

### バッチ処理の例
```python
from content2sis_unified import SISExtractor
from _unified import ContentGenerator

# 複数ファイルの一括SIS抽出
extractor = SISExtractor()
file_paths = ["/path/to/image1.png", "/path/to/text1.txt", "/path/to/audio1.wav"]

sis_results = []
for file_path in file_paths:
    result = extractor.extract_sis_from_content(file_path)
    if result.success:
        sis_results.append(result.data)
        print(f"✅ {file_path}: 成功")
    else:
        print(f"❌ {file_path}: {result.error}")

# SIS結果から複数コンテンツ生成
generator = ContentGenerator()
for i, sis_data in enumerate(sis_results):
    for content_type in ["text", "image", "music"]:
        result = generator.generate_content(sis_data, content_type)
        if result.success:
            print(f"✅ SIS{i+1} → {content_type}: {result.data['output_path']}")
```

---

## 📚 従来のAPI使用例（後方互換性）

### Content2SIS従来使用例
```python
# 画像からSIS抽出
result = image2SIS("/path/to/image.png")
if result['success']:
    sis_data = result['sis_data']
    save_sis_to_file(sis_data, "/path/to/output.json")

# 音声からテキスト抽出
result = speech2text("/path/to/audio.mp3")
if result['success']:
    text_content = result['extracted_text']
    print(f"音声内容: {text_content}")
```

### SIS2Content従来使用例
```python
# SISから画像生成
sis_data = load_sis_data("/path/to/sis.json")
result = generate_content_with_unsloth(
    sis_data, 
    "http://unsloth:5007", 
    "image",
    width=1024,
    height=1024
)
if result['success']:
    print(f"Generated content saved to: {result['output_path']}")
```

---

## 🎯 移行ガイド

### 従来APIから統合APIへの移行

#### Before（従来API）
```python
# 従来のコード
result = image2SIS("/path/to/image.png")
if result['success']:
    sis_data = result['sis_data']

result = generate_content_with_unsloth(sis_data, api_uri, "text")
if result['success']:
    text = result['generated_text']
```

#### After（統合API）
```python
# 新しいコード
from content2sis_unified import SISExtractor
from _unified import ContentGenerator

extractor = SISExtractor()
result = extractor.extract_sis_from_content("/path/to/image.png")
if result.success:
    sis_data = result.data

generator = ContentGenerator()
result = generator.generate_content(sis_data, "text")
if result.success:
    text = result.data['content']
```

詳細な移行ガイドは `README_UNIFIED_USAGE_GUIDE.md` を参照してください。
