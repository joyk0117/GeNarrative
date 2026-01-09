#!/usr/bin/env python3
"""
Common configuration and base classes for GeNarrative pipeline

統一された設定管理とベースクラスを提供
"""

import os
import time
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
from datetime import datetime
from abc import ABC, abstractmethod


# ========================================
# 設定クラス
# ========================================

@dataclass
class APIConfig:
    """API サーバー設定
    - unsloth_uri は後方互換用
    - ollama_uri/ollama_model を追加し、LLM呼び出しは原則こちらを使用
    """
    unsloth_uri: str = "http://unsloth:5006"
    ollama_uri: str = "http://ollama:11434"
    sd_uri: str = "http://sd:7860"
    music_uri: str = "http://music:5003"
    tts_uri: str = "http://tts:5002"
    # 従来のモデル名（未使用の場合あり）
    model_name: str = "unsloth/gemma-3n-E4B-it"
    # Ollamaで使用するモデル
    ollama_model: str = "gemma3:4b-it-qat"
    timeout: int = 300


@dataclass
class GenerationConfig:
    """生成設定クラス"""
    image_width: int = 1024
    image_height: int = 768
    music_duration: int = 30
    text_word_count: int = 50
    temperature: float = 0.7
    max_tokens: int = 1000


@dataclass
class ProcessingConfig:
    """処理設定クラス"""
    output_dir: str = "/workspaces/GeNarrative-dev/dev/scripts"
    save_debug_info: bool = False
    auto_save_sis: bool = True
    use_timestamp: bool = True
    cache_enabled: bool = True
    cache_dir: str = "/tmp/sis_cache"


# ========================================
# カスタム例外クラス
# ========================================

class GeNarrativeError(Exception):
    """基底例外クラス"""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        self.error_code = error_code or 'UNKNOWN_ERROR'
        self.details = details or {}
        super().__init__(message)


class FileProcessingError(GeNarrativeError):
    """ファイル処理エラー"""
    pass


class ServerConnectionError(GeNarrativeError):
    """サーバー接続エラー"""
    def __init__(self, server_name: str, uri: str):
        self.server_name = server_name
        self.uri = uri
        super().__init__(
            f"Cannot connect to {server_name} at {uri}",
            error_code='SERVER_CONNECTION_ERROR',
            details={'server_name': server_name, 'uri': uri}
        )


class ModelNotLoadedError(GeNarrativeError):
    """モデル未読み込みエラー"""
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(
            f"Model not loaded: {model_name}",
            error_code='MODEL_NOT_LOADED',
            details={'model_name': model_name}
        )


class ContentTypeError(GeNarrativeError):
    """コンテンツタイプエラー"""
    def __init__(self, content_type: str, supported_types: list):
        self.content_type = content_type
        self.supported_types = supported_types
        super().__init__(
            f"Unsupported content type: {content_type}. Supported: {supported_types}",
            error_code='UNSUPPORTED_CONTENT_TYPE',
            details={'content_type': content_type, 'supported_types': supported_types}
        )


class ValidationError(GeNarrativeError):
    """検証エラー"""
    pass


# ========================================
# 統一された戻り値クラス
# ========================================

@dataclass
class ProcessingResult:
    """統一された処理結果クラス"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    metadata: Dict[str, Any]
    debug_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        辞書形式に変換（後方互換性のため）
        
        Returns:
            Dict[str, Any]: 変換結果。常に以下のキーを含む:
                - success (bool): 処理の成功/失敗
                - error (str | None): エラーメッセージ
                - metadata (dict): メタデータ
                
            成功時は追加で以下のいずれかが含まれる:
                - SIS抽出: sis_data, extraction_time, prompt?, content?, content_format?
                - コンテンツ生成: generated_text / content, generation_time
                - SIS変換: dataの全内容がトップレベルにマージされる
                  (例: scene_sis, story_sis, scenes, raw_text, prompt等)
                  
        Note:
            SIS変換の場合(scene_sis/story_sis/scenes in data)、
            self.dataの内容がresult.update()により直接トップレベルに展開されます。
            そのため、呼び出し側は result['data']['scene_sis'] ではなく
            result['scene_sis'] としてアクセスする必要があります。
        """
        result = {
            'success': self.success,
            'error': self.error,
            'metadata': self.metadata
        }
        
        if self.success and self.data:
            # SIS抽出の場合
            if 'sis_data' in self.data:
                result['sis_data'] = self.data['sis_data']
                result['extraction_time'] = self.metadata.get('timestamp')
                # 追加情報（プロンプトや生テキスト）があれば併せて返す
                for extra_key in ('prompt', 'content', 'content_format'):
                    if extra_key in self.data:
                        result[extra_key] = self.data[extra_key]
            # コンテンツ生成の場合
            elif 'generated_text' in self.data or 'content' in self.data:
                result.update(self.data)
                result['generation_time'] = self.metadata.get('processing_time')
            # SIS変換の場合（story_sis, scenesなど）
            # ⚠️ 重要: dataの内容をトップレベルにマージ
            elif 'story_sis' in self.data or 'scenes' in self.data or 'scene_sis' in self.data:
                result.update(self.data)
            else:
                # dataが直接SISデータの場合（従来互換性）
                result['sis_data'] = self.data
                result['extraction_time'] = self.metadata.get('timestamp')
        
        if self.debug_info:
            result['raw_response'] = self.debug_info.get('raw_response')
            result['debug_info'] = self.debug_info
        
        return result


# ========================================
# 構造化ログクラス
# ========================================

class StructuredLogger:
    """構造化ログクラス"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # ハンドラーの設定（重複を避ける）
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_function_start(self, function_name: str, params: Dict[str, Any]):
        """関数開始ログ"""
        self.logger.info(f"🚀 Starting {function_name}", extra={
            'function': function_name,
            'params': params,
            'timestamp': datetime.now().isoformat()
        })
    
    def log_function_end(self, function_name: str, success: bool, duration: float):
        """関数終了ログ"""
        status = "✅" if success else "❌"
        self.logger.info(f"{status} Completed {function_name} in {duration:.2f}s", extra={
            'function': function_name,
            'success': success,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })
    
    def log_error(self, function_name: str, error: str, details: Dict[str, Any] = None):
        """エラーログ"""
        self.logger.error(f"❌ Error in {function_name}: {error}", extra={
            'function': function_name,
            'error': error,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        })
    
    def info(self, message: str, extra: Dict[str, Any] = None):
        """汎用情報ログ"""
        self.logger.info(message, extra=extra or {})
    
    def error(self, message: str, extra: Dict[str, Any] = None):
        """汎用エラーログ"""
        self.logger.error(message, extra=extra or {})
    
    def warning(self, message: str, extra: Dict[str, Any] = None):
        """汎用警告ログ"""
        self.logger.warning(message, extra=extra or {})
    
    def debug(self, message: str, extra: Dict[str, Any] = None):
        """汎用デバッグログ"""
        self.logger.debug(message, extra=extra or {})


# ========================================
# ベース処理クラス
# ========================================

class ContentProcessor(ABC):
    """コンテンツ処理の基底クラス"""
    
    def __init__(self, 
                 api_config: Optional[APIConfig] = None,
                 processing_config: Optional[ProcessingConfig] = None,
                 logger: Optional[StructuredLogger] = None):
        self.api_config = api_config or APIConfig()
        self.processing_config = processing_config or ProcessingConfig()
        self.logger = logger or StructuredLogger(self.__class__.__name__)
        self._start_time = None
    
    @abstractmethod
    def process(self, *args, **kwargs) -> ProcessingResult:
        """処理の実行"""
        pass
    
    def _start_processing(self, function_name: str, params: Dict[str, Any]):
        """処理開始の共通ロジック"""
        self._start_time = time.time()
        self.logger.log_function_start(function_name, params)
    
    def _end_processing(self, function_name: str, success: bool) -> float:
        """処理終了の共通ロジック"""
        duration = time.time() - self._start_time if self._start_time else 0.0
        self.logger.log_function_end(function_name, success, duration)
        return duration
    
    def _handle_error(self, error: Exception, function_name: str, context: Dict[str, Any] = None) -> ProcessingResult:
        """統一エラーハンドリング"""
        duration = self._end_processing(function_name, False)
        
        self.logger.log_error(function_name, str(error), context)
        
        if isinstance(error, GeNarrativeError):
            error_code = error.error_code
            details = error.details
        else:
            error_code = 'UNEXPECTED_ERROR'
            details = {'exception_type': type(error).__name__}
        
        return ProcessingResult(
            success=False,
            data=None,
            error=str(error),
            metadata={
                'function_name': function_name,
                'processing_time': duration,
                'timestamp': datetime.now().isoformat(),
                'error_code': error_code
            },
            debug_info=details if self.processing_config.save_debug_info else None
        )
    
    def _validate_file_path(self, file_path: str) -> None:
        """ファイルパスの検証"""
        if not os.path.exists(file_path):
            raise FileProcessingError(
                f"File not found: {file_path}",
                error_code='FILE_NOT_FOUND',
                details={'file_path': file_path}
            )


# ========================================
# ユーティリティ関数
# ========================================

def detect_content_type(file_path: str) -> str:
    """ファイル拡張子からコンテンツタイプを判定"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in ['.wav', '.mp3', '.m4a', '.flac']:
        return 'audio'
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        return 'image'
    elif ext in ['.txt', '.md', '.doc', '.docx']:
        return 'text'
    else:
        return 'unknown'


def handle_processing_error(error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """統一エラーハンドリング関数（後方互換性）"""
    if isinstance(error, GeNarrativeError):
        return {
            'success': False,
            'error': str(error),
            'error_code': error.error_code,
            'details': error.details,
            'context': context or {}
        }
    else:
        return {
            'success': False,
            'error': f"Unexpected error: {str(error)}",
            'error_code': 'UNKNOWN_ERROR',
            'context': context or {}
        }


def create_standard_response(
    success: bool,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    function_name: str = '',
    processing_time: float = 0.0,
    debug_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """標準レスポンス作成ヘルパー"""
    result = ProcessingResult(
        success=success,
        data=data,
        error=error,
        metadata={
            'function_name': function_name,
            'processing_time': processing_time,
            'timestamp': datetime.now().isoformat()
        },
        debug_info=debug_info
    )
    return result.to_dict()
