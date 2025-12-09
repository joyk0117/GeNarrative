FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Fix APT mirror and install basic tools and Python
RUN set -eux; \
        sed -i 's|http://archive.ubuntu.com|http://azure.archive.ubuntu.com|g' /etc/apt/sources.list; \
        if [ -d /etc/apt/sources.list.d ]; then sed -i 's|http://archive.ubuntu.com|http://azure.archive.ubuntu.com|g' /etc/apt/sources.list.d/*.list || true; fi; \
        DEBIAN_FRONTEND=noninteractive apt-get update; \
                DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
                    python3 python3-pip python3-dev build-essential pkg-config git wget \
                    libgl1 libglib2.0-0 libsndfile1 ffmpeg libavcodec-extra \
                    libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev \
                    libavfilter-dev libswscale-dev libswresample-dev; \
        ln -sf python3 /usr/bin/python; \
        rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .

# Install PyTorch first
RUN pip install --upgrade pip && \
    pip install "numpy<2" && \
    pip install --no-cache-dir torch==2.1.2 torchaudio==2.1.2

# Install other packages
RUN pip install --no-cache-dir \
    transformers==4.41.2 \
    flask>=2.3.0 flask-cors>=4.0.0 \
    scipy>=1.10.0 librosa>=0.10.0 soundfile>=0.12.0 requests>=2.31.0 \
    sentencepiece safetensors

# Install audiocraft last (depends on torch)
RUN pip install --no-cache-dir audiocraft==1.0.0

# Create MusicGen model cache directories
RUN mkdir -p /app/models /app/cache

# Copy application file
COPY app.py .

# Expose port
EXPOSE 5003

# Mount point for shared directory
VOLUME ["/app/shared"]

# Start server
CMD ["python", "app.py"]
