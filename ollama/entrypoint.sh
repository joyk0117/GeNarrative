#!/usr/bin/env sh
set -e

# Start Ollama server in background
/bin/ollama serve &
SERVER_PID=$!

# Wait until the server is ready
ATTEMPTS=0
until /bin/ollama list >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS+1))
  if [ "$ATTEMPTS" -ge 120 ]; then
    echo "Ollama server did not become ready in time" >&2
    break
  fi
  sleep 1
done

# Pull target models if not present
for MODEL in gemma3:4b gemma3:4b-it-qat; do
  if ! /bin/ollama list | awk '{print $1}' | grep -qx "$MODEL"; then
    echo "Pulling model $MODEL..."
    /bin/ollama pull "$MODEL" || true
  else
    echo "Model $MODEL already present."
  fi
done

# Keep foreground attached to server
wait $SERVER_PID
