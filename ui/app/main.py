from flask import Flask, render_template, send_from_directory, send_file, jsonify, request
import os
import sys
import json
import base64
import mimetypes
import subprocess
import tempfile
import uuid
import requests
import time
import copy
import shutil
from datetime import datetime
from functools import lru_cache

# Add dev/scripts to Python path for content2sis_unified import
sys.path.insert(0, '/app/dev/scripts')
sys.path.insert(0, '/app/ui/scripts')

# For development environment, also add workspace paths
sys.path.insert(0, '/workspaces/GeNarrative-dev/dev/scripts')
sys.path.insert(0, '/workspaces/GeNarrative-dev/ui/scripts')

# For Windows development, add current workspace paths
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.dirname(os.path.dirname(current_dir))
dev_scripts_path = os.path.join(workspace_root, 'dev', 'scripts')
ui_scripts_path = os.path.join(workspace_root, 'ui', 'scripts')

# Docker dev mount layout note:
# - docker-compose mounts ./ui/app -> /app
# - docker-compose mounts ./ui/scripts -> /app/ui/scripts
# In that case, the heuristic workspace_root becomes '/', so prefer existing paths.
candidate_dev_scripts = [
    os.path.join(current_dir, 'dev', 'scripts'),
    os.path.join(workspace_root, 'dev', 'scripts'),
    '/app/dev/scripts',
]
candidate_ui_scripts = [
    os.path.join(current_dir, 'ui', 'scripts'),
    os.path.join(os.path.dirname(current_dir), 'scripts'),
    os.path.join(workspace_root, 'ui', 'scripts'),
    '/app/ui/scripts',
]

for p in candidate_dev_scripts:
    if isinstance(p, str) and os.path.exists(p):
        dev_scripts_path = p
        break

for p in candidate_ui_scripts:
    if isinstance(p, str) and os.path.exists(p):
        ui_scripts_path = p
        break
sys.path.insert(0, dev_scripts_path)
sys.path.insert(0, ui_scripts_path)


@lru_cache(maxsize=1)
def _load_story_type_blueprints() -> dict:
    """Load story type definitions used by the Project screen lanes."""
    path = os.path.join(ui_scripts_path, 'schemas', 'story_type_blueprints.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"⚠️ Failed to load story_type_blueprints.json: {e}")
        return {}

print(f"📁 Current working directory: {os.getcwd()}")
print(f"📁 Script directory: {current_dir}")
print(f"📁 Workspace root: {workspace_root}")
print(f"📁 Dev scripts path: {dev_scripts_path}")
print(f"📁 UI scripts path: {ui_scripts_path}")
print(f"🔍 Python path (first 10): {sys.path[:10]}")

try:
    from content2sis_unified import SISExtractor
    from common_base import APIConfig
    SIS_EXTRACTOR_AVAILABLE = True
    print("✅ SIS extractor loaded successfully")
except ImportError as e:
    print(f"❌ Warning: Could not import unified SIS extractor: {e}")
    try:
        # Try to import individual SIS functions as fallback
        from content2sis import image2SIS, text2SIS, audio2SIS
        SIS_EXTRACTOR_AVAILABLE = 'fallback'
        print("✅ Fallback SIS functions loaded")
    except ImportError as e2:
        print(f"❌ Fallback SIS functions also failed: {e2}")
        SIS_EXTRACTOR_AVAILABLE = False
        print("⚠️ Using dummy SIS generation for testing")

# SISからコンテンツ生成のインポート
try:
    from _unified import generate_content, ContentGenerator
    from common_base import ProcessingConfig, GenerationConfig
    SIS_TO_CONTENT_AVAILABLE = True
    print("✅ SIS to content generator loaded successfully (_unified)")
except ImportError as e:
    print(f"❌ Warning: Could not import _unified module: {e}")
    # フォールバック: リポジトリ内の sis2content_unified を使用
    try:
        from sis2content_unified import ContentGenerator as _CG_Fallback
        from common_base import ProcessingConfig, GenerationConfig, ProcessingResult

        def generate_content(*, sis_data, content_type, api_config, processing_config, generation_config, **kwargs):
            """Fallback wrapper using sis2content_unified.ContentGenerator.process to mimic _unified.generate_content signature."""
            gen = _CG_Fallback(api_config=api_config, processing_config=processing_config, generation_config=generation_config)
            result_obj = gen.process(sis_data, content_type, **kwargs)
            # Convert ProcessingResult -> dict to keep main flow compatible
            if isinstance(result_obj, ProcessingResult):
                data = result_obj.data or {}
                return {
                    'success': result_obj.success,
                    'error': result_obj.error,
                    'metadata': result_obj.metadata,
                    'generated_text': data.get('generated_text'),
                    'output_path': data.get('output_path'),
                    'image_result': data.get('image_result'),
                    'music_result': data.get('music_result')
                }
            # As a safeguard if structure differs
            return result_obj

        ContentGenerator = _CG_Fallback
        SIS_TO_CONTENT_AVAILABLE = True
        print("✅ SIS to content generator loaded successfully (fallback sis2content_unified)")
    except ImportError as e2:
        print(f"❌ Fallback sis2content_unified also failed: {e2}")
        SIS_TO_CONTENT_AVAILABLE = False
        print("⚠️ SIS to content generation not available")

app = Flask(__name__)

# Shared folder paths
SHARED_DIR = "/app/shared"
SCENE_DIR = "/app/shared/scene"
PROJECTS_DIR = "/app/shared/projects"
TEST_DIR = "/app/ui/scripts/test"


def find_scene_path(scene_id):
    """Find scene path in either SCENE_DIR or PROJECTS_DIR. Returns (scene_path, project_id)"""
    scene_path = os.path.join(SCENE_DIR, scene_id)
    
    # First check in SCENE_DIR
    if os.path.exists(scene_path):
        return scene_path, None
    
    # If not found, search in PROJECTS_DIR
    if os.path.exists(PROJECTS_DIR):
        for project in os.listdir(PROJECTS_DIR):
            project_scenes_dir = os.path.join(PROJECTS_DIR, project, 'scenes')
            if os.path.exists(project_scenes_dir):
                potential_scene_path = os.path.join(project_scenes_dir, scene_id)
                if os.path.exists(potential_scene_path):
                    return potential_scene_path, project
    
    return None, None


def load_structured_sis(scene_id):
    """Return latest structured SIS data for a scene if available."""
    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        return None

    structured_files = [
        f for f in os.listdir(scene_path)
        if f.startswith('sis_structure_') and f.endswith('.json') and not f.endswith('_candidate.json')
    ]

    structured_files.sort(reverse=True)

    for filename in structured_files:
        try:
            with open(os.path.join(scene_path, filename), 'r', encoding='utf-8') as fp:
                return json.load(fp)
        except Exception as exc:
            print(f"Failed to load structured SIS {filename}: {exc}")

    raw_path = os.path.join(scene_path, f'sis_raw_{scene_id}.txt')
    if os.path.exists(raw_path):
        try:
            with open(raw_path, 'r', encoding='utf-8') as fp:
                return json.loads(fp.read())
        except Exception as exc:
            print(f"Failed to parse raw SIS for {scene_id}: {exc}")

    return None


def regenerate_prompts_from_sis(scene_id, sis_json):
    """Generate image, music, and text prompts from the latest SIS snapshot."""
    if not SIS_TO_CONTENT_AVAILABLE:
        raise RuntimeError('SIS to content generation system is not available.')

    if not isinstance(sis_json, dict):
        raise ValueError('Structured SIS must be a JSON object.')

    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        raise RuntimeError(f'Scene {scene_id} not found')
    os.makedirs(scene_path, exist_ok=True)

    # Work on a copy so that downstream validation can fill defaults safely.
    sis_payload = copy.deepcopy(sis_json)

    timeout_value = os.environ.get('OLLAMA_TIMEOUT', 180)
    try:
        timeout_value = int(timeout_value)
    except (TypeError, ValueError):
        timeout_value = 180

    generator = ContentGenerator(
        api_config=APIConfig(
            unsloth_uri=os.environ.get('UNSLOTH_URI', 'http://unsloth:5007'),
            ollama_uri=os.environ.get('OLLAMA_URI', 'http://ollama:11434'),
            sd_uri=os.environ.get('SD_URI', 'http://sd:7860'),
            music_uri=os.environ.get('MUSIC_URI', 'http://music:5003'),
            tts_uri=os.environ.get('TTS_URI', 'http://tts:5002'),
            ollama_model=os.environ.get('OLLAMA_MODEL', 'gemma3:4b-it-qat'),
            timeout=timeout_value
        ),
        generation_config=GenerationConfig(),
        processing_config=ProcessingConfig(output_dir=scene_path)
    )

    # Skip validation - accept any SIS structure

    prompts = {}
    failures = {}

    def _write_prompt(filename, content):
        path = os.path.join(scene_path, filename)
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(content)

    try:
        image_instruction = generator._create_image_prompt(
            sis_payload,
            generator.generation_config.image_width,
            generator.generation_config.image_height
        )
        image_prompt = generator._generate_with_ollama(image_instruction)
        _write_prompt(f'image_{scene_id}_prompt.txt', image_prompt)
        prompts['image'] = {
            'text': image_prompt,
            'filename': f'image_{scene_id}_prompt.txt'
        }
    except Exception as exc:
        print(f"Image prompt regeneration failed for scene {scene_id}: {exc}")
        failures['image'] = str(exc)

    try:
        music_instruction = generator._create_music_prompt(
            sis_payload,
            generator.generation_config.music_duration
        )
        music_prompt = generator._generate_with_ollama(music_instruction)
        _write_prompt('sis2music_prompt.txt', music_prompt)
        _write_prompt(f'music_{scene_id}_prompt.txt', music_prompt)
        prompts['music'] = {
            'text': music_prompt,
            'filename': 'sis2music_prompt.txt'
        }
    except Exception as exc:
        print(f"Music prompt regeneration failed for scene {scene_id}: {exc}")
        failures['music'] = str(exc)

    try:
        text_instruction = generator._create_text_prompt(
            sis_payload,
            generator.generation_config.text_word_count
        )
        text_prompt = generator._generate_with_ollama(text_instruction)
        _write_prompt(f'text_{scene_id}_prompt.txt', text_prompt)
        prompts['text'] = {
            'text': text_prompt,
            'filename': f'text_{scene_id}_prompt.txt'
        }
    except Exception as exc:
        print(f"Text prompt regeneration failed for scene {scene_id}: {exc}")
        failures['text'] = str(exc)

    if not prompts:
        raise RuntimeError('Prompt regeneration failed for all content types.')

    return prompts, failures

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/servers/text")
def text_server():
    return render_template('servers/text.html')

@app.route("/servers/tts")
def tts_server():
    return render_template('servers/tts.html')

@app.route("/servers/image")
def image_server():
    # 統一して動的なサーバーステータスページを返す
    return render_template('servers/image.html')

@app.route("/servers/music")
def music_server():
    return render_template('servers/music.html')

@app.route("/api/servers/music/status")
def music_status():
    """Musicサーバのヘルス情報を取得して返すステータスAPI。
    Docker内部ネットワークのサービス名 'music' を使って http://music:5003/health を確認。
    UIページでオンライン/オフラインを表示する最小限の情報のみ返す。
    """
    target = "http://music:5003/health"
    started = time.time()
    try:
        r = requests.get(target, timeout=5)
        latency_ms = int((time.time() - started) * 1000)
        if r.status_code == 200:
            data = r.json()
            return jsonify({
                'online': True,
                'latency_ms': latency_ms,
                'model_loaded': data.get('model_loaded'),
                'device': data.get('device'),
                'timestamp': data.get('timestamp'),
                'server_uri_internal': 'http://music:5003',
                'server_uri_external': 'http://localhost:5003'
            })
        else:
            return jsonify({'online': False, 'error': f'Status {r.status_code}', 'latency_ms': latency_ms}), 502
    except requests.exceptions.ConnectionError:
        return jsonify({'online': False, 'error': 'Connection error'}), 503
    except requests.exceptions.Timeout:
        return jsonify({'online': False, 'error': 'Timeout'}), 504
    except Exception as e:
        return jsonify({'online': False, 'error': str(e)[:200]}), 500

@app.route("/api/servers/music/generate", methods=['POST'])
def music_generate_proxy():
    """Music生成のUIプロキシ。
    フロントから受け取った prompt/duration などを music サービスへ転送し、
    生成されたファイルのUIアクセス用URLを付けて返す。
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            # フォールバック: RAWボディ/フォームも試す
            try:
                payload = json.loads(request.data or b'{}')
            except Exception:
                payload = {}
        # まずはフォーム/クエリ優先で取得し、なければJSONから
        prompt = (request.values.get('prompt') or payload.get('prompt') or '').strip()
        # 最小限: durationのみ使用（サービス側が対応）
        try:
            duration = int(request.values.get('duration') or payload.get('duration') or 8)
        except Exception:
            duration = 8

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt is required'}), 400

        target = "http://music:5003/generate"
        r = requests.post(target, json={
            'prompt': prompt,
            'duration': duration
        }, timeout=60)

        if r.status_code != 200:
            # 可能ならエラーメッセージを透過
            try:
                err = r.json()
            except Exception:
                err = {'error': f'Upstream status {r.status_code}'}
            return jsonify({'success': False, **err}), 502

        data = r.json() or {}
        filename = data.get('filename')
        file_url = f"/shared/{filename}" if filename else None
        return jsonify({
            'success': True,
            'filename': filename,
            'file_url': file_url,
            'duration': data.get('duration'),
            'sample_rate': data.get('sample_rate'),
            'prompt': data.get('prompt')
        })
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Upstream timeout'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'Cannot connect to music service'}), 503
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route("/api/unsloth/health")
def get_unsloth_health():
    """Compatibility endpoint: report Ollama server status instead of Unsloth"""
    try:
        base = 'http://ollama:11434'
        v = requests.get(f"{base}/api/version", timeout=5)
        if v.status_code == 200:
            version = v.json()
            # Try list models
            try:
                tags = requests.get(f"{base}/api/tags", timeout=5)
                models = tags.json() if tags.status_code == 200 else {}
            except Exception:
                models = {}
            return jsonify({
                'success': True,
                'status': 'healthy',
                'data': {
                    'ollama_version': version,
                    'models': models
                }
            })
        else:
            return jsonify({'success': False, 'status': 'error', 'message': f'Ollama status {v.status_code}'}), v.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'status': 'offline', 'message': 'Cannot connect to Ollama server'}), 503
    except Exception as e:
        return jsonify({'success': False, 'status': 'error', 'message': f'Error checking Ollama: {str(e)}'}), 500

@app.route("/shared/<filename>")
def serve_shared_image(filename):
    """Serve images from shared folder"""
    return send_from_directory(SHARED_DIR, filename)

# ===== etc: Unified Tests =====
@app.route("/etc/tests")
def etc_tests_page():
    return render_template('etc/tests.html')

@app.route("/api/tests/run", methods=['POST'])
def run_unified_tests():
    """Run the unified tests script and return report URL."""
    try:
        # Ensure directory exists
        os.makedirs(TEST_DIR, exist_ok=True)
        # Run the test script synchronously
        cmd = [
            sys.executable,
            '-u',
            os.path.join(TEST_DIR, 'run_unified_tests.py')
        ]
        # Optional: pick specific image by name
        payload = request.get_json(silent=True) or {}
        image_env = {}
        try:
            image_name = (payload.get('image_name') or '').strip()
            image_path = (payload.get('image_path') or '').strip()
        except Exception:
            image_name = ''
            image_path = ''
        if image_path:
            # Trust given absolute path (container path)
            image_env['GENARRATIVE_TEST_IMAGE'] = image_path
        elif image_name:
            # Build path under shared/image
            candidate = os.path.join(SHARED_DIR, 'image', image_name)
            image_env['GENARRATIVE_TEST_IMAGE'] = candidate

        proc = subprocess.run(
            cmd,
            cwd=TEST_DIR,
            capture_output=True,
            text=True,
            env=dict(os.environ, **image_env),
            timeout=600
        )
        stdout = proc.stdout or ''
        stderr = proc.stderr or ''
        if proc.returncode != 0:
            return jsonify({
                'success': False,
                'error': f'Process exited with code {proc.returncode}',
                'message': stdout + ('\n[stderr]\n' + stderr if stderr else '')
            }), 500
        # Report path is static in the script
        report_rel_url = '/etc/tests/unified_test_report.html'
        return jsonify({
            'success': True,
            'report_url': report_rel_url,
            'message': stdout
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Timeout running tests (10m)'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/etc/tests/<path:filename>')
def serve_test_artifacts(filename):
    """Serve the unified test report and artifacts from TEST_DIR."""
    return send_from_directory(TEST_DIR, filename)

@app.route('/api/tests/images')
def list_test_images():
    """List available image files under shared/image for selection."""
    try:
        img_dir = os.path.join(SHARED_DIR, 'image')
        files = []
        if os.path.isdir(img_dir):
            for name in sorted(os.listdir(img_dir)):
                lower = name.lower()
                if lower.endswith(('.png', '.jpg', '.jpeg')):
                    files.append(name)
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/projects")
def project_list():
    """Display project list"""
    projects = []
    if os.path.exists(PROJECTS_DIR):
        for item in os.listdir(PROJECTS_DIR):
            project_path = os.path.join(PROJECTS_DIR, item)
            if os.path.isdir(project_path):
                # Count scenes and story in project
                scene_count = 0
                has_story = False
                
                scenes_dir = os.path.join(project_path, 'scenes')
                if os.path.exists(scenes_dir):
                    scene_count = len([d for d in os.listdir(scenes_dir) if os.path.isdir(os.path.join(scenes_dir, d))])
                
                story_dir = os.path.join(project_path, 'story')
                if os.path.exists(story_dir) and os.listdir(story_dir):
                    has_story = True
                
                project_info = {
                    'id': item,
                    'name': item,
                    'scene_count': scene_count,
                    'has_story': has_story
                }
                projects.append(project_info)
    
    # Sort by newest first
    projects.sort(key=lambda x: x['id'], reverse=True)
    return render_template('project_list.html', projects=projects)

@app.route("/projects/<project_id>")
def project_detail(project_id):
    """Display scenes within a specific project"""
    project_path = os.path.join(PROJECTS_DIR, project_id)
    
    if not os.path.exists(project_path):
        return "Project not found", 404
    
    scenes = []
    scenes_dir = os.path.join(project_path, 'scenes')
    
    if os.path.exists(scenes_dir):
        for item in os.listdir(scenes_dir):
            scene_path = os.path.join(scenes_dir, item)
            if os.path.isdir(scene_path):
                # Basic scene information
                scene_info = {
                    'id': item,
                    'has_image': False,
                    'image_filename': None,
                    'has_text': False,
                    'has_music': False
                }
                
                # Look for files in scene directory
                for file in os.listdir(scene_path):
                    # Check for image files
                    if file.startswith('image_') and file.endswith('.png') and not file.endswith('_candidate.png'):
                        scene_info['has_image'] = True
                        scene_info['image_filename'] = file
                    # Check for text files
                    elif file.startswith('text_') and file.endswith('.txt'):
                        scene_info['has_text'] = True
                    # Check for music files
                    elif file.startswith('music_') and (file.endswith('.mp3') or file.endswith('.wav')) and not file.endswith('_candidate.wav'):
                        scene_info['has_music'] = True
                
                scenes.append(scene_info)
    
    # Sort by newest first
    scenes.sort(key=lambda x: x['id'], reverse=True)
    return render_template(
        'project_scene_list.html',
        project_id=project_id,
        scenes=scenes,
        story_type_blueprints=_load_story_type_blueprints(),
    )

@app.route("/projects/<project_id>/create", methods=['POST'])
def create_project(project_id):
    """Create a new project directory structure"""
    try:
        project_path = os.path.join(PROJECTS_DIR, project_id)
        
        if os.path.exists(project_path):
            return jsonify({'success': False, 'error': 'Project already exists'}), 400
        
        # Create project directory structure
        os.makedirs(project_path, exist_ok=True)
        os.makedirs(os.path.join(project_path, 'scenes'), exist_ok=True)
        os.makedirs(os.path.join(project_path, 'story'), exist_ok=True)
        
        return jsonify({'success': True, 'project_id': project_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/scene/<scene_id>")
def scene_detail(scene_id):
    """Display details of a specific scene"""
    scene_path, project_id = find_scene_path(scene_id)
    
    if not scene_path:
        return "Scene not found", 404
    
    # Collect files
    files = os.listdir(scene_path)
    
    scene_data = {
        'id': scene_id,
        'project_id': project_id,
        'sis_files': [],
        'text_files': [],
        'image_files': [],
        'music_files': [],
        'tts_files': [],
        'prompt_files': []
    }
    
    for file in files:
        if file.startswith('sis_structure_') and file.endswith('.json') and not file.endswith('_candidate.json'):
            scene_data['sis_files'].append(file)
        elif file.startswith('text_') and file.endswith('.txt') and not file.endswith('_prompt.txt') and not file.endswith('_candidate.txt'):
            # 純粋な本文テキストのみ。メタ/最終プロンプト(text_*_prompt.txt)は除外
            scene_data['text_files'].append(file)
        elif file.startswith('image_') and file.endswith('.png') and not file.endswith('_candidate.png'):
            scene_data['image_files'].append(file)
        elif file.startswith('music_') and file.endswith('.wav') and not file.endswith('_candidate.wav'):
            scene_data['music_files'].append(file)
        elif file.startswith('tts_') and file.endswith('.wav') and not file.endswith('_candidate.wav'):
            scene_data['tts_files'].append(file)
        # 画像プロンプトファイル（保存済み）
        elif file.endswith('_prompt.txt') and (
            file.startswith('image_') or file.startswith('sis2image_') or file.startswith('prompt_')
            or file.startswith('text_') or file.startswith('sis2text_')
            or file.startswith('music_') or file.startswith('sis2music_')
        ):
            scene_data['prompt_files'].append(file)
    
    return render_template('scene_detail.html', scene=scene_data)

@app.route("/scene/<scene_id>/file/<filename>")
def serve_scene_file(scene_id, filename):
    """Serve scene files"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return "Scene not found", 404
    
    return send_from_directory(scene_path, filename)

@app.route("/scene/<scene_id>/sis/<filename>")
def get_sis_content(scene_id, filename):
    """Return SIS file content in JSON format"""
    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        return jsonify({"error": "Scene not found"}), 404
    
    file_path = os.path.join(scene_path, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        return jsonify(content)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/scene/<scene_id>/text/<filename>")
def get_text_content_route(scene_id, filename):
    """Return text file content"""
    return get_text_content(scene_id, filename)

@app.route('/scene/<scene_id>/data')
def get_scene_data(scene_id):
    """Return comprehensive scene data for slideshow"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404
    
    try:
        scene_data = {
            'id': scene_id,
            'hasImage': False,
            'image': None,
            'text': '',
            'hasTTS': False,
            'hasMusic': False
        }

        main_text_filename = f'text_{scene_id}.txt'
        main_text_path = os.path.join(scene_path, main_text_filename)

        # メインテキスト: text_<scene_id>.txt のみをStory用テキストとして使用
        if os.path.exists(main_text_path):
            try:
                with open(main_text_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        scene_data['text'] = content
            except Exception as e:
                print(f"Error reading main text file {main_text_filename}: {e}")

        # 画像 / TTS / Music の有無だけディレクトリから確認
        for file in os.listdir(scene_path):
            file_path = os.path.join(scene_path, file)

            # Check for image
            if file.startswith('image_') and file.endswith('.png') and not file.endswith('_candidate.png'):
                scene_data['hasImage'] = True
                scene_data['image'] = f'/scene/{scene_id}/file/{file}'

            # Check for TTS audio
            elif file.startswith('tts_') and file.endswith(('.wav', '.mp3')) and not file.endswith('_candidate.wav'):
                scene_data['hasTTS'] = True

            # Check for music
            elif file.startswith('music_') and file.endswith(('.wav', '.mp3')) and not file.endswith('_candidate.wav'):
                scene_data['hasMusic'] = True

        return jsonify(scene_data)
        
    except Exception as e:
        return jsonify({'error': f'Error reading scene data: {str(e)}'}), 500

@app.route('/scene/<scene_id>/tts')
def serve_scene_tts(scene_id):
    """Serve TTS audio file for a scene"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return "Scene not found", 404
    
    # Look for TTS audio file
    for file in os.listdir(scene_path):
        if file.startswith('tts_') and file.endswith(('.wav', '.mp3')) and not file.endswith('_candidate.wav'):
            file_path = os.path.join(scene_path, file)
            return send_file(file_path)
    
    return "TTS audio not found", 404

@app.route('/scene/<scene_id>/music')
def serve_scene_music(scene_id):
    """Serve music file for a scene"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return "Scene not found", 404
    
    # Look for music file
    for file in os.listdir(scene_path):
        if file.startswith('music_') and file.endswith(('.wav', '.mp3')) and not file.endswith('_candidate.wav'):
            file_path = os.path.join(scene_path, file)
            return send_file(file_path)
    
    return "Music not found", 404

@app.route('/scene/<scene_id>/image')
def serve_scene_image(scene_id):
    """Serve image file for a scene"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return "Scene not found", 404
    
    # Look for image file
    for file in os.listdir(scene_path):
        if file.startswith('image_') and file.endswith(('.png', '.jpg', '.jpeg')) and not file.endswith('_candidate.png'):
            file_path = os.path.join(scene_path, file)
            return send_file(file_path)
    
    return "Image not found", 404

@app.route('/shared/<path:filename>')
def serve_shared_file(filename):
    """Serve files from shared directory"""
    return send_from_directory(SHARED_DIR, filename)

@app.route("/story")
def narrative_list():
    """Display narrative list"""
    narratives = []
    narrative_dir = os.path.join(SHARED_DIR, 'story')
    
    if os.path.exists(narrative_dir):
        for file in os.listdir(narrative_dir):
            if file.endswith('.html'):
                file_path = os.path.join(narrative_dir, file)
                try:
                    # Get file information
                    stat = os.stat(file_path)
                    size_kb = stat.st_size / 1024
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    
                    # Extract title from filename (remove .html extension)
                    title = file[:-5] if file.endswith('.html') else file
                    
                    narratives.append({
                        'filename': file,
                        'title': title,
                        'size_kb': size_kb,
                        'modified': modified.strftime('%Y-%m-%d %H:%M:%S'),
                        'path': f'/story/view/{file}'
                    })
                except Exception as e:
                    print(f"Error reading narrative file {file}: {e}")
    
    # Sort by modification date in descending order
    narratives.sort(key=lambda x: x['modified'], reverse=True)
    return render_template('narrative_list.html', narratives=narratives)

@app.route("/story/view/<filename>")
def view_narrative(filename):
    """Serve narrative HTML file"""
    narrative_dir = os.path.join(SHARED_DIR, 'story')
    return send_from_directory(narrative_dir, filename)

@app.route("/story/delete/<filename>", methods=['POST'])
def delete_narrative(filename):
    """Delete narrative file"""
    try:
        narrative_dir = os.path.join(SHARED_DIR, 'story')
        file_path = os.path.join(narrative_dir, filename)
        
        if os.path.exists(file_path) and filename.endswith('.html'):
            os.remove(file_path)
            return jsonify({'success': True, 'message': 'Narrative deleted successfully'})
        else:
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Error deleting narrative: {str(e)}'}), 500

@app.route("/story/save", methods=['POST'])
def save_narrative():
    """Save narrative as HTML file"""
    try:
        data = request.get_json()
        narrative_data = data.get('narrative', [])
        narrative_title = data.get('title', f'Narrative_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        
        if not narrative_data:
            return jsonify({'error': 'No narrative data provided'}), 400
        
        # Create narrative directory if it doesn't exist
        narrative_dir = os.path.join(SHARED_DIR, 'story')
        os.makedirs(narrative_dir, exist_ok=True)
        
        # Generate HTML content
        html_content = generate_narrative_html(narrative_data, narrative_title)
        
        # Save HTML file
        filename = f"{narrative_title}.html"
        file_path = os.path.join(narrative_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'path': f'/shared/story/{filename}'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error saving narrative: {str(e)}'}), 500

def generate_narrative_html(narrative_data, title):
    """Generate HTML content for narrative with embedded assets"""
    
    # Process narrative data to embed assets
    processed_data = []
    for scene_data in narrative_data:
        processed_scene = scene_data.copy()
        scene_id = scene_data.get('id')
        scene_path, _ = find_scene_path(scene_id) if scene_id else (None, None)
        scene_files = os.listdir(scene_path) if scene_path and os.path.exists(scene_path) else []
        
        if scene_path and scene_data.get('hasImage') and scene_data.get('image'):
            # Embed image as base64
            for file in scene_files:
                if file.startswith('image_') and file.endswith('.png') and not file.endswith('_candidate.png'):
                    img_file_path = os.path.join(scene_path, file)
                    if os.path.exists(img_file_path):
                        with open(img_file_path, 'rb') as img_file:
                            img_data = base64.b64encode(img_file.read()).decode('utf-8')
                            processed_scene['image_data'] = f"data:image/png;base64,{img_data}"
                    break
        
        # Embed TTS audio as base64
        if scene_path and scene_data.get('hasTTS'):
            for file in scene_files:
                if file.startswith('tts_') and file.endswith(('.wav', '.mp3')):
                    tts_file_path = os.path.join(scene_path, file)
                    if os.path.exists(tts_file_path):
                        with open(tts_file_path, 'rb') as tts_file:
                            tts_data = base64.b64encode(tts_file.read()).decode('utf-8')
                            mime_type = 'audio/wav' if file.endswith('.wav') else 'audio/mp3'
                            processed_scene['tts_data'] = f"data:{mime_type};base64,{tts_data}"
                    break
        
        # Embed music as base64
        if scene_path and scene_data.get('hasMusic'):
            for file in scene_files:
                if file.startswith('music_') and file.endswith(('.wav', '.mp3')):
                    music_file_path = os.path.join(scene_path, file)
                    if os.path.exists(music_file_path):
                        with open(music_file_path, 'rb') as music_file:
                            music_data = base64.b64encode(music_file.read()).decode('utf-8')
                            mime_type = 'audio/wav' if file.endswith('.wav') else 'audio/mp3'
                            processed_scene['music_data'] = f"data:{mime_type};base64,{music_data}"
                    break
        
        processed_data.append(processed_scene)
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css">
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
        }}
        
        .narrative-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .narrative-header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .narrative-swiper {{
            width: 100%;
            height: 600px;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        
        .narrative-slide {{
            display: flex;
            flex-direction: row;
            justify-content: center;
            align-items: center;
            background: white;
            padding: 40px;
            position: relative;
            gap: 40px;
            min-height: 500px;
        }}
        
        .slide-content {{
            display: flex;
            flex-direction: row;
            align-items: center;
            gap: 40px;
            width: 100%;
            max-width: 1000px;
        }}
        
        .slide-image-container {{
            flex: 0 0 400px;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        
        .slide-text-container {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .slide-image {{
            width: 100%;
            max-width: 400px;
            height: auto;
            max-height: 400px;
            object-fit: contain;
            border-radius: 12px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        
        .slide-image.no-image {{
            width: 400px;
            height: 300px;
            background-color: #e9ecef;
            border: 2px dashed #ced4da;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #6c757d;
            font-size: 18px;
        }}
        
        .slide-text {{
            font-size: 18px;
            line-height: 1.6;
            color: #333;
            max-height: 400px;
            overflow-y: auto;
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #007bff;
            text-align: left;
            margin: 0;
        }}
        
        .slide-scene-info {{
            position: absolute;
            top: 20px;
            left: 20px;
            background-color: rgba(0,0,0,0.7);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: bold;
        }}
        
        .slide-number {{
            position: absolute;
            top: 20px;
            right: 20px;
            background-color: rgba(0,123,255,0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: bold;
        }}
        
        .narrative-swiper .swiper-button-next,
        .narrative-swiper .swiper-button-prev {{
            color: #007bff;
            background-color: rgba(255,255,255,0.9);
            width: 44px;
            height: 44px;
            border-radius: 50%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .narrative-swiper .swiper-pagination-bullet {{
            background-color: #007bff;
            opacity: 0.7;
        }}
        
        .narrative-swiper .swiper-pagination-bullet-active {{
            opacity: 1;
        }}
        
        .audio-controls {{
            text-align: center;
            margin-top: 20px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .audio-btn {{
            margin: 0 10px;
            padding: 10px 20px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }}
        
        .audio-btn:hover {{
            background-color: #0056b3;
        }}
        
        .audio-btn:disabled {{
            background-color: #6c757d;
            cursor: not-allowed;
        }}
    </style>
</head>
<body>
    <div class="narrative-container">
        <div class="narrative-header">
            <h1>{title}</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="swiper narrative-swiper">
            <div class="swiper-wrapper">
                {generate_slides_html(processed_data)}
            </div>
            
            <div class="swiper-button-next"></div>
            <div class="swiper-button-prev"></div>
            <div class="swiper-pagination"></div>
        </div>
        
        <div class="audio-controls">
            <div id="audioNotice" class="audio-notice" style="display: block; margin-bottom: 15px; padding: 10px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 6px; color: #856404; text-align: center;">
                🔊 Click anywhere on the page to enable audio playback
            </div>
            <button class="audio-btn" onclick="toggleAutoPlay()">Auto Play: ON</button>
            <button class="audio-btn" onclick="stopAllAudio()">Stop Audio</button>
            <button class="audio-btn" onclick="playCurrentSlideAudio()">Play Current Slide</button>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js"></script>
    <script>
        let narrativeSwiper;
        let autoPlay = true;
        let currentTTSAudio = null;
        let currentMusicAudio = null;
        let hasUserInteracted = false;
        
        // Store embedded audio data
        const embeddedAudio = {json.dumps({scene['id']: {'tts': scene.get('tts_data'), 'music': scene.get('music_data')} for scene in processed_data})};
        
        document.addEventListener('DOMContentLoaded', function() {{
            initializeSwiper();
            setupUserInteraction();
        }});
        
        function setupUserInteraction() {{
            // Add click event listener to enable audio after user interaction
            document.addEventListener('click', function enableAudio() {{
                hasUserInteracted = true;
                const audioNotice = document.getElementById('audioNotice');
                if (audioNotice) {{
                    audioNotice.style.display = 'none';
                }}
                if (autoPlay && narrativeSwiper) {{
                    setTimeout(() => {{
                        playSlideAudio(narrativeSwiper.activeIndex);
                    }}, 100);
                }}
            }}, {{ once: true }});
            
            // Add keydown event listener as well
            document.addEventListener('keydown', function enableAudioKey() {{
                hasUserInteracted = true;
                const audioNotice = document.getElementById('audioNotice');
                if (audioNotice) {{
                    audioNotice.style.display = 'none';
                }}
                if (autoPlay && narrativeSwiper) {{
                    setTimeout(() => {{
                        playSlideAudio(narrativeSwiper.activeIndex);
                    }}, 100);
                }}
            }}, {{ once: true }});
        }}
        
        function initializeSwiper() {{
            narrativeSwiper = new Swiper('.narrative-swiper', {{
                direction: 'horizontal',
                loop: false,
                speed: 600,
                navigation: {{
                    nextEl: '.swiper-button-next',
                    prevEl: '.swiper-button-prev',
                }},
                pagination: {{
                    el: '.swiper-pagination',
                    clickable: true,
                    type: 'bullets',
                }},
                keyboard: {{ enabled: true }},
                mousewheel: {{ enabled: true }},
                on: {{
                    slideChange: function () {{
                        if (autoPlay && hasUserInteracted) {{
                            playSlideAudio(this.activeIndex);
                        }}
                    }},
                    init: function () {{
                        // Display initial slide without auto-playing audio
                        console.log('Swiper initialized. Click anywhere to enable audio.');
                    }}
                }}
            }});
        }}
        
        function playSlideAudio(slideIndex) {{
            stopAllAudio();
            
            const slides = document.querySelectorAll('.narrative-slide');
            if (!slides || slideIndex >= slides.length) return;
            
            const currentSlide = slides[slideIndex];
            const sceneId = currentSlide.dataset.sceneId;
            const hasTTS = currentSlide.dataset.hasTts === 'true';
            const hasMusic = currentSlide.dataset.hasMusic === 'true';
            
            if (hasTTS && embeddedAudio[sceneId] && embeddedAudio[sceneId].tts) {{
                playTTSAudio(sceneId);
            }}
            
            if (hasMusic && embeddedAudio[sceneId] && embeddedAudio[sceneId].music) {{
                setTimeout(() => {{
                    playMusicAudio(sceneId);
                }}, hasTTS ? 1000 : 0);
            }}
        }}
        
        function playTTSAudio(sceneId) {{
            try {{
                const ttsData = embeddedAudio[sceneId].tts;
                if (ttsData) {{
                    const audio = new Audio(ttsData);
                    audio.volume = 0.8;
                    audio.play().catch(console.error);
                    currentTTSAudio = audio;
                }}
            }} catch (error) {{
                console.error('Error playing TTS:', error);
            }}
        }}
        
        function playMusicAudio(sceneId) {{
            try {{
                const musicData = embeddedAudio[sceneId].music;
                if (musicData) {{
                    const audio = new Audio(musicData);
                    audio.volume = 0.3;
                    audio.loop = true;
                    audio.play().catch(console.error);
                    currentMusicAudio = audio;
                }}
            }} catch (error) {{
                console.error('Error playing music:', error);
            }}
        }}
        
        function stopAllAudio() {{
            if (currentTTSAudio) {{
                currentTTSAudio.pause();
                currentTTSAudio.currentTime = 0;
                currentTTSAudio = null;
            }}
            if (currentMusicAudio) {{
                currentMusicAudio.pause();
                currentMusicAudio.currentTime = 0;
                currentMusicAudio = null;
            }}
        }}
        
        function toggleAutoPlay() {{
            autoPlay = !autoPlay;
            const btn = event.target;
            btn.textContent = `Auto Play: ${{autoPlay ? 'ON' : 'OFF'}}`;
            if (!autoPlay) {{
                stopAllAudio();
            }}
        }}
        
        function playCurrentSlideAudio() {{
            hasUserInteracted = true;
            const audioNotice = document.getElementById('audioNotice');
            if (audioNotice) {{
                audioNotice.style.display = 'none';
            }}
            if (narrativeSwiper) {{
                playSlideAudio(narrativeSwiper.activeIndex);
            }}
        }}
    </script>
</body>
</html>"""
    
    return html_template

def generate_slides_html(narrative_data):
    """Generate HTML for slides with embedded assets"""
    slides_html = ""
    total_slides = len(narrative_data)
    
    for i, scene_data in enumerate(narrative_data):
        scene_id = scene_data.get('id', f'scene_{i}')
        has_image = scene_data.get('hasImage', False)
        text = scene_data.get('text', 'No text available')
        has_tts = scene_data.get('hasTTS', False)
        has_music = scene_data.get('hasMusic', False)
        
        # Use embedded image data if available
        if has_image and scene_data.get('image_data'):
            image_html = f'<img src="{scene_data["image_data"]}" alt="Scene {scene_id}" class="slide-image">'
        else:
            image_html = '<div class="slide-image no-image">No Image Available</div>'
        
        slide_html = f"""
                <div class="swiper-slide">
                    <div class="narrative-slide" data-scene-id="{scene_id}" data-has-tts="{str(has_tts).lower()}" data-has-music="{str(has_music).lower()}">
                        <div class="slide-scene-info">Scene {scene_id}</div>
                        <div class="slide-number">{i + 1} / {total_slides}</div>
                        <div class="slide-content">
                            <div class="slide-image-container">
                                {image_html}
                            </div>
                            <div class="slide-text-container">
                                <div class="slide-text">{text}</div>
                            </div>
                        </div>
                    </div>
                </div>"""
        
        slides_html += slide_html
    
    return slides_html

def get_text_content(scene_id, filename):
    """Return text file content"""
    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        return "Scene not found", 404
    
    file_path = os.path.join(scene_path, filename)
    
    if not os.path.exists(file_path):
        return "File not found", 404
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}", 500

@app.route("/projects/<project_id>/scenes/<scene_id>/upload_image", methods=['POST'])
def upload_project_image(project_id, scene_id):
    """Upload and replace image file in project scene"""
    scene_path = os.path.join(PROJECTS_DIR, project_id, 'scenes', scene_id)
    
    if not os.path.exists(scene_path):
        return jsonify({'success': False, 'error': 'Scene not found'}), 404
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    try:
        # Remove existing image files
        for existing_file in os.listdir(scene_path):
            if existing_file.startswith('image_') and existing_file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                os.remove(os.path.join(scene_path, existing_file))
        
        # Save new image
        new_filename = f"image_{scene_id}.png"
        file_path = os.path.join(scene_path, new_filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': new_filename,
            'message': 'Image uploaded successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/projects/<project_id>/scenes/<scene_id>/save_sis", methods=['POST'])
def save_project_sis(project_id, scene_id):
    """Save edited SIS content to file in project scene"""
    scene_path = os.path.join(PROJECTS_DIR, project_id, 'scenes', scene_id)
    
    if not os.path.exists(scene_path):
        return jsonify({'success': False, 'error': 'Scene not found'}), 404
    
    try:
        sis_data = request.get_json()
        if not sis_data:
            return jsonify({'success': False, 'error': 'No content provided'}), 400
        
        filename = f'sis_structure_{scene_id}.json'
        file_path = os.path.join(scene_path, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(sis_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'SIS saved successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/scene/<scene_id>/upload_image", methods=['POST'])
def upload_image(scene_id):
    """Upload and replace image file in scene"""
    scene_path, project_id = find_scene_path(scene_id)
    
    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check if this is an overwrite operation
    is_overwrite = request.form.get('overwrite', 'false').lower() == 'true'
    prompt = request.form.get('prompt', '')
    
    # Check file type
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Allowed: ' + ', '.join(allowed_extensions)}), 400
    
    try:
        # Remove existing image files
        for existing_file in os.listdir(scene_path):
            if existing_file.startswith('image_') and existing_file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                os.remove(os.path.join(scene_path, existing_file))
        
        # Save new image with standard naming
        new_filename = f"image_{scene_id}.png"
        file_path = os.path.join(scene_path, new_filename)
        file.save(file_path)
        
        # If this is an overwrite with prompt, save the prompt information
        if is_overwrite and prompt:
            prompt_filename = f"image_{scene_id}_prompt.txt"
            prompt_path = os.path.join(scene_path, prompt_filename)
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(f"Generated Image Prompt:\n{prompt}\n\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        message = 'Image replaced successfully' if is_overwrite else 'Image uploaded successfully'
        
        return jsonify({
            'success': True,
            'filename': new_filename,
            'message': message,
            'overwrite': is_overwrite
        })
        
    except Exception as e:
        return jsonify({'error': f'Error uploading image: {str(e)}'}), 500

@app.route("/scene/<scene_id>/upload_music", methods=['POST'])
def upload_music(scene_id):
    """Upload and replace music file in scene"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file type
    allowed_extensions = {'.wav', '.mp3', '.ogg', '.m4a'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Allowed: ' + ', '.join(allowed_extensions)}), 400
    
    try:
        # Remove existing music files
        for existing_file in os.listdir(scene_path):
            if existing_file.startswith('music_') and existing_file.endswith(('.wav', '.mp3', '.ogg', '.m4a')):
                os.remove(os.path.join(scene_path, existing_file))
        
        # Save new music with standard naming (always save as .wav for consistency)
        new_filename = f"music_{scene_id}.wav"
        file_path = os.path.join(scene_path, new_filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': new_filename,
            'message': 'Music uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error uploading music: {str(e)}'}), 500

@app.route("/scene/<scene_id>/save_text", methods=['POST'])
def save_text(scene_id):
    """Save edited text content to file"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404
    
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'No content provided'}), 400
    
    content = data['content']
    filename = data.get('filename', f'text_{scene_id}.txt')
    
    # Ensure filename follows the expected pattern
    if not filename.startswith('text_') or not filename.endswith('.txt'):
        filename = f'text_{scene_id}.txt'
    
    try:
        file_path = os.path.join(scene_path, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Text saved successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error saving text: {str(e)}'}), 500

@app.route("/scene/<scene_id>/save_sis", methods=['POST'])
def save_sis(scene_id):
    """Save edited SIS content to file"""
    scene_path, project_id = find_scene_path(scene_id)
    
    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404
    
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'No content provided'}), 400
    
    content = data['content']
    filename = data.get('filename')

    # Decide filename if not provided or invalid
    if not filename:
        # Guess by content shape (very simple heuristic)
        stripped = content.lstrip()
        if stripped.startswith('{') or stripped.startswith('['):
            filename = f'sis_structure_{scene_id}.json'
        else:
            filename = f'sis_raw_{scene_id}.txt'

    # Validate/normalize filename
    is_raw = filename.startswith('sis_raw_') and filename.endswith('.txt')
    is_json = filename.startswith('sis_structure_') and filename.endswith('.json')
    if not (is_raw or is_json):
        # Fallback by content heuristic
        stripped = content.lstrip()
        if stripped.startswith('{') or stripped.startswith('['):
            filename = f'sis_structure_{scene_id}.json'
            is_json = True
            is_raw = False
        else:
            filename = f'sis_raw_{scene_id}.txt'
            is_raw = True
            is_json = False

    try:
        file_path = os.path.join(scene_path, filename)
        
        if is_json:
            # Validate JSON content
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                return jsonify({'error': f'Invalid JSON format: {str(e)}'}), 400
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            # Raw text: save as-is
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'SIS saved successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error saving SIS: {str(e)}'}), 500

@app.route("/scene/<scene_id>/save_prompt", methods=['POST'])
def save_prompt(scene_id):
    """Save edited image prompt content to file"""
    scene_path, _ = find_scene_path(scene_id)

    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404

    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'No content provided'}), 400

    content = data['content']
    filename = data.get('filename', f'image_{scene_id}_prompt.txt')

    # Ensure filename follows the expected pattern for prompt files
    valid_prefix = (
        filename.startswith('image_') or filename.startswith('sis2image_') or filename.startswith('prompt_')
        or filename.startswith('text_') or filename.startswith('sis2text_')
        or filename.startswith('music_') or filename.startswith('sis2music_')
    )
    if not (valid_prefix and filename.endswith('_prompt.txt')):
        filename = f'image_{scene_id}_prompt.txt'

    try:
        file_path = os.path.join(scene_path, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Prompt saved successfully'
        })
    except Exception as e:
        return jsonify({'error': f'Error saving prompt: {str(e)}'}), 500

 

@app.route("/scene/<scene_id>/generate_sis", methods=['POST'])
def generate_sis(scene_id):
    """Generate SIS from scene content (image, text, or music).

    シンプル版:
      - content_type (image|text|music) をPOST JSONで受け取り、対応ファイルを検索
      - SISExtractor -> fallback -> dummy の順に試行
      - LLM出力は raw テキストとして保存・返却し、JSONとしても解釈できれば json_valid=True
      - 構造化JSONが得られた場合のみ各種 prompt を生成
    """
    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404

    # Debug info (軽量)
    debug_info = {
        'SIS_EXTRACTOR_AVAILABLE': SIS_EXTRACTOR_AVAILABLE,
        'scene_id': scene_id,
    }

    # リクエストJSON取得
    data = request.get_json(silent=True) or {}
    content_type = data.get('content_type')
    output_mode = (data.get('output_mode') or 'overwrite').strip()
    if output_mode not in ['overwrite', 'candidate']:
        output_mode = 'overwrite'
    if content_type not in ['image', 'text', 'music']:
        return jsonify({'error': 'Invalid or missing content_type'}), 400

    # 対応ファイル検索
    patterns = {
        'image': ('image_', '.png'),
        'text': ('text_', '.txt'),
        'music': ('music_', '.wav'),
    }
    prefix, suffix = patterns[content_type]
    content_file = None
    for f in os.listdir(scene_path):
        if f.startswith(prefix) and f.endswith(suffix):
            content_file = os.path.join(scene_path, f)
            break
    if not content_file:
        return jsonify({'error': f'No {content_type} file found'}), 404

    # SIS生成
    result = None
    method = 'none'
    processing_time = 0

    try:
        if SIS_EXTRACTOR_AVAILABLE is True:
            api_config = APIConfig(
                ollama_uri="http://ollama:11434",
                ollama_model=os.environ.get('OLLAMA_MODEL', 'gemma3:4b-it-qat'),
                timeout=120
            )
            extractor = SISExtractor(api_config=api_config)
            result = extractor.process(content_file, content_type)
            method = 'unified'
            processing_time = getattr(result, 'metadata', {}).get('processing_time', 0)
    except Exception as e:
        print(f"Unified extraction failed: {e}")
        result = None

    if result is None and (SIS_EXTRACTOR_AVAILABLE in [True, 'fallback']):
        try:
            result = extract_sis_fallback(content_file, content_type)
            method = 'fallback'
        except Exception as e:
            print(f"Fallback extraction failed: {e}")
            result = None

    if result is None:
        try:
            result = generate_dummy_sis(content_file, content_type)
            method = 'dummy'
        except Exception as e:
            return jsonify({'error': f'All SIS generation methods failed: {e}'}), 500

    # raw テキスト抽出
    raw_text = ''
    sis_json = None
    if method == 'unified' and hasattr(result, 'data'):
        d = result.data
        if isinstance(d, dict):
            if 'content' in d:
                raw_text = d.get('content', '')
            elif 'sis_data' in d:
                try:
                    sis_json = d['sis_data'] if isinstance(d['sis_data'], dict) else None
                    raw_text = json.dumps(d['sis_data'], ensure_ascii=False, indent=2)
                except Exception:
                    raw_text = str(d['sis_data'])
            else:
                raw_text = str(d)
        else:
            raw_text = str(d)
    elif method in ['fallback', 'dummy'] and isinstance(result, dict):
        if result.get('success') and 'sis_data' in result:
            try:
                sis_json = result['sis_data'] if isinstance(result['sis_data'], dict) else None
                raw_text = json.dumps(result['sis_data'], ensure_ascii=False, indent=2)
            except Exception:
                raw_text = str(result['sis_data'])
        else:
            raw_text = str(result)

    if not raw_text:
        raw_text = 'No SIS content produced.'

    # JSONパース試行（壊れていてもOK）
    json_valid = False
    parse_error = None
    if sis_json is None and raw_text:
        try:
            sis_json = json.loads(raw_text)
            json_valid = True
        except Exception as e:
            parse_error = str(e)
    else:
        json_valid = sis_json is not None

    # 保存 (raw + optional structured)
    sis_raw_name = f'sis_raw_{scene_id}.txt' if output_mode == 'overwrite' else f'sis_raw_{scene_id}_candidate.txt'
    sis_struct_name = f'sis_structure_{scene_id}.json' if output_mode == 'overwrite' else f'sis_structure_{scene_id}_candidate.json'
    try:
        with open(os.path.join(scene_path, sis_raw_name), 'w', encoding='utf-8') as f:
            f.write(raw_text)
    except Exception as e:
        print(f"Failed to save raw SIS: {e}")

    if json_valid:
        try:
            with open(os.path.join(scene_path, sis_struct_name), 'w', encoding='utf-8') as jf:
                json.dump(sis_json, jf, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save structured SIS: {e}")

    return jsonify({
        'success': True,
        'filename': sis_raw_name,
        'candidate_raw_filename': sis_raw_name if output_mode == 'candidate' else None,
        'candidate_structured_filename': sis_struct_name if (output_mode == 'candidate' and json_valid) else None,
        'output_mode': output_mode,
        'sis_raw_text': raw_text,
        'json_valid': json_valid,
        'json_parse_error': parse_error,
        'processing_time': processing_time,
        'method': method,
        'prompts': {},
        'debug_info': debug_info,
    })


@app.route("/scene/<scene_id>/save_generated_sis", methods=['POST'])
def save_generated_sis(scene_id):
    """Confirm pending generated SIS by overwriting canonical raw/structured files."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True) or {}
        candidate_raw = (payload.get('candidate_raw_filename') or '').strip()
        candidate_struct = (payload.get('candidate_structured_filename') or '').strip()

        def _is_safe(name: str) -> bool:
            return bool(name) and '/' not in name and '\\' not in name

        if not _is_safe(candidate_raw) or not candidate_raw.endswith('_candidate.txt') or not candidate_raw.startswith('sis_raw_'):
            return jsonify({'success': False, 'error': 'Invalid SIS candidate raw filename'}), 400

        raw_src = os.path.join(scene_path, candidate_raw)
        if not os.path.exists(raw_src):
            return jsonify({'success': False, 'error': 'Candidate raw file not found'}), 404

        raw_dst_name = f'sis_raw_{scene_id}.txt'
        raw_dst = os.path.join(scene_path, raw_dst_name)
        os.replace(raw_src, raw_dst)

        struct_dst_name = None
        if candidate_struct:
            if not _is_safe(candidate_struct) or not candidate_struct.endswith('_candidate.json') or not candidate_struct.startswith('sis_structure_'):
                return jsonify({'success': False, 'error': 'Invalid SIS candidate structured filename'}), 400
            struct_src = os.path.join(scene_path, candidate_struct)
            if not os.path.exists(struct_src):
                return jsonify({'success': False, 'error': 'Candidate structured file not found'}), 404
            struct_dst_name = f'sis_structure_{scene_id}.json'
            struct_dst = os.path.join(scene_path, struct_dst_name)
            os.replace(struct_src, struct_dst)

        return jsonify({
            'success': True,
            'sis_raw_filename': raw_dst_name,
            'sis_structured_filename': struct_dst_name,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/scene/<scene_id>/discard_generated_sis", methods=['POST'])
def discard_generated_sis(scene_id):
    """Discard pending generated SIS candidate files."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True) or {}
        candidate_raw = (payload.get('candidate_raw_filename') or '').strip()
        candidate_struct = (payload.get('candidate_structured_filename') or '').strip()

        def _safe_delete(name: str):
            if not name:
                return
            if '/' in name or '\\' in name:
                return
            try:
                p = os.path.join(scene_path, name)
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

        _safe_delete(candidate_raw)
        _safe_delete(candidate_struct)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/scene/<scene_id>/regenerate_prompts", methods=['POST'])
def regenerate_prompts(scene_id):
    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        return jsonify({'success': False, 'error': 'Scene not found'}), 404

    sis_json = load_structured_sis(scene_id)
    if not sis_json:
        return jsonify({
            'success': False,
            'error': 'No structured SIS data is available. Generate or save a JSON SIS first.'
        }), 400

    try:
        prompts, failures = regenerate_prompts_from_sis(scene_id, sis_json)
    except Exception as exc:
        print(f"Prompt regeneration failed for scene {scene_id}: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500

    response = {
        'success': True,
        'prompts': prompts
    }

    if failures:
        response['warnings'] = failures

    return jsonify(response)

@app.route("/scene/<scene_id>/generate_image", methods=['POST'])
def generate_image_from_sis(scene_id):
    """Generate image from SIS data"""
    try:
        print(f"🖼️ Generate Image from SIS API called for scene: {scene_id}")
        sys.stdout.flush()
        
        # リクエストボディからオプションを取得（prompt_only など）
        req_json = None
        try:
            req_json = request.get_json(silent=True) or {}
        except Exception:
            req_json = {}
        prompt_only = bool(req_json.get('prompt_only', False))
        if prompt_only:
            print("⏭️ prompt_only mode enabled: will generate prompt and skip SD image generation")
            sys.stdout.flush()

        scene_path, _ = find_scene_path(scene_id)
        
        if not scene_path:
            print(f"❌ Scene not found: {scene_id}")
            sys.stdout.flush()
            return jsonify({'error': 'Scene not found'}), 404
        
        # SISファイルを探す
        sis_files = [f for f in os.listdir(scene_path) if f.startswith('sis_structure_') and f.endswith('.json') and not f.endswith('_candidate.json')]
        
        if not sis_files:
            print(f"❌ No SIS file found in scene: {scene_path}")
            sys.stdout.flush()
            return jsonify({'error': 'No SIS file found. Please generate SIS first.'}), 404
        
        # 最新のSISファイルを使用
        sis_file = sis_files[0]
        sis_filepath = os.path.join(scene_path, sis_file)
        
        # SISデータを読み込み
        try:
            with open(sis_filepath, 'r', encoding='utf-8') as f:
                sis_data = json.load(f)
            print(f"✅ SIS data loaded: {sis_file}")
            print(f"📝 SIS summary: {sis_data.get('summary', 'N/A')[:100]}")
            print(f"📊 SIS data keys: {list(sis_data.keys())}")
            sys.stdout.flush()
        except Exception as sis_error:
            print(f"❌ Error reading SIS file: {sis_error}")
            sys.stdout.flush()
            return jsonify({'error': f'Error reading SIS file: {str(sis_error)}'}), 500
        
        # SISからコンテンツ生成モジュールが利用可能か確認
        if not SIS_TO_CONTENT_AVAILABLE:
            print(f"❌ SIS to content generation not available")
            sys.stdout.flush()
            return jsonify({'error': 'SIS to content generation system not available'}), 500
        
        # APIコンフィグ設定
        api_config = APIConfig(
            unsloth_uri='http://unsloth:5007',
            sd_uri='http://sd:7860',
            music_uri='http://music:5003',
            tts_uri='http://tts:5002',
            timeout=120
        )
        
        # 画像生成設定
        processing_config = ProcessingConfig(output_dir='/app/shared')
        generation_config = GenerationConfig(
            image_width=1024,
            image_height=768,
            max_tokens=512,
            temperature=0.8
        )
        
        # 画像生成実行
        print(f"🎨 Starting image generation from SIS...")
        print(f"🔧 API Config - Unsloth: {api_config.unsloth_uri}, SD: {api_config.sd_uri}")
        print(f"🔧 Generation Config - Size: {generation_config.image_width}x{generation_config.image_height}")
        sys.stdout.flush()
        
        try:
            result = generate_content(
                sis_data=sis_data,
                content_type='image',
                api_config=api_config,
                processing_config=processing_config,
                generation_config=generation_config,
                custom_timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
                test_case_name=f"scene_{scene_id}",
                skip_actual_generation=prompt_only
            )
            print(f"🎨 generate_content returned: {type(result)}")
            print(f"🎨 Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            sys.stdout.flush()
        except Exception as gen_error:
            print(f"❌ Error in generate_content: {gen_error}")
            print(f"📍 Exception type: {type(gen_error).__name__}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return jsonify({'error': f'Error in image generation: {str(gen_error)}'}), 500
        
        if result['success']:
            print(f"✅ Image generation completed successfully")
            print(f"📁 Output path: {result['output_path']}")
            print(f"⏱️ Processing time: {result['metadata']['processing_time']:.1f} seconds")
            
            # 画像ファイルが生成されている場合の処理
            image_info = {}
            replaced_filename = None
            # プロンプトをシーンディレクトリに保存（常に保存）
            prompt_filename = f"image_{scene_id}_prompt.txt"
            try:
                prompt_txt = result.get('generated_text') or ''
                prompt_path_scene = os.path.join(scene_path, prompt_filename)
                with open(prompt_path_scene, 'w', encoding='utf-8') as pf:
                    pf.write(prompt_txt)
                print(f"💾 Prompt saved to scene: {prompt_path_scene}")
            except Exception as pe:
                print(f"⚠️ Failed to save prompt text to scene: {pe}")

            if not prompt_only and result.get('image_result') and result['image_result'].get('success'):
                img_result = result['image_result']
                print(f"🖼️ Image file generated: {img_result['image_path']}")
                
                # 画像のWebアクセスURLを生成
                # /app/shared/test_result_xxx/image.png -> /shared/test_result_xxx/image.png
                relative_path = img_result['image_path'].replace('/app/shared/', '').replace('\\', '/')
                image_url = f"/shared/{relative_path}"
                
                image_info = {
                    'image_generated': True,
                    'image_path': img_result['image_path'],
                    # Save確定用: /app/shared 配下の生成結果をそのまま返す
                    'source_path': img_result['image_path'],
                    'image_url': image_url,
                    'image_filename': img_result['image_filename'],
                    'image_size': img_result['image_size'],
                    'generation_time': img_result['generation_time']
                }
                print(f"🌐 Image URL: {image_url}")
            else:
                print(f"⚠️ Image prompt generated but actual image not created")
                image_info = {
                    'image_generated': False,
                    'reason': 'prompt_only' if prompt_only else result.get('image_result', {}).get('error', 'Image server not available')
                }
            
            sys.stdout.flush()
            
            return jsonify({
                'success': True,
                'message': 'Image generation from SIS completed successfully',
                'prompt': result['generated_text'],
                'prompt_path': result['output_path'],
                'prompt_filename': prompt_filename,
                'processing_time': result['metadata']['processing_time'],
                'image_info': image_info,
                'method': 'sis_to_image',
                'prompt_only': prompt_only
                , 'replaced_image': None
            })
        
        else:
            error_msg = result.get('error', 'Unknown error in image generation')
            print(f"❌ Image generation failed: {error_msg}")
            sys.stdout.flush()
            
            return jsonify({
                'error': f'Image generation failed: {error_msg}',
                'error_code': 'IMAGE_GENERATION_FAILED'
            }), 500
    
    except Exception as e:
        error_message = f"Unexpected error in image generation: {str(e)}"
        print(f"❌ {error_message}")
        print(f"📍 Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        
        return jsonify({
            'error': error_message,
            'error_code': 'UNEXPECTED_ERROR'
        }), 500

@app.route("/scene/<scene_id>/sd_generate_image", methods=['POST'])
def sd_generate_image(scene_id):
    """Stable Diffusionへのダイレクトtxt2img（Unsloth非依存・軽量版）。
    Request JSON: { prompt: str, width?: int=1024, height?: int=768, steps?: int=20, cfg_scale?: float=7.0, sampler_name?: str, seed?: int=-1 }
    Response: { success, image_url?, image_filename?, prompt?, error? }
    """
    try:
        data = request.get_json(silent=True) or {}
        prompt = (data.get('prompt') or '').strip()
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400

        width = int(data.get('width') or 512)
        height = int(data.get('height') or 512)
        steps = int(data.get('steps') or 20)
        cfg_scale = float(data.get('cfg_scale') or 7.0)
        sampler = data.get('sampler_name') or 'Euler a'
        seed = data.get('seed') if data.get('seed') is not None else -1

        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        sd_uri = 'http://sd:7860'
        payload = {
            'prompt': prompt,
            'negative_prompt': data.get('negative_prompt') or 'low quality, blurry, distorted, watermark, text',
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'sampler_name': sampler,
            'seed': seed,
            'batch_size': 1,
            'n_iter': 1,
        }

        resp = requests.post(f"{sd_uri}/sdapi/v1/txt2img", json=payload, timeout=(10, 300))
        if resp.status_code != 200:
            return jsonify({'success': False, 'error': f"HTTP {resp.status_code} from SD"}), resp.status_code

        rj = resp.json() or {}
        images = rj.get('images') or []
        if not images:
            return jsonify({'success': False, 'error': 'No images returned from SD'}), 502

        # 先頭画像をデコードして保存
        import base64 as _b64
        img_b64 = images[0]
        try:
            img_bytes = _b64.b64decode(img_b64)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Base64 decode error: {str(e)}'}), 500

        # 既存画像は消さず「候補画像」として保存（Saveで確定）
        candidate_filename = f"image_{scene_id}_candidate.png"
        target_path = os.path.join(scene_path, candidate_filename)

        with open(target_path, 'wb') as f:
            f.write(img_bytes)

        # プロンプト保存
        try:
            with open(os.path.join(scene_path, f"image_{scene_id}_prompt.txt"), 'w', encoding='utf-8') as pf:
                pf.write(prompt)
        except Exception:
            pass

        image_url = f"/scene/{scene_id}/file/{candidate_filename}"
        return jsonify({
            'success': True,
            # 互換のため image_url は候補画像URL
            'image_url': image_url,
            'candidate_image_url': image_url,
            'candidate_filename': candidate_filename,
            'is_candidate': True,
            'prompt': prompt,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/save_generated_image", methods=['POST'])
def save_generated_image(scene_id):
    """候補画像をシーンの本番画像(image_<scene_id>.*)として確定保存する。
    Request JSON:
      - candidate_filename?: str  (sceneディレクトリ内の候補)
      - source_path?: str         (/app/shared 配下の生成物パス)
    Response:
      { success, filename, image_url }
    """
    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        return jsonify({'success': False, 'error': 'Scene not found'}), 404

    data = request.get_json(silent=True) or {}
    candidate_filename = (data.get('candidate_filename') or '').strip()
    source_path = (data.get('source_path') or '').strip()

    src_path = None
    if candidate_filename:
        # scene配下のみ許可
        if '/' in candidate_filename or '\\' in candidate_filename:
            return jsonify({'success': False, 'error': 'Invalid candidate_filename'}), 400
        src_path = os.path.join(scene_path, candidate_filename)
    elif source_path:
        # /app/shared 配下のみ許可
        norm = source_path.replace('\\\\', '/').replace('\\', '/')
        if not norm.startswith('/app/shared/'):
            return jsonify({'success': False, 'error': 'Invalid source_path'}), 400
        src_path = source_path
    else:
        return jsonify({'success': False, 'error': 'candidate_filename or source_path is required'}), 400

    if not os.path.exists(src_path):
        return jsonify({'success': False, 'error': 'Source image not found'}), 404

    # 既存の image_*.{png,jpg,jpeg} を削除（候補ファイルは後でmove/copyする）
    try:
        for existing_file in os.listdir(scene_path):
            if existing_file.startswith('image_') and existing_file.endswith(('.png', '.jpg', '.jpeg')):
                # candidate_filename は残してOK（moveするなら消えても良いが安全に避ける）
                if candidate_filename and existing_file == candidate_filename:
                    continue
                try:
                    os.remove(os.path.join(scene_path, existing_file))
                except Exception as rm_err:
                    print(f"⚠️ Failed to remove old image {existing_file}: {rm_err}")
    except Exception:
        pass

    # 本番ファイル名（png固定。入力がjpgでも一旦png名で保存）
    target_filename = f"image_{scene_id}.png"
    target_path = os.path.join(scene_path, target_filename)

    try:
        import shutil
        # scene内候補はmove、それ以外はcopy
        if candidate_filename and os.path.abspath(src_path).startswith(os.path.abspath(scene_path)):
            shutil.move(src_path, target_path)
        else:
            shutil.copy2(src_path, target_path)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to save image: {str(e)}'}), 500

    image_url = f"/scene/{scene_id}/file/{target_filename}"
    return jsonify({'success': True, 'filename': target_filename, 'image_url': image_url})


@app.route("/scene/<scene_id>/discard_generated_image", methods=['POST'])
def discard_generated_image(scene_id):
    """候補画像(image_<scene_id>_candidate.png)を破棄する。"""
    scene_path, _ = find_scene_path(scene_id)
    if not scene_path:
        return jsonify({'success': False, 'error': 'Scene not found'}), 404

    data = request.get_json(silent=True) or {}
    candidate_filename = (data.get('candidate_filename') or '').strip()
    if candidate_filename:
        if '/' in candidate_filename or '\\' in candidate_filename:
            return jsonify({'success': False, 'error': 'Invalid candidate_filename'}), 400
        if not candidate_filename.endswith('_candidate.png'):
            return jsonify({'success': False, 'error': 'Invalid candidate filename'}), 400
    else:
        candidate_filename = f"image_{scene_id}_candidate.png"

    candidate_path = os.path.join(scene_path, candidate_filename)
    if os.path.exists(candidate_path):
        try:
            os.remove(candidate_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to delete candidate: {str(e)}'}), 500

    return jsonify({'success': True})

@app.route("/scene/<scene_id>/generate_text", methods=['POST'])
def generate_text_from_sis(scene_id):
    """Generate story text from SIS data and save to scene text file.
    Response: { success, generated_text?, text_filename?, processing_time?, error? }
    """
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        # Find SIS file
        sis_files = [f for f in os.listdir(scene_path) if f.startswith('sis_structure_') and f.endswith('.json') and not f.endswith('_candidate.json')]
        if not sis_files:
            return jsonify({'success': False, 'error': 'No SIS file found. Please generate SIS first.'}), 404
        sis_filepath = os.path.join(scene_path, sis_files[0])

        # Load SIS JSON
        try:
            with open(sis_filepath, 'r', encoding='utf-8') as f:
                sis_data = json.load(f)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error reading SIS file: {str(e)}'}), 500

        # Enforce unified pipeline only (no direct Ollama fallback)
        if not SIS_TO_CONTENT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Unified content generator is not available', 'error_code': 'UNIFIED_UNAVAILABLE'}), 503

        generated_text = None
        processing_time = None
        try:
            api_config = APIConfig(
                unsloth_uri='http://unsloth:5007',
                sd_uri='http://sd:7860',
                music_uri='http://music:5003',
                tts_uri='http://tts:5002',
                timeout=120
            )
            processing_config = ProcessingConfig(output_dir='/app/shared')
            generation_config = GenerationConfig()

            result = generate_content(
                sis_data=sis_data,
                content_type='text',
                api_config=api_config,
                processing_config=processing_config,
                generation_config=generation_config,
                custom_timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
                test_case_name=f"scene_{scene_id}"
            )

            if isinstance(result, dict) and result.get('success'):
                generated_text = result.get('generated_text')
                md = result.get('metadata') or {}
                processing_time = md.get('processing_time')
            else:
                err = result.get('error') if isinstance(result, dict) else 'Unknown error'
                return jsonify({'success': False, 'error': f'Text generation failed: {err}', 'error_code': 'UNIFIED_GENERATION_FAILED'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': f'Unified generation error: {str(e)}', 'error_code': 'UNIFIED_EXCEPTION'}), 500

        payload = request.get_json(silent=True) or {}
        output_mode = (payload.get('output_mode') or 'overwrite').strip().lower()

        target_text_filename = (payload.get('text_filename') or f"text_{scene_id}.txt").strip()
        if not target_text_filename or '/' in target_text_filename or '\\' in target_text_filename:
            return jsonify({'success': False, 'error': 'Invalid text filename'}), 400
        if not (target_text_filename.startswith('text_') and target_text_filename.endswith('.txt')):
            target_text_filename = f"text_{scene_id}.txt"
        if target_text_filename.endswith('_prompt.txt') or target_text_filename.endswith('_candidate.txt'):
            target_text_filename = f"text_{scene_id}.txt"

        actual_text_filename = target_text_filename
        candidate_text_filename = None
        if output_mode == 'candidate':
            base, ext = os.path.splitext(target_text_filename)
            candidate_text_filename = f"{base}_candidate{ext}"
            actual_text_filename = candidate_text_filename

        # Save generated text into scene
        try:
            text_path = os.path.join(scene_path, actual_text_filename)
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(generated_text or '')
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to save generated text: {str(e)}'}), 500

        return jsonify({
            'success': True,
            'generated_text': generated_text,
            'text_filename': target_text_filename,
            'candidate_filename': candidate_text_filename,
            'output_mode': output_mode,
            'processing_time': processing_time
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/generate_tts", methods=['POST'])
def generate_tts_from_text(scene_id):
    """Regenerate scene TTS audio using the latest text content."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400

        text_filename = (payload.get('text_filename') or f"text_{scene_id}.txt").strip()
        if not text_filename or '/' in text_filename or '\\' in text_filename:
            return jsonify({'success': False, 'error': 'Invalid text filename'}), 400

        text_path = os.path.join(scene_path, text_filename)
        if not os.path.exists(text_path):
            return jsonify({'success': False, 'error': f'Text file not found: {text_filename}'}), 404

        text_override = payload.get('text_override')
        if isinstance(text_override, str) and text_override.strip():
            text_content = text_override.strip()
        else:
            try:
                with open(text_path, 'r', encoding='utf-8') as f:
                    text_content = f.read().strip()
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to read text file: {str(e)}'}), 500

        if not text_content:
            return jsonify({'success': False, 'error': 'Text content is empty'}), 400

        default_tts_name = text_filename
        if default_tts_name.startswith('text_'):
            default_tts_name = 'tts_' + default_tts_name[len('text_'):]
        default_tts_name = os.path.splitext(default_tts_name)[0] + '.wav'

        tts_filename = (payload.get('tts_filename') or default_tts_name).strip()
        if not tts_filename or '/' in tts_filename or '\\' in tts_filename:
            return jsonify({'success': False, 'error': 'Invalid TTS filename'}), 400

        output_mode = (payload.get('output_mode') or 'overwrite').strip().lower()

        target_tts_filename = tts_filename
        actual_tts_filename = target_tts_filename
        candidate_tts_filename = None
        if output_mode == 'candidate':
            base, ext = os.path.splitext(target_tts_filename)
            candidate_tts_filename = f"{base}_candidate{ext or '.wav'}"
            actual_tts_filename = candidate_tts_filename

        tts_path = os.path.join(scene_path, actual_tts_filename)

        params = {'text': text_content}
        for optional_key in ('speaker_id', 'style_wav', 'language_id'):
            value = payload.get(optional_key)
            if isinstance(value, str) and value.strip():
                params[optional_key] = value.strip()

        try:
            resp = requests.get("http://tts:5002/api/tts", params=params, timeout=(5, 90))
        except requests.exceptions.RequestException as exc:
            return jsonify({'success': False, 'error': f'TTS request failed: {str(exc)}'}), 503

        if resp.status_code != 200:
            return jsonify({
                'success': False,
                'error': f"TTS server error: HTTP {resp.status_code}",
                'details': resp.text
            }), resp.status_code

        try:
            # Write TTS file
            with open(tts_path, 'wb') as f:
                f.write(resp.content)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to write TTS file: {str(e)}'}), 500

        audio_b64 = base64.b64encode(resp.content).decode('ascii')

        return jsonify({
            'success': True,
            'tts_filename': actual_tts_filename,
            'target_tts_filename': target_tts_filename,
            'candidate_filename': candidate_tts_filename,
            'output_mode': output_mode,
            'audio_data': f'data:audio/wav;base64,{audio_b64}',
            'bytes': len(resp.content)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/save_generated_text", methods=['POST'])
def save_generated_text(scene_id):
    """Confirm pending generated text by overwriting the canonical text file."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True) or {}
        candidate_filename = (payload.get('candidate_filename') or '').strip()
        target_filename = (payload.get('text_filename') or f"text_{scene_id}.txt").strip()

        if not candidate_filename or '/' in candidate_filename or '\\' in candidate_filename:
            return jsonify({'success': False, 'error': 'Invalid candidate_filename'}), 400
        if not candidate_filename.endswith('_candidate.txt'):
            return jsonify({'success': False, 'error': 'Invalid candidate filename'}), 400

        if not target_filename or '/' in target_filename or '\\' in target_filename:
            return jsonify({'success': False, 'error': 'Invalid text filename'}), 400
        if not (target_filename.startswith('text_') and target_filename.endswith('.txt')):
            target_filename = f"text_{scene_id}.txt"

        cand_path = os.path.join(scene_path, candidate_filename)
        if not os.path.exists(cand_path):
            return jsonify({'success': False, 'error': 'No pending generated text to save'}), 400

        target_path = os.path.join(scene_path, target_filename)
        try:
            os.replace(cand_path, target_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to save text: {str(e)}'}), 500

        return jsonify({'success': True, 'text_filename': target_filename})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/discard_generated_text", methods=['POST'])
def discard_generated_text(scene_id):
    """Discard pending generated text candidate file."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True) or {}
        candidate_filename = (payload.get('candidate_filename') or '').strip()

        if not candidate_filename:
            candidate_filename = f"text_{scene_id}_candidate.txt"

        if '/' in candidate_filename or '\\' in candidate_filename:
            return jsonify({'success': False, 'error': 'Invalid candidate_filename'}), 400
        if not candidate_filename.endswith('_candidate.txt'):
            return jsonify({'success': False, 'error': 'Invalid candidate filename'}), 400

        cand_path = os.path.join(scene_path, candidate_filename)
        if os.path.exists(cand_path):
            try:
                os.remove(cand_path)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to discard candidate: {str(e)}'}), 500

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/save_generated_tts", methods=['POST'])
def save_generated_tts(scene_id):
    """Confirm pending generated TTS by overwriting the canonical tts file."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True) or {}
        candidate_filename = (payload.get('candidate_filename') or '').strip()
        target_filename = (payload.get('tts_filename') or '').strip()

        # Backward/lenient support: if client doesn't send tts_filename, infer from candidate.
        # e.g. tts_XXXX_candidate.wav -> tts_XXXX.wav
        if not target_filename and candidate_filename.endswith('_candidate.wav'):
            target_filename = candidate_filename[:-len('_candidate.wav')] + '.wav'

        if not candidate_filename or '/' in candidate_filename or '\\' in candidate_filename:
            return jsonify({'success': False, 'error': 'Invalid candidate_filename'}), 400
        if not candidate_filename.endswith('_candidate.wav'):
            return jsonify({'success': False, 'error': 'Invalid candidate filename'}), 400

        if not target_filename or '/' in target_filename or '\\' in target_filename:
            return jsonify({'success': False, 'error': 'Invalid tts filename'}), 400
        if not (target_filename.startswith('tts_') and target_filename.endswith('.wav')):
            return jsonify({'success': False, 'error': 'Invalid tts filename'}), 400

        cand_path = os.path.join(scene_path, candidate_filename)
        if not os.path.exists(cand_path):
            return jsonify({'success': False, 'error': 'No pending generated speech to save'}), 400

        target_path = os.path.join(scene_path, target_filename)
        try:
            os.replace(cand_path, target_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to save speech: {str(e)}'}), 500

        return jsonify({'success': True, 'tts_filename': target_filename})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/discard_generated_tts", methods=['POST'])
def discard_generated_tts(scene_id):
    """Discard pending generated TTS candidate file."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True) or {}
        candidate_filename = (payload.get('candidate_filename') or '').strip()
        if not candidate_filename:
            return jsonify({'success': False, 'error': 'candidate_filename is required'}), 400

        if '/' in candidate_filename or '\\' in candidate_filename:
            return jsonify({'success': False, 'error': 'Invalid candidate_filename'}), 400
        if not candidate_filename.endswith('_candidate.wav'):
            return jsonify({'success': False, 'error': 'Invalid candidate filename'}), 400

        cand_path = os.path.join(scene_path, candidate_filename)
        if os.path.exists(cand_path):
            try:
                os.remove(cand_path)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to discard candidate: {str(e)}'}), 500

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500

@app.route("/scene/<scene_id>/generate_music", methods=['POST'])
def generate_music_for_scene(scene_id):
    """Musicサーバから音楽を生成し、シーンディレクトリに保存して返す。
    入力: JSON { prompt: str, duration?: int=8 }
    出力: { success, music_filename, music_url }
    """
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        payload = request.get_json(silent=True) or {}
        prompt = (payload.get('prompt') or '').strip()
        try:
            duration = int(payload.get('duration') or 8)
        except Exception:
            duration = 8
        if not prompt:
            # 既存のプロンプトファイルを優先順で参照: sis2music_prompt.txt > music_final_prompt.txt > music_<scene>_prompt.txt
            for cand in ("sis2music_prompt.txt", "music_final_prompt.txt", f"music_{scene_id}_prompt.txt"):
                prompt_file = os.path.join(scene_path, cand)
                if os.path.exists(prompt_file):
                    try:
                        with open(prompt_file, 'r', encoding='utf-8') as pf:
                            prompt = (pf.read() or '').strip()
                    except Exception:
                        prompt = ''
                    if prompt:
                        break
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt is required'}), 400

        # Upstreamに生成依頼
        try:
            upstream = requests.post("http://music:5003/generate", json={'prompt': prompt, 'duration': duration}, timeout=(10, 120))
        except requests.exceptions.RequestException as exc:
            return jsonify({'success': False, 'error': f'Music service error: {str(exc)}'}), 503

        if upstream.status_code != 200:
            return jsonify({'success': False, 'error': f'Upstream HTTP {upstream.status_code}'}), upstream.status_code

        uj = upstream.json() or {}
        src_path = uj.get('path')
        filename = uj.get('filename') or f"music_{uuid.uuid4().hex[:8]}.wav"
        if not src_path or not os.path.exists(src_path):
            # 失敗時でもファイルがない場合はエラー
            return jsonify({'success': False, 'error': 'No audio file produced'}), 502

        # 既存ファイルは置換せず、候補ファイルとして保存
        target_name = f"music_{scene_id}_candidate.wav"
        target_path = os.path.join(scene_path, target_name)
        import shutil
        try:
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            shutil.copy2(src_path, target_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to copy file: {str(e)}'}), 500

        # 共有直下に残る生成元ファイルをクリーンアップ（安全な範囲のみ）
        try:
            shared_root = '/app/shared'
            norm_src = os.path.realpath(src_path)
            norm_root = os.path.realpath(shared_root)
            if norm_src.startswith(norm_root + os.sep) and os.path.basename(norm_src).startswith('music_') and norm_src.lower().endswith('.wav'):
                try:
                    os.remove(norm_src)
                except Exception as rm_err:
                    print(f"⚠️ Failed to remove source file {norm_src}: {rm_err}")
        except Exception:
            pass

        music_url = f"/scene/{scene_id}/file/{target_name}"
        # プロンプトも保存（上書き）: 従来の music_<scene>_prompt.txt と実プロンプト sis2music_prompt.txt の両方を更新
        try:
            with open(os.path.join(scene_path, f"music_{scene_id}_prompt.txt"), 'w', encoding='utf-8') as mf:
                mf.write(prompt)
            with open(os.path.join(scene_path, "sis2music_prompt.txt"), 'w', encoding='utf-8') as mf2:
                mf2.write(prompt)
        except Exception:
            pass

        return jsonify({'success': True, 'music_filename': target_name, 'music_url': music_url})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/save_generated_music", methods=['POST'])
def save_generated_music(scene_id):
    """Confirm pending generated music by overwriting the scene's canonical file."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        candidate_name = f"music_{scene_id}_candidate.wav"
        candidate_path = os.path.join(scene_path, candidate_name)
        if not os.path.exists(candidate_path):
            return jsonify({'success': False, 'error': 'No pending generated music to save'}), 400

        # Remove existing music files (excluding candidate)
        try:
            for existing in os.listdir(scene_path):
                if existing == candidate_name:
                    continue
                if existing.startswith('music_') and existing.endswith(('.wav', '.mp3', '.ogg', '.m4a')):
                    try:
                        os.remove(os.path.join(scene_path, existing))
                    except Exception:
                        pass
        except Exception:
            pass

        target_name = f"music_{scene_id}.wav"
        target_path = os.path.join(scene_path, target_name)

        try:
            os.replace(candidate_path, target_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to save music: {str(e)}'}), 500

        music_url = f"/scene/{scene_id}/file/{target_name}"
        return jsonify({'success': True, 'music_filename': target_name, 'music_url': music_url})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500


@app.route("/scene/<scene_id>/discard_generated_music", methods=['POST'])
def discard_generated_music(scene_id):
    """Discard pending generated music candidate file."""
    try:
        scene_path, _ = find_scene_path(scene_id)
        if not scene_path:
            return jsonify({'success': False, 'error': 'Scene not found'}), 404

        candidate_name = f"music_{scene_id}_candidate.wav"
        candidate_path = os.path.join(scene_path, candidate_name)

        if os.path.exists(candidate_path):
            try:
                os.remove(candidate_path)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to discard candidate: {str(e)}'}), 500

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500

def extract_sis_fallback(content_file, content_type):
    """Fallback SIS extraction using individual functions"""
    try:
        print(f"🔄 Attempting fallback SIS extraction for {content_type}: {content_file}")
        
        if content_type == 'image':
            result = image2SIS(content_file)
        elif content_type == 'text':
            result = text2SIS(content_file)
        elif content_type == 'music':
            result = audio2SIS(content_file)
        else:
            return {
                'success': False,
                'error': f'Unsupported content type: {content_type}',
                'sis_data': None
            }
        
        print(f"✅ Fallback SIS extraction completed for {content_type}")
        return result
        
    except Exception as e:
        print(f"❌ Fallback extraction failed for {content_type}: {e}")
        return {
            'success': False,
            'error': f'Fallback extraction failed: {str(e)}',
            'sis_data': None
        }

def generate_dummy_sis(content_file, content_type):
    """Generate dummy SIS for testing when no extraction system is available"""
    try:
        # Create a basic SIS structure based on content type
        timestamp = datetime.now().isoformat()
        
        # Try to get actual file information if available
        file_name = os.path.basename(content_file) if content_file else f"sample_{content_type}_file"
        file_exists = os.path.exists(content_file) if content_file else False
        
        base_sis = {
            "summary": f"Dummy analysis of {content_type} content",
            "emotions": ["neutral", "calm", "peaceful"],
            "mood": "balanced",
            "themes": [f"{content_type}_analysis", "sample_content", "test_generation"],
            "narrative": {
                "characters": ["main_character", "supporting_character"],
                "location": "sample_location",
                "weather": "clear_day",
                "tone": "neutral",
                "style": "descriptive"
            },
            "visual": {
                "style": "realistic",
                "composition": "centered",
                "lighting": "natural_daylight",
                "perspective": "eye_level",
                "colors": ["blue", "white", "gray", "green"]
            },
            "audio": {
                "genre": "ambient",
                "tempo": "moderate",
                "instruments": ["piano", "strings", "synthesizer"],
                "structure": "intro-development-climax-resolution",
                "dynamics": "steady_with_variations",
                "harmony": "consonant",
                "melody": "simple_and_memorable"
            },
            "extraction_time": timestamp,
            "source": {
                "file": file_name,
                "type": content_type,
                "method": "dummy_generation",
                "file_exists": file_exists,
                "generated_for_testing": True
            }
        }
        
        # Customize based on content type
        if content_type == 'image':
            base_sis["summary"] = "Dummy visual analysis of image content"
            base_sis["visual"]["style"] = "photographic"
            base_sis["visual"]["composition"] = "rule_of_thirds"
            base_sis["themes"] = ["visual_composition", "color_harmony", "artistic_expression"]
            base_sis["emotions"] = ["contemplative", "serene", "inspired"]
            
        elif content_type == 'text':
            base_sis["summary"] = "Dummy textual content analysis"
            base_sis["narrative"]["style"] = "literary"
            base_sis["narrative"]["tone"] = "engaging"
            base_sis["themes"] = ["narrative_storytelling", "character_development", "plot_progression"]
            base_sis["emotions"] = ["curious", "engaged", "thoughtful"]
            
        elif content_type == 'music':
            base_sis["summary"] = "Dummy audio content analysis"
            base_sis["audio"]["genre"] = "instrumental"
            base_sis["audio"]["tempo"] = "andante"
            base_sis["audio"]["dynamics"] = "crescendo_and_diminuendo"
            base_sis["themes"] = ["musical_expression", "emotional_journey", "auditory_experience"]
            base_sis["emotions"] = ["melodic", "rhythmic", "harmonious"]
        
        return {
            'success': True,
            'sis_data': base_sis,
            'error': None
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Dummy SIS generation failed: {str(e)}',
            'sis_data': None
        }

@app.route("/scene/<scene_id>/upload_tts", methods=['POST'])
def upload_tts(scene_id):
    """Upload and replace TTS file in scene"""
    scene_path, _ = find_scene_path(scene_id)
    
    if not scene_path:
        return jsonify({'error': 'Scene not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file type
    allowed_extensions = {'.wav', '.mp3', '.ogg', '.m4a'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Allowed: ' + ', '.join(allowed_extensions)}), 400
    
    try:
        # Remove existing TTS files
        for existing_file in os.listdir(scene_path):
            if existing_file.startswith('tts_') and existing_file.endswith(('.wav', '.mp3', '.ogg', '.m4a')):
                os.remove(os.path.join(scene_path, existing_file))
        
        # Save new TTS with standard naming (always save as .wav for consistency)
        new_filename = f"tts_{scene_id}.wav"
        file_path = os.path.join(scene_path, new_filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': new_filename,
            'message': 'TTS uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error uploading TTS: {str(e)}'}), 500

@app.route("/scene/create", methods=['POST'])
def create_scene():
    """Create a new scene"""
    try:
        data = request.get_json()
        scene_id = data.get('sceneId')
        creation_type = data.get('creationType', 'empty')
        source_scene = data.get('sourceScene')
        
        if not scene_id:
            return jsonify({'error': 'Scene ID is required'}), 400
        
        # Create scene directory
        scene_path = os.path.join(SCENE_DIR, scene_id)
        if os.path.exists(scene_path):
            return jsonify({'error': 'Scene with this ID already exists'}), 400
        
        os.makedirs(scene_path, exist_ok=True)
        
        if creation_type == 'copy' and source_scene:
            # Copy from existing scene
            source_path = os.path.join(SCENE_DIR, source_scene)
            if not os.path.exists(source_path):
                return jsonify({'error': 'Source scene not found'}), 404
            
            # Copy files from source scene
            for file in os.listdir(source_path):
                source_file_path = os.path.join(source_path, file)
                if os.path.isfile(source_file_path):
                    # Generate new filename with new scene ID
                    if file.startswith('text_'):
                        new_filename = f"text_{scene_id}.txt"
                    elif file.startswith('image_'):
                        ext = os.path.splitext(file)[1]
                        new_filename = f"image_{scene_id}{ext}"
                    elif file.startswith('music_'):
                        ext = os.path.splitext(file)[1]
                        new_filename = f"music_{scene_id}{ext}"
                    elif file.startswith('tts_'):
                        ext = os.path.splitext(file)[1]
                        new_filename = f"tts_{scene_id}{ext}"
                    elif file.startswith('sis_structure_'):
                        new_filename = f"sis_structure_{scene_id}.json"
                    else:
                        continue  # Skip other files
                    
                    dest_file_path = os.path.join(scene_path, new_filename)
                    
                    # Copy file content
                    if file.endswith('.json'):
                        # Update JSON content with new scene ID
                        with open(source_file_path, 'r', encoding='utf-8') as f:
                            content = json.load(f)
                        # Update scene ID references in JSON if any
                        content_str = json.dumps(content, indent=2)
                        content_str = content_str.replace(source_scene, scene_id)
                        with open(dest_file_path, 'w', encoding='utf-8') as f:
                            f.write(content_str)
                    else:
                        # Copy binary files directly
                        import shutil
                        shutil.copy2(source_file_path, dest_file_path)
        else:
            # Create empty scene with default files
            # 空シーン作成時は text_*.txt を作成しない（必要になったら保存時に生成）
            
            # デフォルトでSISファイルを作成
            sis_file = os.path.join(scene_path, f"sis_structure_{scene_id}.json")
            default_sis = {
                "scene_id": scene_id,
                "title": f"Scene {scene_id}",
                "description": "Scene description",
                "elements": [],
                "created_at": datetime.now().isoformat()
            }
            with open(sis_file, 'w', encoding='utf-8') as f:
                json.dump(default_sis, f, indent=2, ensure_ascii=False)
            
            # プレースホルダー画像ファイルを作成
            image_file = os.path.join(scene_path, f"image_{scene_id}.txt")
            with open(image_file, 'w', encoding='utf-8') as f:
                f.write(f"Placeholder for image {scene_id}. Upload an actual image using the scene editor.")
        
        return jsonify({
            'success': True,
            'scene_id': scene_id,
            'message': f'Scene {scene_id} created successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error creating scene: {str(e)}'}), 500

@app.route("/projects/<project_id>/scenes/<scene_id>/create", methods=['POST'])
def create_project_scene(project_id, scene_id):
    """Create a new scene within a project"""
    try:
        import shutil
        data = request.get_json()
        creation_type = data.get('creation_type', 'empty')
        source_scene = data.get('source_scene')
        
        project_path = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.exists(project_path):
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        # Create scene directory within project
        scenes_dir = os.path.join(project_path, 'scenes')
        os.makedirs(scenes_dir, exist_ok=True)
        
        scene_path = os.path.join(scenes_dir, scene_id)
        if os.path.exists(scene_path):
            return jsonify({'success': False, 'error': 'Scene with this ID already exists'}), 400
        
        os.makedirs(scene_path, exist_ok=True)
        
        if creation_type == 'copy' and source_scene:
            # Copy from existing scene in the same project
            source_path = os.path.join(scenes_dir, source_scene)
            if not os.path.exists(source_path):
                return jsonify({'success': False, 'error': 'Source scene not found'}), 404
            
            # Copy files from source scene
            for file in os.listdir(source_path):
                source_file_path = os.path.join(source_path, file)
                if os.path.isfile(source_file_path):
                    # Generate new filename with new scene ID
                    if file.startswith('text_'):
                        new_filename = f"text_{scene_id}.txt"
                    elif file.startswith('image_'):
                        ext = os.path.splitext(file)[1]
                        new_filename = f"image_{scene_id}{ext}"
                    elif file.startswith('music_'):
                        ext = os.path.splitext(file)[1]
                        new_filename = f"music_{scene_id}{ext}"
                    elif file.startswith('tts_'):
                        ext = os.path.splitext(file)[1]
                        new_filename = f"tts_{scene_id}{ext}"
                    elif file.startswith('sis_structure_'):
                        new_filename = f"sis_structure_{scene_id}.json"
                    else:
                        new_filename = file
                    
                    dest_file_path = os.path.join(scene_path, new_filename)
                    
                    # Copy file content
                    if file.endswith('.json'):
                        # Update JSON content with new scene ID
                        with open(source_file_path, 'r', encoding='utf-8') as f:
                            content = json.load(f)
                        content_str = json.dumps(content, indent=2)
                        content_str = content_str.replace(source_scene, scene_id)
                        with open(dest_file_path, 'w', encoding='utf-8') as f:
                            f.write(content_str)
                    else:
                        shutil.copy2(source_file_path, dest_file_path)
        else:
            # Create empty scene with default files
            # 空シーン作成時は text_*.txt を作成しない（必要になったら保存時に生成）
            
            sis_file = os.path.join(scene_path, f"sis_structure_{scene_id}.json")
            default_sis = {
                "scene_id": scene_id,
                "title": f"Scene {scene_id}",
                "description": "Scene description",
                "elements": [],
                "created_at": datetime.now().isoformat()
            }
            with open(sis_file, 'w', encoding='utf-8') as f:
                json.dump(default_sis, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'scene_id': scene_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/projects/<project_id>/scenes/<scene_id>/delete", methods=['POST'])
def delete_project_scene(project_id, scene_id):
    """Delete a scene from a project"""
    try:
        import shutil
        project_path = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.exists(project_path):
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        scene_path = os.path.join(project_path, 'scenes', scene_id)
        if not os.path.exists(scene_path):
            return jsonify({'success': False, 'error': 'Scene not found'}), 404
        
        shutil.rmtree(scene_path)
        
        return jsonify({'success': True, 'message': f'Scene {scene_id} deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/projects/<project_id>/scenes/<scene_id>/file/<filename>")
def serve_project_scene_file(project_id, scene_id, filename):
    """Serve scene files from a project"""
    scene_path = os.path.join(PROJECTS_DIR, project_id, 'scenes', scene_id)
    return send_from_directory(scene_path, filename)

@app.route("/projects/<project_id>/<scene_id>")
def project_scene_detail_alt(project_id, scene_id):
    """Display details of a specific scene within a project using existing scene_detail.html"""
    scene_path = os.path.join(PROJECTS_DIR, project_id, 'scenes', scene_id)
    
    if not os.path.exists(scene_path):
        return "Scene not found", 404
    
    # Collect files
    files = os.listdir(scene_path)
    
    scene_data = {
        'id': scene_id,
        'project_id': project_id,
        'sis_files': [],
        'text_files': [],
        'image_files': [],
        'music_files': [],
        'tts_files': [],
        'prompt_files': []
    }
    
    for file in files:
        if file.startswith('sis_structure_') and file.endswith('.json') and not file.endswith('_candidate.json'):
            scene_data['sis_files'].append(file)
        elif file.startswith('text_') and file.endswith('.txt') and not file.endswith('_prompt.txt') and not file.endswith('_candidate.txt'):
            scene_data['text_files'].append(file)
        elif file.startswith('image_') and file.endswith('.png') and not file.endswith('_candidate.png'):
            scene_data['image_files'].append(file)
        elif file.startswith('music_') and file.endswith('.wav') and not file.endswith('_candidate.wav'):
            scene_data['music_files'].append(file)
        elif file.startswith('tts_') and file.endswith('.wav') and not file.endswith('_candidate.wav'):
            scene_data['tts_files'].append(file)
        elif file.endswith('_prompt.txt') and (
            file.startswith('image_') or file.startswith('sis2image_') or file.startswith('prompt_')
            or file.startswith('text_') or file.startswith('sis2text_')
            or file.startswith('music_') or file.startswith('sis2music_')
        ):
            scene_data['prompt_files'].append(file)
    
    return render_template('scene_detail.html', scene=scene_data)

@app.route("/projects/<project_id>/delete", methods=['POST'])
def delete_project(project_id):
    """Delete a project"""
    try:
        import shutil
        project_path = os.path.join(PROJECTS_DIR, project_id)
        
        if not os.path.exists(project_path):
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        # Remove the entire project directory and all its contents
        shutil.rmtree(project_path)
        
        return jsonify({'success': True, 'message': f'Project {project_id} deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/scene/<scene_id>/delete', methods=['DELETE'])
def delete_scene(scene_id):
    """Delete a scene"""
    try:
        scene_path, _ = find_scene_path(scene_id)
        
        if not scene_path:
            return jsonify({'error': 'Scene not found'}), 404
        
        # Remove the entire scene directory and all its contents
        import shutil
        shutil.rmtree(scene_path)
        
        return jsonify({
            'success': True,
            'message': f'Scene {scene_id} deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error deleting scene: {str(e)}'}), 500

@app.route('/projects/<project_id>/generate_story_sis', methods=['POST'])
def generate_project_story_sis(project_id):
    """Generate StorySIS from project scenes arranged by scene_type"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        output_mode = (data.get('output_mode') or 'return').strip().lower()
        
        story_type = data.get('story_type')
        scenes_by_type = data.get('scenes_by_type', {})
        
        if not story_type:
            return jsonify({'success': False, 'error': 'story_type is required'}), 400
        
        if not scenes_by_type or not isinstance(scenes_by_type, dict):
            return jsonify({'success': False, 'error': 'scenes_by_type must be a dictionary'}), 400
        
        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        # Load SceneSIS data for each scene
        scenes_list = []
        scene_type_overrides = []
        
        for scene_type, scene_ids in scenes_by_type.items():
            for scene_id in scene_ids:
                # Find scene path
                scene_path, _ = find_scene_path(scene_id)
                if not scene_path:
                    return jsonify({
                        'success': False,
                        'error': f'Scene {scene_id} not found'
                    }), 404
                
                # Load SceneSIS (try both naming conventions)
                sis_file = os.path.join(scene_path, f"sis_structure_{scene_id}.json")
                if not os.path.exists(sis_file):
                    # Fallback to alternative naming
                    sis_file = os.path.join(scene_path, f"{scene_id}_sis.json")
                    if not os.path.exists(sis_file):
                        return jsonify({
                            'success': False,
                            'error': f'SceneSIS not found for scene {scene_id}'
                        }), 404
                
                with open(sis_file, 'r', encoding='utf-8') as f:
                    scene_sis = json.load(f)
                
                scenes_list.append(scene_sis)
                scene_type_overrides.append(scene_type)
        
        if not scenes_list:
            return jsonify({
                'success': False,
                'error': 'No scenes provided'
            }), 400
        
        # Import and run the transformation
        from sis2sis import scene2story
        
        result = scene2story(
            scene_sis_list=scenes_list,
            api_config=APIConfig(),
            requested_story_type=story_type,
            scene_type_overrides=scene_type_overrides
        )
        
        if result.get('success'):
            # Extract story_sis from result
            story_sis = result.get('story_sis') or result.get('data', {}).get('story_sis', {})
            
            if not story_sis:
                return jsonify({
                    'success': False,
                    'error': 'No StorySIS generated'
                }), 500

            response_payload = {
                'success': True,
                'story_sis': story_sis,
                'output_mode': output_mode,
            }

            # Candidate mode: persist generated StorySIS as a temporary file.
            # This avoids overwriting or auto-saving the main StorySIS until user confirms.
            if output_mode == 'candidate':
                story_dir = os.path.join(project_dir, 'story')
                os.makedirs(story_dir, exist_ok=True)

                candidate_filename = 'story_candidate.json'
                candidate_path = os.path.join(story_dir, candidate_filename)

                with open(candidate_path, 'w', encoding='utf-8') as f:
                    json.dump(story_sis, f, indent=2, ensure_ascii=False)

                response_payload.update({
                    'candidate_filename': candidate_filename,
                })

            return jsonify(response_payload)
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error during StorySIS generation')
            }), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/projects/<project_id>/save_story_sis', methods=['POST'])
def save_project_story_sis(project_id):
    """Save StorySIS to project directory"""
    try:
        story_sis = request.get_json()
        if not story_sis:
            return jsonify({'success': False, 'error': 'No StorySIS data provided'}), 400
        
        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        # Create story directory
        story_dir = os.path.join(project_dir, 'story')
        os.makedirs(story_dir, exist_ok=True)
        
        # Save StorySIS
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        story_filename = f'story_{timestamp}.json'
        story_file = os.path.join(story_dir, story_filename)
        
        with open(story_file, 'w', encoding='utf-8') as f:
            json.dump(story_sis, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'file_path': story_file,
            'filename': story_filename,
            'message': f'StorySIS saved to {story_filename}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error saving StorySIS: {str(e)}'
        }), 500


@app.route('/projects/<project_id>/save_generated_story_sis', methods=['POST'])
def save_generated_project_story_sis(project_id):
    """Finalize (save) a generated StorySIS candidate into a timestamped story_*.json file."""
    try:
        data = request.get_json(silent=True) or {}
        candidate_filename = (data.get('candidate_filename') or 'story_candidate.json').strip()

        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404

        story_dir = os.path.join(project_dir, 'story')
        if not os.path.isdir(story_dir):
            return jsonify({'success': False, 'error': 'Story directory not found'}), 404

        candidate_path = os.path.join(story_dir, candidate_filename)
        if not os.path.isfile(candidate_path):
            return jsonify({'success': False, 'error': 'Candidate StorySIS not found'}), 404

        with open(candidate_path, 'r', encoding='utf-8') as f:
            story_sis = json.load(f)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        story_filename = f'story_{timestamp}.json'
        story_file = os.path.join(story_dir, story_filename)

        with open(story_file, 'w', encoding='utf-8') as f:
            json.dump(story_sis, f, indent=2, ensure_ascii=False)

        # Remove candidate after finalizing
        try:
            os.remove(candidate_path)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'filename': story_filename,
            'story_sis': story_sis,
            'message': f'StorySIS saved to {story_filename}'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error saving generated StorySIS: {str(e)}'
        }), 500


@app.route('/projects/<project_id>/discard_generated_story_sis', methods=['POST'])
def discard_generated_project_story_sis(project_id):
    """Discard (delete) a generated StorySIS candidate file."""
    try:
        data = request.get_json(silent=True) or {}
        candidate_filename = (data.get('candidate_filename') or 'story_candidate.json').strip()

        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404

        story_dir = os.path.join(project_dir, 'story')
        if not os.path.isdir(story_dir):
            return jsonify({'success': True, 'message': 'No story directory; nothing to discard'})

        candidate_path = os.path.join(story_dir, candidate_filename)
        if os.path.isfile(candidate_path):
            try:
                os.remove(candidate_path)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to delete candidate: {str(e)}'}), 500

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': f'Error discarding generated StorySIS: {str(e)}'}), 500

@app.route('/projects/<project_id>/get_story_sis')
def get_project_story_sis(project_id):
    """Get the latest StorySIS from project directory"""
    try:
        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        # Get story directory
        story_dir = os.path.join(project_dir, 'story')
        if not os.path.isdir(story_dir):
            return jsonify({'success': True, 'story_sis': None})
        
        # Find all story files
        story_files = [f for f in os.listdir(story_dir) if f.startswith('story_') and f.endswith('.json')]
        
        if not story_files:
            return jsonify({'success': True, 'story_sis': None})
        
        # Get the latest file
        story_files.sort(reverse=True)
        latest_file = os.path.join(story_dir, story_files[0])
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            story_sis = json.load(f)
        
        return jsonify({
            'success': True,
            'story_sis': story_sis,
            'filename': story_files[0]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error loading StorySIS: {str(e)}'
        }), 500

@app.route('/projects/<project_id>/save_scene_arrangement', methods=['POST'])
def save_scene_arrangement(project_id):
    """Save scene arrangement (scene-to-scene_type mapping) to project directory"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        story_type = data.get('story_type')
        scenes_by_type = data.get('scenes_by_type', {})
        
        if not story_type:
            return jsonify({'success': False, 'error': 'story_type is required'}), 400
        
        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        # Create story directory
        story_dir = os.path.join(project_dir, 'story')
        os.makedirs(story_dir, exist_ok=True)
        
        # Save scene arrangement
        arrangement_file = os.path.join(story_dir, 'scene_arrangement.json')
        arrangement_data = {
            'story_type': story_type,
            'scenes_by_type': scenes_by_type,
            'updated_at': datetime.now().isoformat()
        }
        
        # Write to temp file first, then rename (atomic operation)
        temp_arrangement_file = arrangement_file + '.tmp'
        try:
            with open(temp_arrangement_file, 'w', encoding='utf-8') as f:
                json.dump(arrangement_data, f, indent=2, ensure_ascii=False)
            
            # Replace old file with new one
            if os.path.exists(arrangement_file):
                os.remove(arrangement_file)
            os.rename(temp_arrangement_file, arrangement_file)
        except Exception as e:
            # Clean up temp file if something went wrong
            if os.path.exists(temp_arrangement_file):
                os.remove(temp_arrangement_file)
            raise e
        
        return jsonify({
            'success': True,
            'message': 'Scene arrangement saved successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error saving scene arrangement: {str(e)}'
        }), 500

@app.route('/projects/<project_id>/get_scene_arrangement')
def get_scene_arrangement(project_id):
    """Get scene arrangement from project directory"""
    try:
        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        # Get story directory
        story_dir = os.path.join(project_dir, 'story')
        arrangement_file = os.path.join(story_dir, 'scene_arrangement.json')
        
        if not os.path.exists(arrangement_file):
            return jsonify({'success': True, 'arrangement': None})
        
        with open(arrangement_file, 'r', encoding='utf-8') as f:
            arrangement_data = json.load(f)
        
        return jsonify({
            'success': True,
            'arrangement': arrangement_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error loading scene arrangement: {str(e)}'
        }), 500

@app.route('/projects/<project_id>/generate_scenes_from_story', methods=['POST'])
def generate_scenes_from_story(project_id):
    """Generate SceneSIS and scenes from StorySIS scene_blueprints"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        story_sis = data.get('story_sis')
        if not story_sis:
            return jsonify({'success': False, 'error': 'story_sis is required'}), 400
        
        scenes_needed = data.get('scenes_needed', {})
        print(f"[DEBUG] scenes_needed received: {scenes_needed}")
        
        if not scenes_needed:
            return jsonify({'success': False, 'error': 'No scenes needed. All scene types have reached their target count.'}), 400
        
        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        scenes_dir = os.path.join(project_dir, 'scenes')
        os.makedirs(scenes_dir, exist_ok=True)
        
        scene_blueprints = story_sis.get('scene_blueprints', [])
        if not scene_blueprints:
            return jsonify({'success': False, 'error': 'No scene_blueprints found in StorySIS'}), 400
        
        created_scenes = []
        scenes_by_type = {}
        
        # Load existing scene arrangement if it exists
        story_dir = os.path.join(project_dir, 'story')
        os.makedirs(story_dir, exist_ok=True)
        arrangement_file = os.path.join(story_dir, 'scene_arrangement.json')
        
        if os.path.exists(arrangement_file):
            try:
                with open(arrangement_file, 'r', encoding='utf-8') as f:
                    existing_arrangement = json.load(f)
                    scenes_by_type = existing_arrangement.get('scenes_by_type', {})
            except Exception as e:
                print(f"Warning: Could not load existing arrangement: {e}")
                scenes_by_type = {}
        
        # Group blueprints by scene_type
        blueprints_by_type = {}
        for blueprint in scene_blueprints:
            scene_type = blueprint.get('scene_type')
            if scene_type:
                if scene_type not in blueprints_by_type:
                    blueprints_by_type[scene_type] = []
                blueprints_by_type[scene_type].append(blueprint)
        
        # Generate only needed scenes for each type
        from sis2sis import story2scene_single
        
        print(f"[DEBUG] Starting scene generation loop. blueprints_by_type keys: {list(blueprints_by_type.keys())}")
        
        for scene_type, needed_count in scenes_needed.items():
            print(f"[DEBUG] Processing scene_type: {scene_type}, needed_count: {needed_count}")
            if scene_type not in blueprints_by_type:
                print(f"[DEBUG] Warning: scene_type {scene_type} not found in blueprints_by_type")
                continue
            
            blueprints = blueprints_by_type[scene_type]
            # Generate up to needed_count scenes from available blueprints
            for i in range(min(needed_count, len(blueprints))):
                blueprint = blueprints[i % len(blueprints)]  # Cycle through blueprints if needed
                
                # Generate unique scene ID
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                scene_id = f"{timestamp}_{len(created_scenes):03d}"
                
                # Create scene directory
                scene_path = os.path.join(scenes_dir, scene_id)
                os.makedirs(scene_path, exist_ok=True)
                
                # Use LLM to generate SceneSIS from StorySIS
                try:
                    print(f"[DEBUG] Generating SceneSIS for scene_type: {scene_type} using LLM")
                    result = story2scene_single(
                        story_sis=story_sis,
                        blueprint=blueprint,
                        blueprint_index=i,
                        api_config=APIConfig()
                    )
                    
                    print(f"[DEBUG] story2scene_single result: success={result.get('success')}")
                    
                    if result.get('success'):
                        # story2scene_single returns a dict with 'data' containing 'scene_sis'
                        data_dict = result.get('data', {})
                        scene_sis = data_dict.get('scene_sis', {})
                        
                        # Ensure scene_sis is not empty and has proper structure
                        if not scene_sis or not isinstance(scene_sis, dict) or 'sis_type' not in scene_sis:
                            print(f"[WARNING] Invalid scene_sis structure from LLM")
                            raise ValueError("Invalid SceneSIS structure")
                        
                        # Update scene_id
                        scene_sis['scene_id'] = scene_id
                        print(f"[DEBUG] Successfully generated SceneSIS with LLM for {scene_id}")
                    else:
                        # Fallback: create basic SceneSIS if LLM fails
                        print(f"Warning: LLM generation failed for {scene_type}, using fallback")
                        summary = blueprint.get('summary', '')
                        scene_sis = {
                            'sis_type': 'scene',
                            'scene_id': scene_id,
                            'scene_type': scene_type,
                            'title': f'Scene {len(created_scenes) + 1}: {scene_type}',
                            'summary': summary,
                            'semantics': {
                                'common': {
                                    'descriptions': [summary] if summary else [],
                                    'themes': story_sis.get('semantics', {}).get('common', {}).get('themes', []),
                                    'mood': '',
                                    'characters': [],
                                    'location': '',
                                    'time': '',
                                    'weather': '',
                                    'objects': []
                                },
                            'visual': {
                                'setting': '',
                                'characters': [],
                                'objects': [],
                                'actions': []
                            },
                            'audio': {
                                'dialogue': [],
                                'sound_effects': [],
                                'music_mood': ''
                            },
                            'narrative': {
                                'pov': '',
                                'tone': '',
                                'pacing': ''
                            }
                        }
                        }
                except Exception as e:
                    print(f"Error generating SceneSIS with LLM: {str(e)}")
                    # Fallback: create basic SceneSIS
                    summary = blueprint.get('summary', '')
                    scene_sis = {
                        'sis_type': 'scene',
                        'scene_id': scene_id,
                        'scene_type': scene_type,
                        'title': f'Scene {len(created_scenes) + 1}: {scene_type}',
                        'summary': summary,
                        'semantics': {
                            'common': {
                                'descriptions': [summary] if summary else [],
                                'themes': story_sis.get('semantics', {}).get('common', {}).get('themes', []),
                                'mood': '',
                                'characters': [],
                                'location': '',
                                'time': '',
                                'weather': '',
                                'objects': []
                            },
                        'visual': {
                            'setting': '',
                            'characters': [],
                            'objects': [],
                            'actions': []
                        },
                        'audio': {
                            'dialogue': [],
                            'sound_effects': [],
                            'music_mood': ''
                        },
                        'narrative': {
                            'pov': '',
                            'tone': '',
                            'pacing': ''
                        }
                    }
                    }
                
                # Save SceneSIS
                sis_file = os.path.join(scene_path, f'sis_structure_{scene_id}.json')
                with open(sis_file, 'w', encoding='utf-8') as f:
                    json.dump(scene_sis, f, indent=2, ensure_ascii=False)
                
                # Generate prompts from SceneSIS (equivalent to Update Prompts button)
                prompts = {}
                try:
                    print(f"[DEBUG] Generating prompts for scene {scene_id}")
                    prompts, failures = regenerate_prompts_from_sis(scene_id, scene_sis)
                    if failures:
                        print(f"[WARNING] Some prompts failed to generate for {scene_id}: {failures}")
                except Exception as e:
                    print(f"[WARNING] Failed to generate prompts for scene {scene_id}: {str(e)}")
                
                # Auto-generate Image (equivalent to Image Generate button)
                if prompts.get('image', {}).get('text'):
                    try:
                        print(f"[DEBUG] Auto-generating image for scene {scene_id}")
                        image_prompt = prompts['image']['text']
                        sd_uri = 'http://sd:7860'
                        sd_payload = {
                            'prompt': image_prompt,
                            'negative_prompt': 'low quality, blurry, distorted, watermark, text',
                            'width': 512,
                            'height': 512,
                            'steps': 20,
                            'cfg_scale': 7.0,
                            'sampler_name': 'Euler a',
                            'seed': -1,
                            'batch_size': 1,
                            'n_iter': 1,
                        }
                        sd_resp = requests.post(f"{sd_uri}/sdapi/v1/txt2img", json=sd_payload, timeout=(10, 300))
                        if sd_resp.status_code == 200:
                            sd_result = sd_resp.json() or {}
                            images = sd_result.get('images') or []
                            if images:
                                import base64 as _b64
                                img_bytes = _b64.b64decode(images[0])
                                img_filename = f"image_{scene_id}.png"
                                img_path = os.path.join(scene_path, img_filename)
                                with open(img_path, 'wb') as f:
                                    f.write(img_bytes)
                                print(f"[DEBUG] Image generated successfully for {scene_id}")
                        else:
                            print(f"[WARNING] Image generation failed for {scene_id}: HTTP {sd_resp.status_code}")
                    except Exception as e:
                        print(f"[WARNING] Failed to auto-generate image for {scene_id}: {str(e)}")
                
                # Auto-generate Text & TTS (equivalent to Text & Speech Generate button)
                try:
                    print(f"[DEBUG] Auto-generating text for scene {scene_id}")
                    api_config = APIConfig(
                        unsloth_uri='http://unsloth:5007',
                        sd_uri='http://sd:7860',
                        music_uri='http://music:5003',
                        tts_uri='http://tts:5002',
                        timeout=120
                    )
                    text_result = generate_content(
                        sis_data=scene_sis,
                        content_type='text',
                        api_config=api_config,
                        processing_config=ProcessingConfig(output_dir='/app/shared'),
                        generation_config=GenerationConfig(),
                        custom_timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
                        test_case_name=f"scene_{scene_id}"
                    )
                    if isinstance(text_result, dict) and text_result.get('success'):
                        generated_text = text_result.get('generated_text')
                        if generated_text:
                            text_filename = f"text_{scene_id}.txt"
                            text_path = os.path.join(scene_path, text_filename)
                            with open(text_path, 'w', encoding='utf-8') as f:
                                f.write(generated_text)
                            print(f"[DEBUG] Text generated successfully for {scene_id}")
                            
                            # Auto-generate TTS (directly call TTS server)
                            try:
                                print(f"[DEBUG] Auto-generating TTS for scene {scene_id}")
                                tts_params = {'text': generated_text}
                                tts_resp = requests.get("http://tts:5002/api/tts", params=tts_params, timeout=(5, 90))
                                if tts_resp.status_code == 200:
                                    tts_filename = f"tts_{scene_id}.wav"
                                    tts_path = os.path.join(scene_path, tts_filename)
                                    with open(tts_path, 'wb') as f:
                                        f.write(tts_resp.content)
                                    print(f"[DEBUG] TTS generated successfully for {scene_id}")
                                else:
                                    print(f"[WARNING] TTS generation failed for {scene_id}: HTTP {tts_resp.status_code}")
                            except Exception as e:
                                print(f"[WARNING] Failed to auto-generate TTS for {scene_id}: {str(e)}")
                    else:
                        print(f"[WARNING] Text generation failed for {scene_id}")
                except Exception as e:
                    print(f"[WARNING] Failed to auto-generate text for {scene_id}: {str(e)}")
                
                # Auto-generate Music (equivalent to Music Generate button)
                if prompts.get('music', {}).get('text'):
                    try:
                        print(f"[DEBUG] Auto-generating music for scene {scene_id}")
                        music_prompt = prompts['music']['text']
                        music_resp = requests.post(
                            "http://music:5003/generate",
                            json={'prompt': music_prompt, 'duration': 8},
                            timeout=(10, 120)
                        )
                        if music_resp.status_code == 200:
                            music_result = music_resp.json() or {}
                            music_src_path = music_result.get('path')
                            if music_src_path and os.path.exists(music_src_path):
                                import shutil
                                music_filename = f"music_{scene_id}.wav"
                                music_dest = os.path.join(scene_path, music_filename)
                                shutil.copy(music_src_path, music_dest)
                                print(f"[DEBUG] Music generated successfully for {scene_id}")
                        else:
                            print(f"[WARNING] Music generation failed for {scene_id}: HTTP {music_resp.status_code}")
                    except Exception as e:
                        print(f"[WARNING] Failed to auto-generate music for {scene_id}: {str(e)}")
                
                created_scenes.append(scene_id)
                
                # Group by scene_type for arrangement (append to existing scenes)
                if scene_type not in scenes_by_type:
                    scenes_by_type[scene_type] = []
                scenes_by_type[scene_type].append(scene_id)
        
        # Save updated scene arrangement (preserving existing scenes)
        arrangement_data = {
            'story_type': story_sis.get('story_type', ''),
            'scenes_by_type': scenes_by_type,
            'updated_at': datetime.now().isoformat()
        }
        
        # Write to temp file first, then rename (atomic operation)
        temp_arrangement_file = arrangement_file + '.tmp'
        try:
            with open(temp_arrangement_file, 'w', encoding='utf-8') as f:
                json.dump(arrangement_data, f, indent=2, ensure_ascii=False)
            
            # Replace old file with new one
            if os.path.exists(arrangement_file):
                os.remove(arrangement_file)
            os.rename(temp_arrangement_file, arrangement_file)
        except Exception as e:
            # Clean up temp file if something went wrong
            if os.path.exists(temp_arrangement_file):
                os.remove(temp_arrangement_file)
            raise e
        
        return jsonify({
            'success': True,
            'scenes_created': created_scenes,
            'message': f'Successfully created {len(created_scenes)} scene(s)'
        })
        
    except Exception as e:
        print(f"Error in generate_scenes_from_story: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/projects/<project_id>/add_single_scene', methods=['POST'])
def add_single_scene(project_id):
    """Add a single scene to a specific lane (scene_type) with full content generation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        story_sis = data.get('story_sis')
        scene_type = data.get('scene_type')
        blueprint = data.get('blueprint')
        
        if not story_sis or not scene_type or not blueprint:
            return jsonify({'success': False, 'error': 'story_sis, scene_type, and blueprint are required'}), 400
        
        # Verify project exists
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        scenes_dir = os.path.join(project_dir, 'scenes')
        os.makedirs(scenes_dir, exist_ok=True)
        
        # Generate unique scene ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scene_id = f"{timestamp}_{scene_type}"
        
        # Create scene directory
        scene_path = os.path.join(scenes_dir, scene_id)
        os.makedirs(scene_path, exist_ok=True)
        
        # Use LLM to generate SceneSIS from blueprint
        from sis2sis import story2scene_single
        
        print(f"[DEBUG] Generating SceneSIS for single scene: {scene_type}")
        
        try:
            result = story2scene_single(
                story_sis=story_sis,
                blueprint=blueprint,
                blueprint_index=0,
                api_config=APIConfig()
            )
            
            print(f"[DEBUG] story2scene_single result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
            print(f"[DEBUG] result.success: {result.get('success')}")
            
            if result.get('success'):
                # story2scene_single returns a dict with 'data' containing 'scene_sis'
                data_dict = result.get('data', {})
                scene_sis = data_dict.get('scene_sis', {})
                
                # Ensure scene_sis is not empty and has proper structure
                if not scene_sis or not isinstance(scene_sis, dict) or 'sis_type' not in scene_sis:
                    print(f"[WARNING] Invalid scene_sis structure: {scene_sis}")
                    raise ValueError("Invalid SceneSIS structure returned from LLM")
                
                scene_sis['scene_id'] = scene_id
                print(f"[DEBUG] Successfully generated SceneSIS with LLM for {scene_id}")
                print(f"[DEBUG] SceneSIS keys: {list(scene_sis.keys())}")
            else:
                # Fallback
                print(f"Warning: LLM generation failed, using fallback")
                summary = blueprint.get('summary', '')
                scene_sis = {
                    'sis_type': 'scene',
                    'scene_id': scene_id,
                    'scene_type': scene_type,
                    'summary': summary,
                    'semantics': {
                        'common': {
                            'descriptions': [summary] if summary else [],
                            'mood': '',
                            'characters': [],
                            'location': '',
                            'time': '',
                            'weather': '',
                            'objects': []
                        },
                        'visual': {},
                        'audio': {},
                        'text': {}
                    }
                }
        except Exception as e:
            print(f"Error generating SceneSIS: {str(e)}")
            summary = blueprint.get('summary', '')
            scene_sis = {
                'sis_type': 'scene',
                'scene_id': scene_id,
                'scene_type': scene_type,
                'summary': summary,
                'semantics': {
                    'common': {
                        'descriptions': [summary] if summary else [],
                        'mood': '',
                        'characters': [],
                        'location': '',
                        'time': '',
                        'weather': '',
                        'objects': []
                    },
                    'visual': {},
                    'audio': {},
                    'text': {}
                }
            }
        
        # Save SceneSIS
        sis_file = os.path.join(scene_path, f'sis_structure_{scene_id}.json')
        with open(sis_file, 'w', encoding='utf-8') as f:
            json.dump(scene_sis, f, indent=2, ensure_ascii=False)
        
        # Generate prompts from SceneSIS
        prompts = {}
        try:
            print(f"[DEBUG] Generating prompts for scene {scene_id}")
            prompts, failures = regenerate_prompts_from_sis(scene_id, scene_sis)
            if failures:
                print(f"[WARNING] Some prompts failed: {failures}")
        except Exception as e:
            print(f"[WARNING] Failed to generate prompts: {str(e)}")
        
        # Auto-generate Image
        if prompts.get('image', {}).get('text'):
            try:
                print(f"[DEBUG] Auto-generating image for scene {scene_id}")
                image_prompt = prompts['image']['text']
                sd_uri = 'http://sd:7860'
                sd_payload = {
                    'prompt': image_prompt,
                    'negative_prompt': 'low quality, blurry, distorted, watermark, text',
                    'width': 512,
                    'height': 512,
                    'steps': 20,
                    'cfg_scale': 7.0,
                    'sampler_name': 'Euler a',
                    'seed': -1,
                    'batch_size': 1,
                    'n_iter': 1,
                }
                sd_resp = requests.post(f"{sd_uri}/sdapi/v1/txt2img", json=sd_payload, timeout=(10, 300))
                if sd_resp.status_code == 200:
                    sd_result = sd_resp.json() or {}
                    images = sd_result.get('images') or []
                    if images:
                        import base64 as _b64
                        img_bytes = _b64.b64decode(images[0])
                        img_filename = f"image_{scene_id}.png"
                        img_path = os.path.join(scene_path, img_filename)
                        with open(img_path, 'wb') as f:
                            f.write(img_bytes)
                        print(f"[DEBUG] Image generated successfully")
                else:
                    print(f"[WARNING] Image generation failed: HTTP {sd_resp.status_code}")
            except Exception as e:
                print(f"[WARNING] Failed to auto-generate image: {str(e)}")
        
        # Auto-generate Text & TTS
        try:
            print(f"[DEBUG] Auto-generating text for scene {scene_id}")
            api_config = APIConfig(
                unsloth_uri='http://unsloth:5007',
                sd_uri='http://sd:7860',
                music_uri='http://music:5003',
                tts_uri='http://tts:5002',
                timeout=120
            )
            text_result = generate_content(
                sis_data=scene_sis,
                content_type='text',
                api_config=api_config,
                processing_config=ProcessingConfig(output_dir='/app/shared'),
                generation_config=GenerationConfig(),
                custom_timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
                test_case_name=f"scene_{scene_id}"
            )
            if isinstance(text_result, dict) and text_result.get('success'):
                generated_text = text_result.get('generated_text')
                if generated_text:
                    text_filename = f"text_{scene_id}.txt"
                    text_path = os.path.join(scene_path, text_filename)
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(generated_text)
                    print(f"[DEBUG] Text generated successfully")
                    
                    # Auto-generate TTS
                    try:
                        print(f"[DEBUG] Auto-generating TTS for scene {scene_id}")
                        tts_params = {'text': generated_text}
                        tts_resp = requests.get("http://tts:5002/api/tts", params=tts_params, timeout=(5, 90))
                        if tts_resp.status_code == 200:
                            tts_filename = f"tts_{scene_id}.wav"
                            tts_path = os.path.join(scene_path, tts_filename)
                            with open(tts_path, 'wb') as f:
                                f.write(tts_resp.content)
                            print(f"[DEBUG] TTS generated successfully")
                        else:
                            print(f"[WARNING] TTS generation failed: HTTP {tts_resp.status_code}")
                    except Exception as e:
                        print(f"[WARNING] Failed to auto-generate TTS: {str(e)}")
            else:
                print(f"[WARNING] Text generation failed")
        except Exception as e:
            print(f"[WARNING] Failed to auto-generate text: {str(e)}")
        
        # Auto-generate Music
        if prompts.get('music', {}).get('text'):
            try:
                print(f"[DEBUG] Auto-generating music for scene {scene_id}")
                music_prompt = prompts['music']['text']
                music_resp = requests.post(
                    "http://music:5003/generate",
                    json={'prompt': music_prompt, 'duration': 8},
                    timeout=(10, 120)
                )
                if music_resp.status_code == 200:
                    music_result = music_resp.json() or {}
                    music_src_path = music_result.get('path')
                    if music_src_path and os.path.exists(music_src_path):
                        import shutil
                        music_filename = f"music_{scene_id}.wav"
                        music_dest = os.path.join(scene_path, music_filename)
                        shutil.copy(music_src_path, music_dest)
                        print(f"[DEBUG] Music generated successfully")
                else:
                    print(f"[WARNING] Music generation failed: HTTP {music_resp.status_code}")
            except Exception as e:
                print(f"[WARNING] Failed to auto-generate music: {str(e)}")
        
        # Update scene arrangement
        story_dir = os.path.join(project_dir, 'story')
        os.makedirs(story_dir, exist_ok=True)
        arrangement_file = os.path.join(story_dir, 'scene_arrangement.json')
        
        scenes_by_type = {}
        if os.path.exists(arrangement_file):
            try:
                with open(arrangement_file, 'r', encoding='utf-8') as f:
                    existing_arrangement = json.load(f)
                    scenes_by_type = existing_arrangement.get('scenes_by_type', {})
            except Exception as e:
                print(f"Warning: Could not load existing arrangement: {e}")
        
        # Add new scene to arrangement
        if scene_type not in scenes_by_type:
            scenes_by_type[scene_type] = []
        scenes_by_type[scene_type].append(scene_id)
        
        # Save updated arrangement
        arrangement_data = {
            'story_type': story_sis.get('story_type', ''),
            'scenes_by_type': scenes_by_type,
            'updated_at': datetime.now().isoformat()
        }
        
        temp_arrangement_file = arrangement_file + '.tmp'
        try:
            with open(temp_arrangement_file, 'w', encoding='utf-8') as f:
                json.dump(arrangement_data, f, indent=2, ensure_ascii=False)
            
            if os.path.exists(arrangement_file):
                os.remove(arrangement_file)
            os.rename(temp_arrangement_file, arrangement_file)
        except Exception as e:
            if os.path.exists(temp_arrangement_file):
                os.remove(temp_arrangement_file)
            raise e
        
        return jsonify({
            'success': True,
            'scene_id': scene_id,
            'message': f'Successfully created scene: {scene_id}'
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/projects/<project_id>/scenes/<scene_id>', methods=['GET'])
def get_project_scene_info(project_id, scene_id):
    """Get scene information for display in project view"""
    try:
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        if not os.path.isdir(project_dir):
            return jsonify({'success': False, 'error': f'Project {project_id} not found'}), 404
        
        scene_path = os.path.join(project_dir, 'scenes', scene_id)
        if not os.path.isdir(scene_path):
            return jsonify({'success': False, 'error': f'Scene {scene_id} not found'}), 404
        
        # Get scene name (from SIS or use scene_id)
        scene_name = scene_id
        sis_files = [f for f in os.listdir(scene_path) if f.startswith('sis_structure_') and f.endswith('.json')]
        if sis_files:
            try:
                with open(os.path.join(scene_path, sis_files[0]), 'r', encoding='utf-8') as f:
                    sis_data = json.load(f)
                    scene_name = sis_data.get('summary', scene_id)[:50]  # Use summary as name
            except Exception as e:
                print(f"Error reading SIS: {e}")
        
        # Check for thumbnail
        thumbnail_path = None
        has_image = False
        for file in os.listdir(scene_path):
            if file.startswith('image_') and file.endswith('.png') and not file.endswith('_candidate.png'):
                thumbnail_path = f'/scene/{scene_id}/file/{file}'
                has_image = True
                break
        
        # Check for text file
        has_text = any(f.startswith('text_') and f.endswith('.txt') 
                      for f in os.listdir(scene_path))
        
        # Check for music file
        has_music = any(f.startswith('music_') and f.endswith(('.wav', '.mp3', '.ogg'))
                       for f in os.listdir(scene_path))
        
        return jsonify({
            'success': True,
            'scene_id': scene_id,
            'scene_name': scene_name,
            'thumbnail_path': thumbnail_path,
            'has_image': has_image,
            'has_text': has_text,
            'has_music': has_music
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/projects/<project_id>/bulk_delete_scenes', methods=['POST'])
def bulk_delete_scenes(project_id):
    """Bulk delete multiple scenes from a project"""
    try:
        data = request.get_json()
        scene_ids = data.get('scene_ids', [])
        
        if not scene_ids:
            return jsonify({'success': False, 'error': 'No scene IDs provided'}), 400
        
        project_scenes_dir = os.path.join(PROJECTS_DIR, project_id, 'scenes')
        if not os.path.exists(project_scenes_dir):
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        deleted_count = 0
        failed_scenes = []
        
        # Delete each scene directory
        for scene_id in scene_ids:
            scene_path = os.path.join(project_scenes_dir, scene_id)
            if os.path.exists(scene_path):
                try:
                    shutil.rmtree(scene_path)
                    deleted_count += 1
                except Exception as e:
                    failed_scenes.append({'scene_id': scene_id, 'error': str(e)})
            else:
                failed_scenes.append({'scene_id': scene_id, 'error': 'Scene not found'})
        
        # Update scene_arrangement.json to remove deleted scenes
        arrangement_file = os.path.join(PROJECTS_DIR, project_id, 'scene_arrangement.json')
        if os.path.exists(arrangement_file):
            try:
                with open(arrangement_file, 'r', encoding='utf-8') as f:
                    arrangement_data = json.load(f)
                
                # Remove deleted scene IDs from all scene type arrays
                scenes_by_type = arrangement_data.get('scenes_by_type', {})
                for scene_type, scene_list in scenes_by_type.items():
                    scenes_by_type[scene_type] = [s for s in scene_list if s not in scene_ids]
                
                arrangement_data['scenes_by_type'] = scenes_by_type
                arrangement_data['updated_at'] = datetime.now().isoformat()
                
                # Write atomically
                temp_arrangement_file = arrangement_file + '.tmp'
                try:
                    with open(temp_arrangement_file, 'w', encoding='utf-8') as f:
                        json.dump(arrangement_data, f, indent=2, ensure_ascii=False)
                    
                    if os.path.exists(arrangement_file):
                        os.remove(arrangement_file)
                    os.rename(temp_arrangement_file, arrangement_file)
                except Exception as e:
                    if os.path.exists(temp_arrangement_file):
                        os.remove(temp_arrangement_file)
                    raise e
                    
            except Exception as e:
                # Log error but don't fail the entire operation
                print(f"Warning: Failed to update scene_arrangement.json: {str(e)}")
        
        response = {
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Successfully deleted {deleted_count} scene(s)'
        }
        
        if failed_scenes:
            response['failed_scenes'] = failed_scenes
            response['warning'] = f'{len(failed_scenes)} scene(s) could not be deleted'
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route("/story/<filename>/generate_video", methods=['POST'])
def generate_story_video(filename):
    """Generate video from story HTML file and return for download"""
    try:
        narrative_dir = os.path.join(SHARED_DIR, 'story')
        html_file_path = os.path.join(narrative_dir, filename)
        
        if not os.path.exists(html_file_path) or not filename.endswith('.html'):
            return jsonify({'error': 'Story file not found'}), 404
        
        # Read the HTML file to extract narrative data
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Create temporary video file
        temp_video_fd, temp_video_path = tempfile.mkstemp(suffix='.mp4')
        
        try:
            # Close the file descriptor to allow FFmpeg to write to it
            os.close(temp_video_fd)
            
            # Extract embedded audio and narrative data from the HTML and create video
            success = create_video_from_html(html_content, temp_video_path, filename[:-5])
            
            if success and os.path.exists(temp_video_path):
                # Generate filename for download
                video_filename = f"{filename[:-5]}_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                
                # Return video file for download with auto cleanup
                def remove_file(response):
                    try:
                        os.unlink(temp_video_path)
                    except:
                        pass
                    return response
                
                response = send_file(
                    temp_video_path,
                    as_attachment=True,
                    download_name=video_filename,
                    mimetype='video/mp4'
                )
                
                # Register cleanup function (Note: This might not work perfectly in all cases)
                # The file will be cleaned up when the server restarts or manually
                return response
            else:
                try:
                    os.unlink(temp_video_path)
                except:
                    pass
                return jsonify({'error': 'Failed to generate video'}), 500
                
        except Exception as e:
            # Clean up on error
            try:
                os.unlink(temp_video_path)
            except:
                pass
            raise e
            
    except Exception as e:
        return jsonify({'error': f'Error generating video: {str(e)}'}), 500

def create_video_from_html(html_content, output_path, story_title):
    """Create video from HTML content using FFmpeg"""
    try:
        import re
        
        # Extract embedded audio data from HTML
        # Look for the embeddedAudio JavaScript object
        audio_pattern = r'const embeddedAudio = ({.*?});'
        audio_match = re.search(audio_pattern, html_content, re.DOTALL)
        
        if not audio_match:
            return False
        
        audio_data_str = audio_match.group(1)
        # Parse the audio data (simplified extraction)
        embedded_audio = json.loads(audio_data_str)
        
        # Extract scene data pattern
        slides_pattern = r'data-scene-id="([^"]*)"[^>]*data-has-tts="([^"]*)"[^>]*data-has-music="([^"]*)"'
        slides_matches = re.findall(slides_pattern, html_content)
        
        # Extract image data from HTML
        img_pattern = r'<img src="data:image/[^;]+;base64,([^"]+)"'
        img_matches = re.findall(img_pattern, html_content)
        
        # Extract text content
        text_pattern = r'<div class="slide-text">([^<]+)</div>'
        text_matches = re.findall(text_pattern, html_content)
        
        if not slides_matches:
            return False
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_clips = []
            
            for i, (scene_id, has_tts, has_music) in enumerate(slides_matches):
                clip_path = os.path.join(temp_dir, f'scene_{i:03d}.mp4')
                
                # Get image data
                image_data = None
                if i < len(img_matches):
                    image_data = img_matches[i]
                
                # Get text content
                text_content = ""
                if i < len(text_matches):
                    text_content = text_matches[i].strip()
                
                # Get audio data
                tts_data = None
                music_data = None
                
                if scene_id in embedded_audio:
                    tts_data = embedded_audio[scene_id].get('tts')
                    music_data = embedded_audio[scene_id].get('music')
                
                # Create individual scene clip
                if create_scene_clip(clip_path, image_data, text_content, tts_data, music_data, temp_dir, i):
                    scene_clips.append(clip_path)
            
            if not scene_clips:
                return False
            
            # Concatenate all scene clips
            return concatenate_clips(scene_clips, output_path, temp_dir)
    
    except Exception as e:
        print(f"Error creating video: {e}")
        return False

def create_scene_clip(output_path, image_data, text_content, tts_data, music_data, temp_dir, scene_index):
    """Create video clip for a single scene"""
    try:
        # Default clip duration
        clip_duration = 5.0
        
        # Save image if available
        image_path = None
        if image_data:
            image_path = os.path.join(temp_dir, f'image_{scene_index:03d}.png')
            with open(image_path, 'wb') as f:
                f.write(base64.b64decode(image_data))
        
        # Save TTS audio if available
        tts_path = None
        if tts_data and tts_data.startswith('data:audio/'):
            audio_data = tts_data.split(',')[1]
            tts_path = os.path.join(temp_dir, f'tts_{scene_index:03d}.wav')
            with open(tts_path, 'wb') as f:
                f.write(base64.b64decode(audio_data))
            
            # Get audio duration for TTS
            duration_cmd = [
                'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
                '-of', 'csv=p=0', tts_path
            ]
            try:
                result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    clip_duration = max(float(result.stdout.strip()), 3.0)
            except:
                pass
        
        # Save music if available
        music_path = None
        if music_data and music_data.startswith('data:audio/'):
            audio_data = music_data.split(',')[1]
            music_path = os.path.join(temp_dir, f'music_{scene_index:03d}.wav')
            with open(music_path, 'wb') as f:
                f.write(base64.b64decode(audio_data))
        
        # Build FFmpeg command
        cmd = ['ffmpeg', '-y']
        
        # Input image (or create black screen if no image)
        if image_path:
            cmd.extend(['-loop', '1', '-i', image_path])
        else:
            cmd.extend(['-f', 'lavfi', '-i', 'color=black:size=1280x720'])
        
        # Add TTS audio
        if tts_path:
            cmd.extend(['-i', tts_path])
        
        # Add music audio
        if music_path:
            cmd.extend(['-i', music_path])
        
        # Video settings
        cmd.extend(['-t', str(clip_duration)])
        cmd.extend(['-c:v', 'libx264', '-pix_fmt', 'yuv420p'])
        cmd.extend(['-r', '30'])  # 30fps
        
        # Audio mixing and video filtering
        if tts_path and music_path:
            if image_path:
                # Combine video filter with audio mixing
                filter_complex = f'[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[video];[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2[audio]'
                cmd.extend(['-filter_complex', filter_complex])
                cmd.extend(['-map', '[video]', '-map', '[audio]'])
            else:
                cmd.extend(['-filter_complex', '[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2[audio]'])
                cmd.extend(['-map', '0:v', '-map', '[audio]'])
        elif tts_path:
            if image_path:
                cmd.extend(['-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black'])
            cmd.extend(['-map', '0:v', '-map', '1:a'])
        elif music_path:
            if image_path:
                cmd.extend(['-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black'])
            cmd.extend(['-map', '0:v', '-map', '1:a'])
        else:
            # No audio, create silent audio
            if image_path:
                filter_complex = f'[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[video];anullsrc=channel_layout=stereo:sample_rate=44100[audio]'
                cmd.extend(['-filter_complex', filter_complex])
                cmd.extend(['-map', '[video]', '-map', '[audio]'])
            else:
                cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100'])
                cmd.extend(['-map', '0:v', '-map', '1:a'])
        
        cmd.extend(['-shortest'])
        cmd.append(output_path)
        
        # Execute FFmpeg command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"FFmpeg error for scene {scene_index}: {result.stderr}")
            return False
        
        return os.path.exists(output_path)
    
    except Exception as e:
        print(f"Error creating scene clip {scene_index}: {e}")
        return False

def concatenate_clips(clip_paths, output_path, temp_dir):
    """Concatenate multiple video clips into one"""
    try:
        # Create concat file
        concat_file = os.path.join(temp_dir, 'concat.txt')
        with open(concat_file, 'w') as f:
            for clip_path in clip_paths:
                f.write(f"file '{clip_path}'\n")
        
        # FFmpeg concat command
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"FFmpeg concat error: {result.stderr}")
            return False
        
        return os.path.exists(output_path)
    
    except Exception as e:
        print(f"Error concatenating clips: {e}")
        return False


@app.route("/api/servers/image/status")
def api_servers_image_status():
    """画像生成サーバー状態確認API（A1111準拠）"""
    try:
        sd_internal_uri = 'http://sd:7860'
        sd_external_uri = 'http://localhost:7860'

        server_status = {
            # 後方互換のため既存キーも残す
            'server_uri': sd_internal_uri,
            'server_uri_internal': sd_internal_uri,
            'server_uri_external': sd_external_uri,
            'timestamp': datetime.now().isoformat(),
            'online': False,
            'memory_info': None,
            'models_info': None,
            'samplers_info': None,
            'options_info': None,
            'current_model': None,
            'model_loaded': None,
            'error': None
        }

        # オンライン判定は確実に存在するエンドポイントで行う
        try:
            models_resp = requests.get(f"{sd_internal_uri}/sdapi/v1/sd-models", timeout=10)
            if models_resp.status_code == 200:
                server_status['online'] = True
                server_status['models_info'] = models_resp.json()
            else:
                server_status['error'] = f"HTTP {models_resp.status_code} on /sdapi/v1/sd-models"
        except requests.exceptions.ConnectionError:
            server_status['error'] = "Connection refused - Server may be offline"
        except requests.exceptions.Timeout:
            server_status['error'] = "Connection timeout"
        except Exception as e:
            server_status['error'] = str(e)

        # 追加情報（オンライン時のみ）
        if server_status['online']:
            try:
                # サンプラー一覧
                samplers_response = requests.get(f"{sd_internal_uri}/sdapi/v1/samplers", timeout=10)
                if samplers_response.status_code == 200:
                    server_status['samplers_info'] = samplers_response.json()
            except Exception as e:
                server_status['additional_info_error'] = str(e)

            # オプションから現在のモデル名を取得し、ロード有無を推定
            try:
                options_resp = requests.get(f"{sd_internal_uri}/sdapi/v1/options", timeout=10)
                if options_resp.status_code == 200:
                    options = options_resp.json()
                    server_status['options_info'] = options
                    current = options.get('sd_model_checkpoint') or options.get('sd_model', '')
                    server_status['current_model'] = current
                    # A1111ではモデル未ロード時に空文字や"None"となるケースがあるため防御的に判定
                    if current and str(current).strip().lower() not in ('none', 'null', 'not loaded', 'no model'):
                        server_status['model_loaded'] = True
                    else:
                        server_status['model_loaded'] = False
                else:
                    server_status['options_error'] = f"HTTP {options_resp.status_code} on /sdapi/v1/options"
            except Exception as e:
                server_status['options_error'] = str(e)

            # メモリ情報は任意（存在しない環境もあるため失敗しても無視）
            try:
                mem_resp = requests.get(f"{sd_internal_uri}/sdapi/v1/memory", timeout=5)
                if mem_resp.status_code == 200:
                    server_status['memory_info'] = mem_resp.json()
            except Exception:
                pass

        return jsonify(server_status)

    except Exception as e:
        return jsonify({
            'error': f'Server status check failed: {str(e)}',
            'online': False,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route("/api/servers/image/models", methods=["GET"]) 
def api_servers_image_models():
    """A1111の利用可能モデル一覧を取得"""
    sd_uri = 'http://sd:7860'
    try:
        resp = requests.get(f"{sd_uri}/sdapi/v1/sd-models", timeout=15)
        if resp.status_code != 200:
            return jsonify({
                'success': False,
                'error': f"HTTP {resp.status_code} on /sdapi/v1/sd-models",
                'models': []
            }), resp.status_code
        return jsonify({
            'success': True,
            'models': resp.json()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'models': []}), 500

@app.route("/api/servers/image/models/refresh", methods=["POST"]) 
def api_servers_image_models_refresh():
    """A1111のチェックポイントリストを再スキャン"""
    sd_uri = 'http://sd:7860'
    try:
        resp = requests.post(f"{sd_uri}/sdapi/v1/refresh-checkpoints", timeout=20)
        if resp.status_code != 200:
            return jsonify({'success': False, 'error': f"HTTP {resp.status_code}"}), resp.status_code
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/servers/image/model/load", methods=["POST"]) 
def api_servers_image_model_load():
    """指定モデルをロード（sd_model_checkpointを設定しリロード）"""
    sd_uri = 'http://sd:7860'
    try:
        data = request.get_json(force=True) if request.data else {}
        target = (data.get('checkpoint') or data.get('title') or data.get('filename') or '').strip()
        if not target:
            return jsonify({'success': False, 'error': 'checkpoint (or title/filename) is required'}), 400

        # まず利用可能モデル一覧から一致候補を探す
        models_resp = requests.get(f"{sd_uri}/sdapi/v1/sd-models", timeout=15)
        if models_resp.status_code != 200:
            return jsonify({'success': False, 'error': 'failed to fetch models list'}), 502
        models = models_resp.json() or []

        def normalize(s: str) -> str:
            return (s or '').strip().lower()

        selected = None
        for m in models:
            title = m.get('title') or m.get('model_name')
            filename = m.get('filename')
            if normalize(target) in {normalize(title), normalize(os.path.basename(filename or ''))}:
                selected = title or os.path.basename(filename)
                break
        # 直接指定がタイトルそのものの場合も使用
        if not selected:
            selected = target

        # モデル切替（sd_model_checkpoint を設定）
        options_payload = { 'sd_model_checkpoint': selected }
        # モデルロードは時間がかかるため、接続は短く・読み取りは長く待機
        try:
            set_resp = requests.post(
                f"{sd_uri}/sdapi/v1/options",
                json=options_payload,
                timeout=(5, 300)  # connect 5s, read up to 300s
            )
            if set_resp.status_code != 200:
                return jsonify({'success': False, 'error': f"HTTP {set_resp.status_code} on /sdapi/v1/options"}), set_resp.status_code
        except requests.exceptions.ReadTimeout:
            # 読み取りタイムアウトはロード継続中の可能性が高いので、loading状態で返す
            return jsonify({'success': True, 'loading': True, 'message': 'Model loading in progress'}), 202

        # 確実に反映させるためリロード（存在しない場合もあるため失敗は無視）
        try:
            requests.post(f"{sd_uri}/sdapi/v1/reload-checkpoint", timeout=10)
        except Exception:
            pass

        # 現在のモデル名を確認
        opts = requests.get(f"{sd_uri}/sdapi/v1/options", timeout=15)
        current = None
        if opts.status_code == 200:
            optj = opts.json()
            current = optj.get('sd_model_checkpoint') or optj.get('sd_model')

        return jsonify({'success': True, 'current_model': current})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/servers/image/model/unload", methods=["POST"]) 
def api_servers_image_model_unload():
    """現在のモデルをアンロード（VRAM解放）。A1111のunload APIが無い場合はフォールバック。"""
    sd_uri = 'http://sd:7860'
    try:
        # 1) 公式のアンロードエンドポイントを試す
        unload_success = False
        try:
            resp = requests.post(f"{sd_uri}/sdapi/v1/unload-checkpoint", timeout=(5, 120))
            if resp.status_code == 200:
                unload_success = True
        except Exception:
            pass

        # 2) フォールバック: 空文字列をsd_model_checkpointに設定してアンロード
        if not unload_success:
            try:
                # 空文字列を設定してモデルをアンロード
                r = requests.post(f"{sd_uri}/sdapi/v1/options", 
                                json={'sd_model_checkpoint': ''}, 
                                timeout=(5, 30))
                if r.status_code == 200:
                    unload_success = True
            except Exception:
                pass

        # 最終状態確認
        opts = requests.get(f"{sd_uri}/sdapi/v1/options", timeout=15)
        current = None
        model_loaded = None
        if opts.status_code == 200:
            optj = opts.json()
            current = optj.get('sd_model_checkpoint') or optj.get('sd_model')
            # モデルロード状態を判定
            if current and str(current).strip().lower() not in ('none', 'null', '', 'not loaded', 'no model'):
                model_loaded = True
            else:
                model_loaded = False

        return jsonify({
            'success': unload_success,
            'unloaded': not model_loaded if model_loaded is not None else unload_success,
            'current_model': current,
            'model_loaded': model_loaded
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/servers/image/txt2img", methods=["POST"]) 
def api_servers_image_txt2img():
    """A1111のtxt2imgを呼び出すテスト用API。最初の1枚をBase64で返す。"""
    sd_uri = 'http://sd:7860'
    try:
        data = request.get_json(force=True)
        prompt = (data.get('prompt') or '').strip()
        if not prompt:
            return jsonify({'success': False, 'error': 'prompt is required'}), 400

        width = int(data.get('width') or 512)
        height = int(data.get('height') or 512)
        steps = int(data.get('steps') or 20)
        cfg_scale = float(data.get('cfg_scale') or 7.0)
        sampler = data.get('sampler') or data.get('sampler_name') or 'Euler a'
        seed = data.get('seed') if data.get('seed') is not None else -1

        payload = {
            'prompt': prompt,
            'negative_prompt': data.get('negative_prompt') or '',
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'sampler_name': sampler,
            'seed': seed,
            'batch_size': 1,
            'n_iter': 1,
        }

        resp = requests.post(f"{sd_uri}/sdapi/v1/txt2img", json=payload, timeout=(10, 600))
        if resp.status_code != 200:
            return jsonify({'success': False, 'error': f"HTTP {resp.status_code} from A1111"}), resp.status_code

        rj = resp.json()
        images = rj.get('images') or []
        info = rj.get('info')
        if not images:
            return jsonify({'success': False, 'error': 'no images returned', 'info': info}), 502
        # A1111は先頭画像がbase64で返る
        b64 = images[0]

        return jsonify({'success': True, 'image_base64': b64, 'info': info})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/servers/image/test")
def api_servers_image_test():
    """画像生成サーバーテスト用API"""
    try:
        sd_uri = 'http://sd:7860'
        
        # テスト用の簡単な画像生成パラメータ
        test_params = {
            "prompt": "a simple red apple on white background",
            "negative_prompt": "low quality, blurry",
            "width": 512,
            "height": 512,
            "steps": 10,
            "cfg_scale": 7.5,
            "sampler_name": "DPM++ 2M Karras",
            "batch_size": 1,
            "n_iter": 1,
            "seed": 42
        }
        
        start_time = time.time()
        
        response = requests.post(
            f"{sd_uri}/sdapi/v1/txt2img",
            json=test_params,
            timeout=60
        )
        
        generation_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            test_result = {
                'success': True,
                'generation_time': generation_time,
                'image_generated': 'images' in result and len(result['images']) > 0,
                'response_size': len(response.content),
                'timestamp': datetime.now().isoformat()
            }
            
            if test_result['image_generated']:
                test_result['image_count'] = len(result['images'])
                test_result['image_size_estimate'] = len(result['images'][0]) if result['images'] else 0
            
            return jsonify(test_result)
        else:
            return jsonify({
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}',
                'generation_time': generation_time,
                'timestamp': datetime.now().isoformat()
            })
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Test generation timed out (60 seconds)',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
    })

# -----------------------------
# TTS server helpers (Coqui TTS proxy)
# -----------------------------

@app.route("/api/servers/tts/status")
def api_servers_tts_status():
    """Coqui TTS サーバーの稼働状況を返す。"""
    base_internal = "http://tts:5002"
    base_external = "http://localhost:5002"
    model_name = os.environ.get("TTS_MODEL_NAME", "tts_models/en/ljspeech/tacotron2-DDC")

    status = {
        "server_uri_internal": base_internal,
        "server_uri_external": base_external,
        "health_endpoint": f"{base_internal}/api/tts",
        "timestamp": datetime.now().isoformat(),
        "online": False,
        "model_name": model_name,
        "error": None
    }

    try:
        # ルートページは稼働中であれば 200 を返す簡易ヘルスチェック
        resp = requests.get(base_internal + "/", timeout=5)
        if resp.status_code == 200:
            status["online"] = True
        else:
            status["error"] = f"HTTP {resp.status_code}"
    except requests.exceptions.RequestException as exc:
        status["error"] = str(exc)

    return jsonify(status)


@app.route("/api/servers/tts/synthesize", methods=["POST"])
def api_servers_tts_synthesize():
    """テキストをCoqui TTSへ転送し、音声データを返す。"""
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON payload"}), 400

    text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
    if not text:
        return jsonify({"success": False, "error": "text is required"}), 400

    params = {"text": text}
    # 任意パラメータは存在する場合のみ付与する。
    for key in ("speaker_id", "style_wav", "language_id"):
        value = (payload.get(key) or "").strip()
        if value:
            params[key] = value

    try:
        resp = requests.get("http://tts:5002/api/tts", params=params, timeout=(5, 60))
    except requests.exceptions.RequestException as exc:
        return jsonify({"success": False, "error": str(exc)}), 503

    if resp.status_code != 200:
        return jsonify({
            "success": False,
            "error": f"HTTP {resp.status_code}",
            "details": resp.text
        }), resp.status_code

    audio_b64 = base64.b64encode(resp.content).decode("ascii")
    filename = f"tts_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"

    return jsonify({
        "success": True,
        "audio_data": f"data:audio/wav;base64,{audio_b64}",
        "filename": filename,
        "bytes": len(resp.content)
    })


# -----------------------------
# Text server proxies (now backed by Ollama)
# -----------------------------

@app.route("/api/servers/text/status")
def api_servers_text_status():
    """テキストサーバー状態確認API（Ollama使用）"""
    try:
        ollama_internal_uri = 'http://ollama:11434'
        ollama_external_uri = 'http://localhost:11434'

        status = {
            'server_uri_internal': ollama_internal_uri,
            'server_uri_external': ollama_external_uri,
            'timestamp': datetime.now().isoformat(),
            'online': False,
            'health': None,
            'model_status': None,
            'error': None
        }

        # Health -> use /api/version and /api/tags
        try:
            h = requests.get(f"{ollama_internal_uri}/api/version", timeout=10)
            if h.status_code == 200:
                status['health'] = {'version': h.json()}
                status['online'] = True
            else:
                status['error'] = f"HTTP {h.status_code} on /api/version"
        except requests.exceptions.ConnectionError:
            status['error'] = "Connection refused - Server may be offline"
        except requests.exceptions.Timeout:
            status['error'] = "Connection timeout"
        except Exception as e:
            status['error'] = str(e)

        # Model status:
        # 1) installed models via /api/tags
        # 2) currently loaded models via /api/ps
        model_loaded = False
        if status['online']:
            try:
                tags = requests.get(f"{ollama_internal_uri}/api/tags", timeout=10)
                if tags.status_code == 200:
                    tj = tags.json() or {}
                    models = [m.get('model') for m in tj.get('models', []) if isinstance(m, dict)]
                    desired = os.environ.get('OLLAMA_MODEL', 'gemma3:4b-it-qat')
                    # installed かどうか（ディスク）
                    installed = desired in (models or [])
                    loaded_models = []
                    try:
                        ps = requests.get(f"{ollama_internal_uri}/api/ps", timeout=10)
                        if ps.status_code == 200:
                            psj = ps.json() or {}
                            loaded_models = [m.get('name') for m in psj.get('models', []) if isinstance(m, dict)]
                    except Exception:
                        pass
                    # VRAM上でロードされているかは /api/ps に出る名前で判定
                    model_loaded = any(desired == name for name in loaded_models)
                    status['model_status'] = {
                        'model_loaded': model_loaded,
                        'installed_models': models,
                        'loaded_models': loaded_models
                    }
            except Exception:
                pass
        status['model_loaded'] = model_loaded

        return jsonify(status)

    except Exception as e:
        return jsonify({
            'error': f'Text server status check failed: {str(e)}',
            'online': False,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route("/api/servers/text/model/load", methods=["POST"])
def api_servers_text_model_load():
    """Ollamaモデルのpull（/api/pull）"""
    try:
        base = 'http://ollama:11434'
        data = request.get_json(silent=True) or {}
        model_id = (data.get('model_id') or os.environ.get('OLLAMA_MODEL') or 'gemma3:4b-it-qat').strip()
        payload = {'name': model_id, 'stream': False}
        resp = requests.post(f"{base}/api/pull", json=payload, timeout=(10, 600))
        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = {'raw': resp.text}
            return jsonify({'success': False, 'error': f"HTTP {resp.status_code} from /api/pull", 'details': err}), resp.status_code
        # モデルをVRAMへウォームアップするため、空プロンプトで軽く生成を叩く
        # keep_alive=-1 で自動アンロードを無効化
        try:
            warm = {
                'model': model_id,
                'prompt': '',
                'stream': False,
                'keep_alive': -1,
                'options': {
                    'num_predict': 0
                }
            }
            _ = requests.post(f"{base}/api/generate", json=warm, timeout=(10, 60))
        except Exception:
            # ウォームアップ失敗は致命的ではないため無視
            pass
        return jsonify({'success': True, 'result': resp.json(), 'warmed': True, 'model': model_id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/servers/text/model/load/status/<job_id>")
def api_servers_text_model_load_status(job_id):
    """Ollamaでは非同期ジョブIDは使わないため、簡易応答を返す"""
    return jsonify({'success': True, 'status': 'completed'}), 200

@app.route("/api/servers/text/model/unload", methods=["POST"])
def api_servers_text_model_unload():
    """Ollamaモデルをkeep_alive=0で即座にアンロード"""
    try:
        base = 'http://ollama:11434'
        data = request.get_json(silent=True) or {}
        model_id = (data.get('model_id') or os.environ.get('OLLAMA_MODEL') or 'gemma3:4b-it-qat').strip()
        
        # keep_alive=0で即座にアンロード
        payload = {
            'model': model_id,
            'keep_alive': 0
        }
        resp = requests.post(f"{base}/api/generate", json=payload, timeout=(10, 30))
        
        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = {'raw': resp.text}
            return jsonify({'success': False, 'error': f"HTTP {resp.status_code} from /api/generate", 'details': err}), resp.status_code
        
        return jsonify({'success': True, 'message': 'Model unloaded from memory', 'model': model_id})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/servers/text/generate", methods=["POST"])
def api_servers_text_generate():
    """Ollama /api/generate への薄いプロキシ。簡易プロンプトも受け付け。"""
    try:
        base = 'http://ollama:11434'
        data = request.get_json(force=True)

        # Accept either {prompt, max_tokens, temperature} or messages
        prompt = (data.get('prompt') or '').strip()
        if not prompt and 'messages' in data:
            # 簡易的に messages からユーザーテキストを抽出
            try:
                for m in data.get('messages'):
                    if m.get('role') == 'user':
                        c = m.get('content')
                        if isinstance(c, list):
                            texts = [x.get('text') for x in c if isinstance(x, dict) and x.get('type') == 'text' and x.get('text')]
                            if texts:
                                prompt = '\n'.join(texts)
                                break
                        elif isinstance(c, str) and c.strip():
                            prompt = c.strip()
                            break
            except Exception:
                pass
        if not prompt:
            return jsonify({'success': False, 'error': 'prompt is required'}), 400

        model = (data.get('model') or os.environ.get('OLLAMA_MODEL') or 'gemma3:4b-it-qat').strip()
        options = {}
        if 'temperature' in data:
            try:
                options['temperature'] = float(data.get('temperature'))
            except Exception:
                pass
        if 'max_tokens' in data:
            try:
                options['num_predict'] = int(data.get('max_tokens'))
            except Exception:
                pass

        payload = {
            'model': model,
            'prompt': prompt,
            'stream': False,
            'options': options or None
        }
        resp = requests.post(f"{base}/api/generate", json=payload, timeout=(10, 180))
        if resp.status_code != 200:
            return jsonify({'success': False, 'error': f"HTTP {resp.status_code} from /api/generate", 'details': resp.text}), resp.status_code
        rj = resp.json() or {}
        return jsonify({'success': True, 'generated_text': rj.get('response'), 'model': rj.get('model')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# SIS ↔ SIS Transformation Endpoints
# ========================================

@app.route("/etc/sis2sis")
def etc_sis2sis_page():
    """SIS ↔ SIS transformation test page"""
    try:
        from sis2sis import STORY_TYPE_BLUEPRINTS, ALL_SCENE_TYPES
        story_types = list(STORY_TYPE_BLUEPRINTS.keys())
        scene_types = ALL_SCENE_TYPES
        story_type_blueprints = {
            key: list(value.get('scene_types', []))
            for key, value in STORY_TYPE_BLUEPRINTS.items()
        }
    except Exception:
        story_type_blueprints = {
            'three_act': ['setup', 'conflict', 'resolution'],
            'kishotenketsu': ['ki', 'sho', 'ten', 'ketsu'],
            'circular': ['home_start', 'away', 'change', 'home_end'],
            'attempts': ['problem', 'attempt', 'result'],
            'catalog': ['intro', 'entry', 'outro']
        }
        story_types = list(story_type_blueprints.keys())
        scene_types = sorted({stype for options in story_type_blueprints.values() for stype in options})
    return render_template(
        'etc/sis2sis.html',
        story_types=story_types,
        scene_types=scene_types,
        story_type_blueprints=story_type_blueprints
    )

@app.route('/api/sis2sis/list_scenes')
def api_list_scene_sis_files():
    """List available SceneSIS JSON files"""
    try:
        sis_dir = os.path.join(SHARED_DIR, 'sis')
        scene_dir = os.path.join(sis_dir, 'scenes')
        files = []
        
        # Check both sis/ and sis/scenes/
        for check_dir in [sis_dir, scene_dir]:
            if os.path.isdir(check_dir):
                for name in sorted(os.listdir(check_dir)):
                    if name.endswith('.json'):
                        try:
                            full_path = os.path.join(check_dir, name)
                            with open(full_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                if data.get('sis_type') == 'scene':
                                    files.append(name)
                        except Exception:
                            pass
        
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sis2sis/list_stories')
def api_list_story_sis_files():
    """List available StorySIS JSON files"""
    try:
        sis_dir = os.path.join(SHARED_DIR, 'sis')
        story_dir = os.path.join(sis_dir, 'stories')
        files = []
        
        # Check both sis/ and sis/stories/
        for check_dir in [sis_dir, story_dir]:
            if os.path.isdir(check_dir):
                for name in sorted(os.listdir(check_dir)):
                    if name.endswith('.json'):
                        try:
                            full_path = os.path.join(check_dir, name)
                            with open(full_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                if data.get('sis_type') == 'story':
                                    files.append(name)
                        except Exception:
                            pass
        
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sis2sis/load_scene')
def api_load_scene_sis():
    """Load a SceneSIS JSON file"""
    try:
        file_name = request.args.get('file', '').strip()
        if not file_name:
            return jsonify({'success': False, 'error': 'file parameter required'}), 400
        
        sis_dir = os.path.join(SHARED_DIR, 'sis')
        scene_dir = os.path.join(sis_dir, 'scenes')
        
        # Try both locations
        for check_dir in [sis_dir, scene_dir]:
            file_path = os.path.join(check_dir, file_name)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({'success': True, 'content': content})
        
        return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sis2sis/load_story')
def api_load_story_sis():
    """Load a StorySIS JSON file"""
    try:
        file_name = request.args.get('file', '').strip()
        if not file_name:
            return jsonify({'success': False, 'error': 'file parameter required'}), 400
        
        sis_dir = os.path.join(SHARED_DIR, 'sis')
        story_dir = os.path.join(sis_dir, 'stories')
        
        # Try both locations
        for check_dir in [sis_dir, story_dir]:
            file_path = os.path.join(check_dir, file_name)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({'success': True, 'content': content})
        
        return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sis2sis/scene2story', methods=['POST'])
def api_scene2story():
    """SceneSIS → StorySIS transformation"""
    try:
        data = request.get_json()
        if not data or 'scenes' not in data:
            return jsonify({'success': False, 'error': 'scenes array required'}), 400
        
        scenes = data.get('scenes', [])
        if not isinstance(scenes, list) or len(scenes) == 0:
            return jsonify({'success': False, 'error': 'scenes must be a non-empty array'}), 400
        raw_story_type = data.get('story_type')
        requested_story_type = None
        if raw_story_type is not None:
            if not isinstance(raw_story_type, str):
                return jsonify({'success': False, 'error': 'story_type must be a string'}), 400
            raw_story_type = raw_story_type.strip()
            if raw_story_type:
                from sis2sis import STORY_TYPE_BLUEPRINTS
                allowed_story_types = list(STORY_TYPE_BLUEPRINTS.keys())
                if raw_story_type not in allowed_story_types:
                    return jsonify({
                        'success': False,
                        'error': f"story_type must be one of {allowed_story_types}"
                    }), 400
                requested_story_type = raw_story_type

        raw_scene_type_overrides = data.get('scene_type_overrides')
        scene_type_overrides = None
        if raw_scene_type_overrides is not None:
            from sis2sis import normalize_scene_type_overrides
            try:
                scene_type_overrides = normalize_scene_type_overrides(raw_scene_type_overrides, len(scenes))
            except ValueError as exc:
                return jsonify({'success': False, 'error': str(exc)}), 400
            if not any(scene_type_overrides):
                scene_type_overrides = None
        
        # Import and run the transformation
        from sis2sis import scene2story

        raw_scene_blueprint_count = data.get('scene_blueprint_count')
        scene_blueprint_count = None
        if raw_scene_blueprint_count is not None:
            if not isinstance(raw_scene_blueprint_count, int):
                return jsonify({'success': False, 'error': 'scene_blueprint_count must be an integer'}), 400
            if raw_scene_blueprint_count < 1 or raw_scene_blueprint_count > 50:
                return jsonify({'success': False, 'error': 'scene_blueprint_count must be between 1 and 50'}), 400
            scene_blueprint_count = raw_scene_blueprint_count

        scene_type_counts = None
        raw_scene_type_counts = data.get('scene_type_counts')
        if raw_scene_type_counts is not None:
            if not isinstance(raw_scene_type_counts, dict):
                return jsonify({'success': False, 'error': 'scene_type_counts must be an object'}), 400
            parsed_counts = {}
            if requested_story_type:
                from sis2sis import STORY_TYPE_BLUEPRINTS
                allowed_roles = set(STORY_TYPE_BLUEPRINTS[requested_story_type]['scene_types'])
                for key in raw_scene_type_counts.keys():
                    if key not in allowed_roles:
                        return jsonify({'success': False, 'error': f"scene_type_counts contains invalid role '{key}' for story_type '{requested_story_type}'"}), 400
            for key, value in raw_scene_type_counts.items():
                if not isinstance(key, str):
                    return jsonify({'success': False, 'error': 'scene_type_counts keys must be strings'}), 400
                if not isinstance(value, int):
                    return jsonify({'success': False, 'error': f"scene_type_counts['{key}'] must be an integer"}), 400
                if value < 1 or value > 50:
                    return jsonify({'success': False, 'error': f"scene_type_counts['{key}'] must be between 1 and 50"}), 400
                parsed_counts[key] = value
            if parsed_counts:
                scene_type_counts = parsed_counts
        
        result = scene2story(
            scene_sis_list=scenes,
            api_config=APIConfig(),
            requested_story_type=requested_story_type,
            scene_type_overrides=scene_type_overrides,
            scene_blueprint_count=scene_blueprint_count,
            scene_type_counts=scene_type_counts
        )
        
        if result.get('success'):
            # ProcessingResult.to_dict()の構造に対応
            # dataキーの中にstory_sisがあるか、直接story_sisキーがあるかを確認
            story_sis = result.get('story_sis') or result.get('data', {}).get('story_sis', {})
            prompt = result.get('prompt') or result.get('data', {}).get('prompt', '')
            story_type_guide = result.get('story_type_guide') or result.get('data', {}).get('story_type_guide', '')
            
            # デバッグ用: 返り値の構造をログ出力
            print(f"DEBUG scene2story result keys: {result.keys()}")
            print(f"DEBUG story_sis content: {story_sis}")
            
            # Save to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = os.path.join(SHARED_DIR, 'sis', 'stories')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f'story_{timestamp}.json')
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(story_sis, f, indent=2, ensure_ascii=False)
            
            return jsonify({
                'success': True,
                'story_sis': story_sis,
                'prompt': prompt,
                'story_type_guide': story_type_guide,
                'output_path': output_path,
                'metadata': result.get('metadata', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/sis2sis/story2scene_single', methods=['POST'])
def api_story2scene_single():
    """StorySIS → 単一SceneSIS transformation"""
    try:
        data = request.get_json()
        if not data or 'story_sis' not in data or 'blueprint' not in data:
            return jsonify({'success': False, 'error': 'story_sis and blueprint required'}), 400
        
        story_sis = data.get('story_sis', {})
        blueprint = data.get('blueprint', {})
        blueprint_index = data.get('blueprint_index', 0)
        
        if not isinstance(story_sis, dict) or not isinstance(blueprint, dict):
            return jsonify({'success': False, 'error': 'story_sis and blueprint must be objects'}), 400
        
        # Import and run the transformation
        from sis2sis import story2scene_single
        
        result = story2scene_single(
            story_sis=story_sis,
            blueprint=blueprint,
            blueprint_index=blueprint_index,
            api_config=APIConfig()
        )
        
        if result.get('success'):
            scene_sis = result.get('scene_sis') or result.get('data', {}).get('scene_sis', {})
            prompt = result.get('prompt') or result.get('data', {}).get('prompt', '')
            scene_type_hint = result.get('scene_type_hint') or result.get('data', {}).get('scene_type_hint') or blueprint.get('scene_type')
            
            return jsonify({
                'success': True,
                'scene_sis': scene_sis,
                'prompt': prompt,
                'blueprint_index': blueprint_index,
                'scene_type_hint': scene_type_hint,
                'metadata': result.get('metadata', {})
            })
        else:
            error_msg = result.get('error', 'Unknown error')
            # デバッグ用: エラー詳細をログ出力
            print(f"DEBUG story2scene_single failed: {error_msg}")
            print(f"DEBUG result keys: {result.keys()}")
            
            return jsonify({
                'success': False,
                'error': error_msg,
                'blueprint_index': blueprint_index
            }), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/sis2sis/story2scene', methods=['POST'])
def api_story2scene():
    """StorySIS → SceneSIS transformation"""
    try:
        data = request.get_json()
        if not data or 'story_sis' not in data:
            return jsonify({'success': False, 'error': 'story_sis object required'}), 400
        
        story_sis = data.get('story_sis', {})
        if not isinstance(story_sis, dict):
            return jsonify({'success': False, 'error': 'story_sis must be an object'}), 400
        
        # Import and run the transformation
        from sis2sis import story2scene
        
        result = story2scene(
            story_sis=story_sis,
            api_config=APIConfig()
        )
        
        if result.get('success'):
            # ProcessingResult.to_dict()の構造に対応
            scenes = result.get('scenes') or result.get('data', {}).get('scenes', [])
            
            # デバッグ用: 返り値の構造をログ出力
            print(f"DEBUG story2scene result keys: {result.keys()}")
            print(f"DEBUG scenes count: {len(scenes)}")
            
            # Save to files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = os.path.join(SHARED_DIR, 'sis', 'scenes', f'story_{timestamp}')
            os.makedirs(output_dir, exist_ok=True)
            
            saved_paths = []
            for i, scene_data in enumerate(scenes):
                scene_sis = scene_data.get('scene_sis', {})
                scene_type = scene_data.get('scene_type_hint') or 'scene'
                scene_id = scene_sis.get('scene_id', 'unknown')[:8]
                output_path = os.path.join(output_dir, f'scene_{i+1:02d}_{scene_type}_{scene_id}.json')
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(scene_sis, f, indent=2, ensure_ascii=False)
                
                saved_paths.append(output_path)
            
            return jsonify({
                'success': True,
                'scenes': scenes,
                'output_dir': output_dir,
                'saved_paths': saved_paths,
                'metadata': result.get('metadata', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/sis2sis/save_scenes', methods=['POST'])
def api_save_scenes():
    """生成されたSceneSISをファイルに保存"""
    try:
        data = request.get_json()
        if not data or 'scenes' not in data:
            return jsonify({'success': False, 'error': 'scenes array required'}), 400
        
        scenes = data.get('scenes', [])
        story_sis = data.get('story_sis', {})
        
        if not isinstance(scenes, list) or len(scenes) == 0:
            return jsonify({'success': False, 'error': 'scenes must be a non-empty array'}), 400
        
        # 保存先ディレクトリを作成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        story_title = story_sis.get('title', 'story').replace(' ', '_')[:30]
        output_dir = os.path.join(SHARED_DIR, 'sis', 'scenes', f'{story_title}_{timestamp}')
        os.makedirs(output_dir, exist_ok=True)
        
        saved_paths = []
        for i, scene_data in enumerate(scenes):
            scene_sis = scene_data.get('scene_sis', {})
            scene_type = scene_data.get('scene_type_hint') or 'scene'
            scene_id = scene_sis.get('scene_id', str(uuid.uuid4()))[:8]
            output_path = os.path.join(output_dir, f'scene_{i+1:02d}_{scene_type}_{scene_id}.json')
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(scene_sis, f, indent=2, ensure_ascii=False)
            
            saved_paths.append(output_path)
        
        return jsonify({
            'success': True,
            'output_dir': output_dir,
            'saved_paths': saved_paths,
            'saved_count': len(saved_paths)
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
