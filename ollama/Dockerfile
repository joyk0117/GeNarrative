# Minimal Ollama container based on the official image
# Keep it simple: we only expose the API and run the server.

FROM ollama/ollama:latest

# Expose Ollama API port
EXPOSE 11434

# Default volume for models/cache (same as official)
VOLUME ["/root/.ollama"]

# Add entrypoint script to auto-pull model at container start
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
