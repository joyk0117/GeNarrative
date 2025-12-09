FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# APTミラー固定と基本ツール・Pythonインストール
RUN set -eux; \
        sed -i 's|http://archive.ubuntu.com|http://azure.archive.ubuntu.com|g' /etc/apt/sources.list; \
        if [ -d /etc/apt/sources.list.d ]; then sed -i 's|http://archive.ubuntu.com|http://azure.archive.ubuntu.com|g' /etc/apt/sources.list.d/*.list || true; fi; \
        DEBIAN_FRONTEND=noninteractive apt-get update; \
        # venv作成失敗回避のため python3-venv を追加
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            python3 python3-pip python3-venv git wget libgl1 libglib2.0-0; \
        ln -sf python3 /usr/bin/python; \
        rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt .

# PyTorchを先にインストール
RUN pip install --upgrade pip && \
    pip install torch>=2.0.0 torchvision>=0.15.0

# その他のパッケージをインストール
RUN pip install diffusers>=0.20.0 transformers>=4.30.0 accelerate>=0.20.0 pytorch_lightning>=2.0.0

# xformersを個別にインストール（PyTorch後）- 失敗しても続行
RUN pip install xformers>=0.0.20 || echo "xformers installation failed, continuing without it"

# 残りのパッケージをインストール
RUN pip install gradio>=3.40.0

# Automatic1111 (Stable Diffusion WebUI) のセットアップ
RUN git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git /workspace/webui

# root起動禁止チェックを無効化
RUN sed -i 's/if \[ "$(id -u)" == "0" \ ]; then/#&/g' /workspace/webui/webui.sh && \
    sed -i 's/    echo "ERROR: This script must not be launched as root, aborting..."/#&/g' /workspace/webui/webui.sh && \
    sed -i 's/    exit 1/#&/g' /workspace/webui/webui.sh

RUN mkdir -p /workspace/webui/models/Stable-diffusion

# webui-user.sh の設定を環境変数で制御
ENV COMMANDLINE_ARGS="--listen --port 7860 --api --ui-debug-mode"

EXPOSE 7860
EXPOSE 5000

CMD ["bash", "/workspace/webui/webui.sh"]
