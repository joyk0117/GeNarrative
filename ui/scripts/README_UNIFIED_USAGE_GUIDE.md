# 統一実装使用ガイド

## 概要

`content2sis.py` と `.py` の統一実装が完了しました。
このガイドでは、新しい統一されたAPIの使用方法と既存コ#### 後方互換性関数の使用
```python
from content2sis_unified import audio2SIS, image2SIS, text2SIS, speech2text

# 従来のAPI使用方法
sis_result = audio2SIS("/path/to/audio.wav")
sis_result = image2SIS("/path/to/image.png")
sis_result = text2SIS("/path/to/text.txt")

# 新機能: 音声からテキスト抽出
text_result = speech2text("/path/to/audio.mp3")
if text_result['success']:
    print(f"音声内容: {text_result['extracted_text']}")
```## 🆕 新しい統一API

### 1. Content2SIS (統一版)

#### 新しい統一エントリーポイント
```python
from content2sis_unified import extract_sis_from_content
from common_base import APIConfig, ProcessingConfig

# 基本的な使用方法（ファイルタイプ自動判定）
result = extract_sis_from_content("/path/to/content/file.jpg")

# 設定クラスを使用した高度な使用方法
api_config = APIConfig(
    unsloth_uri="http://localhost:5007",
    model_name="custom-model"
)

processing_config = ProcessingConfig(
    save_debug_info=True,
    auto_save_sis=True
)

result = extract_sis_from_content(
    "/path/to/content/file.wav",
    content_type="audio",  # 明示的に指定
    api_config=api_config,
    processing_config=processing_config
)

# 結果の処理
if result['success']:
    sis_data = result['sis_data']
    print(f"Summary: {sis_data['summary']}")
    print(f"Emotions: {sis_data['emotions']}")
else:
    print(f"Error: {result['error']}")
    print(f"Error Code: {result['metadata']['error_code']}")
```

### 2. SIS2Content (統一版)

#### 新しい統一エントリーポイント
```python
from _unified import generate_content
from common_base import APIConfig, GenerationConfig

# SIS データの準備（用語上）
sis_data = {
    "summary": "A peaceful mountain scene",
    "emotions": ["calm", "serene"],
    # ... 他のSIS要素
}

# 基本的な使用方法
result = generate_content(sis_data, "image")

# 設定クラスを使用した高度な使用方法
api_config = APIConfig(
    unsloth_uri="http://localhost:5007",
    sd_uri="http://localhost:7860"
)

generation_config = GenerationConfig(
    image_width=1024,
    image_height=1024,
    temperature=0.8
)

result = generate_content(
    sis_data,
    "image",
    api_config=api_config,
    generation_config=generation_config,
    test_case_name="my_test"
)

# 結果の処理
if result['success']:
    print(f"Generated: {result['output_path']}")
    print(f"Processing time: {result['metadata']['processing_time']:.2f}s")
    
    # 画像が実際に生成された場合
    if result.get('image_result', {}).get('success'):
        print(f"Image saved: {result['image_result']['image_path']}")
else:
    print(f"Error: {result['error']}")
```

## 🔄 既存コードからの移行

### Phase 1: 後方互換性を利用した段階移行

既存の関数名はそのまま使用可能です：

```python
# 既存コード（そのまま動作）
from content2sis_unified import audio2SIS, image2SIS, text2SIS
from _unified import generate_content_with_unsloth

# 従来通りの使用
sis_result = audio2SIS("/path/to/audio.wav")
content_result = generate_content_with_unsloth(
    sis_result['sis_data'], 
    "http://unsloth:5007", 
    "text"
)
```

### Phase 2: 統一APIへの移行

```python
# 移行後のコード
from content2sis_unified import extract_sis_from_content
from _unified import generate_content

# より一貫性のあるAPI
sis_result = extract_sis_from_content("/path/to/audio.wav")
content_result = generate_content(sis_result['sis_data'], "text")
```

## 📊 統一された戻り値構造

### 成功時のレスポンス
```python
{
    'success': True,
    'sis_data': {...},           # Content2SIS の場合
    'generated_text': "...",     # SIS2Content の場合
    'output_path': "/path/...",  # SIS2Content の場合
    'metadata': {
        'function_name': 'extract_sis_from_content',
        'processing_time': 45.2,
        'timestamp': '2025-08-06T10:30:00',
        'content_type': 'audio'
    },
    'error': None
}
```

### 失敗時のレスポンス
```python
{
    'success': False,
    'sis_data': None,
    'error': "File not found: /path/to/file.wav",
    'metadata': {
        'function_name': 'extract_sis_from_content',
        'processing_time': 0.1,
        'timestamp': '2025-08-06T10:30:00',
        'error_code': 'FILE_NOT_FOUND'
    },
    'debug_info': {             # save_debug_info=True の場合のみ
        'file_path': '/path/to/file.wav'
    }
}
```

## 🔧 設定クラスの活用

### APIConfig - API接続設定
```python
from common_base import APIConfig

api_config = APIConfig(
    unsloth_uri="http://unsloth:5007",    # Unsloth サーバー
    sd_uri="http://sd:7860",              # Stable Diffusion サーバー
    music_uri="http://music:5003",        # Music サーバー
    model_name="unsloth/gemma-3n-E4B-it", # 使用モデル
    timeout=300                           # タイムアウト(秒)
)
```

### GenerationConfig - 生成設定
```python
from common_base import GenerationConfig

generation_config = GenerationConfig(
    image_width=1024,        # 画像幅
    image_height=1024,       # 画像高さ
    music_duration=30,       # 音楽長さ(秒)
    text_word_count=100,     # テキスト単語数
    temperature=0.7,         # 生成温度
    max_tokens=1000          # 最大トークン数
)
```

### ProcessingConfig - 処理設定
```python
from common_base import ProcessingConfig

processing_config = ProcessingConfig(
    output_dir="/path/to/output",    # 出力ディレクトリ
    save_debug_info=False,           # デバッグ情報保存
    auto_save_sis=True,              # SIS自動保存
    use_timestamp=True,              # タイムスタンプ使用
    cache_enabled=True,              # キャッシュ有効化
    cache_dir="/tmp/sis_cache"       # キャッシュディレクトリ
)
```

## 🛡️ エラーハンドリング

### カスタム例外の活用
```python
from common_base import (
    GeNarrativeError, FileProcessingError, 
    ServerConnectionError, ModelNotLoadedError,
    ContentTypeError, ValidationError
)

try:
    result = extract_sis_from_content("/path/to/file.txt")
    
except FileProcessingError as e:
    print(f"File error: {e}")
    print(f"Error code: {e.error_code}")
    print(f"Details: {e.details}")
    
except ServerConnectionError as e:
    print(f"Server connection failed: {e.server_name} at {e.uri}")
    
except ModelNotLoadedError as e:
    print(f"Model not loaded: {e.model_name}")
    
except ContentTypeError as e:
    print(f"Unsupported type: {e.content_type}")
    print(f"Supported types: {e.supported_types}")
    
except GeNarrativeError as e:
    print(f"GeNarrative error: {e}")
    print(f"Error code: {e.error_code}")
    
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 統一エラーハンドリング関数
```python
from common_base import handle_processing_error

try:
    # 処理実行
    result = some_processing_function()
    
except Exception as e:
    error_response = handle_processing_error(e, {
        'function': 'my_function',
        'input_file': '/path/to/file'
    })
    
    print(f"Error handled: {error_response}")
```

## 📈 ロギングシステム

### 構造化ログの使用
```python
from common_base import StructuredLogger

logger = StructuredLogger("MyApplication")

# 関数開始ログ
logger.log_function_start("process_content", {
    'file_path': '/path/to/file.wav',
    'content_type': 'audio'
})

# 関数終了ログ
logger.log_function_end("process_content", True, 45.2)

# エラーログ
logger.log_error("process_content", "File processing failed", {
    'file_path': '/path/to/file.wav',
    'error_type': 'FileNotFoundError'
})
```

## 🧪 テストとデバッグ

### テストスクリプトの実行
```bash
# 統一実装のテスト
python test_unified_implementation.py

# 個別機能のテスト
python -c "
from content2sis_unified import extract_sis_from_content
result = extract_sis_from_content('/path/to/test/file.jpg')
print(f'Success: {result[\"success\"]}')
"
```

### デバッグ情報の有効化
```python
from common_base import ProcessingConfig

# デバッグ情報を有効にした設定
debug_config = ProcessingConfig(
    save_debug_info=True,
    output_dir="/path/to/debug/output"
)

result = extract_sis_from_content(
    "/path/to/file.wav",
    processing_config=debug_config
)

# デバッグ情報の確認
if 'debug_info' in result:
    print(f"Debug info: {result['debug_info']}")
```

## 🚀 バッチ処理の例

### 複数ファイルの一括処理
```python
import os
from content2sis_unified import extract_sis_from_content
from _unified import generate_content
from common_base import APIConfig, GenerationConfig

def batch_process_directory(input_dir: str, output_dir: str):
    """ディレクトリ内のファイルを一括処理"""
    
    # 設定
    api_config = APIConfig()
    generation_config = GenerationConfig()
    
    results = []
    
    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)
        
        if not os.path.isfile(file_path):
            continue
        
        print(f"Processing: {filename}")
        
        # SIS抽出
        sis_result = extract_sis_from_content(
            file_path,
            api_config=api_config
        )
        
        if not sis_result['success']:
            print(f"SIS extraction failed: {sis_result['error']}")
            continue
        
        # コンテンツ生成（テキスト、画像、音楽）
        for content_type in ['text', 'image', 'music']:
            content_result = generate_content(
                sis_result['sis_data'],
                content_type,
                api_config=api_config,
                generation_config=generation_config,
                test_case_name=f"{os.path.splitext(filename)[0]}_{content_type}"
            )
            
            results.append({
                'input_file': filename,
                'content_type': content_type,
                'success': content_result['success'],
                'output_path': content_result.get('output_path'),
                'error': content_result.get('error')
            })
    
    return results

# 使用例
results = batch_process_directory("/input/dir", "/output/dir")
success_count = len([r for r in results if r['success']])
print(f"Processed: {success_count}/{len(results)} successful")
```

## 📚 まとめ

### ✅ 統一実装の利点

1. **一貫性**: 両スクリプトで統一されたAPI設計
2. **保守性**: 共通基盤による効率的な保守
3. **拡張性**: 設定クラスによる柔軟な拡張
4. **エラーハンドリング**: 統一されたエラー処理
5. **ログ**: 構造化されたログシステム
6. **後方互換性**: 既存コードを破壊しない移行

### 🎯 推奨移行スケジュール

1. **Week 1**: 新しい統一スクリプトのテスト
2. **Week 2**: 既存コードで後方互換性関数を使用
3. **Week 3**: 段階的に統一APIに移行
4. **Week 4**: 設定クラスとエラーハンドリングの活用

この統一実装により、GeNarrativeパイプラインの保守性と拡張性が大幅に向上し、開発効率が改善されます。
