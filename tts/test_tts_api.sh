#!/bin/bash

# TTS API Test Script
# Tests Japanese and English speech generation

echo "=== TTS API Test Script ==="
echo "Output directory: ../shared/"

# Check if TTS server is running
echo "Checking TTS server status..."
if ! curl -s http://localhost:5002 > /dev/null; then
    echo "❌ TTS server is not running"
    echo "Please start with the following command:"
    echo "docker-compose up -d tts"
    exit 1
fi

echo "✅ TTS server is running"
echo ""

# Create output directory
OUTPUT_DIR="../shared"
mkdir -p "$OUTPUT_DIR"

# Japanese speech test
echo "🇯🇵 Japanese speech generation test"
echo "Text: 'おはようございます。今日は良い天気ですね。'"

curl -G "http://localhost:5002/api/tts" \
  --data-urlencode "text=おはようございます。今日は良い天気ですね。" \
  -o "$OUTPUT_DIR/test_japanese_greeting.wav" \
  --silent --show-error

if [ $? -eq 0 ]; then
    file_size=$(stat -c%s "$OUTPUT_DIR/test_japanese_greeting.wav")
    echo "✅ Japanese speech generation successful (${file_size} bytes)"
else
    echo "❌ Japanese speech generation failed"
fi

echo ""

# Long Japanese text test
echo "🇯🇵 Long Japanese text test"
echo "Text: 'こんにちは。私は音声合成システムです...'"

curl -G "http://localhost:5002/api/tts" \
  --data-urlencode "text=こんにちは。私は音声合成システムです。今日は美しい晴れの日ですね。この技術により、テキストから自然な音声を生成することができます。" \
  -o "$OUTPUT_DIR/test_japanese_long.wav" \
  --silent --show-error

if [ $? -eq 0 ]; then
    file_size=$(stat -c%s "$OUTPUT_DIR/test_japanese_long.wav")
    echo "✅ Long Japanese speech generation successful (${file_size} bytes)"
else
    echo "❌ Long Japanese speech generation failed"
fi

echo ""

# English speech test (test if it works with Japanese model)
echo "🇺🇸 English speech test (using Japanese model)"
echo "Text: 'Hello, this is a test of English speech.'"

curl "http://localhost:5002/api/tts?text=Hello,%20this%20is%20a%20test%20of%20English%20speech." \
  -o "$OUTPUT_DIR/test_english_on_ja_model.wav" \
  --silent --show-error

if [ $? -eq 0 ]; then
    file_size=$(stat -c%s "$OUTPUT_DIR/test_english_on_ja_model.wav")
    echo "✅ English speech generation successful (${file_size} bytes)"
else
    echo "❌ English speech generation failed"
fi

echo ""
echo "=== Test completed ==="
echo "Generated files:"
ls -la "$OUTPUT_DIR"/test_*.wav | tail -3

echo ""
echo "File format verification:"
file "$OUTPUT_DIR"/test_*.wav | tail -3

echo ""
echo "🎵 How to play audio files:"
echo "  aplay $OUTPUT_DIR/test_japanese_greeting.wav"
echo "  or open with your audio player"
