# Unified Test Scripts (content2sis_unified & sis2content_unified)

This folder contains a simple end-to-end test runner that:
- Extracts SIS from an image and a text (content2sis_unified.py)
- Generates content from SIS: image prompt + image, story text, music prompt + music, TTS (sis2content_unified.py)
- Writes a single HTML report into this folder so you can review results in a browser

## Files
- `run_unified_tests.py`: main test runner, outputs `unified_test_report.html` in the same folder

## Prerequisites
- Recommended: run inside Docker Compose so service hostnames resolve:
  - `ollama` at http://ollama:11434
  - `sd` at http://sd:7860
  - `music` at http://music:5003
  - `tts` at http://tts:5002
- Shared inputs should be placed under the repository `shared/` folder:
  - An image: `shared/image/*.png|jpg|jpeg`
  - A text: `shared/text/*.txt|md` (if absent, a small sample text is auto-created)

## How to run (Windows PowerShell)
```powershell
# From repo root
python .\ui\scripts\test\run_unified_tests.py
```

If you're running services on the Windows host (localhost), set:
```powershell
$env:GENARRATIVE_USE_LOCALHOST = "1"
python .\ui\scripts\test\run_unified_tests.py
```

This will target:
- Ollama: http://localhost:11434
- SD: http://localhost:7860
- Music: http://localhost:5003
- TTS: http://localhost:5002

## Output
- `unified_test_report.html` in this folder
  - Shows SIS JSON for image/text
  - Shows story text
  - Shows generated image (if SD available)
  - Embeds generated music and TTS audio (if services available)

## Notes
- The script keeps error handling simple and reports failures inline in the HTML.
- Image/music/TTS may fail if corresponding services are not running; the report will show the error.
- Generated files are saved into this folder to make paths easy for the HTML report.
