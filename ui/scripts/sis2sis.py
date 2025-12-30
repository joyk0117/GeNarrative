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
import copy
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from functools import lru_cache
from string import Template
import copy

# 共通基盤のインポート
from common_base import (
    APIConfig, ProcessingConfig, GenerationConfig,
    ContentProcessor, ProcessingResult, StructuredLogger,
    GeNarrativeError, FileProcessingError, ServerConnectionError, 
    ModelNotLoadedError, ContentTypeError, ValidationError,
    create_standard_response
)
# Story type presets aligned with docs/SIS.md §3.3
STORY_TYPE_BLUEPRINTS = {
    "three_act": {
        "overview": "Drama pattern (difficulty → resolution)",
        "scene_types": ["setup", "conflict", "resolution"],
        "scene_type_descriptions": {
            "setup": "Introduce characters, setting, and the initial situation.",
            "conflict": "Escalate problems and obstacles leading to a turning point.",
            "resolution": "Resolve the main conflict and show the new status quo."
        }
    },
    "kishotenketsu": {
        "overview": "Twist/punchline pattern (meaning flips at the end)",
        "scene_types": ["ki", "sho", "ten", "ketsu"],
        "scene_type_descriptions": {
            "ki": "Introduce the situation and characters without strong conflict.",
            "sho": "Develop the situation and deepen relationships or context.",
            "ten": "Introduce an unexpected twist that re-frames earlier scenes.",
            "ketsu": "Conclude by revealing the new meaning after the twist."
        }
    },
    "circular": {
        "overview": "Journey-and-return pattern (leave → change → return)",
        "scene_types": ["home_start", "away", "change", "home_end"],
        "scene_type_descriptions": {
            "home_start": "Show the ordinary world before the journey begins.",
            "away": "Depict the journey into a different place, state, or situation.",
            "change": "Show events that transform the character or situation.",
            "home_end": "Return to the starting point, highlighting what has changed."
        }
    },
    "attempts": {
        "overview": "Multiple-attempts pattern (trial and error)",
        "scene_types": ["problem", "attempt", "result"],
        "scene_type_descriptions": {
            "problem": "Define the main problem or goal that must be solved.",
            "attempt": "Show one or more trials and partial successes or failures.",
            "result": "Reveal the final outcome of the attempts and their consequences."
        }
    },
    "catalog": {
        "overview": "Catalog/introduction pattern (weak ordering)",
        "scene_types": ["intro", "entry", "outro"],
        "scene_type_descriptions": {
            "intro": "Introduce the theme and explain what will be presented.",
            "entry": "Present one catalog item, character, or example at a time.",
            "outro": "Summarise the catalog and restate the overall impression."
        }
    }
}

ALL_SCENE_TYPES = sorted({stype for cfg in STORY_TYPE_BLUEPRINTS.values() for stype in cfg["scene_types"]})

PROMPT_DIR = Path(__file__).parent / 'prompts'


@lru_cache(maxsize=8)
def _load_prompt_template(filename: str) -> Template:
    """Load and cache prompt templates stored under ui/scripts/prompts."""
    template_path = PROMPT_DIR / filename
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    with open(template_path, 'r', encoding='utf-8') as prompt_file:
        return Template(prompt_file.read())


def _generate_story_id() -> str:
    """Generate a story_id without relying on UUID.

    Uses timestamp-based identifier so that the application assigns IDs,
    not the LLM.
    """
    return datetime.now().strftime("story_%Y%m%d_%H%M%S_%f")


def _generate_scene_id() -> str:
    """Generate a scene_id without relying on UUID.

    Uses timestamp-based identifier; final format is an internal detail.
    """
    return datetime.now().strftime("scene_%Y%m%d_%H%M%S_%f")


def _expand_scene_types_for_story_type(story_type: str, scene_count: int) -> List[str]:
    """Expand a story_type's canonical scene_types to the requested count while preserving order.

    Policy (simple, deterministic):
    - If scene_count <= len(base_roles): use the prefix of base_roles.
    - If scene_count > len(base_roles): repeat the "middle" role so the first/last structure remains.
      - three_act: setup + conflict*(n-2) + resolution
      - kishotenketsu: ki + sho*(n-3) + ten + ketsu
      - circular: home_start + away*(n-3) + change + home_end
      - attempts: problem + attempt*(n-2) + result
      - catalog: intro + entry*(n-2) + outro
    """
    if story_type not in STORY_TYPE_BLUEPRINTS:
        raise ValidationError(f"Unknown story_type: {story_type}")
    if not isinstance(scene_count, int) or scene_count < 1:
        raise ValidationError("scene_blueprint_count must be a positive integer")

    base_roles = STORY_TYPE_BLUEPRINTS[story_type].get('scene_types', [])
    if not isinstance(base_roles, list) or not base_roles:
        raise ValidationError(f"story_type {story_type} has no scene_types defined")

    if scene_count <= len(base_roles):
        return list(base_roles[:scene_count])

    policies = {
        'three_act': (['setup'], 'conflict', ['resolution']),
        'kishotenketsu': (['ki'], 'sho', ['ten', 'ketsu']),
        'circular': (['home_start'], 'away', ['change', 'home_end']),
        'attempts': (['problem'], 'attempt', ['result']),
        'catalog': (['intro'], 'entry', ['outro']),
    }

    if story_type in policies:
        prefix, repeat_role, suffix = policies[story_type]
        # For very small counts, respect canonical order via base_roles.
        min_structured = len(prefix) + len(suffix)
        if scene_count <= min_structured:
            return list(base_roles[:scene_count])
        middle_count = scene_count - min_structured
        return list(prefix) + [repeat_role] * middle_count + list(suffix)

    # Fallback: repeat the last role if an unknown story_type is added later.
    return list(base_roles) + [base_roles[-1]] * (scene_count - len(base_roles))


def _expand_scene_types_by_counts(story_type: str, scene_type_counts: Dict[str, int]) -> List[str]:
    """Expand canonical scene_types by per-role counts while preserving order.

    Example (kishotenketsu): {'ki':1,'sho':2,'ten':1,'ketsu':1} -> ['ki','sho','sho','ten','ketsu']

    Rules:
    - Keys must be a subset of the canonical roles for the given story_type.
    - Missing roles default to 1.
    - Counts must be integers >= 1.
    """
    if story_type not in STORY_TYPE_BLUEPRINTS:
        raise ValidationError(f"Unknown story_type: {story_type}")
    if not isinstance(scene_type_counts, dict):
        raise ValidationError("scene_type_counts must be an object")

    base_roles = STORY_TYPE_BLUEPRINTS[story_type].get('scene_types', [])
    if not isinstance(base_roles, list) or not base_roles:
        raise ValidationError(f"story_type {story_type} has no scene_types defined")

    allowed = set(base_roles)
    for key, value in scene_type_counts.items():
        if key not in allowed:
            raise ValidationError(
                f"scene_type_counts contains invalid role '{key}' for story_type '{story_type}'"
            )
        if not isinstance(value, int):
            raise ValidationError(f"scene_type_counts['{key}'] must be an integer")
        if value < 1:
            raise ValidationError(f"scene_type_counts['{key}'] must be >= 1")

    expanded: List[str] = []
    for role in base_roles:
        count = scene_type_counts.get(role, 1)
        expanded.extend([role] * count)
    return expanded


def _constrain_story_sis_schema_for_story_type(
    base_schema: Dict[str, Any],
    story_type: str,
    scene_blueprint_count: Optional[int] = None,
    scene_type_counts: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """Constrain the StorySIS JSON Schema for a selected story_type.

    When story_type is selected, we can tighten the Structured Output schema so that:
    - story_type is const
    - scene_blueprints is a fixed-length tuple
    - each scene_blueprints[i].scene_type is const (slot role)

    NOTE: UI の scene_type_overrides は「入力Sceneの役割ヒント」としてプロンプトにのみ反映し、
    StorySIS.scene_blueprints のラベル（slot順）は story_type の定義順を必ず維持する。
    """
    if story_type not in STORY_TYPE_BLUEPRINTS:
        return base_schema

    base_roles = STORY_TYPE_BLUEPRINTS[story_type].get('scene_types', [])
    if not isinstance(base_roles, list) or not base_roles:
        return base_schema

    if scene_type_counts is not None:
        expected_roles = _expand_scene_types_by_counts(story_type, scene_type_counts)
    elif scene_blueprint_count is None:
        expected_roles = list(base_roles)
    else:
        expected_roles = _expand_scene_types_for_story_type(story_type, scene_blueprint_count)

    schema = copy.deepcopy(base_schema)
    props = schema.get('properties')
    if not isinstance(props, dict):
        return schema

    story_type_prop = props.get('story_type')
    if isinstance(story_type_prop, dict):
        story_type_prop['const'] = story_type
        story_type_prop.setdefault('type', 'string')
    else:
        props['story_type'] = {'type': 'string', 'const': story_type}

    sb = props.get('scene_blueprints')
    if not isinstance(sb, dict):
        sb = {'type': 'array'}
        props['scene_blueprints'] = sb

    sb['type'] = 'array'
    sb['minItems'] = len(expected_roles)
    sb['maxItems'] = len(expected_roles)

    items: List[Dict[str, Any]] = []
    for role in expected_roles:
        items.append({
            'type': 'object',
            'properties': {
                'scene_type': {'type': 'string', 'const': role},
                'summary': {'type': 'string'}
            },
            'required': ['scene_type', 'summary'],
            'additionalProperties': False
        })

    sb['items'] = items
    sb['additionalItems'] = False

    return schema


def _build_story_type_guide(selected_story_type: Optional[str] = None) -> str:
    """Create human-readable guidance text for story_type and scene roles.

    If selected_story_type is provided and known, explain only that structure.
    Otherwise, list all available story_type options briefly.
    """
    lines: List[str] = []

    if selected_story_type and selected_story_type in STORY_TYPE_BLUEPRINTS:
        cfg = STORY_TYPE_BLUEPRINTS[selected_story_type]
        lines.append(f"Selected story_type: {selected_story_type}")
        overview = cfg.get('overview')
        if overview:
            lines.append(f"Overview: {overview}")

        roles = cfg.get('scene_types', [])
        role_desc = cfg.get('scene_type_descriptions', {})
        if roles:
            lines.append("Scene roles:")
            for role in roles:
                desc = role_desc.get(role, "")
                if desc:
                    lines.append(f"- {role}: {desc}")
                else:
                    lines.append(f"- {role}")
    else:
        lines.append("Available story_type options:")
        for key, cfg in STORY_TYPE_BLUEPRINTS.items():
            overview = cfg.get('overview', '')
            roles = cfg.get('scene_types', [])
            role_desc = cfg.get('scene_type_descriptions', {})
            role_parts = []
            for role in roles:
                desc = role_desc.get(role)
                if desc:
                    role_parts.append(f"{role} ({desc})")
                else:
                    role_parts.append(role)
            roles_joined = "; ".join(role_parts) if role_parts else ''
            if roles_joined:
                lines.append(f"- {key}: {overview} | Scene roles: {roles_joined}")
            else:
                lines.append(f"- {key}: {overview}")

    return "\n".join(lines)


def normalize_scene_type_overrides(overrides: Optional[List[Any]], scene_count: int) -> Optional[List[Optional[str]]]:
    """Validate and normalize manual scene_type assignments."""
    if overrides is None:
        return None
    if not isinstance(overrides, list):
        raise ValueError('scene_type_overrides must be an array aligned with scenes')
    if len(overrides) != scene_count:
        raise ValueError(f'scene_type_overrides must contain exactly {scene_count} entries')
    normalized: List[Optional[str]] = []
    allowed = set(ALL_SCENE_TYPES)
    for idx, value in enumerate(overrides):
        if value is None:
            normalized.append(None)
            continue
        if not isinstance(value, str):
            raise ValueError(f'scene_type_overrides[{idx}] must be a string or null')
        cleaned = value.strip()
        if not cleaned:
            normalized.append(None)
            continue
        if cleaned not in allowed:
            raise ValueError(
                f'scene_type_overrides[{idx}] must be one of {sorted(allowed)} (got {cleaned})'
            )
        normalized.append(cleaned)
    return normalized


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
            requested_story_type = kwargs.get('requested_story_type')
            scene_blueprint_count = kwargs.get('scene_blueprint_count')
            scene_type_counts = kwargs.get('scene_type_counts')
            if requested_story_type is not None:
                if not isinstance(requested_story_type, str) or requested_story_type.strip() == '':
                    requested_story_type = None
                else:
                    requested_story_type = requested_story_type.strip()
                    if requested_story_type not in STORY_TYPE_BLUEPRINTS:
                        raise ValidationError(
                            f"story_type must be one of {list(STORY_TYPE_BLUEPRINTS.keys())}"
                        )
            if scene_type_counts is not None:
                if not isinstance(scene_type_counts, dict):
                    raise ValidationError('scene_type_counts must be an object')
            manual_scene_types: Optional[List[Optional[str]]] = None
            manual_scene_type_count = 0
            if 'scene_type_overrides' in kwargs:
                try:
                    manual_scene_types = normalize_scene_type_overrides(
                        kwargs.get('scene_type_overrides'),
                        len(scene_sis_list)
                    )
                except ValueError as exc:
                    raise ValidationError(str(exc))
                manual_scene_type_count = len([st for st in manual_scene_types if st])
            self.logger.info(f"Starting {function_name}", extra={
                'function': function_name,
                'scene_count': len(scene_sis_list),
                'requested_story_type': requested_story_type,
                'manual_scene_type_count': manual_scene_type_count
            })
            
            # サーバーとモデルの確認
            self._check_server_and_model()
            
            # StorySISスキーマの取得
            story_sis_schema = self._story_sis_schema()
            # story_type が選択されている場合は、Schema側を上書きしてLLM出力を強制する
            if requested_story_type:
                story_sis_schema = _constrain_story_sis_schema_for_story_type(
                    story_sis_schema,
                    requested_story_type,
                    scene_blueprint_count=scene_blueprint_count,
                    scene_type_counts=scene_type_counts
                )
            
            # プロンプト作成
            prompt = self._create_scenes_to_story_prompt(
                scene_sis_list,
                requested_story_type=requested_story_type,
                scene_type_overrides=manual_scene_types,
                scene_blueprint_count=scene_blueprint_count,
                scene_type_counts=scene_type_counts
            )
            
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
            if requested_story_type:
                story_sis_json['story_type'] = requested_story_type

            # story_id は必ずアプリケーション側で付与する
            # LLM が何か値を返していても上書きする
            story_sis_json['story_id'] = _generate_story_id()

            # story_type 未指定の場合のみ、手動指定を出力側にも反映する
            # story_type を選択している場合は、scene_blueprints のラベル順を固定する（B仕様）
            if (not requested_story_type) and manual_scene_type_count:
                blueprints = story_sis_json.get('scene_blueprints')
                if isinstance(blueprints, list):
                    for idx, override in enumerate(manual_scene_types or []):
                        if override and idx < len(blueprints):
                            bp = blueprints[idx]
                            if isinstance(bp, dict):
                                bp['scene_type'] = override

            self.logger.info(f"{function_name} completed successfully", extra={
                'function': function_name,
                'duration_sec': round(req_duration, 4)
            })

            story_type_guide = _build_story_type_guide(requested_story_type)
            
            return ProcessingResult(
                success=True,
                data={
                    'story_sis': story_sis_json,
                    'content': raw_text,
                    'content_format': 'json',
                    'prompt': prompt,
                    'story_type_guide': story_type_guide,
                    'scene_type_overrides': manual_scene_types
                },
                error=None,
                metadata={
                    'function': function_name,
                    'scene_count': len(scene_sis_list),
                    'request_duration_sec': round(req_duration, 4),
                    'timestamp': datetime.now().isoformat(),
                    'requested_story_type': requested_story_type,
                    'story_type_source': 'requested' if requested_story_type else 'auto',
                    'final_story_type': story_sis_json.get('story_type'),
                    'story_type_guide': story_type_guide,
                    'scene_type_overrides': manual_scene_types,
                    'scene_type_source': 'manual' if manual_scene_type_count else 'auto'
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
                'blueprint_scene_type': blueprint.get('scene_type', 'unknown')
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
            scene_type_hint = blueprint.get('scene_type')
            fallback_applied = len(applied_defaults) > 0
            if fallback_applied:
                self.logger.warning(
                    "SceneSIS response missing fields; applied fallback defaults",
                    extra={
                        'function': function_name,
                        'blueprint_index': blueprint_index,
                        'scene_type_hint': scene_type_hint,
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
                    'scene_type_hint': scene_type_hint,
                    'fallback_applied': fallback_applied,
                    'fallback_details': applied_defaults
                },
                error=None,
                metadata={
                    'function': function_name,
                    'story_id': story_sis.get('story_id', 'unknown'),
                    'blueprint_index': blueprint_index,
                    'scene_type_hint': scene_type_hint,
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
                    'scene_type_hint': blueprint.get('scene_type', 'unknown')
                })
                
                # 単一シーン生成を呼び出し
                result = self.story_to_scene(story_sis, blueprint, idx, **kwargs)
                
                if result.success:
                    scene_data = {
                        'scene_sis': result.data.get('scene_sis'),
                        'raw_text': result.data.get('raw_text'),
                        'prompt': result.data.get('prompt'),
                        'blueprint_index': idx,
                        'duration_sec': result.data.get('duration_sec', 0),
                        'scene_type_hint': blueprint.get('scene_type')
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
    
    def _create_scenes_to_story_prompt(
        self,
        scene_sis_list: List[Dict[str, Any]],
        requested_story_type: Optional[str] = None,
        scene_type_overrides: Optional[List[Optional[str]]] = None,
        scene_blueprint_count: Optional[int] = None,
        scene_type_counts: Optional[Dict[str, int]] = None
    ) -> str:
        """SceneSISリストからStorySIS生成用プロンプトを作成"""
        scenes_json = json.dumps(scene_sis_list, indent=2, ensure_ascii=False)
        if requested_story_type:
            story_type_task = (
                f'1. Use the requested story_type "{requested_story_type}" exactly for StorySIS.story_type '
                'and align scene_blueprints with that narrative structure'
            )
            story_type_requirement = f'StorySIS.story_type MUST be "{requested_story_type}"'
            if isinstance(scene_blueprint_count, int) and scene_blueprint_count > 0:
                story_type_task += f' and generate exactly {scene_blueprint_count} scene_blueprints'
                story_type_requirement += f' and StorySIS.scene_blueprints MUST have exactly {scene_blueprint_count} items'
            if isinstance(scene_type_counts, dict) and scene_type_counts:
                base_roles = STORY_TYPE_BLUEPRINTS.get(requested_story_type, {}).get('scene_types', [])
                if isinstance(base_roles, list) and base_roles:
                    parts = []
                    total = 0
                    for role in base_roles:
                        cnt = scene_type_counts.get(role, 1)
                        if isinstance(cnt, int) and cnt > 0:
                            total += cnt
                            parts.append(f"{role} x{cnt}")
                    if parts:
                        story_type_task += ' with these role counts: ' + ', '.join(parts)
                        story_type_requirement += f' (total {total})'
        else:
            story_type_task = (
                '1. Analyze the scenes to determine the appropriate story_type '
                '(e.g., "three_act", "kishotenketsu", "attempts", "catalog")'
            )
            story_type_requirement = 'Pick the story_type that best matches the provided scenes'

        assignments_block = ''
        role_alignment_task = ''
        if scene_type_overrides:
            assignment_lines = []
            for idx, override in enumerate(scene_type_overrides):
                if not override:
                    continue
                summary = scene_sis_list[idx].get('summary', '') if idx < len(scene_sis_list) else ''
                trunc_summary = (summary[:80] + '...') if summary and len(summary) > 80 else summary
                detail = f' — {trunc_summary}' if trunc_summary else ''
                assignment_lines.append(f'- Scene {idx + 1}: **{override}**{detail}')
            if assignment_lines:
                assignments_block = "## Scene Role Assignments\n" + "\n".join(assignment_lines) + "\n\n"
                role_alignment_task = '6. Use the scene role assignments when labeling scene_blueprints. '
                role_alignment_task += 'Do not rename the provided scene_type values.'

        story_type_guide = _build_story_type_guide(requested_story_type)

        template = _load_prompt_template('scene2story.md')
        prompt = template.safe_substitute(
            SCENES_JSON=scenes_json,
            STORY_TYPE_TASK=story_type_task,
            STORY_TYPE_REQUIREMENT=story_type_requirement,
            ASSIGNMENTS_BLOCK=assignments_block,
            ROLE_ALIGNMENT_TASK=role_alignment_task,
            STORY_TYPE_GUIDE=story_type_guide
        ).strip()
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
        template = _load_prompt_template('story2scene.md')
        story_type_guide = _build_story_type_guide(story_sis.get('story_type'))
        prompt = template.safe_substitute(
            STORY_CONTEXT_JSON=story_json,
            BLUEPRINT_JSON=blueprint_json,
            BLUEPRINT_INDEX=index + 1,
            STORY_TYPE_GUIDE=story_type_guide
        ).strip()
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
        # scene_id も必ずアプリケーション側で生成する
        scene['scene_id'] = _generate_scene_id()
        if 'scene_id' not in applied_defaults:
            applied_defaults.append('scene_id')
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

        ensure_value(semantics_common, 'mood', lambda: story_common.get('mood', 'neutral'),
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
                    "description": "Identifier for this story (assigned by the system)"
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
                    "enum": list(STORY_TYPE_BLUEPRINTS.keys()),
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
                    "description": "Identifier for this scene (assigned by the system)"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what happens in this scene"
                },
                "semantics": semantics_schema
            },
            "required": ["sis_type", "scene_id", "summary", "semantics"]
        }


# ========================================
# 統一エントリーポイント関数
# ========================================

def scene2story(
    scene_sis_list: List[Dict[str, Any]],
    api_config: Optional[APIConfig] = None,
    processing_config: Optional[ProcessingConfig] = None,
    logger: Optional[StructuredLogger] = None,
    requested_story_type: Optional[str] = None,
    scene_type_overrides: Optional[List[Optional[str]]] = None,
    scene_blueprint_count: Optional[int] = None,
    scene_type_counts: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    複数のSceneSISからStorySISを生成
    
    Args:
        scene_sis_list: SceneSISのリスト
        api_config: API設定
        processing_config: 処理設定
        logger: ロガー
        requested_story_type: 固定したいStorySIS.story_type（任意）
    
    Returns:
        統一された戻り値辞書
    """
    transformer = SISTransformer(api_config, processing_config, logger)
    result = transformer.scenes_to_story(
        scene_sis_list,
        requested_story_type=requested_story_type,
        scene_type_overrides=scene_type_overrides,
        scene_blueprint_count=scene_blueprint_count,
        scene_type_counts=scene_type_counts
    )
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
    parser.add_argument('--story_type', choices=list(STORY_TYPE_BLUEPRINTS.keys()),
                       help='Force StorySIS.story_type when running in scene2story mode')
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
        result = scene2story(
            scene_sis_list,
            api_config,
            requested_story_type=args.story_type
        )
        
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
                scene_type_hint = scene_data.get('scene_type_hint') or 'scene'
                output_path = os.path.join(args.output_dir, f"scene_{i+1:02d}_{scene_type_hint}_{scene_id[:8]}.json")
                save_sis_to_file(scene_sis, output_path)
        else:
            print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
