#!/usr/bin/env python3
"""
Unified Content to SIS (Semantic Interface Structure) Extraction Script

統一された実装方針による、各種コンテンツからのSIS抽出機能
- 既存の個別関数（audio2SIS, image2SIS, text2SIS）を維持
- 新しい統合エントリーポイント（extract_sis_from_content）を追加
- 統一されたエラーハンドリングと戻り値構造
- 設定クラスとロギングシステムの統合

Author: Generated from GeNarrative Pipeline
Created: August 6, 2025
Updated: August 6, 2025 - Unified implementation
"""

import os
import json
import base64
import requests
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from functools import lru_cache
from string import Template

# 共通基盤のインポート
from common_base import (
    APIConfig, ProcessingConfig, GenerationConfig,
    ContentProcessor, ProcessingResult, StructuredLogger,
    GeNarrativeError, FileProcessingError, ServerConnectionError, 
    ModelNotLoadedError, ContentTypeError, ValidationError,
    detect_content_type, create_standard_response
)


PROMPT_DIR = Path(__file__).parent / 'prompts'


@lru_cache(maxsize=16)
def _load_prompt_template(filename: str) -> Template:
    """Load and cache prompt templates stored under ui/scripts/prompts."""
    template_path = PROMPT_DIR / filename
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    with open(template_path, 'r', encoding='utf-8') as prompt_file:
        return Template(prompt_file.read())


# ========================================
# SIS抽出プロセッサクラス（用語上。クラス名は互換のためSISExtractor）
# ========================================

class SISExtractor(ContentProcessor):
    """統一されたSIS抽出クラス"""
    
    def __init__(self, 
                 api_config: Optional[APIConfig] = None,
                 processing_config: Optional[ProcessingConfig] = None,
                 logger: Optional[StructuredLogger] = None):
        super().__init__(api_config, processing_config, logger)
    
    def process(self, content_path: str, content_type: str = None, **kwargs) -> ProcessingResult:
        """統合SIS抽出処理（処理内容は同一、用語をSISに統一）"""
        function_name = 'extract_sis_from_content'
        
        try:
            # 処理開始
            self._start_processing(function_name, {
                'content_path': content_path,
                'content_type': content_type
            })
            
            # ファイルパス検証
            self._validate_file_path(content_path)
            
            # コンテンツタイプ判定
            if content_type is None:
                content_type = detect_content_type(content_path)
            
            if content_type == 'unknown':
                raise ContentTypeError(content_type, ['audio', 'image', 'text'])
            
            # 対応する処理を実行
            if content_type == 'audio':
                result = self._process_audio(content_path, **kwargs)
            elif content_type == 'image':
                result = self._process_image(content_path, **kwargs)
            elif content_type == 'text':
                result = self._process_text(content_path, **kwargs)
            else:
                raise ContentTypeError(content_type, ['audio', 'image', 'text'])
            
            # 処理終了
            duration = self._end_processing(function_name, result.success)
            result.metadata['processing_time'] = duration
            
            return result
            
        except Exception as e:
            return self._handle_error(e, function_name, {'content_path': content_path})
    
    def _process_audio(self, audio_path: str, **kwargs) -> ProcessingResult:
        """音声ファイルの処理"""
        # 音声ファイル形式の検証
        supported_formats = ['.wav', '.mp3', '.m4a', '.flac']
        file_ext = os.path.splitext(audio_path)[1].lower()
        if file_ext not in supported_formats:
            raise ValidationError(
                f'Unsupported audio format: {file_ext}. Supported: {supported_formats}',
                error_code='UNSUPPORTED_AUDIO_FORMAT'
            )
        
        # ファイルサイズチェック
        file_size = os.path.getsize(audio_path)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            raise ValidationError(
                f'Audio file too large: {file_size / (1024*1024):.1f}MB. Maximum: 50MB',
                error_code='FILE_TOO_LARGE'
            )
        
        # SIS抽出実行
        sis_data = self._extract_sis_from_audio(audio_path)
        
        return ProcessingResult(
            success=True,
            data={'sis_data': sis_data},
            error=None,
            metadata={
                'content_type': 'audio',
                'file_size': file_size,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def _process_image(self, image_path: str, **kwargs) -> ProcessingResult:
        """画像ファイルの処理（Structured Output を使用、完全なSceneSISスキーマに準拠）"""
        # 画像をbase64エンコード
        image_base64 = self._load_and_encode_image(image_path)
        if not image_base64:
            raise ValidationError(
                'Failed to encode image to base64',
                error_code='IMAGE_ENCODING_FAILED'
            )

        # 完全なSceneSISスキーマを取得
        scene_sis_schema = self._scene_sis_schema()
        sis_prompt = _load_prompt_template('content2sis_scene_from_image.md').substitute()
        system_prompt = _load_prompt_template('content2sis_scene_system.md').substitute()
        # 計測開始
        req_start = time.time()

        # Structured Output 呼び出し
        sis_json, raw_text = self._ollama_chat_structured(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': sis_prompt}
            ],
            schema=scene_sis_schema,
            images=[image_base64]
        )
        req_duration = time.time() - req_start

        # scene_idをアプリケーション側で生成（sis2sis.pyと同様）
        sis_json['scene_id'] = self._generate_scene_id()
        sis_json['sis_type'] = 'scene'

        return ProcessingResult(
            success=True,
            data={'sis_data': sis_json, 'content': raw_text, 'content_format': 'json', 'prompt': sis_prompt},
            error=None,
            metadata={
                'content_type': 'image',
                'image_path': image_path,
                'image_file_size': os.path.getsize(image_path) if os.path.exists(image_path) else None,
                'image_base64_length': len(image_base64),
                'request_duration_sec': round(req_duration, 4),
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def _process_text(self, text_path: str, **kwargs) -> ProcessingResult:
        """テキスト→SIS（Structured Output を使用、完全なSceneSISスキーマに準拠）"""
        # テキスト内容の読み込み
        text_content = self._load_text_content(text_path)
        if not text_content:
            raise ValidationError(
                'Failed to load text content or empty file',
                error_code='TEXT_LOADING_FAILED'
            )

        # 完全なSceneSISスキーマを取得
        scene_sis_schema = self._scene_sis_schema()
        sis_prompt = _load_prompt_template('content2sis_scene_from_text.md').substitute(
            text_json=json.dumps(text_content, ensure_ascii=False)
        )
        system_prompt = _load_prompt_template('content2sis_scene_system.md').substitute()

        sis_json, raw_text = self._ollama_chat_structured(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': sis_prompt}
            ],
            schema=scene_sis_schema
        )

        # scene_idをアプリケーション側で生成（sis2sis.pyと同様）
        sis_json['scene_id'] = self._generate_scene_id()
        sis_json['sis_type'] = 'scene'

        return ProcessingResult(
            success=True,
            data={'sis_data': sis_json, 'content': raw_text, 'content_format': 'json', 'prompt': sis_prompt},
            error=None,
            metadata={
                'content_type': 'text',
                'text_length': len(text_content),
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def _check_server_and_model(self) -> None:
        """サーバーとモデルの状態確認（Ollama版）"""
        try:
            # Ollama バージョンでオンライン確認
            v = requests.get(f"{self.api_config.ollama_uri}/api/version", timeout=10)
            if v.status_code != 200:
                raise ServerConnectionError("Ollama", self.api_config.ollama_uri)

            # モデルが存在するか確認（tags）
            tags = requests.get(f"{self.api_config.ollama_uri}/api/tags", timeout=10)
            if tags.status_code == 200:
                tj = tags.json() or {}
                models = [m.get('model') for m in tj.get('models', []) if isinstance(m, dict)]
                # 一致条件: 完全一致
                if self.api_config.ollama_model not in (models or []):
                    # 未インストールでも生成は動く場合があるが、明示的にエラーにする
                    raise ModelNotLoadedError(self.api_config.ollama_model)
        except requests.exceptions.ConnectionError:
            raise ServerConnectionError("Ollama", self.api_config.ollama_uri)
    
    def _extract_sis_from_audio(self, audio_path: str) -> Dict[str, Any]:
        """音声からのSIS抽出（Ollamaでは未サポートのため簡易対応）"""
        # ここでは未対応として明示し、将来的にWhisper等との連携を検討
        raise GeNarrativeError(
            'Audio-to-SIS via Ollama is not supported in this build. Please use image/text SIS or provide a text summary of the audio.',
            error_code='AUDIO_SIS_NOT_SUPPORTED'
        )
    
    def _ollama_chat_structured(self, messages: list, schema: Dict[str, Any], images: Optional[list] = None) -> Tuple[Dict[str, Any], str]:
        """/api/chat を用いた Structured Output 呼び出し。JSONを厳密に返す。
        Returns: (sis_json, raw_text)
        """
        self._check_server_and_model()
        payload = {
            'model': self.api_config.ollama_model,
            'messages': messages.copy(),
            'stream': False,
            'format': schema,
            'options': {
                'temperature': 0
            }
        }
        # 画像が渡された場合は user メッセージの images フィールドに添付
        if images:
            cleaned_images = []
            for img in images:
                if isinstance(img, str) and img.startswith('data:'):
                    try:
                        cleaned_images.append(img.split('base64,', 1)[1])
                    except Exception:
                        cleaned_images.append(img)
                else:
                    cleaned_images.append(img)

            for message in reversed(payload['messages']):
                if isinstance(message, dict) and message.get('role') == 'user':
                    existing = message.get('images')
                    if isinstance(existing, list):
                        message['images'] = existing + cleaned_images
                    else:
                        message['images'] = cleaned_images
                    break
        try:
            resp = requests.post(f"{self.api_config.ollama_uri}/api/chat", json=payload, timeout=180)
            if resp.status_code != 200:
                raise GeNarrativeError(f"HTTP {resp.status_code}: {resp.text}")
            rj = resp.json() or {}
            content = ''
            # chat 応答仕様: message.content にJSON文字列
            msg = rj.get('message') or {}
            content = msg.get('content') or ''
            if not content:
                # 一部モデル実装差異に備え fallback
                content = rj.get('response') or ''
            if not content:
                raise GeNarrativeError('Empty content from Ollama chat')
            # JSONとして厳密にパース
            sis_json = json.loads(content)
            return sis_json, content
        except requests.exceptions.Timeout:
            raise GeNarrativeError('Request timeout (3 minutes)')
        except json.JSONDecodeError as e:
            raise ValidationError(f'Structured output is not valid JSON: {e}', error_code='STRUCTURED_JSON_INVALID')

    def _scene_sis_schema(self) -> Dict[str, Any]:
        """完全なSceneSISのJSONスキーマを返す（sis2sis.pyと同じ構造）"""
        # SceneSIS_semantics.jsonを読み込む
        schema_path = Path(__file__).parent / 'schemas' / 'SceneSIS_semantics.json'
        
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                semantics_schema = json.load(f)
        else:
            # フォールバックスキーマ
            semantics_schema = {
                "type": "object",
                "properties": {
                    "common": {"type": "object"},
                    "text": {"type": "object"},
                    "visual": {"type": "object"},
                    "audio": {"type": "object"}
                },
                "required": ["common", "text", "visual", "audio"]
            }
        
        return {
            "type": "object",
            "properties": {
                "sis_type": {
                    "type": "string",
                    "const": "scene",
                    "description": "Must be 'scene'"
                },
                "scene_id": {
                    "type": "string",
                    "description": "Identifier for this scene (assigned by the system)"
                },
                "semantics": semantics_schema
            },
            "required": ["sis_type", "scene_id", "semantics"]
        }

    def _generate_scene_id(self) -> str:
        """scene_idを生成（sis2sis.pyと同じ形式）"""
        return datetime.now().strftime("scene_%Y%m%d_%H%M%S_%f")

    

    def _schema_field_guide_template(self, schema: Dict[str, Any]) -> str:
        """JSON Schema をもとにLLMが理解しやすいテンプレートJSONを生成"""
        try:
            def build(prop: Dict[str, Any]) -> Any:
                if not isinstance(prop, dict):
                    return "value"

                desc = (prop.get('description') or '').strip()
                prop_type = prop.get('type')
                examples = prop.get('examples')
                if isinstance(examples, list) and examples:
                    example_value = examples[0]
                    # JSON Schema stores examples as JSON values; ensure strings remain strings
                    return example_value

                if prop_type == 'object' and isinstance(prop.get('properties'), dict) and prop['properties']:
                    return {k: build(v) for k, v in prop['properties'].items()}

                if prop_type == 'array':
                    item_prop = prop.get('items') if isinstance(prop.get('items'), dict) else None
                    item_value = build(item_prop) if item_prop else (desc or 'item description')
                    if isinstance(item_value, dict):
                        return [item_value]
                    if isinstance(item_value, list):
                        return item_value
                    return [item_value or (desc or 'item description')]

                return desc or (f"{prop_type} value" if prop_type else 'value description')

            props = (schema or {}).get('properties', {})
            guide_template = {key: build(prop) for key, prop in props.items()}
            return json.dumps(guide_template, ensure_ascii=False, indent=2)
        except Exception:
            return ''
    
    def _extract_sis_from_text(self, text_content: str) -> Dict[str, Any]:
        """テキストからのSIS抽出"""
        self._check_server_and_model()

        sis_prompt = _load_prompt_template('content2sis_legacy_sis_from_text.md').substitute(
            text_content=text_content
        )

        try:
            payload = {
                'model': self.api_config.ollama_model,
                'prompt': sis_prompt,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'num_predict': 800
                }
            }
            response = requests.post(
                f"{self.api_config.ollama_uri}/api/generate",
                json=payload,
                timeout=180
            )
            if response.status_code == 200:
                result = response.json() or {}
                text = result.get('response') or ''
                if text:
                    sis_data = self._parse_sis_json_response(text)
                    if sis_data:
                        sis_data['extraction_time'] = datetime.now().isoformat()
                        return sis_data
                    else:
                        raise ValidationError('Failed to parse JSON from response')
                else:
                    raise GeNarrativeError('Empty response from Ollama')
            else:
                raise GeNarrativeError(f'HTTP {response.status_code}: {response.text}')
        except requests.exceptions.Timeout:
            raise GeNarrativeError('Request timeout (3 minutes)')
    
    def _load_and_encode_image(self, image_path: str) -> Optional[str]:
        """画像ファイルをbase64エンコード"""
        try:
            with open(image_path, 'rb') as img_file:
                image_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            return image_base64
        except Exception as e:
            self.logger.log_error('_load_and_encode_image', str(e))
            return None
    
    def _load_text_content(self, text_path: str) -> Optional[str]:
        """テキストファイルの内容を読み込み"""
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            return content if content else None
        except Exception as e:
            self.logger.log_error('_load_text_content', str(e))
            return None
    
    def _parse_sis_json_response(self, generated_text: str) -> Optional[Dict[str, Any]]:
        """生成されたテキストからJSONを抽出・解析"""
        try:
            # 1) 前処理: LLMトークンやコードフェンスの除去
            text = (generated_text or '').strip()
            for token in (
                '<bos>', '<eos>', '<pad>', '<unk>',
                '<start_of_turn>', '<end_of_turn>',
                '<start_of_turn>model', '<start_of_turn>user', '<start_of_turn>assistant',
            ):
                text = text.replace(token, '')

            # コードフェンスの中身を優先
            if '```json' in text:
                try:
                    inner = text.split('```json', 1)[1]
                    inner = inner.split('```', 1)[0]
                    text = inner.strip()
                except Exception:
                    pass
            elif '```' in text:
                try:
                    inner = text.split('```', 1)[1]
                    inner = inner.split('```', 1)[0]
                    text = inner.strip()
                except Exception:
                    pass

            # 2) まずは素直にパース
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

            # 3) フォールバック: 最初の '{' から対応する '}' までのブロックを抽出（単純な括弧対応）
            start = text.find('{')
            if start != -1:
                depth = 0
                end = -1
                for i in range(start, len(text)):
                    ch = text[i]
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end != -1:
                    candidate = text[start:end]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # 軽微な末尾カンマの削除などの簡易修正
                        candidate_fixed = candidate.replace(',}', '}').replace(',]', ']')
                        try:
                            return json.loads(candidate_fixed)
                        except Exception:
                            pass

            # 4) 失敗
            raise json.JSONDecodeError('Failed to extract valid JSON block', text, 0)

        except json.JSONDecodeError as e:
            self.logger.log_error('_parse_sis_json_response', f'JSON decode error: {e}')
            return None
        except Exception as e:
            self.logger.log_error('_parse_sis_json_response', f'Parsing error: {e}')
            return None


# ========================================
# 統一エントリーポイント関数
# ========================================

def extract_sis_from_content(
    content_path: str,
    content_type: str = None,
    api_config: Optional[APIConfig] = None,
    processing_config: Optional[ProcessingConfig] = None,
    logger: Optional[StructuredLogger] = None
) -> Dict[str, Any]:
    """
    統合されたSIS抽出関数
    
    Args:
        content_path: コンテンツファイルのパス
        content_type: コンテンツタイプ ('audio' | 'image' | 'text' | None)
        api_config: API設定
        processing_config: 処理設定
        logger: ロガー
    
    Returns:
        統一された戻り値辞書
    """
    extractor = SISExtractor(api_config, processing_config, logger)
    result = extractor.process(content_path, content_type)
    return result.to_dict()


# ========================================
# 既存関数（後方互換性のため）
# ========================================

def audio2SIS(
    audio_path: str = "/app/shared/music_0264b049.wav",
    api_uri: str = "http://unsloth:5006",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:
    """
    音声ファイルからSIS抽出（後方互換性）
    """
    api_config = APIConfig(unsloth_uri=api_uri, model_name=model_name)
    return extract_sis_from_content(audio_path, 'audio', api_config)


def image2SIS(
    image_path: str = "/app/shared/image/story_image_20250726_094413.png",
    api_uri: str = "http://unsloth:5006",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:
    """
    画像ファイルからSIS抽出（後方互換性）
    """
    api_config = APIConfig(unsloth_uri=api_uri, model_name=model_name)
    return extract_sis_from_content(image_path, 'image', api_config)


def text2SIS(
    text_path: str = "/app/shared/text/text_20250804_230132.txt",
    api_uri: str = "http://unsloth:5006",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:
    """
    テキストファイルからSIS抽出（後方互換性）
    """
    api_config = APIConfig(unsloth_uri=api_uri, model_name=model_name)
    return extract_sis_from_content(text_path, 'text', api_config)


def speech2text(
    audio_path: str,
    api_uri: str = "http://unsloth:5006",
    model_name: str = "unsloth/gemma-3n-E4B-it"
) -> Dict[str, Any]:
    """
    音声ファイルからテキスト抽出（本ビルドでは未サポート）

    Note:
        本関数は Unsloth サーバを使用していましたが、要件により無効化しました。
        代わりに外部の音声認識（例: Whisper）を導入するか、テキストを別途用意してください。

    Raises:
        GeNarrativeError: 現在未サポートである旨の例外
    """
    raise GeNarrativeError(
        'speech2text() is disabled: Unsloth is not used in this build. '
        'Please provide text manually or integrate a speech-to-text service (e.g., Whisper).',
        error_code='SPEECH_TO_TEXT_NOT_SUPPORTED'
    )


# ========================================
# ユーティリティ関数（既存のものを統合）
# ========================================

def save_sis_to_file(sis_data: Dict[str, Any], output_path: str) -> bool:
    """
    SIS data to file in JSON format.
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sis_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 SIS data saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save SIS data: {e}")
        return False


def json2jsonl(json_file_path: str, jsonl_file_path: str = None) -> bool:
    """
    Convert JSON file to JSONL format.
    """
    try:
        if jsonl_file_path is None:
            base_name = os.path.splitext(json_file_path)[0]
            jsonl_file_path = f"{base_name}.jsonl"
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        os.makedirs(os.path.dirname(jsonl_file_path), exist_ok=True)
        with open(jsonl_file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
        
        print(f"🔄 JSON to JSONL conversion completed")
        print(f"   Input:  {json_file_path}")
        print(f"   Output: {jsonl_file_path}")
        return True
        
    except FileNotFoundError:
        print(f"❌ JSON file not found: {json_file_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON format: {e}")
        return False
    except Exception as e:
        print(f"❌ JSON to JSONL conversion failed: {e}")
        return False
