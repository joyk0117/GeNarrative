#!/usr/bin/env python3
"""
Run end-to-end tests for:
- content2sis_unified.py (image/text -> SIS)
- sis2content_unified.py (SIS -> image prompt+image, story text, music prompt+music, TTS)

Results are written as HTML to this folder.

Notes:
- Intended to run inside Docker Compose network so service hostnames (ollama, sd, music, tts) resolve.
- To run on host (Windows), set environment variable GENARRATIVE_USE_LOCALHOST=1 to target localhost ports.
- Keeps implementation simple with minimal error handling.
"""

import os
import sys
import json
import time
import base64
import shutil
from datetime import datetime
from typing import Dict, Any, Optional
import importlib.util
import importlib

# Ensure we can import project scripts when running from this folder
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(THIS_DIR)  # ui/scripts
UI_ROOT = os.path.dirname(SCRIPTS_DIR)   # ui
REPO_ROOT = os.path.dirname(UI_ROOT)     # repo root

# Add common search paths
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, 'dev', 'scripts'))

# Ensure we import common_base from ui/scripts explicitly to avoid path conflicts
def _force_load_common_base(scripts_dir: str):
    target = os.path.join(scripts_dir, 'common_base.py')
    spec = importlib.util.spec_from_file_location('common_base', target)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules['common_base'] = module
        spec.loader.exec_module(module)
        return module
    raise RuntimeError('Failed to load common_base from ui/scripts')

common_base = _force_load_common_base(SCRIPTS_DIR)
from common_base import APIConfig, GenerationConfig, ProcessingConfig  # type: ignore

# Now import the rest, which will see the patched common_base
from content2sis_unified import extract_sis_from_content
from sis2content_unified import generate_content, ContentGenerator


def make_api_config() -> APIConfig:
    """Create APIConfig; if GENARRATIVE_USE_LOCALHOST=1, point to localhost services."""
    use_local = os.environ.get('GENARRATIVE_USE_LOCALHOST') == '1'
    if use_local:
        return APIConfig(
            ollama_uri='http://localhost:11434',
            sd_uri='http://localhost:7860',
            music_uri='http://localhost:5003',
            tts_uri='http://localhost:5002',
        )
    # default uses docker-compose service names
    return APIConfig()


def find_first_file(search_dir: str, exts) -> Optional[str]:
    """Return first file in search_dir matching one of exts (case-insensitive)."""
    if not os.path.isdir(search_dir):
        return None
    for name in os.listdir(search_dir):
        path = os.path.join(search_dir, name)
        if os.path.isfile(path):
            lower = name.lower()
            if any(lower.endswith(e) for e in exts):
                return path
    return None


def ensure_sample_text(path: str) -> str:
    """Create a small sample text file if not present."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write("A calm mountain valley with a gentle stream under golden sunlight. A lone hiker breathes in the quiet air.")
    return path


def html_escape(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def write_html(report_path: str, sections: Dict[str, str]):
    """Write a simple HTML report using provided sections (name -> HTML chunk)."""
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '  <meta charset="utf-8"/>',
        '  <meta name="viewport" content="width=device-width, initial-scale=1"/>',
        '  <title>Unified Tests Report</title>',
        '  <style>',
        '    body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }',
        '    h1 { margin-bottom: 0; }',
        '    .ts { color: #666; font-size: 0.9em; margin-top: 4px; }',
        '    section { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 16px 0; }',
        '    pre { background: #f7f7f7; padding: 12px; border-radius: 6px; overflow: auto; }',
        '    .ok { color: #0a7; }',
        '    .ng { color: #c33; }',
        '    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }',
        '    img { max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 6px; }',
        '    audio { width: 100%; }',
        '  </style>',
        '</head>',
        '<body>',
        '  <h1>Unified Tests Report</h1>',
        f'  <div class="ts">Generated at {datetime.now().isoformat()}</div>'
    ]

    for title, content in sections.items():
        html_parts.append('<section>')
        html_parts.append(f'<h2>{title}</h2>')
        html_parts.append(content)
        html_parts.append('</section>')

    html_parts.extend(['</body>', '</html>'])
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))


def parse_llm_json_like(generated_text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extraction from LLM output.
    - Prefer fenced JSON (```json ... ``` or ``` ... ```)
    - Then try whole text
    - Then try balanced braces substring
    - Minor fix: remove trailing commas before } or ]
    Returns dict on success, else None.
    """
    if not generated_text:
        return None
    text = generated_text.strip()
    # Prefer fenced JSON
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
    # Try direct json
    try:
        return json.loads(text)
    except Exception:
        pass
    # Balanced braces extraction
    start = text.find('{')
    if start != -1:
        depth = 0
        end = -1
        for i, ch in enumerate(text[start:], start=start):
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
            except Exception:
                candidate_fixed = candidate.replace(',}', '}').replace(',]', ']')
                try:
                    return json.loads(candidate_fixed)
                except Exception:
                    return None
    return None


def main():
    out_dir = THIS_DIR  # report is written here
    test_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_out_dir = os.path.join(out_dir, f'test_result_{test_ts}')
    os.makedirs(base_out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, 'unified_test_report.html')

    # Prepare inputs
    shared_dir = os.path.join(REPO_ROOT, 'shared')
    # Allow overriding the test image via environment variable
    # If GENARRATIVE_TEST_IMAGE is set and the file exists, use it. Otherwise fall back to first file.
    override_image = os.environ.get('GENARRATIVE_TEST_IMAGE')
    if override_image and os.path.isfile(override_image):
        image_input = override_image
    else:
        image_input = find_first_file(os.path.join(shared_dir, 'image'), ['.png', '.jpg', '.jpeg'])
    text_input = find_first_file(os.path.join(shared_dir, 'text'), ['.txt', '.md'])
    if not text_input:
        text_input = ensure_sample_text(os.path.join(shared_dir, 'text', 'sample_input.txt'))

    api_config = make_api_config()
    generation_config = GenerationConfig(
        text_word_count=40,
        image_width=512,
        image_height=384,
        music_duration=10
    )
    # 生成系は output_dir/test_result_<ts> に保存されるため、
    # 二重に test_result_<ts>/test_result_<ts> にならないよう output_dir は THIS_DIR を渡す
    processing_config = ProcessingConfig(output_dir=out_dir)

    sections = {}

    # 1) Content2SIS: Image -> SIS (raw) + try-parse JSON
    if image_input:
        start = time.time()
        sis_img = extract_sis_from_content(image_input, 'image', api_config=api_config)
        dur = time.time() - start
        # Always copy and show source image
        img_copy_path = os.path.join(base_out_dir, os.path.basename(image_input))
        try:
            shutil.copy2(image_input, img_copy_path)
        except Exception:
            img_copy_path = image_input
        rel_img = os.path.relpath(img_copy_path, out_dir)

        parsed_sis_img = None
        parsed_info_html = ''
        if sis_img.get('success'):
            # 画像→SIS は LLMの生応答をそのまま表示する
            raw_text = sis_img.get('content') or sis_img.get('generated_text')
            prompt_text = sis_img.get('prompt')
            if raw_text:
                raw_path = os.path.join(base_out_dir, 'sis_from_image_raw.txt')
                with open(raw_path, 'w', encoding='utf-8') as f:
                    f.write(raw_text)
                rel_raw = os.path.relpath(raw_path, out_dir)
                prompt_block = ''
                if prompt_text:
                    prompt_path = os.path.join(base_out_dir, 'sis_image_prompt.txt')
                    with open(prompt_path, 'w', encoding='utf-8') as pf:
                        pf.write(prompt_text)
                    rel_prompt = os.path.relpath(prompt_path, out_dir)
                    prompt_block = (
                        f'<div>Prompt used for Image SIS extraction:</div>'
                        f'<div>Prompt file: {html_escape(rel_prompt)}</div>'
                        f'<pre>{html_escape(prompt_text)}</pre>'
                    )
                # Try parse JSON to use for downstream SIS2Content steps
                parsed_sis_img = parse_llm_json_like(raw_text)
                if parsed_sis_img:
                    sis_img_json_path = os.path.join(base_out_dir, 'sis_from_image.json')
                    with open(sis_img_json_path, 'w', encoding='utf-8') as jf:
                        jf.write(json.dumps(parsed_sis_img, ensure_ascii=False, indent=2))
                    rel_sis_json = os.path.relpath(sis_img_json_path, out_dir)
                    parsed_info_html = (
                        f'<div class="ok">JSON parsed successfully. Using this SIS for downstream steps.</div>'
                        f'<div>SIS JSON file: {html_escape(rel_sis_json)}</div>'
                    )
                sections['Content2SIS (Image)'] = (
                    f'<div class="ok">SUCCESS (⏱️ {dur:.2f}s)</div>'
                    f'<div>Source image:</div><div><img src="{html_escape(rel_img)}" alt="source image"/></div>'
                    f'{prompt_block}'
                    f'{parsed_info_html}'
                    f'<div>LLM raw response file: {html_escape(rel_raw)}</div>'
                    f'<pre>{html_escape(raw_text)}</pre>'
                )
            else:
                # 互換: sis_data が来た場合はJSON表示
                sis_json = json.dumps(sis_img.get('sis_data'), ensure_ascii=False, indent=2)
                sis_img_path = os.path.join(base_out_dir, 'sis_from_image.json')
                with open(sis_img_path, 'w', encoding='utf-8') as f:
                    f.write(sis_json)
                rel_sis = os.path.relpath(sis_img_path, out_dir)
                sections['Content2SIS (Image)'] = (
                    f'<div class="ok">SUCCESS (⏱️ {dur:.2f}s)</div>'
                    f'<div>Source image:</div><div><img src="{html_escape(rel_img)}" alt="source image"/></div>'
                    f'<div>SIS JSON file: {html_escape(rel_sis)}</div>'
                    f'<pre>{html_escape(sis_json)}</pre>'
                )
        else:
            sections['Content2SIS (Image)'] = (
                f'<div class="ng">FAILED (⏱️ {dur:.2f}s)</div>'
                f'<div>Source image:</div><div><img src="{html_escape(rel_img)}" alt="source image"/></div>'
                f'<div>Error: {html_escape(sis_img.get("error", "Unknown error"))}</div>'
            )
    else:
        sections['Content2SIS (Image)'] = '<div class="ng">No image file found under shared/image/</div>'

    # Base SIS for downstream: use parsed_sis_img if available, otherwise fallback sample
    if image_input and 'sis_img' in locals() and sis_img.get('success') and 'parsed_sis_img' in locals() and parsed_sis_img:
        base_sis = parsed_sis_img
    else:
        base_sis = {
            "summary": "A peaceful mountain landscape with a gentle stream in golden hour.",
            "emotions": ["calm", "peaceful", "serene"],
            "mood": "tranquil",
            "themes": ["nature", "harmony", "solitude"],
            "narrative": {
                "characters": ["lone traveler"],
                "location": "mountain valley with stream",
                "weather": "clear sunny day",
                "tone": "contemplative",
                "style": "nature documentary"
            },
            "visual": {
                "style": "photorealistic landscape",
                "composition": "wide angle mountain view",
                "lighting": "soft golden hour light",
                "perspective": "elevated viewpoint",
                "colors": ["emerald green", "sky blue", "golden yellow"]
            },
            "audio": {
                "genre": "ambient nature sounds",
                "tempo": "slow and flowing",
                "instruments": ["acoustic guitar", "flute", "nature sounds"],
                "structure": "ambient soundscape"
            }
        }

    # 2) SIS2Content: Image prompt + Image (use image SIS)
    start = time.time()
    res_img = generate_content(
        base_sis, 'image', api_config=api_config,
        generation_config=generation_config,
        processing_config=processing_config,
        test_case_name='test_image',
        custom_timestamp=test_ts
    )
    dur = time.time() - start
    if res_img.get('success'):
        img_sec = [
            f'<div class="ok">SUCCESS (⏱️ {dur:.2f}s)</div>',
            f'<div>Prompt file: {html_escape(res_img.get("output_path", ""))}</div>'
        ]
        # Read and show the actual prompt content sent to SD
        prompt_path = res_img.get('output_path')
        if prompt_path and os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as pf:
                    prompt_text = pf.read()
                img_sec.append('<div>Prompt content sent to SD:</div>')
                img_sec.append(f'<pre>{html_escape(prompt_text)}</pre>')
            except Exception:
                pass
        img_result = res_img.get('image_result') or {}
        if img_result.get('success'):
            img_path = img_result.get('image_path') or ''
            rel_img2 = os.path.relpath(img_path, out_dir) if img_path else ''
            if os.path.exists(img_path):
                img_sec.append(f'<div>Generated image:</div><div><img src="{html_escape(rel_img2)}" alt="generated image"/></div>')
            else:
                img_sec.append('<div class="ng">Image file not found on disk</div>')
        else:
            err = img_result.get('error', 'Image generation step failed')
            img_sec.append(f'<div class="ng">{html_escape(err)}</div>')
        sections['SIS2Content (Image)'] = '\n'.join(img_sec)
    else:
        sections['SIS2Content (Image)'] = (
            f'<div class="ng">FAILED (⏱️ {dur:.2f}s)</div>'
            f'<div>Error: {html_escape(res_img.get("error", "Unknown error"))}</div>'
        )

    # 3) SIS2Content: Music prompt + Music (use image SIS)
    start = time.time()
    res_music = generate_content(
        base_sis, 'music', api_config=api_config,
        generation_config=generation_config,
        processing_config=processing_config,
        test_case_name='test_music',
        custom_timestamp=test_ts
    )
    dur = time.time() - start
    if res_music.get('success'):
        mus_sec = [
            f'<div class="ok">SUCCESS (⏱️ {dur:.2f}s)</div>',
            f'<div>Prompt file: {html_escape(res_music.get("output_path", ""))}</div>'
        ]
        # Read and show the actual prompt content sent to music server
        music_prompt_path = res_music.get('output_path')
        if music_prompt_path and os.path.exists(music_prompt_path):
            try:
                with open(music_prompt_path, 'r', encoding='utf-8') as mpf:
                    music_prompt_text = mpf.read()
                mus_sec.append('<div>Prompt content sent to Music:</div>')
                mus_sec.append(f'<pre>{html_escape(music_prompt_text)}</pre>')
            except Exception:
                pass
        mus_result = res_music.get('music_result') or {}
        if mus_result.get('success'):
            mus_path = mus_result.get('music_path') or ''
            rel_mus = os.path.relpath(mus_path, out_dir) if mus_path else ''
            if os.path.exists(mus_path):
                mus_sec.append(f'<div>Generated music:</div><audio controls src="{html_escape(rel_mus)}"></audio>')
            else:
                mus_sec.append('<div class="ng">Music file not found on disk</div>')
        else:
            err = mus_result.get('error', 'Music generation step failed')
            mus_sec.append(f'<div class="ng">{html_escape(err)}</div>')
        sections['SIS2Content (Music)'] = '\n'.join(mus_sec)
    else:
        sections['SIS2Content (Music)'] = (
            f'<div class="ng">FAILED (⏱️ {dur:.2f}s)</div>'
            f'<div>Error: {html_escape(res_music.get("error", "Unknown error"))}</div>'
        )

    # 4) SIS2Content: Text (story) using image SIS + TTS
    start = time.time()
    res_text = generate_content(
        base_sis, 'text', api_config=api_config,
        generation_config=generation_config,
        processing_config=processing_config,
        test_case_name='test_text',
        custom_timestamp=test_ts
    )
    dur = time.time() - start
    if res_text.get('success'):
        story_text = res_text.get('generated_text', '')
        story_path = res_text.get('output_path', '')
        # Generate TTS from the generated story text and attach here
        generator = ContentGenerator(api_config=api_config, generation_config=generation_config, processing_config=processing_config)
        tts_res = generator.text2speech(story_text, test_case_name='test_text_tts', output_filename='story_tts', custom_timestamp=test_ts)
        tts_html = ''
        if tts_res.get('success'):
            audio_path = tts_res.get('audio_path') or ''
            rel_audio = os.path.relpath(audio_path, out_dir) if audio_path else ''
            if audio_path and os.path.exists(audio_path):
                tts_html = (
                    f'<div>Generated TTS audio:</div>'
                    f'<audio controls src="{html_escape(rel_audio)}"></audio>'
                )
            else:
                tts_html = '<div class="ng">TTS audio file not found on disk</div>'
        else:
            tts_html = f'<div class="ng">TTS FAILED: {html_escape(tts_res.get("error", "Unknown error"))}</div>'

        sections['SIS2Content (Story Text + TTS)'] = (
            f'<div class="ok">SUCCESS (⏱️ {dur:.2f}s)</div>'
            f'<div>Story output file: {html_escape(story_path)}</div>'
            f'<pre>{html_escape(story_text)}</pre>'
            f'{tts_html}'
        )
    else:
        sections['SIS2Content (Story Text + TTS)'] = (
            f'<div class="ng">FAILED (⏱️ {dur:.2f}s)</div>'
            f'<div>Error: {html_escape(res_text.get("error", "Unknown error"))}</div>'
        )
    # 5) Content2SIS: Text -> SIS using the generated story text as input (raw-first, then try-parse JSON)
    if 'story_path' in locals() and story_path and os.path.exists(story_path):
        start = time.time()
        sis_txt = extract_sis_from_content(story_path, 'text', api_config=api_config)
        dur = time.time() - start
        if sis_txt.get('success'):
            # Prefer raw text output if present, then try parse JSON for downstream usage
            raw_text2 = sis_txt.get('content') or sis_txt.get('generated_text')
            parsed_sis_txt = None
            parsed_info_html2 = ''
            rel_sis_txt = ''

            if raw_text2:
                # Save raw
                sis_raw_txt_path = os.path.join(base_out_dir, 'sis_from_text_raw.txt')
                with open(sis_raw_txt_path, 'w', encoding='utf-8') as f:
                    f.write(raw_text2)
                rel_sis_raw_txt = os.path.relpath(sis_raw_txt_path, out_dir)
                # Try parse
                parsed_sis_txt = parse_llm_json_like(raw_text2)
                if parsed_sis_txt:
                    sis_txt_json_path = os.path.join(base_out_dir, 'sis_from_text.json')
                    with open(sis_txt_json_path, 'w', encoding='utf-8') as jf:
                        jf.write(json.dumps(parsed_sis_txt, ensure_ascii=False, indent=2))
                    rel_sis_txt = os.path.relpath(sis_txt_json_path, out_dir)
                    parsed_info_html2 = (
                        f'<div class="ok">JSON parsed successfully from raw Text SIS.</div>'
                        f'<div>SIS JSON file: {html_escape(rel_sis_txt)}</div>'
                    )
            else:
                # Backward compatibility: sis_data present as dict
                if isinstance(sis_txt.get('sis_data'), dict):
                    parsed_sis_txt = sis_txt.get('sis_data')
                    sis_txt_json_path = os.path.join(base_out_dir, 'sis_from_text.json')
                    with open(sis_txt_json_path, 'w', encoding='utf-8') as jf:
                        jf.write(json.dumps(parsed_sis_txt, ensure_ascii=False, indent=2))
                    rel_sis_txt = os.path.relpath(sis_txt_json_path, out_dir)
                    parsed_info_html2 = f'<div>SIS JSON file: {html_escape(rel_sis_txt)}</div>'

            # Load original story text for display
            try:
                with open(story_path, 'r', encoding='utf-8') as tf:
                    orig_text = tf.read()
            except Exception:
                orig_text = '(failed to read story text)'

            # Append prompt used
            prompt_text2 = sis_txt.get('prompt')
            prompt_block2 = ''
            if prompt_text2:
                prompt_path2 = os.path.join(base_out_dir, 'sis_from_text_prompt.txt')
                with open(prompt_path2, 'w', encoding='utf-8') as pf:
                    pf.write(prompt_text2)
                rel_prompt2 = os.path.relpath(prompt_path2, out_dir)
                prompt_block2 = (
                    f'<div>Prompt used for Text SIS extraction:</div>'
                    f'<div>Prompt file: {html_escape(rel_prompt2)}</div>'
                    f'<pre>{html_escape(prompt_text2)}</pre>'
                )

            # Assemble section with raw (if any) and parsed info
            raw_block2 = ''
            if raw_text2:
                raw_block2 = (
                    f'<div>LLM raw response file: {html_escape(rel_sis_raw_txt)}</div>'
                    f'<pre>{html_escape(raw_text2)}</pre>'
                )

            sections['Content2SIS (Text)'] = (
                f'<div class="ok">SUCCESS (⏱️ {dur:.2f}s)</div>'
                f'<div>Source text file (generated story): {html_escape(os.path.relpath(story_path, out_dir))}</div>'
                f'<pre>{html_escape(orig_text)}</pre>'
                f'{prompt_block2}'
                f'{parsed_info_html2}'
                f'{raw_block2}'
            )
        else:
            sections['Content2SIS (Text)'] = (
                f'<div class="ng">FAILED (⏱️ {dur:.2f}s)</div>'
                f'<div>Error: {html_escape(sis_txt.get("error", "Unknown error"))}</div>'
            )
    else:
        sections['Content2SIS (Text)'] = (
            '<div class="ng">Skipped: story text not available due to previous failure</div>'
        )

    write_html(report_path, sections)
    print(f"\n📄 Report written to: {report_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
