# TTS (Text-to-Speech) Server Setup and Usage Guide

## Overview

This project implements a speech synthesis server using Coqui TTS.
It supports both English-only model (LJSpeech) and Japanese-only model (Kokoro).

## Supported Models

### 1. English Model: LJSpeech
- **Model Name**: `tts_models/en/ljspeech/tacotron2-DDC`
- **Vocoder**: HiFiGAN vocoder (automatically selected)
- **Features**: High-quality English speech, single speaker

### 2. Japanese Model: Kokoro
- **Model Name**: `tts_models/ja/kokoro/tacotron2-DDC`
- **Vocoder**: `vocoder_models/ja/kokoro/hifigan_v1`
- **Features**: High-quality Japanese speech, single speaker

## File Structure

```
tts/
├── Dockerfile              # Container configuration for TTS server
├── requirements.txt         # Python dependencies (including Japanese support)
└── README.md               # This file
```

## Configuration Files

### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5002

# For Japanese model
CMD ["tts-server", "--model_name", "tts_models/ja/kokoro/tacotron2-DDC", "--port", "5002"]

# For English model
# CMD ["tts-server", "--model_name", "tts_models/en/ljspeech/tacotron2-DDC", "--port", "5002"]
```

### requirements.txt
```
TTS[server,ja]==0.22.0
```

**Important**: The `[ja]` extra is required for Japanese phonemizer.

## Server Startup Methods

### Using Docker Compose (Recommended)

1. **Start with Japanese model**:
```bash
# When Japanese model is configured in docker-compose.yml
docker-compose up -d tts
```

2. **Switch to English model**:
```bash
# Change command in docker-compose.yml
# command: ["--model_name", "tts_models/en/ljspeech/tacotron2-DDC", "--port", "5002"]
docker-compose stop tts
docker-compose rm -f tts
docker-compose up -d tts
```

### Using Docker Directly

1. **Build image**:
```bash
cd tts/
docker build -t genarrative-tts .
```

2. **Start with Japanese model**:
```bash
docker run -d -p 5002:5002 --name tts-ja \
  genarrative-tts tts-server --model_name "tts_models/ja/kokoro/tacotron2-DDC" --port 5002
```

3. **Start with English model**:
```bash
docker run -d -p 5002:5002 --name tts-en \
  genarrative-tts tts-server --model_name "tts_models/en/ljspeech/tacotron2-DDC" --port 5002
```

## API Usage

### Basic Request Format

```
GET http://localhost:5002/api/tts?text=[text]
```

### For Japanese Text (Important)

Japanese text must be URL-encoded.

#### ✅ Correct Method

```bash
# URL encoding with curl
curl -G "http://localhost:5002/api/tts" \
  --data-urlencode "text=こんにちは、今日は良い天気ですね" \
  -o output.wav
```

#### ❌ Incorrect Method

```bash
# This will result in 400 Bad Request error
curl "http://localhost:5002/api/tts?text=こんにちは" -o output.wav
```

### Practical Usage Examples

#### 1. Japanese Speech Generation

```bash
# Short greeting
curl -G "http://localhost:5002/api/tts" \
  --data-urlencode "text=おはようございます" \
  -o greeting.wav

# Long sentence
curl -G "http://localhost:5002/api/tts" \
  --data-urlencode "text=私は音声合成システムです。今日は美しい晴れの日ですね。" \
  -o long_speech.wav
```

#### 2. English Speech Generation

```bash
# English can be specified directly
curl "http://localhost:5002/api/tts?text=Hello, how are you today?" \
  -o english_greeting.wav

curl "http://localhost:5002/api/tts?text=This is a test of the English TTS system." \
  -o english_test.wav
```

### Programmatic Usage

#### Python Example

```python
import requests
import urllib.parse

def generate_japanese_speech(text, output_file):
    url = "http://localhost:5002/api/tts"
    params = {"text": text}
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        with open(output_file, 'wb') as f:
            f.write(response.content)
        print(f"Audio file generated successfully: {output_file}")
    else:
        print(f"Error: {response.status_code}")

# Usage example
generate_japanese_speech("こんにちは、元気ですか？", "japanese_test.wav")
```

## Troubleshooting

### 1. HTTP 400 Bad Request Error

**Cause**: Japanese text is not properly URL-encoded

**Solution**: Use `curl -G --data-urlencode` or appropriate URL encoding libraries

### 2. Container Won't Start

**Cause**: Model downloading in progress, or configuration error

**Solution**:
```bash
# Check logs
docker logs [container_name]

# Recreate container
docker-compose stop tts
docker-compose rm -f tts
docker-compose up -d tts
```

### 3. Audio File is Empty or Unplayable

**Cause**: API request failed

**Verification Steps**:
```bash
# Check file format
file output.wav

# Check error messages (if HTML file)
head output.wav
```

## Performance Information

### Audio File Size Guidelines

- **Format**: 16bit, 22050Hz, Mono WAV
- **Size**: Approximately 44KB/second
- **Examples**:
  - Short greeting (2-3 seconds): 80-130KB
  - Long sentence (10-15 seconds): 400-600KB

### Generation Time

- **First time**: Model download + generation (several minutes)
- **Subsequent times**: 1-3 seconds

## Implementation History

### August 3, 2025
- Changed from English LJSpeech model to Japanese Kokoro model
- Resolved URL encoding issues
- Optimized Docker configuration
- Added Japanese phonemizer dependencies

### Feature Comparison

| Feature | English Model | Japanese Model |
|---------|---------------|----------------|
| Model | LJSpeech | Kokoro |
| Audio Quality | High quality | High quality |
| URL Encoding | Not required | Required |
| Initial Setup | TTS[server] | TTS[server,ja] |

## Future Enhancement Plans

- Multi-language model integration
- Voice cloning functionality implementation
- Emotional expression features
- API authentication functionality
