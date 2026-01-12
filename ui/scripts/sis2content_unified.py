#!/usr/bin/env python3
"""
Unified SIS (formerly SIS) to Content Generation Script

統一された実装方針による、SISデータ（旧称SIS）からのコンテンツ生成機能
- 統一されたエントリーポイント
- 設定クラスによる設定管理
- 統一されたエラーハンドリングと戻り値構造
- 改良されたログシステム

Usage:
    python _unified.py --mode image [--sis_file path/to/sis.json] [--width 512] [--height 512]
    python _unified.py --mode music [--sis_file path/to/sis.json] [--duration 30]
    python _unified.py --mode text [--sis_file path/to/sis.json] [--word_count 50]
    python _unified.py --mode tts [--sis_file path/to/sis.json] [--text_input "Direct text"] [--output_filename speech]
"""

import os
import sys
import json
import requests
import time
import argparse
import base64
import shutil
import re
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from functools import lru_cache
from string import Template

# 共通基盤のインポート
from common_base import (
    APIConfig, ProcessingConfig, GenerationConfig,
    ContentProcessor, ProcessingResult, StructuredLogger,
    GeNarrativeError, FileProcessingError, ServerConnectionError, 
    ModelNotLoadedError, ContentTypeError, ValidationError,
    create_standard_response
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
# コンテンツ生成プロセッサクラス
# ========================================

class ContentGenerator(ContentProcessor):
    """統一されたコンテンツ生成クラス"""
    
    def __init__(self, 
                 api_config: Optional[APIConfig] = None,
                 processing_config: Optional[ProcessingConfig] = None,
                 generation_config: Optional[GenerationConfig] = None,
                 logger: Optional[StructuredLogger] = None):
        super().__init__(api_config, processing_config, logger)
        self.generation_config = generation_config or GenerationConfig()
    
    def process(self, sis_data: Dict[str, Any], content_type: str, **kwargs) -> ProcessingResult:
        """統合コンテンツ生成処理"""
        function_name = 'generate_content'
        
        try:
            # 処理開始
            self._start_processing(function_name, {
                'content_type': content_type,
                'sis_summary': sis_data.get('summary', 'N/A')[:100]
            })
            
            # SIS データの正規化（semanticsフィールドがある場合は展開）
            sis_data = self._normalize_sis_data(sis_data)
            
            # SIS データの検証
            self._validate_sis_data(sis_data)
            
            # コンテンツタイプの検証
            if content_type not in ['image', 'music', 'text']:
                raise ContentTypeError(content_type, ['image', 'music', 'text'])
            
            # 画像生成の場合の特別処理：SDサーバーが利用可能でUnslothが利用不可の場合
            if content_type == "image":
                unsloth_available = self._is_unsloth_available()
                sd_available = self._check_sd_server()
                
                self.logger.logger.info(f"🔍 Server availability check - Unsloth: {unsloth_available}, SD: {sd_available}")
                
                if sd_available and not unsloth_available:
                    self.logger.logger.info("🖼️ Using direct SD generation (Unsloth not available)")
                    return self._generate_image_directly(sis_data, **kwargs)
                elif not sd_available:
                    raise GeNarrativeError("SD server is not available for image generation")
                else:
                    self.logger.logger.info("🤖 Using Unsloth + SD pipeline")
            
            # プロンプト生成
            prompt = self._create_prompt(sis_data, content_type, **kwargs)

            # 生成エンジンの選択
            if content_type in ("text", "music", "image"):
                # テキスト/音楽/画像用のプロンプトは Ollama 経由で生成（Unsloth 不使用）
                generated_text = self._generate_with_ollama(prompt)
            else:
                # 念のためのフォールバック（通常到達しない）
                generated_text = self._generate_with_ollama(prompt)
            
            # 結果の保存
            output_path = self._save_generated_content(
                generated_text, content_type, **kwargs
            )
            
            # 追加コンテンツ生成（画像・音楽）
            # skip_actual_generation=True の場合は、プロンプト生成のみで終了
            if kwargs.get('skip_actual_generation'):
                self.logger.logger.info("⏭️ Skipping actual generation (prompt-only mode)")
                additional_results = {}
            else:
                additional_results = self._generate_additional_content(
                    generated_text, content_type, **kwargs
                )
            
            # 処理終了
            duration = self._end_processing(function_name, True)
            
            # 結果データの作成
            result_data = {
                'generated_text': generated_text,
                'output_path': output_path,
                'content_type': content_type
            }
            result_data.update(additional_results)
            
            return ProcessingResult(
                success=True,
                data=result_data,
                error=None,
                metadata={
                    'function_name': function_name,
                    'processing_time': duration,
                    'content_type': content_type,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            return self._handle_error(e, function_name, {
                'content_type': content_type,
                'sis_summary': sis_data.get('summary', 'N/A')[:100] if isinstance(sis_data, dict) else 'Invalid SIS'
            })
    
    def _normalize_sis_data(self, sis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        SIS データの正規化
        - semantics フィールドがある場合は、その中身をトップレベルに展開
        - scene_id, sis_type, summary などのメタデータは保持
        """
        if not isinstance(sis_data, dict):
            return sis_data
        
        # semantics フィールドが存在する場合
        if 'semantics' in sis_data and isinstance(sis_data['semantics'], dict):
            self.logger.logger.info("🔄 Normalizing SIS data: extracting 'semantics' field to top level")
            
            # semantics の中身を取り出す
            semantics = sis_data['semantics']
            
            # 新しい正規化されたデータを作成
            normalized = {
                'common': semantics.get('common', {}),
                'text': semantics.get('text', {}),
                'visual': semantics.get('visual', {}),
                'audio': semantics.get('audio', {})
            }
            
            # メタデータを保持（あれば）
            if 'scene_id' in sis_data:
                normalized['scene_id'] = sis_data['scene_id']
            if 'sis_type' in sis_data:
                normalized['sis_type'] = sis_data['sis_type']
            if 'summary' in sis_data:
                normalized['summary'] = sis_data['summary']
            
            return normalized
        
        # semantics フィールドがない場合はそのまま返す
        return sis_data
    
    def _validate_sis_data(self, sis_data: Dict[str, Any]) -> None:
        """SIS データの検証"""
        if not isinstance(sis_data, dict):
            raise ValidationError('SIS data must be a dictionary')
        
        # 基本的なフィールドの存在確認（厳密な検証は緩和）
        if not sis_data:
            raise ValidationError('SIS data is empty')
        
        # 最低限必要なフィールドの確認（SceneSIS_semantics.json形式）
        essential_fields = ['common']
        missing_essential = [field for field in essential_fields if field not in sis_data or not sis_data[field]]
        
        if missing_essential:
            raise ValidationError(
                f'Missing essential SIS fields: {missing_essential}',
                error_code='INCOMPLETE_SIS_DATA'
            )
        
        # 欠損フィールドを警告として記録（エラーにしない）
        expected_fields = ['common', 'text', 'visual', 'audio']
        missing_fields = [field for field in expected_fields if field not in sis_data]
        
        if missing_fields:
            self.logger.logger.warning(f"⚠️ SIS missing optional fields: {missing_fields}")
            # 欠損フィールドにデフォルト値を設定
            for field in missing_fields:
                if field == 'common':
                    sis_data[field] = {'mood': '', 'characters': [], 'location': '', 'time': '', 'weather': '', 'objects': [], 'descriptions': []}
                elif field == 'text':
                    sis_data[field] = {'style': '', 'language': 'English', 'tone': '', 'point_of_view': 'third'}
                elif field == 'visual':
                    sis_data[field] = {'style': '', 'composition': '', 'lighting': '', 'perspective': ''}
                elif field == 'audio':
                    sis_data[field] = {'genre': '', 'tempo': '', 'instruments': []}
    
    def _create_prompt(self, sis_data: Dict[str, Any], content_type: str, **kwargs) -> str:
        """コンテンツタイプに応じたプロンプト生成"""
        if content_type == "image":
            return self._create_image_prompt(
                sis_data, 
                kwargs.get('width', self.generation_config.image_width),
                kwargs.get('height', self.generation_config.image_height)
            )
        elif content_type == "music":
            return self._create_music_prompt(
                sis_data, 
                kwargs.get('duration', self.generation_config.music_duration)
            )
        elif content_type == "text":
            return self._create_text_prompt(
                sis_data, 
                kwargs.get('word_count', self.generation_config.text_word_count)
            )
        else:
            raise ContentTypeError(content_type, ['image', 'music', 'text'])
    
    def _create_image_prompt(self, sis_data: Dict[str, Any], width: int, height: int) -> str:
        """画像生成プロンプト作成"""
        sis_json = json.dumps(sis_data, indent=2, ensure_ascii=False)

        return _load_prompt_template('sis2content_image_prompt.md').substitute(
            width=width,
            height=height,
            sis_json=sis_json
        )
    
    def _create_music_prompt(self, sis_data: Dict[str, Any], duration: int) -> str:
        """音楽生成プロンプト作成（画像と同じシンプルな構造）"""
        sis_json = json.dumps(sis_data, indent=2, ensure_ascii=False)

        return _load_prompt_template('sis2content_music_prompt.md').substitute(
            duration=duration,
            sis_json=sis_json
        )
    
    def _create_fallback_music_prompt(self, sis_data: Dict[str, Any], duration: int) -> str:
        """LLM失敗時のフォールバック: ルールベースで音楽プロンプト生成"""
        self.logger.logger.info("🔧 Using fallback rule-based music prompt generation")
        
        prompt_parts = []
        
        # SceneSIS形式から情報抽出
        common = sis_data.get('common', {})
        audio = sis_data.get('audio', {})
        
        # ジャンル
        genre = audio.get('genre', 'ambient')
        if genre:
            prompt_parts.append(genre)
        
        # テンポ
        tempo = audio.get('tempo', 'moderate')
        if tempo:
            prompt_parts.append(f"{tempo} tempo")
        
        # 楽器
        instruments = audio.get('instruments', [])
        if instruments:
            inst_str = ', '.join(instruments[:2])  # 最大2楽器
            prompt_parts.append(inst_str)
        
        # ムード
        mood = common.get('mood', '')
        if mood:
            prompt_parts.append(f"{mood} atmosphere")
        
        if not prompt_parts:
            return "ambient music"
        
        return ', '.join(prompt_parts)
    
    def _create_text_prompt(self, sis_data: Dict[str, Any], word_count: int) -> str:
        """テキスト生成プロンプト作成"""
        sis_json = json.dumps(sis_data, indent=2, ensure_ascii=False)

        return _load_prompt_template('sis2content_text_prompt.md').substitute(
            word_count=word_count,
            sis_json=sis_json
        )
    
    def _generate_with_unsloth(self, prompt: str, content_type: str) -> str:
        """Unslothサーバーでの生成"""
        # サーバー状態確認
        self._check_unsloth_server()
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            "generation_options": {
                "max_new_tokens": self.generation_config.max_tokens,
                "temperature": self.generation_config.temperature,
                "cache_implementation": "static"
            }
        }
        
        try:
            response = requests.post(
                f"{self.api_config.unsloth_uri}/generate",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.api_config.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('generated_text'):
                    return self._clean_generated_text(result['generated_text'])
                else:
                    raise GeNarrativeError(result.get('error', 'No generated text in response'))
            else:
                raise GeNarrativeError(f'HTTP {response.status_code}: {response.text}')
                
        except requests.exceptions.Timeout:
            raise GeNarrativeError(f'Request timeout ({self.api_config.timeout} seconds)')

    def _generate_with_ollama(self, prompt: str) -> str:
        """Ollamaサーバーでのテキスト生成"""
        base = self.api_config.ollama_uri
        model = self.api_config.ollama_model
        payload = {
            'model': model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': float(self.generation_config.temperature),
                'num_predict': int(self.generation_config.max_tokens)
            }
        }
        try:
            resp = requests.post(f"{base}/api/generate", json=payload, timeout=(10, self.api_config.timeout))
            if resp.status_code != 200:
                raise GeNarrativeError(f"HTTP {resp.status_code} from Ollama: {resp.text[:200]}")
            rj = resp.json() or {}
            text = (rj.get('response') or '').strip()
            if not text:
                raise GeNarrativeError('Empty response from Ollama')
            return self._clean_generated_text(text)
        except requests.exceptions.Timeout:
            raise GeNarrativeError(f'Ollama request timeout ({self.api_config.timeout} seconds)')
        except requests.exceptions.ConnectionError as e:
            raise ServerConnectionError("Ollama", base) from e
    
    def _check_unsloth_server(self) -> None:
        """Unslothサーバー状態確認"""
        try:
            response = requests.get(f"{self.api_config.unsloth_uri}/health", timeout=10)
            if response.status_code != 200:
                raise ServerConnectionError("Unsloth", self.api_config.unsloth_uri)
            
            health_data = response.json()
            if not health_data.get('model_loaded', False):
                raise ModelNotLoadedError(self.api_config.model_name)
                
        except requests.exceptions.ConnectionError:
            raise ServerConnectionError("Unsloth", self.api_config.unsloth_uri)
    
    def _is_unsloth_available(self) -> bool:
        """Unslothサーバーが利用可能かチェック（エラーを投げない版）"""
        try:
            response = requests.get(f"{self.api_config.unsloth_uri}/health", timeout=5)
            if response.status_code != 200:
                return False
            
            health_data = response.json()
            return health_data.get('model_loaded', False)
                
        except Exception:
            return False
    
    def _generate_image_directly(self, sis_data: Dict[str, Any], **kwargs) -> ProcessingResult:
        """Unsloth無しで直接SDサーバーを使用した画像生成"""
        function_name = 'generate_image_directly'
        
        try:
            self.logger.logger.info("🖼️ Starting direct SD image generation")
            
            # SISデータから直接画像プロンプトを作成
            image_prompt = self._create_direct_image_prompt(sis_data)
            self.logger.logger.info(f"🎨 Generated prompt: {image_prompt[:100]}...")
            
            # プロンプトをテキストファイルとして保存
            output_path = self._save_generated_content(
                image_prompt, 'image', **kwargs
            )
            self.logger.logger.info(f"📁 Prompt saved to: {output_path}")
            
            # プロンプトのみの要求なら、SD生成はスキップ
            if kwargs.get('skip_actual_generation'):
                self.logger.logger.info("⏭️ Skipping SD image generation (prompt-only mode)")
                image_result = {}
            else:
                # SDサーバーで画像生成
                self.logger.logger.info("🖥️ Starting SD server image generation...")
                image_result = self._generate_image_with_sd(
                    image_prompt, 
                    kwargs.get('width', self.generation_config.image_width),
                    kwargs.get('height', self.generation_config.image_height),
                    **kwargs
                )
            
            if image_result.get('success'):
                self.logger.logger.info(f"✅ Image generation successful: {image_result.get('image_filename')}")
            else:
                self.logger.logger.warning(f"⚠️ Image generation failed: {image_result.get('error')}")
            
            # 処理終了
            duration = self._end_processing(function_name, True)
            
            # 結果データの作成
            result_data = {
                'generated_text': image_prompt,
                'output_path': output_path,
                'content_type': 'image',
                # 画像生成をスキップした場合は image_result を含めない
                **({} if kwargs.get('skip_actual_generation') else {'image_result': image_result})
            }
            
            return ProcessingResult(
                success=True,
                data=result_data,
                error=None,
                metadata={
                    'function_name': function_name,
                    'processing_time': duration,
                    'content_type': 'image',
                    'method': 'prompt_only' if kwargs.get('skip_actual_generation') else 'direct_sd_generation',
                    'timestamp': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.logger.error(f"❌ Direct image generation failed: {str(e)}")
            return self._handle_error(e, function_name, {
                'sis_summary': sis_data.get('summary', 'N/A')[:100] if isinstance(sis_data, dict) else 'Invalid SIS'
            })
    
    def _create_direct_image_prompt(self, sis_data: Dict[str, Any]) -> str:
        """SISデータから直接画像プロンプトを生成（LLMを使用）"""
        self.logger.logger.info("🎨 Creating image prompt from SIS data using LLM")
        
        # SceneSIS形式のSISデータをJSON文字列化
        sis_json_str = json.dumps(sis_data, ensure_ascii=False, indent=2)
        self.logger.logger.info(f"📊 SIS data size: {len(sis_json_str)} chars")
        
        # LLMに渡すプロンプト
        system_prompt = _load_prompt_template('sis2content_direct_image_system.md').substitute()
        user_prompt = _load_prompt_template('sis2content_direct_image_user.md').substitute(
            sis_json=sis_json_str
        )
        
        try:
            # Ollamaで画像プロンプトを生成
            self.logger.logger.info("🤖 Calling Ollama to generate image prompt...")
            payload = {
                'model': self.api_config.ollama_model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                'stream': False,
                'options': {
                    'temperature': 0.3,  # 創造的だが一貫性を保つ
                    'num_predict': 150   # プロンプトは短めに
                }
            }
            
            response = requests.post(
                f"{self.api_config.ollama_uri}/api/chat",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                message = result.get('message', {})
                generated_prompt = message.get('content', '').strip()
                
                if generated_prompt:
                    # 不要な引用符やマークダウンを除去
                    generated_prompt = generated_prompt.strip('"\'`')
                    if generated_prompt.startswith('```'):
                        lines = generated_prompt.split('\n')
                        generated_prompt = '\n'.join([l for l in lines if not l.startswith('```')]).strip()
                    
                    # 品質タグを追加
                    if 'high quality' not in generated_prompt.lower():
                        generated_prompt += ', high quality, detailed, masterpiece'
                    
                    self.logger.logger.info(f"✅ Generated prompt ({len(generated_prompt)} chars): {generated_prompt[:100]}...")
                    return generated_prompt
                else:
                    raise GeNarrativeError('Empty response from LLM')
            else:
                raise GeNarrativeError(f'HTTP {response.status_code}: {response.text}')
                
        except Exception as e:
            self.logger.logger.warning(f"⚠️ LLM prompt generation failed: {str(e)}, falling back to rule-based")
            # フォールバック: ルールベースの簡易プロンプト生成
            return self._create_fallback_image_prompt(sis_data)
    
    def _create_fallback_image_prompt(self, sis_data: Dict[str, Any]) -> str:
        """LLM失敗時のフォールバック: ルールベースでプロンプト生成"""
        self.logger.logger.info("🔧 Using fallback rule-based prompt generation")
        
        prompt_parts = []
        
        # SceneSIS形式から情報抽出
        common = sis_data.get('common', {})
        visual = sis_data.get('visual', {})
        
        # キャラクター
        characters = common.get('characters', [])
        for char in characters[:2]:  # 最大2キャラクター
            if isinstance(char, dict):
                name = char.get('name', '')
                traits = ', '.join(char.get('traits', [])[:3])
                visual_info = char.get('visual', {})
                hair = visual_info.get('hair', '')
                clothes = visual_info.get('clothes', '')
                parts = [p for p in [name, traits, hair, clothes] if p]
                if parts:
                    prompt_parts.append(' '.join(parts))
        
        # 場所・時間・天気
        location = common.get('location', '')
        time = common.get('time', '')
        weather = common.get('weather', '')
        scene_parts = [p for p in [location, time, weather] if p]
        if scene_parts:
            prompt_parts.append(', '.join(scene_parts))
        
        # オブジェクト
        objects = common.get('objects', [])
        for obj in objects[:3]:  # 最大3オブジェクト
            if isinstance(obj, dict):
                obj_name = obj.get('name', '')
                obj_colors = ', '.join(obj.get('colors', []))
                if obj_name:
                    prompt_parts.append(f"{obj_colors} {obj_name}" if obj_colors else obj_name)
        
        # 説明
        descriptions = common.get('descriptions', [])
        if descriptions:
            prompt_parts.append(descriptions[0])
        
        # ビジュアルスタイル
        style = visual.get('style', '')
        lighting = visual.get('lighting', '')
        composition = visual.get('composition', '')
        visual_parts = [p for p in [lighting, style, composition] if p]
        if visual_parts:
            prompt_parts.append(', '.join(visual_parts))
        
        # ムード
        mood = common.get('mood', '')
        if mood:
            prompt_parts.append(f"{mood} atmosphere")
        
        base_prompt = ', '.join(prompt_parts)
        return f"{base_prompt}, high quality, detailed, masterpiece"
    
    def _clean_generated_text(self, generated_text: str) -> str:
        """生成テキストのクリーニング"""
        clean_text = generated_text.strip()
        
        # LLMトークンの除去
        llm_tokens = [
            '<bos>', '<eos>', '<pad>', '<unk>',
            '<start_of_turn>', '<end_of_turn>',
            '<start_of_turn>model', '<start_of_turn>user', '<start_of_turn>assistant',
        ]
        
        for token in llm_tokens:
            clean_text = clean_text.replace(token, '')
        
        # マークダウンコードブロックの除去
        if '```' in clean_text:
            clean_text = re.sub(r'```[^`]*```', '', clean_text)
        
        # モデルレスポンスの抽出
        if '<start_of_turn>model' in clean_text:
            clean_text = clean_text.split('<start_of_turn>model')[-1]
            clean_text = clean_text.replace('<end_of_turn>', '')
        
        return clean_text.strip()
    
    def _save_generated_content(self, generated_text: str, content_type: str, **kwargs) -> str:
        """生成コンテンツの保存"""
        # タイムスタンプとディレクトリの決定
        custom_timestamp = kwargs.get('custom_timestamp')
        if custom_timestamp:
            timestamp = custom_timestamp
            test_dir = f"{self.processing_config.output_dir}/test_result_{timestamp}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_dir = f"{self.processing_config.output_dir}/test_result_{timestamp}"
        
        # ファイル名の決定
        test_case_name = kwargs.get('test_case_name', '')
        prefix = f"{test_case_name}_" if test_case_name else ""
        
        if content_type == "text":
            filename = f"{prefix}sis2story.txt"
        elif content_type == "image":
            filename = f"{prefix}sis2image_prompt.txt"
        elif content_type == "music":
            filename = f"{prefix}sis2music_prompt.txt"
        else:
            filename = f"{prefix}sis_{content_type}.txt"
        
        output_path = f"{test_dir}/{filename}"
        os.makedirs(test_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(generated_text)
        
        return output_path
    
    def _generate_additional_content(self, generated_text: str, content_type: str, **kwargs) -> Dict[str, Any]:
        """追加コンテンツ生成（画像・音楽）"""
        additional_results = {}
        
        if content_type == "image":
            # Stable Diffusion での画像生成
            if self._check_sd_server():
                self.logger.logger.info("🖼️ Generating actual image...")
                image_result = self._generate_image_with_sd(
                    generated_text, 
                    kwargs.get('width', self.generation_config.image_width),
                    kwargs.get('height', self.generation_config.image_height),
                    **kwargs
                )
                additional_results['image_result'] = image_result
            else:
                self.logger.logger.warning("⚠️ SD server not available, skipping image generation")
        
        elif content_type == "music":
            # Music server での音楽生成
            if self._check_music_server():
                self.logger.logger.info("🎵 Generating actual music...")
                music_result = self._generate_music_with_server(
                    generated_text,
                    kwargs.get('duration', self.generation_config.music_duration),
                    **kwargs
                )
                additional_results['music_result'] = music_result
            else:
                self.logger.logger.warning("⚠️ Music server not available, skipping music generation")
        
        return additional_results
    
    def _check_sd_server(self) -> bool:
        """Stable Diffusion サーバー確認"""
        try:
            self.logger.logger.info(f"🔍 Checking SD server at: {self.api_config.sd_uri}")
            response = requests.get(f"{self.api_config.sd_uri}/sdapi/v1/memory", timeout=10)
            
            if response.status_code == 200:
                memory_info = response.json()
                self.logger.logger.info(f"✅ SD server is available")
                self.logger.logger.info(f"💾 Memory info: {memory_info.get('ram', {})}")
                return True
            else:
                self.logger.logger.warning(f"⚠️ SD server returned status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError as e:
            self.logger.logger.error(f"❌ SD server connection error: {str(e)}")
            return False
        except requests.exceptions.Timeout as e:
            self.logger.logger.error(f"❌ SD server timeout: {str(e)}")
            return False
        except Exception as e:
            self.logger.logger.error(f"❌ SD server check failed: {str(e)}")
            return False
    
    def _check_music_server(self) -> bool:
        """Music サーバー確認"""
        try:
            response = requests.get(f"{self.api_config.music_uri}/health", timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def _check_tts_server(self) -> bool:
        """TTS サーバー確認"""
        try:
            response = requests.get(f"{self.api_config.tts_uri}", timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def _generate_image_with_sd(self, image_prompt: str, width: int, height: int, **kwargs) -> Dict[str, Any]:
        """Stable Diffusion で画像生成"""
        self.logger.logger.info(f"🖼️ Starting SD image generation {width}x{height}")
        self.logger.logger.info(f"📝 Prompt: {image_prompt[:100]}...")
        self.logger.logger.info(f"🔗 SD URI: {self.api_config.sd_uri}")
        
        # まずSDサーバーの健康状態をチェック
        try:
            health_response = requests.get(f"{self.api_config.sd_uri}/sdapi/v1/memory", timeout=10)
            self.logger.logger.info(f"🏥 SD health check: {health_response.status_code}")
            if health_response.status_code == 200:
                memory_info = health_response.json()
                self.logger.logger.info(f"💾 SD memory info: {memory_info.get('ram', {}).get('used', 'unknown')}")
            else:
                self.logger.logger.warning(f"⚠️ SD health check failed: {health_response.status_code}")
        except Exception as health_error:
            self.logger.logger.warning(f"⚠️ SD health check error: {str(health_error)}")
        
        generation_params = {
            "prompt": image_prompt,
            "negative_prompt": "low quality, blurry, distorted, ugly, bad anatomy, text, watermark",
            "width": width,
            "height": height,
            "steps": 25,
            "cfg_scale": 7.5,
            "sampler_name": "DPM++ 2M Karras",
            "batch_size": 1,
            "n_iter": 1,
            "seed": -1,
        }
        
        self.logger.logger.info(f"🔧 Generation params: steps={generation_params['steps']}, cfg_scale={generation_params['cfg_scale']}, sampler={generation_params['sampler_name']}")
        self.logger.logger.info(f"📐 Image dimensions: {width}x{height}")
        
        start_time = time.time()
        
        try:
            self.logger.logger.info(f"📡 Sending POST request to {self.api_config.sd_uri}/sdapi/v1/txt2img")
            self.logger.logger.info(f"📦 Request payload size: {len(str(generation_params))} chars")
            
            response = requests.post(
                f"{self.api_config.sd_uri}/sdapi/v1/txt2img",
                json=generation_params,
                headers={'Content-Type': 'application/json'},
                timeout=120
            )
            
            generation_time = time.time() - start_time
            self.logger.logger.info(f"⏱️ SD request completed in {generation_time:.1f} seconds")
            self.logger.logger.info(f"📊 Response status: {response.status_code}")
            self.logger.logger.info(f"📊 Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    self.logger.logger.info(f"✅ JSON response parsed successfully")
                    self.logger.logger.info(f"🔑 Response keys: {list(result.keys())}")
                    
                    if 'images' in result and result['images']:
                        img_base64 = result['images'][0]
                        self.logger.logger.info(f"🖼️ Base64 image data length: {len(img_base64)} chars")
                        
                        try:
                            img_bytes = base64.b64decode(img_base64)
                            self.logger.logger.info(f"✅ Base64 decode successful, image size: {len(img_bytes)} bytes")
                            
                            # 画像の保存
                            image_path = self._save_generated_image(img_bytes, **kwargs)
                            self.logger.logger.info(f"✅ Image saved successfully to: {image_path}")
                            
                            return {
                                'success': True,
                                'image_path': image_path,
                                'image_filename': os.path.basename(image_path),
                                'image_size': len(img_bytes),
                                'generation_time': generation_time,
                                'prompt': image_prompt,
                                'parameters': generation_params
                            }
                        except Exception as decode_error:
                            error_msg = f'Base64 decode error: {str(decode_error)}'
                            self.logger.logger.error(f"❌ {error_msg}")
                            return {'success': False, 'error': error_msg}
                    else:
                        error_msg = f'No images in response from SD server. Response: {result}'
                        self.logger.logger.error(f"❌ {error_msg}")
                        return {'success': False, 'error': error_msg}
                
                except json.JSONDecodeError as json_error:
                    error_msg = f'JSON decode error: {str(json_error)}. Raw response: {response.text[:500]}'
                    self.logger.logger.error(f"❌ {error_msg}")
                    return {'success': False, 'error': error_msg}
            else:
                error_msg = f'HTTP {response.status_code}: {response.text[:500]}'
                self.logger.logger.error(f"❌ SD server error: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except requests.exceptions.Timeout:
            error_msg = f'Image generation timed out after {120} seconds'
            self.logger.logger.error(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
        except requests.exceptions.ConnectionError as conn_error:
            error_msg = f'Connection error to SD server: {str(conn_error)}'
            self.logger.logger.error(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f'Unexpected image generation error: {str(e)}'
            self.logger.logger.error(f"❌ {error_msg}")
            import traceback
            self.logger.logger.error(f"📍 Traceback: {traceback.format_exc()}")
            return {'success': False, 'error': error_msg}
    
    def _generate_music_with_server(self, music_prompt: str, duration: int, **kwargs) -> Dict[str, Any]:
        """Music server で音楽生成"""
        payload = {
            "prompt": music_prompt,
            "duration": duration,
            "temperature": 0.8
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.api_config.music_uri}/generate",
                json=payload,
                timeout=max(120, duration * 3)
            )
            
            if response.status_code == 200:
                result = response.json()
                generation_time = time.time() - start_time
                
                if 'filename' in result:
                    original_music_path = f"/app/shared/{result['filename']}"
                    
                    if os.path.exists(original_music_path):
                        # 音楽ファイルの移動
                        music_path = self._save_generated_music(original_music_path, **kwargs)
                        music_size = os.path.getsize(music_path)
                        
                        return {
                            'success': True,
                            'music_path': music_path,
                            'music_filename': os.path.basename(music_path),
                            'music_size': music_size,
                            'sample_rate': result.get('sample_rate', 32000),
                            'generation_time': generation_time
                        }
                    else:
                        return {'success': False, 'error': f'Generated file not found: {original_music_path}'}
                else:
                    return {'success': False, 'error': 'No filename in response'}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except requests.exceptions.Timeout:
            timeout_duration = max(120, duration * 3)
            return {'success': False, 'error': f'Music generation timed out ({timeout_duration} seconds)'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _save_generated_image(self, img_bytes: bytes, **kwargs) -> str:
        """生成画像の保存"""
        # 保存先ディレクトリの決定
        custom_timestamp = kwargs.get('custom_timestamp')
        if custom_timestamp:
            test_dir = f"{self.processing_config.output_dir}/test_result_{custom_timestamp}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_dir = f"{self.processing_config.output_dir}/test_result_{timestamp}"
        
        # ファイル名の決定
        test_case_name = kwargs.get('test_case_name', '')
        prefix = f"{test_case_name}_" if test_case_name else ""
        image_path = f"{test_dir}/{prefix}generated_image.png"
        
        self.logger.logger.info(f"💾 Saving image to: {image_path}")
        self.logger.logger.info(f"📊 Image data size: {len(img_bytes)} bytes")
        self.logger.logger.info(f"📁 Target directory: {test_dir}")
        
        try:
            # ディレクトリ作成
            os.makedirs(test_dir, exist_ok=True)
            self.logger.logger.info(f"✅ Directory created/confirmed: {test_dir}")
            
            # ファイル保存
            with open(image_path, "wb") as f:
                f.write(img_bytes)
            
            # 保存確認
            if os.path.exists(image_path):
                saved_size = os.path.getsize(image_path)
                self.logger.logger.info(f"✅ Image saved successfully: {saved_size} bytes")
                self.logger.logger.info(f"📁 Final path: {image_path}")
            else:
                self.logger.logger.error(f"❌ Image file not found after save attempt")
                
        except Exception as save_error:
            self.logger.logger.error(f"❌ Error saving image: {str(save_error)}")
            raise
        
        return image_path
    
    def _save_generated_music(self, original_music_path: str, **kwargs) -> str:
        """生成音楽の保存"""
        # 保存先ディレクトリの決定
        custom_timestamp = kwargs.get('custom_timestamp')
        if custom_timestamp:
            test_dir = f"{self.processing_config.output_dir}/test_result_{custom_timestamp}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_dir = f"{self.processing_config.output_dir}/test_result_{timestamp}"
        
        # ファイル名の決定
        test_case_name = kwargs.get('test_case_name', '')
        prefix = f"{test_case_name}_" if test_case_name else ""
        music_path = f"{test_dir}/{prefix}generated_music.wav"
        
        # 移動
        os.makedirs(test_dir, exist_ok=True)
        shutil.move(original_music_path, music_path)
        
        return music_path


    def text2speech(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        テキストを音声に変換する関数
        
        Args:
            text: 音声に変換するテキスト（英語前提）
            **kwargs: 追加パラメータ
                - custom_timestamp: カスタムタイムスタンプ
                - test_case_name: テストケース名
                - output_filename: 出力ファイル名（拡張子なし）
        
        Returns:
            音声生成結果の辞書
        """
        self.logger.logger.info(f"🎤 Starting text-to-speech conversion")
        self.logger.logger.info(f"📝 Text: {text[:100]}{'...' if len(text) > 100 else ''}")
        
        # TTSサーバー確認
        if not self._check_tts_server():
            return {
                'success': False,
                'error': 'TTS server is not available',
                'audio_path': None
            }
        
        start_time = time.time()
        
        try:
            # TTSサーバーにリクエスト送信
            params = {"text": text}
            response = requests.get(
                f"{self.api_config.tts_uri}/api/tts",
                params=params,
                timeout=60
            )
            
            if response.status_code == 200:
                generation_time = time.time() - start_time
                
                # 音声ファイルの保存
                audio_path = self._save_generated_audio(response.content, **kwargs)
                audio_size = len(response.content)
                
                self.logger.logger.info(f"✅ TTS generation successful")
                self.logger.logger.info(f"📁 Audio saved to: {audio_path}")
                self.logger.logger.info(f"⏱️ Generation time: {generation_time:.1f} seconds")
                self.logger.logger.info(f"📊 File size: {audio_size / 1024:.1f}KB")
                
                return {
                    'success': True,
                    'audio_path': audio_path,
                    'audio_filename': os.path.basename(audio_path),
                    'audio_size': audio_size,
                    'generation_time': generation_time,
                    'text_length': len(text),
                    'error': None
                }
            else:
                error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                self.logger.logger.error(f"❌ TTS request failed: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'audio_path': None
                }
                
        except requests.exceptions.Timeout:
            error_msg = 'TTS request timeout (60 seconds)'
            self.logger.logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'audio_path': None
            }
        except Exception as e:
            error_msg = f'TTS generation error: {str(e)}'
            self.logger.logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'audio_path': None
            }
    
    def _save_generated_audio(self, audio_bytes: bytes, **kwargs) -> str:
        """生成音声の保存"""
        # 保存先ディレクトリの決定
        custom_timestamp = kwargs.get('custom_timestamp')
        if custom_timestamp:
            test_dir = f"{self.processing_config.output_dir}/test_result_{custom_timestamp}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_dir = f"{self.processing_config.output_dir}/test_result_{timestamp}"
        
        # ファイル名の決定
        test_case_name = kwargs.get('test_case_name', '')
        output_filename = kwargs.get('output_filename', 'generated_speech')
        
        prefix = f"{test_case_name}_" if test_case_name else ""
        audio_path = f"{test_dir}/{prefix}{output_filename}.wav"
        
        # 保存
        os.makedirs(test_dir, exist_ok=True)
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        
        return audio_path


# ========================================
# 統一エントリーポイント関数
# ========================================

def generate_content(
    sis_data: Dict[str, Any],
    content_type: str,
    api_config: Optional[APIConfig] = None,
    processing_config: Optional[ProcessingConfig] = None,
    generation_config: Optional[GenerationConfig] = None,
    logger: Optional[StructuredLogger] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    統合されたコンテンツ生成関数
    
    Args:
        sis_data: SIS構造データ
        content_type: コンテンツタイプ ('image' | 'music' | 'text')
        api_config: API設定
        processing_config: 処理設定
        generation_config: 生成設定
        logger: ロガー
        **kwargs: 追加パラメータ
    
    Returns:
        統一された戻り値辞書
    """
    generator = ContentGenerator(api_config, processing_config, generation_config, logger)
    result = generator.process(sis_data, content_type, **kwargs)
    return result.to_dict()


# ========================================
# 既存関数（後方互換性のため）
# ========================================

def generate_content_with_unsloth(
    sis_data: Dict[str, Any], 
    api_uri: str, 
    content_type: str, 
    **kwargs
) -> Dict[str, Any]:
    """
    既存関数名での互換性関数
    """
    api_config = APIConfig(unsloth_uri=api_uri)
    return generate_content(sis_data, content_type, api_config, **kwargs)


def load_sis_data(sis_file_path: str) -> Optional[Dict[str, Any]]:
    """SIS データのロード"""
    try:
        with open(sis_file_path, 'r', encoding='utf-8') as f:
            sis_data = json.load(f)
        print(f"✅ SIS data loaded from: {sis_file_path}")
        return sis_data
    except FileNotFoundError:
        print(f"❌ SIS file not found: {sis_file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in SIS file: {e}")
        return None
    except Exception as e:
        print(f"❌ Error loading SIS file: {e}")
        return None


# ========================================
# メイン関数
# ========================================

def main():
    parser = argparse.ArgumentParser(description='Generate content from SIS data using unified approach')
    parser.add_argument('--mode', choices=['image', 'music', 'text', 'tts'], required=True,
                       help='Type of content to generate')
    parser.add_argument('--api_uri', default='http://unsloth:5007',
                       help='Unsloth API URI (default: http://unsloth:5007)')
    parser.add_argument('--sd_api_uri', default='http://sd:7860',
                       help='Stable Diffusion API URI (default: http://sd:7860)')
    parser.add_argument('--music_api_uri', default='http://music:5003',
                       help='Music API URI (default: http://music:5003)')
    parser.add_argument('--tts_api_uri', default='http://tts:5002',
                       help='TTS API URI (default: http://tts:5002)')
    parser.add_argument('--sis_file', default='/app/shared/sis/test_sis.json',
                       help='Path to SIS JSON file')
    
    # Image-specific arguments
    parser.add_argument('--width', type=int, default=1024,
                       help='Image width (default: 1024)')
    parser.add_argument('--height', type=int, default=768,
                       help='Image height (default: 768)')
    
    # Music-specific arguments
    parser.add_argument('--duration', type=int, default=30,
                       help='Music duration in seconds (default: 30)')
    
    # Text-specific arguments
    parser.add_argument('--word_count', type=int, default=50,
                       help='Target word count for story (default: 50)')
    
    # TTS-specific arguments
    parser.add_argument('--text_input', type=str,
                       help='Direct text input for TTS (overrides SIS-based text generation)')
    parser.add_argument('--output_filename', type=str, default='generated_speech',
                       help='Output filename for TTS audio (without extension, default: generated_speech)')
    
    parser.add_argument('--custom_timestamp', type=str,
                       help='Custom timestamp for directory naming (for batch testing)')
    parser.add_argument('--test_case_name', type=str,
                       help='Test case name prefix for file naming (for batch testing)')
    
    args = parser.parse_args()
    
    print(f"🎯 SIS to {args.mode.title()} Generation (Unified)")
    print("=" * 50)
    
    # 設定の作成
    api_config = APIConfig(
        unsloth_uri=args.api_uri,
        sd_uri=args.sd_api_uri,
        music_uri=args.music_api_uri,
        tts_uri=args.tts_api_uri
    )
    
    generation_config = GenerationConfig(
        image_width=args.width,
        image_height=args.height,
        music_duration=args.duration,
        text_word_count=args.word_count
    )
    
    # SIS データの読み込み
    print(f"\n📄 Loading SIS data...")
    sis_data = load_sis_data(args.sis_file)
    if not sis_data and args.mode != 'tts':
        return False
    
    # TTSモードの場合、直接テキスト入力があればSISデータは不要
    if args.mode == 'tts' and args.text_input:
        sis_data = None  # SISデータを使わない
    elif not sis_data:
        return False
    
    # SIS データのサマリー表示（SISデータがある場合のみ）
    if sis_data:
        print(f"   Summary: {sis_data.get('summary', 'N/A')}")
        print(f"   Emotions: {', '.join(sis_data.get('emotions', []))}")
        print(f"   Mood: {sis_data.get('mood', 'N/A')}")
    
    # コンテンツ生成
    print(f"\n🎨 Generating {args.mode}...")
    
    # TTSモードの特別処理
    if args.mode == 'tts':
        generator = ContentGenerator(api_config, generation_config=generation_config)
        
        if args.text_input:
            # 直接テキスト入力
            text_to_convert = args.text_input
            print(f"📝 Using direct text input: {text_to_convert[:100]}{'...' if len(text_to_convert) > 100 else ''}")
        else:
            # SISからテキスト生成
            print(f"📝 Generating text from SIS data first...")
            text_result = generator.process(sis_data, 'text', **kwargs)
            if not text_result.success:
                print(f"❌ Text generation failed: {text_result.error}")
                return False
            text_to_convert = text_result.data['generated_text']
            print(f"📝 Generated text: {text_to_convert[:100]}{'...' if len(text_to_convert) > 100 else ''}")
        
        # TTS変換
        tts_kwargs = {
            'custom_timestamp': args.custom_timestamp,
            'test_case_name': args.test_case_name,
            'output_filename': args.output_filename
        }
        tts_result = generator.text2speech(text_to_convert, **tts_kwargs)
        
        if tts_result['success']:
            print(f"\n✅ TTS generation completed!")
            print(f"📁 Audio saved to: {tts_result['audio_path']}")
            print(f"⏱️ Generation time: {tts_result['generation_time']:.1f} seconds")
            print(f"📊 File size: {tts_result['audio_size'] / 1024:.1f}KB")
            print(f"📝 Text length: {tts_result['text_length']} characters")
            print(f"\n🎵 How to play:")
            print(f"  aplay {tts_result['audio_path']}")
            return True
        else:
            print(f"\n❌ TTS generation failed: {tts_result['error']}")
            return False
    
    # 従来のコンテンツ生成処理
    kwargs = {
        'width': args.width,
        'height': args.height,
        'duration': args.duration,
        'word_count': args.word_count,
        'custom_timestamp': args.custom_timestamp,
        'test_case_name': args.test_case_name
    }
    
    result = generate_content(
        sis_data, 
        args.mode, 
        api_config, 
        generation_config=generation_config,
        **kwargs
    )
    
    if result['success']:
        print(f"\n✅ {args.mode.title()} generation completed!")
        print(f"📁 Output saved to: {result['output_path']}")
        print(f"⏱️ Generation time: {result['metadata']['processing_time']:.1f} seconds")
        print(f"📝 Content length: {len(result['generated_text'])} characters")
        
        # 追加生成結果の表示
        if result.get('image_result'):
            img_result = result['image_result']
            if img_result['success']:
                print(f"🖼️ Image saved to: {img_result['image_path']}")
                print(f"⏱️ Image generation time: {img_result['generation_time']:.1f} seconds")
            else:
                print(f"❌ Image generation failed: {img_result['error']}")
        
        if result.get('music_result'):
            music_result = result['music_result']
            if music_result['success']:
                print(f"🎵 Music saved to: {music_result['music_path']}")
                print(f"⏱️ Music generation time: {music_result['generation_time']:.1f} seconds")
                print(f"📊 File size: {music_result['music_size'] / 1024:.1f}KB")
                print(f"🎛️ Sample rate: {music_result['sample_rate']} Hz")
            else:
                print(f"❌ Music generation failed: {music_result['error']}")
        
        # プレビュー表示
        preview = result['generated_text'][:200]
        if len(result['generated_text']) > 200:
            preview += "..."
        print(f"\n📖 Preview:\n{preview}")
        
        return True
    else:
        print(f"\n❌ {args.mode.title()} generation failed: {result['error']}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
