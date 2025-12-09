# 入出力・戻り値整理まとめ

## content2sis.py と .py の関数仕様統一

### 統一された戻り値形式

#### 成功時の戻り値構造
```python
# Content2SIS系関数 (audio2SIS, image2SIS, text2SIS, speech2text)
{
    'success': True,
    'sis_data': {
        # SIS構造データ
        'summary': str,
        'emotions': List[str],
        'mood': str,
        'themes': List[str],
        'narrative': {...},
        'visual': {...},
        'audio': {...},
        'extraction_time': str  # ISO format
    },
    'extraction_time': str,    # 重複だが互換性のため残す
    'error': None
}

# SIS2Content系関数 (generate_content_with_unsloth)
{
    'success': True,
    'generated_text': str,     # 生成されたプロンプト/コンテンツ
    'output_path': str,        # 保存先ファイルパス
    'generation_time': float,  # 生成時間（秒）
    'content_type': str,       # 'image' | 'music' | 'text'
    'image_result': Dict | None,  # 画像生成結果（該当時のみ）
    'music_result': Dict | None,  # 音楽生成結果（該当時のみ）
    'error': None
}
```

#### 失敗時の戻り値構造
```python
# 共通失敗レスポンス
{
    'success': False,
    'error': str,              # エラーメッセージ
    'sis_data': None,         # content2sis系の場合
    'generated_text': None,   # 系の場合
    'raw_response': str | None # デバッグ用（オプション）
}
```

### 関数の入力パラメータ標準化

#### Content2SIS系関数
```python
def audio2SIS(
    audio_path: str = "/app/shared/music_0264b049.wav",
    api_uri: str = "http://unsloth:5007",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:

def image2SIS(
    image_path: str = "/app/shared/image/story_image_20250726_094413.png",
    api_uri: str = "http://unsloth:5007",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:

def text2SIS(
    text_path: str = "/app/shared/text/text_20250804_230132.txt",
    api_uri: str = "http://unsloth:5007",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:

def speech2text(
    audio_path: str,
    api_uri: str = "http://unsloth:5007",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:
```

#### SIS2Content系関数
```python
def generate_content_with_unsloth(
    sis_data: Dict[str, Any],      # 必須: SIS構造データ
    api_uri: str,                  # 必須: Unsloth API URI
    content_type: str,             # 必須: "image" | "music" | "text"
    **kwargs                       # オプション: 各種設定
) -> Dict[str, Any]:
```

### SIS構造データの標準化

```python
SIS_STRUCTURE = {
    "summary": str,                    # 必須: コンテンツの要約
    "emotions": List[str],             # 必須: 感情のリスト
    "mood": str,                       # 必須: 全体的なムード
    "themes": List[str],               # 必須: テーマのリスト
    "narrative": {                     # 必須: ナラティブ要素
        "characters": List[str],       # キャラクター
        "location": str,               # 場所・設定
        "weather": str,                # 天候
        "tone": str,                   # トーン
        "style": str                   # スタイル
    },
    "visual": {                        # 必須: 視覚要素
        "style": str,                  # アートスタイル
        "composition": str,            # 構図
        "lighting": str,               # 照明
        "perspective": str,            # 視点
        "colors": List[str]            # 色彩
    },
    "audio": {                         # 必須: 音声要素
        "genre": str,                  # ジャンル
        "tempo": str,                  # テンポ
        "instruments": List[str],      # 楽器
        "structure": str,              # 構造
        "dynamics": str,               # ダイナミクス（音楽のみ）
        "harmony": str,                # ハーモニー（音楽のみ）
        "melody": str                  # メロディー（音楽のみ）
    },
    "extraction_time": str             # オプション: 抽出時刻
}
```

### エラーハンドリングの統一

#### エラータイプの分類
```python
ERROR_TYPES = {
    "FILE_NOT_FOUND": "ファイルが見つかりません",
    "UNSUPPORTED_FORMAT": "サポートされていないファイル形式",
    "SERVER_CONNECTION": "サーバーへの接続に失敗",
    "MODEL_NOT_LOADED": "モデルが読み込まれていません",
    "TIMEOUT": "処理がタイムアウトしました",
    "JSON_PARSE_ERROR": "JSONの解析に失敗",
    "VALIDATION_ERROR": "入力データの検証に失敗",
    "UNKNOWN_ERROR": "予期しないエラーが発生"
}
```

#### エラーレスポンス例
```python
# ファイルが見つからない場合
{
    'success': False,
    'error': 'Audio file not found: /path/to/file.wav',
    'sis_data': None
}

# サーバー接続エラー
{
    'success': False,
    'error': 'Cannot connect to Unsloth server at http://unsloth:5007',
    'sis_data': None
}

# タイムアウトエラー
{
    'success': False,
    'error': 'Request timeout (5 minutes)',
    'raw_response': None
}
```

### 使用パターンの推奨

#### 1. 基本的な使用方法
```python
# Content2SIS
result = image2SIS("/path/to/image.png")
if result['success']:
    sis_data = result['sis_data']
    # SIS データを使用（用語上）
else:
    print(f"Error: {result['error']}")

# SIS2Content
result = generate_content_with_unsloth(
    sis_data, 
    "http://unsloth:5007", 
    "image",
    width=1024,
    height=1024
)
if result['success']:
    print(f"Generated: {result['output_path']}")
else:
    print(f"Error: {result['error']}")
```

#### 2. エラーハンドリング付きの使用方法
```python
try:
    result = audio2SIS("/path/to/audio.wav")
    text_result = speech2text("/path/to/audio.mp3")
    if not result['success']:
    logger.error(f"SIS extraction failed: {result['error']}")
        return None
    
    # SIS データの保存
    save_sis_to_file(result['sis_data'], "/path/to/output.json")
    
    # 続けてコンテンツ生成
    content_result = generate_content_with_unsloth(
        result['sis_data'],
        "http://unsloth:5007",
        "text",
        word_count=100
    )
    
    if content_result['success']:
        logger.info(f"Content generated: {content_result['output_path']}")
    else:
        logger.error(f"Content generation failed: {content_result['error']}")

except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

#### 3. バッチ処理の使用方法
```python
def process_multiple_files(file_list, content_type):
    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for i, file_path in enumerate(file_list):
        # Content2SIS
        sis_result = image2SIS(file_path)  # または audio2SIS, text2SIS, speech2text

## 🔊 音声テキスト抽出関数 (speech2text)

### 入力パラメータ
- **audio_path**: 音声ファイルパス (MP3, WAV, M4A, FLAC対応)
- **api_uri**: UnslothサーバーURI (デフォルト: "http://unsloth:5007")
- **model_name**: 使用モデル (デフォルト: "unsloth/gemma-3n-E4B-it")

### 出力データ構造
```python
{
    'success': bool,                 # 成功/失敗フラグ
    'extracted_text': str | None,    # 抽出されたテキスト
    'audio_file': str,               # 処理した音声ファイルパス
    'file_size': int,                # ファイルサイズ（バイト）
    'extraction_time': str,          # 抽出時刻 (ISO format)
    'prompt_used': str,              # 使用プロンプト ("What is this audio about?")
    'error': str | None              # エラーメッセージ
}
```

### 使用例
```python
from content2sis_unified import speech2text

# 音声からテキスト抽出
result = speech2text("/path/to/kennedy_speech.mp3")
if result['success']:
    print(f"音声内容: {result['extracted_text']}")
    # 出力例: "This audio appears to be a quote from President John F. Kennedy's famous speech about the space race..."
```

### 機能特徴
- 🎤 **音声認識**: 複数音声フォーマット対応
- 📝 **自動要約**: "What is this audio about?" プロンプトで内容を要約
- 🔗 **統合API**: 同じUnslothサーバーでSIS抽出と併用可能
- ⚡ **高速処理**: multimodal APIで効率的な音声解析
        if not sis_result['success']:
            continue
        
        # SIS2Content
        content_result = generate_content_with_unsloth(
            sis_result['sis_data'],
            "http://unsloth:5007",
            content_type,
            custom_timestamp=timestamp,
            test_case_name=f"batch_{i:03d}"
        )
        
        results.append({
            'input_file': file_path,
            'sis_success': sis_result['success'],
            'content_success': content_result['success'],
            'output_path': content_result.get('output_path')
        })
    
    return results
```

### 設定の推奨値

#### API URI設定
```python
DEFAULT_CONFIG = {
    'unsloth_api_uri': 'http://unsloth:5007',
    'sd_api_uri': 'http://sd:7860',
    'music_api_uri': 'http://music:5003',
    'model_name': 'unsloth/gemma-3n-E4B-it'
}
```

#### 生成パラメータ
```python
GENERATION_DEFAULTS = {
    'image': {'width': 1024, 'height': 768},
    'music': {'duration': 30},
    'text': {'word_count': 50},
    'timeout': 300  # 5分
}
```

この整理により、両スクリプトの入出力が統一され、保守性と使いやすさが向上します。
