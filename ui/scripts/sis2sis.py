#!/usr/bin/env python3
"""
SIS to SIS Transformation Script

SIS間の相互変換機能
- scene2story(): 複数のSceneSISからStorySISを生成
- story2scene(): StorySISのscene_blueprintsから各SceneSISを生成

Author: Generated from GeNarrative Pipeline
Created: December 22, 2025
"""
import os
import sys
import json
import argparse
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# 共通基盤のインポート
from common_base import (
    APIConfig, ProcessingConfig, GenerationConfig,
    ContentProcessor, ProcessingResult, StructuredLogger,
    GeNarrativeError, FileProcessingError, ServerConnectionError, 
    ModelNotLoadedError, ContentTypeError, ValidationError,
    create_standard_response
)


# ========================================
# SIS変換プロセッサクラス
# ========================================

class SISTransformer(ContentProcessor):
    """統一されたSIS変換クラス"""
    
    def __init__(self, 
                 api_config: Optional[APIConfig] = None,
                 processing_config: Optional[ProcessingConfig] = None,
                 logger: Optional[StructuredLogger] = None):
        super().__init__(api_config, processing_config, logger)
    
    def process(self, data: Any, mode: str, **kwargs) -> ProcessingResult:
        """統一された処理エントリーポイント（抽象メソッドの実装）"""
        if mode == 'scene2story':
            return self.scenes_to_story(data, **kwargs)
        elif mode == 'story2scene':
            return self.story_to_scenes(data, **kwargs)
        else:
            return ProcessingResult(
                success=False,
                data={},
                error=f"Unsupported mode: {mode}. Use 'scene2story' or 'story2scene'",
                metadata={'mode': mode}
            )
    
    def scenes_to_story(self, scene_sis_list: List[Dict[str, Any]], **kwargs) -> ProcessingResult:
        """複数のSceneSISからStorySISを生成"""
        function_name = 'scene2story'
        
        try:
            self.logger.info(f"Starting {function_name}", extra={
                'function': function_name,
                'scene_count': len(scene_sis_list)
            })
            
            # サーバーとモデルの確認
            self._check_server_and_model()
            
            # StorySISスキーマの取得
            story_sis_schema = self._story_sis_schema()
            
            # プロンプト作成
            prompt = self._create_scenes_to_story_prompt(scene_sis_list)
            
            # 計測開始
            req_start = time.time()
            
            # Structured Output 呼び出し
            story_sis_json, raw_text = self._ollama_chat_structured(
                messages=[
                    {'role': 'system', 'content': 'You are a precise JSON generator for story structure. Output only valid JSON that matches the schema.'},
                    {'role': 'user', 'content': prompt}
                ],
                schema=story_sis_schema
            )
            
            req_duration = time.time() - req_start
            
            self.logger.info(f"{function_name} completed successfully", extra={
                'function': function_name,
                'duration_sec': round(req_duration, 4)
            })
            
            return ProcessingResult(
                success=True,
                data={'story_sis': story_sis_json, 'content': raw_text, 'content_format': 'json', 'prompt': prompt},
                error=None,
                metadata={
                    'function': function_name,
                    'scene_count': len(scene_sis_list),
                    'request_duration_sec': round(req_duration, 4),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            # エラーメッセージをクリーンアップ（トレースバック情報と特殊文字を除外）
            error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
            # 三重引用符をエスケープ
            error_msg = error_msg.replace('"""', '\\"\\"\\"').replace("'''", "\\'\\'\\'")[:500]
            self.logger.error(f"Error in {function_name}", extra={
                'function': function_name,
                'error': error_msg
            })
            return ProcessingResult(
                success=False,
                data={},
                error=error_msg,
                metadata={'function': function_name}
            )
    
    def story_to_scene(self, story_sis: Dict[str, Any], blueprint: Dict[str, Any], blueprint_index: int = 0, **kwargs) -> ProcessingResult:
        """StorySISの1つのblueprintから1つのSceneSISを生成"""
        function_name = 'story2scene_single'
        
        try:
            self.logger.info(f"Starting {function_name}", extra={
                'function': function_name,
                'story_id': story_sis.get('story_id', 'unknown'),
                'blueprint_index': blueprint_index,
                'scene_type': blueprint.get('scene_type', 'unknown')
            })
            
            # サーバーとモデルの確認
            self._check_server_and_model()
            
            # SceneSISスキーマの取得
            scene_sis_schema = self._scene_sis_schema()
            
            # プロンプト作成
            prompt = self._create_story_to_scene_prompt(story_sis, blueprint, blueprint_index)
            
            # 計測開始
            req_start = time.time()
            
            # Structured Output 呼び出し
            scene_sis_json, raw_text = self._ollama_chat_structured(
                messages=[
                    {'role': 'system', 'content': 'You are a precise JSON generator for scene structure. Output only valid JSON that matches the schema.'},
                    {'role': 'user', 'content': prompt}
                ],
                schema=scene_sis_schema
            )
            
            req_duration = time.time() - req_start

            scene_sis_json, applied_defaults = self._ensure_scene_sis_structure(
                scene_sis_json, story_sis, blueprint
            )
            fallback_applied = len(applied_defaults) > 0
            if fallback_applied:
                self.logger.warning(
                    "SceneSIS response missing fields; applied fallback defaults",
                    extra={
                        'function': function_name,
                        'blueprint_index': blueprint_index,
                        'applied_defaults': applied_defaults
                    }
                )
            
            self.logger.info(f"{function_name} completed successfully", extra={
                'function': function_name,
                'duration_sec': round(req_duration, 4)
            })
            
            return ProcessingResult(
                success=True,
                data={
                    'scene_sis': scene_sis_json,
                    'raw_text': raw_text,
                    'prompt': prompt,
                    'blueprint_index': blueprint_index,
                    'duration_sec': round(req_duration, 4),
                    'fallback_applied': fallback_applied,
                    'fallback_details': applied_defaults
                },
                error=None,
                metadata={
                    'function': function_name,
                    'story_id': story_sis.get('story_id', 'unknown'),
                    'blueprint_index': blueprint_index,
                    'scene_type': blueprint.get('scene_type', 'unknown'),
                    'request_duration_sec': round(req_duration, 4),
                    'timestamp': datetime.now().isoformat(),
                    'fallback_applied': fallback_applied
                }
            )
            
        except Exception as e:
            # エラーメッセージをクリーンアップ（トレースバック情報を除外）
            error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
            self.logger.error(f"Error in {function_name}", extra={
                'function': function_name,
                'error': error_msg
            })
            return ProcessingResult(
                success=False,
                data={},
                error=error_msg,
                metadata={'function': function_name, 'blueprint_index': blueprint_index}
            )
    
    def story_to_scenes(self, story_sis: Dict[str, Any], **kwargs) -> ProcessingResult:
        """StorySISのscene_blueprintsから各SceneSISを生成（内部でstory_to_sceneを呼び出し）"""
        function_name = 'story2scene'
        
        try:
            self.logger.info(f"Starting {function_name}", extra={
                'function': function_name,
                'story_id': story_sis.get('story_id', 'unknown')
            })
            
            # scene_blueprintsの取得
            scene_blueprints = story_sis.get('scene_blueprints', [])
            if not scene_blueprints:
                raise ValidationError('StorySIS does not contain scene_blueprints')
            
            # 各blueprintからSceneSISを生成
            generated_scenes = []
            total_duration = 0
            
            for idx, blueprint in enumerate(scene_blueprints):
                self.logger.info(f"Generating scene {idx+1}/{len(scene_blueprints)}", extra={
                    'function': function_name,
                    'scene_index': idx,
                    'scene_type': blueprint.get('scene_type', 'unknown')
                })
                
                # 単一シーン生成を呼び出し
                result = self.story_to_scene(story_sis, blueprint, idx, **kwargs)
                
                if result.success:
                    scene_data = {
                        'scene_sis': result.data.get('scene_sis'),
                        'raw_text': result.data.get('raw_text'),
                        'prompt': result.data.get('prompt'),
                        'blueprint_index': idx,
                        'duration_sec': result.data.get('duration_sec', 0)
                    }
                    generated_scenes.append(scene_data)
                    total_duration += result.data.get('duration_sec', 0)
                else:
                    self.logger.error(f"Failed to generate scene {idx+1}: {result.error}")
            
            if not generated_scenes:
                raise ValidationError('Failed to generate any scenes')
            
            self.logger.info(f"{function_name} completed successfully", extra={
                'function': function_name,
                'total_scenes': len(generated_scenes),
                'total_duration_sec': round(total_duration, 4)
            })
            
            return ProcessingResult(
                success=True,
                data={'scenes': generated_scenes, 'scene_count': len(generated_scenes)},
                error=None,
                metadata={
                    'function': function_name,
                    'story_id': story_sis.get('story_id', 'unknown'),
                    'scene_count': len(generated_scenes),
                    'total_duration_sec': round(total_duration, 4),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            # エラーメッセージをクリーンアップ（トレースバック情報と特殊文字を除外）
            error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
            # 三重引用符をエスケープ
            error_msg = error_msg.replace('"""', '\\"\\"\\"').replace("'''", "\\'\\'\\'")[:500]
            self.logger.error(f"Error in {function_name}", extra={
                'function': function_name,
                'error': error_msg
            })
            return ProcessingResult(
                success=False,
                data={},
                error=error_msg,
                metadata={'function': function_name}
            )
    
    def _create_scenes_to_story_prompt(self, scene_sis_list: List[Dict[str, Any]]) -> str:
        """SceneSISリストからStorySIS生成用プロンプトを作成"""
        scenes_json = json.dumps(scene_sis_list, indent=2, ensure_ascii=False)
        
        prompt = f"""Analyze the following SceneSIS data and generate a complete StorySIS JSON object.

INPUT SCENES:
{scenes_json}

TASK:
1. Analyze the scenes to determine the appropriate story_type (e.g., "three_act", "kishotenketsu", "attempts", "catalog")
2. Extract common themes and overall story meaning
3. Determine consistent text/visual/audio style policies across scenes
4. Generate scene_blueprints that reference the provided scenes
5. Create a complete StorySIS JSON object

REQUIREMENTS:
- Include ALL required fields: sis_type, story_id, title, summary, semantics, story_type, scene_blueprints
- Generate a new UUID for story_id
- In semantics.common, extract themes and descriptions that apply to the whole story
- In scene_blueprints, create entries that match the input scenes (use scene_type like "ki", "sho", "ten", "ketsu" or "setup", "conflict", "resolution")
- Output ONLY valid JSON (no prose, no comments)
"""
        return prompt
    
    def _create_story_to_scene_prompt(self, story_sis: Dict[str, Any], blueprint: Dict[str, Any], index: int) -> str:
        """StorySISとblueprintからSceneSIS生成用プロンプトを作成"""
        story_context = {
            'title': story_sis.get('title', ''),
            'summary': story_sis.get('summary', ''),
            'story_type': story_sis.get('story_type', ''),
            'semantics': story_sis.get('semantics', {})
        }
        
        story_json = json.dumps(story_context, indent=2, ensure_ascii=False)
        blueprint_json = json.dumps(blueprint, indent=2, ensure_ascii=False)
        
        prompt = f"""Generate a complete SceneSIS JSON object based on the provided story context and scene blueprint.

STORY CONTEXT:
{story_json}

SCENE BLUEPRINT (#{index+1}):
{blueprint_json}

TASK:
Generate a detailed SceneSIS that:
1. Matches the scene_type specified in the blueprint
2. Inherits style policies from the story's semantics
3. Contains rich semantic information (characters, location, time, weather, objects, descriptions)
4. Provides specific visual/text/audio generation policies suitable for this scene

REQUIREMENTS:
- Include ALL required fields: sis_type, scene_id, summary, scene_type, semantics
- Generate a new UUID for scene_id
- In semantics.common, provide detailed scene-specific information
- Include at least one character with name, traits, and visual description
- Include at least one object with name and colors
- Provide specific style guidance in semantics.text/visual/audio
- Output ONLY valid JSON (no prose, no comments)
"""
        return prompt

    def _ensure_scene_sis_structure(
        self,
        scene_sis_json: Optional[Dict[str, Any]],
        story_sis: Dict[str, Any],
        blueprint: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """SceneSISの必須フィールドを保証し、欠落時はフォールバック値を補完"""
        applied_defaults: List[str] = []
        scene = scene_sis_json if isinstance(scene_sis_json, dict) else {}
        if scene is not scene_sis_json:
            applied_defaults.append('scene_root')

        def is_missing(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, str):
                return value.strip() == ''
            if isinstance(value, (list, dict)):
                return len(value) == 0
            return False

        def ensure_value(target: Dict[str, Any], key: str, value_provider, label: str):
            if key not in target or is_missing(target[key]):
                target[key] = value_provider() if callable(value_provider) else value_provider
                applied_defaults.append(label)

        default_summary = blueprint.get('summary') or story_sis.get('summary') or 'Scene summary pending.'
        ensure_value(scene, 'sis_type', lambda: 'scene', 'sis_type')
        ensure_value(scene, 'scene_id', lambda: str(uuid.uuid4()), 'scene_id')
        ensure_value(scene, 'scene_type', lambda: blueprint.get('scene_type', 'unknown'), 'scene_type')
        ensure_value(scene, 'summary', lambda: default_summary, 'summary')

        semantics = scene.get('semantics') if isinstance(scene.get('semantics'), dict) else {}
        if semantics is not scene.get('semantics'):
            applied_defaults.append('semantics')

        story_semantics = story_sis.get('semantics', {}) if isinstance(story_sis.get('semantics'), dict) else {}
        story_common = story_semantics.get('common', {}) if isinstance(story_semantics.get('common'), dict) else {}
        story_text = story_semantics.get('text', {}) if isinstance(story_semantics.get('text'), dict) else {}
        story_visual = story_semantics.get('visual', {}) if isinstance(story_semantics.get('visual'), dict) else {}
        story_audio = story_semantics.get('audio', {}) if isinstance(story_semantics.get('audio'), dict) else {}

        semantics_common = semantics.get('common') if isinstance(semantics.get('common'), dict) else {}
        if semantics_common is not semantics.get('common'):
            applied_defaults.append('semantics.common')
        semantics_text = semantics.get('text') if isinstance(semantics.get('text'), dict) else {}
        if semantics_text is not semantics.get('text'):
            applied_defaults.append('semantics.text')
        semantics_visual = semantics.get('visual') if isinstance(semantics.get('visual'), dict) else {}
        if semantics_visual is not semantics.get('visual'):
            applied_defaults.append('semantics.visual')
        semantics_audio = semantics.get('audio') if isinstance(semantics.get('audio'), dict) else {}
        if semantics_audio is not semantics.get('audio'):
            applied_defaults.append('semantics.audio')

        ensure_value(semantics_common, 'mood', lambda: story_common.get('mood', blueprint.get('scene_type', 'neutral')),
                     'semantics.common.mood')
        ensure_value(semantics_common, 'location', lambda: story_common.get('location', 'unspecified location'),
                     'semantics.common.location')
        ensure_value(semantics_common, 'time', lambda: story_common.get('time', 'unspecified time'),
                     'semantics.common.time')
        ensure_value(semantics_common, 'weather', lambda: story_common.get('weather', 'unspecified weather'),
                     'semantics.common.weather')
        ensure_value(semantics_common, 'descriptions', lambda: [default_summary], 'semantics.common.descriptions')

        story_characters = []
        if isinstance(story_common.get('characters'), list) and story_common['characters']:
            story_characters = story_common['characters']
        if is_missing(semantics_common.get('characters')):
            base_character = story_characters[0] if story_characters else {}
            semantics_common['characters'] = [{
                'name': base_character.get('name', 'Protagonist'),
                'traits': base_character.get('traits', ['curious']),
                'visual': base_character.get('visual', {
                    'hair': 'unspecified hair',
                    'clothes': 'unspecified clothes'
                })
            }]
            applied_defaults.append('semantics.common.characters')

        if is_missing(semantics_common.get('objects')):
            semantics_common['objects'] = [{
                'name': 'key_object',
                'colors': ['neutral']
            }]
            applied_defaults.append('semantics.common.objects')

        ensure_value(semantics_text, 'style', lambda: story_text.get('style', 'descriptive narrative'),
                     'semantics.text.style')
        ensure_value(semantics_text, 'language', lambda: story_text.get('language', 'Japanese'),
                     'semantics.text.language')
        ensure_value(semantics_text, 'tone', lambda: story_text.get('tone', 'neutral'),
                     'semantics.text.tone')
        ensure_value(semantics_text, 'point_of_view', lambda: story_text.get('point_of_view', 'third'),
                     'semantics.text.point_of_view')

        ensure_value(semantics_visual, 'style', lambda: story_visual.get('style', 'cinematic realism'),
                     'semantics.visual.style')
        ensure_value(semantics_visual, 'composition', lambda: story_visual.get('composition', 'wide shot'),
                     'semantics.visual.composition')
        ensure_value(semantics_visual, 'lighting', lambda: story_visual.get('lighting', 'natural soft light'),
                     'semantics.visual.lighting')
        ensure_value(semantics_visual, 'perspective', lambda: story_visual.get('perspective', 'eye level'),
                     'semantics.visual.perspective')

        ensure_value(semantics_audio, 'genre', lambda: story_audio.get('genre', 'ambient orchestral'),
                     'semantics.audio.genre')
        ensure_value(semantics_audio, 'tempo', lambda: story_audio.get('tempo', 'slow'),
                     'semantics.audio.tempo')
        ensure_value(semantics_audio, 'instruments', lambda: story_audio.get('instruments', ['piano', 'strings']),
                     'semantics.audio.instruments')

        semantics['common'] = semantics_common
        semantics['text'] = semantics_text
        semantics['visual'] = semantics_visual
        semantics['audio'] = semantics_audio
        scene['semantics'] = semantics

        return scene, applied_defaults
    
    def _check_server_and_model(self) -> None:
        """Ollamaサーバーとモデルの確認"""
        try:
            import requests
            response = requests.get(
                f"{self.api_config.ollama_uri}/api/tags",
                timeout=5
            )
            if response.status_code != 200:
                raise ServerConnectionError(
                    f"Ollama server returned status {response.status_code}",
                    server_type='ollama'
                )
            
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            
            if not any(self.api_config.ollama_model in name for name in model_names):
                raise ModelNotLoadedError(
                    f"Model {self.api_config.ollama_model} not found. Available models: {model_names}",
                    model_name=self.api_config.ollama_model
                )
                
        except requests.exceptions.ConnectionError:
            raise ServerConnectionError(
                f"Cannot connect to Ollama server at {self.api_config.ollama_uri}",
                server_type='ollama'
            )
    
    def _ollama_chat_structured(self, messages: list, schema: Dict[str, Any], images: Optional[list] = None) -> Tuple[Dict[str, Any], str]:
        """Ollama Structured Output を使用したチャット呼び出し"""
        import requests
        
        payload = {
            'model': self.api_config.ollama_model,
            'messages': messages,
            'stream': False,
            'format': schema,
            'options': {
                'num_predict': 4096,  # より長いレスポンスを許可
                'temperature': 0.7
            }
        }
        
        if images:
            for msg in payload['messages']:
                if msg['role'] == 'user':
                    msg['images'] = images
        
        try:
            response = requests.post(
                f"{self.api_config.ollama_uri}/api/chat",
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            
            data = response.json()
            content = data.get('message', {}).get('content', '')
            
            if not content or content.strip() == '':
                raise ValidationError('Ollama returned empty content')
            
            # デバッグ出力: 生のレスポンスの最初の500文字
            self.logger.debug(f"Ollama raw response (first 500 chars): {content[:500]}")
            
            try:
                parsed_json = json.loads(content)
                return parsed_json, content
            except json.JSONDecodeError as e:
                # より詳細なエラーメッセージ
                error_msg = f'Failed to parse JSON from Ollama response: {e}'
                self.logger.error(f"{error_msg}\nRaw response preview: {content[:500]}")
                raise ValidationError(error_msg)
                
        except requests.exceptions.RequestException as e:
            raise ServerConnectionError(f'Ollama API request failed: {e}', server_type='ollama')
    
    def _story_sis_schema(self) -> Dict[str, Any]:
        """StorySISのJSONスキーマを返す"""
        # StorySIS_semantics.jsonを読み込む
        schema_path = Path(__file__).parent / 'schemas' / 'StorySIS_semantics.json'
        
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
                "required": ["common"]
            }
        
        return {
            "type": "object",
            "properties": {
                "sis_type": {
                    "type": "string",
                    "const": "story",
                    "description": "Must be 'story'"
                },
                "story_id": {
                    "type": "string",
                    "description": "UUID for this story"
                },
                "title": {
                    "type": "string",
                    "description": "Story title"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the story"
                },
                "semantics": semantics_schema,
                "story_type": {
                    "type": "string",
                    "enum": ["three_act", "kishotenketsu", "attempts", "catalog", "circular"],
                    "description": "Story structure type"
                },
                "scene_blueprints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "scene_type": {"type": "string"},
                            "summary": {"type": "string"}
                        },
                        "required": ["scene_type", "summary"]
                    },
                    "description": "Scene design blueprints"
                }
            },
            "required": ["sis_type", "story_id", "title", "summary", "semantics", "story_type", "scene_blueprints"]
        }
    
    def _scene_sis_schema(self) -> Dict[str, Any]:
        """SceneSISのJSONスキーマを返す"""
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
                    "description": "UUID for this scene"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what happens in this scene"
                },
                "scene_type": {
                    "type": "string",
                    "description": "Scene type (e.g., 'ki', 'sho', 'ten', 'ketsu', 'setup', 'conflict', 'resolution')"
                },
                "semantics": semantics_schema
            },
            "required": ["sis_type", "scene_id", "summary", "scene_type", "semantics"]
        }


# ========================================
# 統一エントリーポイント関数
# ========================================

def scene2story(
    scene_sis_list: List[Dict[str, Any]],
    api_config: Optional[APIConfig] = None,
    processing_config: Optional[ProcessingConfig] = None,
    logger: Optional[StructuredLogger] = None
) -> Dict[str, Any]:
    """
    複数のSceneSISからStorySISを生成
    
    Args:
        scene_sis_list: SceneSISのリスト
        api_config: API設定
        processing_config: 処理設定
        logger: ロガー
    
    Returns:
        統一された戻り値辞書
    """
    transformer = SISTransformer(api_config, processing_config, logger)
    result = transformer.scenes_to_story(scene_sis_list)
    return result.to_dict()


def story2scene(
    story_sis: Dict[str, Any],
    api_config: Optional[APIConfig] = None,
    processing_config: Optional[ProcessingConfig] = None,
    logger: Optional[StructuredLogger] = None
) -> Dict[str, Any]:
    """
    StorySISのscene_blueprintsから各SceneSISを生成
    
    Args:
        story_sis: StorySISデータ
        api_config: API設定
        processing_config: 処理設定
        logger: ロガー
    
    Returns:
        統一された戻り値辞書
    """
    transformer = SISTransformer(api_config, processing_config, logger)
    result = transformer.story_to_scenes(story_sis)
    return result.to_dict()


def story2scene_single(
    story_sis: Dict[str, Any],
    blueprint: Dict[str, Any],
    blueprint_index: int = 0,
    api_config: Optional[APIConfig] = None,
    processing_config: Optional[ProcessingConfig] = None,
    logger: Optional[StructuredLogger] = None
) -> Dict[str, Any]:
    """
    StorySISの1つのblueprintから1つのSceneSISを生成
    
    Args:
        story_sis: StorySISデータ
        blueprint: scene_blueprintの1要素
        blueprint_index: blueprintのインデックス
        api_config: API設定
        processing_config: 処理設定
        logger: ロガー
    
    Returns:
        統一された戻り値辞書
    """
    transformer = SISTransformer(api_config, processing_config, logger)
    result = transformer.story_to_scene(story_sis, blueprint, blueprint_index)
    return result.to_dict()


# ========================================
# ユーティリティ関数
# ========================================

def load_scene_sis_files(file_paths: List[str]) -> List[Dict[str, Any]]:
    """複数のSceneSISファイルを読み込む"""
    scenes = []
    for path in file_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                scene_data = json.load(f)
                scenes.append(scene_data)
        except Exception as e:
            print(f"⚠️  Failed to load {path}: {e}")
    return scenes


def load_story_sis_file(file_path: str) -> Optional[Dict[str, Any]]:
    """StorySISファイルを読み込む"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {file_path}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return None


def save_sis_to_file(sis_data: Dict[str, Any], output_path: str) -> bool:
    """SISデータをファイルに保存"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sis_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved to: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to save {output_path}: {e}")
        return False


# ========================================
# メイン関数
# ========================================

def main():
    parser = argparse.ArgumentParser(description='Transform SIS data (Scene ↔ Story)')
    parser.add_argument('--mode', choices=['scene2story', 'story2scene'], required=True,
                       help='Transformation mode')
    parser.add_argument('--ollama_uri', default='http://ollama:11434',
                       help='Ollama API URI (default: http://ollama:11434)')
    parser.add_argument('--ollama_model', default='llama3.2-vision:latest',
                       help='Ollama model name (default: llama3.2-vision:latest)')
    
    # scene2story mode
    parser.add_argument('--scene_files', nargs='+',
                       help='Paths to SceneSIS JSON files (for scene2story mode)')
    parser.add_argument('--output_story', default='/app/shared/sis/generated_story_sis.json',
                       help='Output path for generated StorySIS')
    
    # story2scene mode
    parser.add_argument('--story_file',
                       help='Path to StorySIS JSON file (for story2scene mode)')
    parser.add_argument('--output_dir', default='/app/shared/sis/scenes',
                       help='Output directory for generated SceneSIS files')
    
    args = parser.parse_args()
    
    print(f"🎯 SIS Transformation: {args.mode}")
    print("=" * 50)
    
    # 設定の作成
    api_config = APIConfig(
        ollama_uri=args.ollama_uri,
        ollama_model=args.ollama_model
    )
    
    if args.mode == 'scene2story':
        # SceneSIS → StorySIS
        if not args.scene_files:
            print("❌ Error: --scene_files is required for scene2story mode")
            sys.exit(1)
        
        print(f"\n📄 Loading {len(args.scene_files)} SceneSIS files...")
        scene_sis_list = load_scene_sis_files(args.scene_files)
        
        if not scene_sis_list:
            print("❌ Error: No valid SceneSIS files loaded")
            sys.exit(1)
        
        print(f"✅ Loaded {len(scene_sis_list)} scenes")
        
        print("\n🔄 Generating StorySIS from scenes...")
        result = scene2story(scene_sis_list, api_config)
        
        if result['success']:
            story_sis = result['data']['story_sis']
            print("\n✅ StorySIS generated successfully!")
            print(f"   Title: {story_sis.get('title', 'N/A')}")
            print(f"   Story Type: {story_sis.get('story_type', 'N/A')}")
            print(f"   Scenes: {len(story_sis.get('scene_blueprints', []))}")
            
            # 保存
            save_sis_to_file(story_sis, args.output_story)
        else:
            print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    
    elif args.mode == 'story2scene':
        # StorySIS → SceneSIS
        if not args.story_file:
            print("❌ Error: --story_file is required for story2scene mode")
            sys.exit(1)
        
        print(f"\n📄 Loading StorySIS file...")
        story_sis = load_story_sis_file(args.story_file)
        
        if not story_sis:
            sys.exit(1)
        
        print(f"✅ Loaded StorySIS: {story_sis.get('title', 'N/A')}")
        
        print("\n🔄 Generating SceneSIS files from story...")
        result = story2scene(story_sis, api_config)
        
        if result['success']:
            scenes = result['data']['scenes']
            print(f"\n✅ Generated {len(scenes)} scenes successfully!")
            
            # 保存
            os.makedirs(args.output_dir, exist_ok=True)
            for i, scene_data in enumerate(scenes):
                scene_sis = scene_data['scene_sis']
                scene_id = scene_sis.get('scene_id', f'scene_{i}')
                scene_type = scene_sis.get('scene_type', 'unknown')
                output_path = os.path.join(args.output_dir, f"scene_{i+1:02d}_{scene_type}_{scene_id[:8]}.json")
                save_sis_to_file(scene_sis, output_path)
        else:
            print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
