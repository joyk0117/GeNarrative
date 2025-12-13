# GeNarrative

> This repository is an experimental product and is currently under active development and evaluation. Specifications and behavior may change without prior notice.

## 🌟 Overview
GeNarrative is a local, multimodal creative assistant.
You can combine scripts, illustrations, voice, and BGM to create original narrative experiences completely offline.
On the first run, you need to download models and build Docker containers (subsequent runs basically work offline).

We focus on supporting **generation → regeneration → comparison → editing** workflows via a semantic intermediate representation called **SIS (Semantic Interface Structure)**.
Each function is separated into its own Docker service, with an emphasis on privacy, reproducibility, and extensibility.

- Example inputs: Scripts, children’s hand-drawn illustrations
- Example outputs: Narrated multimedia stories (HTML / MP4)
- Goal: Not a **finished end-user app**, but a system where you can **observe, reproduce, and compare** the generation pipeline

## What’s New

### 1) SIS: Exposing the “semantic” intermediate representation
GeNarrative serializes the semantic information of works and scenes as **SIS** (JSON), enabling you to:

- Keep semantics (SIS) fixed while **swapping only models/parameters**
- Preserve generation conditions to **ensure reproducibility**
- **Manually edit or correct** SIS when extraction is imperfect

### 2) Local & separated architecture: Easy to swap and compare
The UI orchestrates each service over REST APIs and aggregates all outputs into `shared/`.
This allows you to **compare LLM / image generation / TTS / music generation on a per-module basis**.

## 🔍 Related Work
Google Gemini provides a “Storybook” feature that can generate a 10-page illustrated storybook with narration from prompts and photos/images.

GeNarrative is not aiming to reproduce that exact finished experience. Instead, it is designed as a local experimental pipeline centered on SIS (a structured intermediate representation), making it easy to generate, regenerate, compare, and swap components. (This project is not affiliated with Google.)

## 🏗️ Architecture / Tech Stack
GeNarrative uses a microservice architecture. The UI orchestrates each service via REST APIs and all artifacts are exchanged through shared storage.

| Component | Technology | Default Port | Description |
|---|---|---|---|
| Unified UI | Flask + Swiper.js | 5000 | Integrated front/back end, workflow execution |
| Image generation | AUTOMATIC1111 (Stable Diffusion) | 7860 | Illustration / image generation |
| Text-to-Speech | Coqui TTS | 5002 | Narration voice generation |
| Music generation | MusicGen (Meta AudioCraft) | 5003 | Background music / sound effects generation |
| LLM runtime | Ollama (Gemma3) | 11434 | Text generation, SIS transformation support |

- Internal network: Docker bridge network
- Shared storage: `shared/` (used by all services)
- Default ports: see `docker-compose.yml` for the source of truth

## 🧩 SIS (Semantic Interface Structure)

- GeNarrative uses **SIS (Semantic Interface Structure)** as the common format for multimodal generation.
- By using SIS as a hub, you can create SIS from scripts or images, and then generate scripts, illustrations, BGM, etc. in a unified manner from SIS.
- You can also re-extract SIS from generated artifacts and use it for search and evaluation (consistency checking).
- For detailed specifications, see `docs/SIS.md`.

## 📁 Directory Structure
```text
GeNarrative/
├── docker-compose.yml      # Definitions of all services
├── requirements.txt        # Shared Python dependencies
├── docs/                   # Documentation
├── sd/                     # Image generation (Stable Diffusion WebUI)
├── tts/                    # Text-to-speech (Coqui TTS)
├── music/                  # Music generation (MusicGen)
├── ui/                     # UI + Flask integrated server
└── shared/                 # Shared data area
```

## 🔧 Technical Challenges and Solutions

| Challenge | Solution |
|---|---|
| Controlling multimodal generation | Design a unified schema (SIS) and meta-prompts for each modality |
| Library load and resource contention | Isolate each function into its own container to localize load |
| Running on local GPUs | Use quantized and lightweight models |
| Unified output | Produce multimedia output as HTML + Swiper.js or MP4 |

## 🚀 Quick Start (Windows / PowerShell)

Please install Docker in advance (NVIDIA environment required for GPU usage).

- Estimated setup time: 30+ minutes for first install and startup
- Required free disk space: 100GB or more
- Recommended GPU: 12GB+ VRAM (depends on model configuration)
(Mainly due to model downloads and container builds.)

```powershell
git clone https://github.com/joyk0117/GeNarrative.git
cd GeNarrative
docker compose up -d
```

After startup, open your browser and access `http://localhost:5000/` to start using the app.

### Checking Service Status
```powershell
# List all services
docker compose ps

# Check individual logs
docker compose logs ui      # UI server
docker compose logs music   # Music generation server
docker compose logs tts     # TTS server
docker compose logs sd      # Image generation server
docker compose logs ollama  # Text generation server
```

### Endpoints
- Unified UI: http://localhost:5000
- Image generation (A1111): http://localhost:7860
- LLM API (Ollama): http://localhost:11434

For exact port settings, see `docker-compose.yml`.

## 🛠️ Troubleshooting (Windows)

### GPU / CUDA
- Check GPU status with `nvidia-smi` (on WSL2 or another supported environment).
- To use GPU in Docker, you need to install the NVIDIA Container Toolkit or equivalent.

### Port Conflicts
```powershell
# Check port usage (example: 5000)
netstat -ano | Select-String ":5000"

# After checking the PID, stop the target process
Get-Process -Id <PID>
Stop-Process -Id <PID> -Force
```

### API Connectivity / Networking
```powershell
# Check connectivity between containers (examples)
docker compose exec ui ping -c 1 music
docker compose exec ui ping -c 1 tts

# Check logs
docker compose logs ui
docker compose logs music
docker compose logs tts
```

## ✅ Reproducibility Check
- Start all services with `docker compose up -d`.
- Get logs for each service with `docker compose logs`.
- Generated artifacts are saved under `shared/` (subdirectories differ by module).
- Main endpoints (defaults):
  - http://localhost:5000 (UI)
  - http://localhost:7860 (Image)
  - http://localhost:5002 (TTS)
  - http://localhost:5003 (Music)
  - http://localhost:11434 (Ollama)

## 📚 Documentation / References
- Structured specification (SIS): `docs/SIS.md`
- UI / API details: `ui/README.md`, `ui/API_REFERENCE.md`
- TTS details: `tts/README.md`

## 🎯 Roadmap
- Automatic generation of full stories
- Stronger multi-language support
- Integration with external AI services
- Gradual modernization (Frontend: Flask → Vue.js, Backend: Flask → FastAPI)
- Fine-tuning (Image: LoRA, LLM: Unsloth)

## 📜 License
MIT License  
Copyright (c) 2025 Yuki Jo

Note: This repository only contains orchestration code.
Third-party models/tools/assets such as Ollama, AUTOMATIC1111, Coqui TTS, and MusicGen must be obtained separately and used in accordance with their respective licenses.
