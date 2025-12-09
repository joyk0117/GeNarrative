#!/bin/bash

# TTS Language Model Switching Script
# Switch between English (LJSpeech) and Japanese (Kokoro) models

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_usage() {
    echo "Usage: $0 [ja|en]"
    echo ""
    echo "Options:"
    echo "  ja  - Switch to Japanese model (Kokoro)"
    echo "  en  - Switch to English model (LJSpeech)"
    echo ""
    echo "Examples:"
    echo "  $0 ja    # Switch to Japanese model"
    echo "  $0 en    # Switch to English model"
}

update_dockerfile() {
    local model_name="$1"
    local dockerfile_path="$SCRIPT_DIR/Dockerfile"
    
    # Update CMD line in Dockerfile
    sed -i "s|CMD \[\"tts-server\", \"--model_name\", \".*\", \"--port\", \"5002\"\]|CMD [\"tts-server\", \"--model_name\", \"$model_name\", \"--port\", \"5002\"]|" "$dockerfile_path"
    
    echo "✅ Dockerfile update completed: $model_name"
}

update_docker_compose() {
    local model_name="$1"
    local compose_path="$PROJECT_ROOT/docker-compose.yml"
    
    # Update command line in docker-compose.yml
    sed -i "s|command: \[\"--model_name\", \".*\", \"--port\", \"5002\"\]|command: [\"--model_name\", \"$model_name\", \"--port\", \"5002\"]|" "$compose_path"
    
    echo "✅ docker-compose.yml update completed: $model_name"
}

restart_tts_service() {
    echo "Restarting TTS service..."
    
    cd "$PROJECT_ROOT"
    
    # Stop TTS service
    docker-compose stop tts
    
    # Remove container
    docker-compose rm -f tts
    
    # Restart TTS service
    docker-compose up -d tts
    
    echo "✅ TTS service restart completed"
    
    # Verify startup
    echo "Verifying service startup..."
    sleep 5
    
    if docker-compose ps tts | grep -q "Up"; then
        echo "✅ TTS service started successfully"
    else
        echo "❌ TTS service failed to start"
        echo "Please check logs: docker-compose logs tts"
    fi
}

# Main processing
case "$1" in
    "ja")
        echo "🇯🇵 Switching to Japanese model (Kokoro)..."
        
        # Update requirements.txt (check Japanese support)
        if ! grep -q "TTS\[server,ja\]" "$SCRIPT_DIR/requirements.txt"; then
            echo "Updating requirements.txt for Japanese support..."
            sed -i 's/TTS\[server\]/TTS[server,ja]/' "$SCRIPT_DIR/requirements.txt"
            echo "✅ requirements.txt update completed"
        fi
        
        # Update Dockerfile and docker-compose.yml
        update_dockerfile "tts_models/ja/kokoro/tacotron2-DDC"
        update_docker_compose "tts_models/ja/kokoro/tacotron2-DDC"
        
        # Restart service
        restart_tts_service
        
        echo ""
        echo "🎌 Switch to Japanese model completed!"
        echo "Test methods:"
        echo "  ./test_tts_api.sh"
        echo "  or:"
        echo "  curl -G \"http://localhost:5002/api/tts\" --data-urlencode \"text=こんにちは\" -o test.wav"
        ;;
        
    "en")
        echo "🇺🇸 Switching to English model (LJSpeech)..."
        
        # Update Dockerfile and docker-compose.yml
        update_dockerfile "tts_models/en/ljspeech/tacotron2-DDC"
        update_docker_compose "tts_models/en/ljspeech/tacotron2-DDC"
        
        # Restart service
        restart_tts_service
        
        echo ""
        echo "🇺🇸 Switch to English model completed!"
        echo "Test methods:"
        echo "  curl \"http://localhost:5002/api/tts?text=Hello%20world\" -o test.wav"
        ;;
        
    *)
        print_usage
        exit 1
        ;;
esac
