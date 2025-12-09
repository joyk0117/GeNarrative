# GeNarrative

> This repository is an experimental product and is currently under active development and evaluation. Specifications and behavior may change without prior notice.

## 🌟 Overview
GeNarrative is a local, multimodal creative assistant. It lets you combine scripts, illustrations, narration audio, and BGM to create original story experiences offline. Each function is isolated in Docker containers, with a focus on privacy, reproducibility, and extensibility.

- Example inputs: Script, children’s hand-drawn illustrations
- Example outputs: Multimedia stories with narration (HTML / MP4)

## 🏗️ Architecture / Tech Stack
GeNarrative is built as a microservice-based system. The UI orchestrates the REST APIs of each service and passes generated assets via shared storage.

| Component       | Technology                        | Default Port | Description                                             |
|-----------------|-----------------------------------|--------------|---------------------------------------------------------|
| Integrated UI   | Flask + Swiper.js                | 5000         | Combined front/back end, workflow execution             |
| Image Generation| Stable Diffusion (AUTOMATIC1111) | 7860         | Illustration / image generation                         |
| TTS             | Coqui TTS                        | 5002         | Narration voice generation                              |
| Music Generation| MusicGen (Meta AudioCraft)       | 5003         | BGM / sound effects generation                          |
| LLM Runtime     | Ollama                           | 11434        | Text generation, SIS conversion support                 |

- Internal network: Docker bridge network
- Shared storage: `shared/` (used by all services)
- For actual ports, `docker-compose.yml` is the source of truth

## 🧩 SIS (Semantic Interface Structure)

- GeNarrative uses **SIS (Semantic Interface Structure)** as a common format for multimodal generation.
- Using SIS as a hub, you can generate SIS from scripts or images, and then generate/manage scripts, illustrations, BGM, etc. from SIS in a unified way.
- You can also re-extract SIS from generated assets and use it for search or evaluation.
- For detailed specifications, see `docs/SIS.md`.

## 📁 Directory Structure
```text
GeNarrative-dev/
├── docker-compose.yml      # Definitions for all services
├── requirements.txt        # Common Python dependencies
├── dev/                    # Development (e.g., Jupyter)
├── docs/                   # Documentation
├── sd/                     # Image generation (Stable Diffusion WebUI)
├── tts/                    # Text-to-speech (Coqui TTS)
├── music/                  # Music generation (MusicGen)
├── ui/                     # UI + integrated Flask server
├── unsloth/                # LLM experimentation/inference
└── shared/                 # Shared data area
```

## 🔧 Technical Challenges and Solutions

| Challenge                          | Solution                                                                   |
|------------------------------------|----------------------------------------------------------------------------|
| Controlling multimodal generation  | Designing a unified schema (SIS) and meta-prompts for each modality       |
| Library load / resource contention | Isolating each function in its own container to localize load             |
| Running on a local GPU             | Using quantized and lightweight models                                    |
| Unified output                     | Multimedia output via HTML + Swiper.js or MP4                             |

## 🚀 Quick Start (Windows / PowerShell)

Install Docker Desktop beforehand (for GPU usage you need WSL2 + NVIDIA environment).

- Approximate setup time: 30 minutes or more (initial image download and build)
- Required free disk space: 100GB or more

```powershell
git clone https://github.com/joyk0117/GeNarrative-dev.git
cd GeNarrative-dev
docker compose up -d
```

After all services start, open `http://127.0.0.1:5000/` in your browser to begin.

### Check Service Status
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
- Integrated UI: http://localhost:5000
- Image generation (A1111): http://localhost:7860
- LLM API (Ollama): http://localhost:11434

See `docker-compose.yml` for detailed port settings.

## 🛠️ Troubleshooting (Windows)

### GPU / CUDA
- Use `nvidia-smi` to check GPU status (run in WSL2 or compatible environment).
- To use GPU from Docker, you need an NVIDIA Container Toolkit–equivalent setup.

### Port Conflicts
```powershell
# Check port usage (example: 5000)
netstat -ano | Select-String ":5000"

# After checking the PID, stop the process
Get-Process -Id <PID>
Stop-Process -Id <PID> -Force
```

### API Connectivity / Network
```powershell
# Check connectivity between containers (examples)
docker compose exec ui ping -c 1 music
docker compose exec ui ping -c 1 tts

# Check logs
docker compose logs ui
docker compose logs music
docker compose logs tts
```

## ✅ Reproducibility Checklist
- Start all services with `docker compose up -d`.
- Collect logs for each service with `docker compose logs`.
- Generated assets are stored under `shared/` (subdirectories vary by module).
- Main endpoints (defaults):
  - http://localhost:5000 (UI)
  - http://localhost:7860 (Image)
  - http://localhost:5002 (TTS)
  - http://localhost:5003 (Music)
  - http://localhost:11434 (Ollama)

## 📚 Documents / References
- Structured specification (SIS): `docs/SIS.md`
- UI / API details: `ui/README.md`, `ui/API_REFERENCE.md`
- Development notes: `dev/README.md`
- TTS details: `tts/README.md`
- Jupyter usage: `jupyter/README.md`

## 🎯 Roadmap
- Automatic generation of entire stories
- Stronger multilingual support
- Integration with external AI services
- Gradual modernization (Frontend: Flask → Vue.js, Backend: Flask → FastAPI)
- Fine-tuning (Image: LoRA, LLM: Unsloth)

## 📜 License
MIT License  
Copyright (c) 2025 Yuki Jo
Note: This repository contains only the orchestration code. 
Third-party models, tools, and other assets (e.g. Ollama, AUTOMATIC1111, Coqui TTS, MusicGen, etc.) 
are obtained separately and must be used in accordance with their respective licenses.