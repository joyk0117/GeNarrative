#!/bin/bash

# TTS Comprehensive Test Script
# Integrated testing of English model → Japanese model switching and speech generation

set -e  # Stop script on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_ROOT/shared"

# Color output definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# TTSサーバーの応答を待つ関数
wait_for_tts_server() {
    local max_attempts=12
    local attempt=1
    
    log_info "TTSサーバーの起動を待機中..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:5002 > /dev/null 2>&1; then
            log_success "TTSサーバーが応答しています (試行: $attempt)"
            return 0
        fi
        
        log_info "試行 $attempt/$max_attempts: サーバーの起動を待機中..."
        sleep 10
        ((attempt++))
    done
    
    log_error "TTSサーバーが起動しませんでした"
    return 1
}

# 音声ファイルを生成してテストする関数
test_tts_generation() {
    local model_type="$1"
    local text="$2"
    local output_file="$3"
    local use_encoding="$4"
    
    log_info "🎵 ${model_type}音声生成テスト"
    log_info "テキスト: '$text'"
    
    if [ "$use_encoding" = "true" ]; then
        # 日本語の場合はURLエンコーディング使用
        curl -G "http://localhost:5002/api/tts" \
             --data-urlencode "text=$text" \
             -o "$output_file" \
             --silent --show-error
    else
        # 英語の場合は直接指定
        curl "http://localhost:5002/api/tts?text=$(echo "$text" | sed 's/ /%20/g')" \
             -o "$output_file" \
             --silent --show-error
    fi
    
    if [ $? -eq 0 ] && [ -f "$output_file" ]; then
        local file_size=$(stat -c%s "$output_file")
        local file_type=$(file "$output_file" | grep -o "WAVE audio" || echo "不明")
        
        if [ "$file_type" = "WAVE audio" ] && [ $file_size -gt 1000 ]; then
            log_success "${model_type}音声生成成功 (${file_size} bytes)"
            return 0
        else
            log_error "${model_type}音声生成失敗: 無効なファイル"
            return 1
        fi
    else
        log_error "${model_type}音声生成失敗"
        return 1
    fi
}

# モデル切り替え関数
switch_model() {
    local target_model="$1"
    log_info "🔄 ${target_model}モデルに切り替え中..."
    
    cd "$SCRIPT_DIR"
    ./switch_model.sh "$target_model"
    
    if [ $? -eq 0 ]; then
        log_success "${target_model}モデルへの切り替え完了"
        return 0
    else
        log_error "${target_model}モデルへの切り替え失敗"
        return 1
    fi
}

# メイン処理開始
echo "=============================================="
echo "🚀 TTS包括テストスクリプト開始"
echo "=============================================="
echo ""

# 出力ディレクトリの作成
mkdir -p "$OUTPUT_DIR"

# 現在のサービス状態確認
log_info "現在のTTSサービス状態を確認中..."
if docker-compose -f "$PROJECT_ROOT/docker-compose.yml" ps tts | grep -q "Up"; then
    log_success "TTSサービスが稼働中です"
else
    log_warning "TTSサービスが停止しています。起動中..."
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" up -d tts
fi

echo ""
echo "=============================================="
echo "📋 テスト 1: 英語モデル (LJSpeech)"
echo "=============================================="

# 英語モデルに切り替え
switch_model "en"

# 英語モデルの起動を待機
wait_for_tts_server

# 英語音声のテスト
test_tts_generation "英語" \
    "Hello, this is a comprehensive test of the English LJSpeech model. The weather is beautiful today." \
    "$OUTPUT_DIR/comprehensive_test_english.wav" \
    false

echo ""
echo "=============================================="
echo "📋 テスト 2: 日本語モデル (Kokoro)"
echo "=============================================="

# 日本語モデルに切り替え
switch_model "ja"

# 日本語モデルの起動を待機
wait_for_tts_server

# 日本語音声のテスト（短文）
test_tts_generation "日本語(短文)" \
    "こんにちは。包括テストを実行中です。" \
    "$OUTPUT_DIR/comprehensive_test_japanese_short.wav" \
    true

# 日本語音声のテスト（長文）
test_tts_generation "日本語(長文)" \
    "これは包括的なテストスクリプトによる日本語音声合成のテストです。kokoroモデルが正常に動作し、高品質な日本語音声を生成できることを確認しています。" \
    "$OUTPUT_DIR/comprehensive_test_japanese_long.wav" \
    true

echo ""
echo "=============================================="
echo "📋 テスト 3: クロスモデルテスト"
echo "=============================================="

# 日本語モデルで英語テキストを処理
test_tts_generation "英語(日本語モデル)" \
    "This is English text processed by the Japanese Kokoro model." \
    "$OUTPUT_DIR/comprehensive_test_english_on_ja.wav" \
    false

echo ""
echo "=============================================="
echo "📊 テスト結果サマリー"
echo "=============================================="

echo ""
log_info "生成されたファイル一覧:"
ls -la "$OUTPUT_DIR"/comprehensive_test_*.wav 2>/dev/null | while read line; do
    echo "  $line"
done

echo ""
log_info "ファイル形式確認:"
for file in "$OUTPUT_DIR"/comprehensive_test_*.wav; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        file_info=$(file "$file" | grep -o "WAVE audio.*")
        file_size=$(stat -c%s "$file")
        duration=$(echo "scale=1; $file_size / 44100" | bc -l 2>/dev/null || echo "計算不可")
        echo "  📄 $filename: $file_info (${file_size} bytes, 約${duration}秒)"
    fi
done

echo ""
echo "=============================================="
echo "🎉 テスト完了"
echo "=============================================="

# 成功したテストの数をカウント
success_count=$(ls "$OUTPUT_DIR"/comprehensive_test_*.wav 2>/dev/null | wc -l)
total_tests=4

echo ""
log_info "テスト結果: $success_count/$total_tests のテストが成功"

if [ $success_count -eq $total_tests ]; then
    log_success "全てのテストが成功しました！🎊"
    echo ""
    echo "🎵 音声ファイルの再生方法:"
    echo "  aplay $OUTPUT_DIR/comprehensive_test_english.wav"
    echo "  aplay $OUTPUT_DIR/comprehensive_test_japanese_short.wav"
    echo "  または音声プレイヤーで開いてください"
else
    log_warning "一部のテストが失敗しました。ログを確認してください。"
    echo ""
    echo "🔍 トラブルシューティング:"
    echo "  docker-compose logs tts"
    echo "  ./switch_model.sh ja  # 日本語モデルに戻す"
fi

echo ""
echo "=============================================="
