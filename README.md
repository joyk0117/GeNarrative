# GeNarrative

> This repository is an experimental product and is still under active development and evaluation. Specifications and behavior are subject to change without notice.

## Overview
GeNarrative is a local, multimodal creative assistant.
It lets you combine scripts, illustrations, voice, and BGM to create original narrative experiences fully offline.
It emphasizes the ability to iterate through **generate → regenerate → compare → edit** using a semantic intermediate representation called **SIS (Semantic Interface Structure)**.
Each function is isolated by Docker containers, with a focus on privacy, reproducibility, and extensibility.

- Example inputs: scripts, children’s hand‑drawn illustrations
- Example outputs: narrated multimedia stories (HTML / MP4)
- Goal: Not a **finished end‑user app**, but a setup where you can **observe, reproduce, and compare** generation pipelines

## What’s New
### 1) SIS: Exposing the Semantic Intermediate Representation
GeNarrative serializes semantic information about works and scenes as **SIS** (JSON), which enables:
- Keeping semantics (SIS) fixed while **swapping only models/parameters**
- Preserving generation conditions to **ensure reproducibility**
- Allowing **manual editing/correction** even when automatic extraction is incomplete

### 2) Local & Isolated Architecture: Easy to Swap and Compare
The UI orchestrates REST APIs for each service and aggregates outputs into `shared/`.
This makes it possible to **compare LLM / image generation / TTS / music generation at the module level**.

## Related Work
Google Gemini provides a "Storybook" feature that can generate a 10-page illustrated storybook with narration from prompts or photos/images.

Rather than reproducing that exact end-user experience, GeNarrative is designed as a local experimental pipeline centered on SIS (a structured intermediate representation) that makes it easy to generate, regenerate, compare, and swap components. This project is not affiliated with Google.

## Architecture / Tech Stack
GeNarrative adopts a microservice architecture. The UI orchestrates each service via REST APIs and exchanges artifacts via shared storage.

| Component | Technology | Default Port | Description |
|---|---|---|---|
| Integrated UI | Flask + Swiper.js | 5000 | Combined front/back end, workflow execution |
| Image Generation | Stable Diffusion (AUTOMATIC1111) | 7860 | Illustration / image generation |
| Text-to-Speech | Coqui TTS | 5002 | Narration audio generation |
| Music Generation | MusicGen (Meta AudioCraft) | 5003 | Background music / sound effects generation |
| LLM Runtime | Ollama (Gemma3) | 11434 | Text generation, SIS conversion assistance |

- Internal network: Docker bridge network
- Shared storage: `shared/` (shared by all services)
- Default ports are defined in `docker-compose.yml` and take precedence

## SIS (Semantic Interface Structure)

- GeNarrative uses **SIS (Semantic Interface Structure)** as a common format for multimodal generation.
- SIS acts as a hub: you can generate SIS from scripts or images, and then generate scripts, illustrations, BGM, etc. from SIS in a unified manner.
- Outputs can also be re‑parsed back into SIS for search and evaluation (consistency checks).
- See `docs/SIS.md` for detailed specifications.

## Directory Layout
```text
GeNarrative/
├── docker-compose.yml      # All service definitions
├── requirements.txt        # Shared Python dependencies
├── docs/                   # Documentation
├── sd/                     # Image generation (Stable Diffusion WebUI)
├── tts/                    # Text-to-speech (Coqui TTS)
├── music/                  # Music generation (MusicGen)
├── ui/                     # UI + Flask integrated server
└── shared/                 # Shared data area
```

## Technical Challenges and Solutions

| Challenge | Solution |
|---|---|
| Controlling multimodal generation | Design of a unified schema (SIS) and creation of meta-prompts for each modality |
| Library load / resource contention | Isolate each function in its own container to localize load |
| Running on local GPU | Use quantized and lightweight models |
| Integrated output | Multimedia output via HTML + Swiper.js or MP4 |

## Quick Start (Windows / PowerShell)

Install Docker in advance (NVIDIA environment required for GPU usage).

- Approximate setup time: 30+ minutes for first install and startup
- Required free disk space: 100GB+

```powershell
git clone https://github.com/joyk0117/GeNarrative.git
cd GeNarrative
docker compose up -d
```

After startup, open `http://127.0.0.1:5000/` in your browser to start using the app.

### Check Service Status
```powershell
# List all services
docker compose ps

# Check individual logs
docker compose logs ui      # UI server
docker compose logs music   # Music generation server
docker compose logs tts     # Text-to-speech server
docker compose logs sd      # Image generation server
docker compose logs ollama  # Text generation server
```

### Endpoints
- Integrated UI: http://localhost:5000
- Image generation (A1111): http://localhost:7860
- LLM API (Ollama): http://localhost:11434

See `docker-compose.yml` for exact port settings.

## Troubleshooting (Windows)

### GPU / CUDA
- Use `nvidia-smi` to check GPU status (run on WSL2 or a compatible environment)
- When using GPU in Docker, you must set up the equivalent of NVIDIA Container Toolkit

### Port Conflicts
```powershell
# Check port usage (example: 5000)
netstat -ano | Select-String ":5000"

# After checking the PID, stop the target process
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

## Reproducibility Checklist
- Start all services with `docker compose up -d`
- Collect logs for each service with `docker compose logs`
- Generated artifacts are saved under `shared/` (subdirectories differ by module)
- Main endpoints (defaults):
  - http://localhost:5000 (UI)
  - http://localhost:7860 (Images)
  - http://localhost:5002 (TTS)
  - http://localhost:5003 (Music)
  - http://localhost:11434 (Ollama)

## Documentation / References
- Structured specification (SIS): `docs/SIS.md`
- UI / API details: `ui/README.md`, `ui/API_REFERENCE.md`
- TTS details: `tts/README.md`

## Roadmap
- Automatic generation of whole stories
- Stronger multilingual support
- Integration with external AI services
- Gradual modernization (frontend: Flask → Vue.js, backend: Flask → FastAPI)
- Fine-tuning (Image: LoRA, LLM: Unsloth)

## License
MIT License  
Copyright (c) 2025 Yuki Jo

Note: This repository contains only orchestration code.
You must obtain Ollama, AUTOMATIC1111, Coqui TTS, MusicGen, and other third‑party models/tools/assets separately and comply with their respective licenses when using them.
