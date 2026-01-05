from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import torch
from audiocraft.models import MusicGen
import torchaudio
import io
import os
import uuid
import logging
from datetime import datetime
import math

# Log configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Keep model in global variables
model = None
device = None


def _apply_output_gain(
    audio_tensor: torch.Tensor,
    *,
    target_peak: float = 0.98,
    max_gain_db: float = 12.0,
) -> tuple[torch.Tensor, float, float]:
    """Apply peak normalization with a gain cap.

    Returns: (processed_audio, peak_before, applied_gain_db)
    """
    if audio_tensor.numel() == 0:
        return audio_tensor, 0.0, 0.0

    # Ensure floating type for scaling.
    if not torch.is_floating_point(audio_tensor):
        audio_tensor = audio_tensor.to(torch.float32)

    peak_before = float(audio_tensor.abs().max().item())
    if peak_before <= 0.0 or not math.isfinite(peak_before):
        return audio_tensor, peak_before, 0.0

    # Clamp env/config values to sane ranges.
    target_peak = float(target_peak)
    if not math.isfinite(target_peak) or target_peak <= 0.0:
        return audio_tensor, peak_before, 0.0
    target_peak = max(0.05, min(target_peak, 0.999))

    max_gain_db = float(max_gain_db)
    if not math.isfinite(max_gain_db):
        max_gain_db = 0.0
    max_gain_db = max(0.0, min(max_gain_db, 30.0))

    desired_scale = target_peak / peak_before
    max_scale = 10.0 ** (max_gain_db / 20.0)
    scale = min(desired_scale, max_scale)

    applied_gain_db = 20.0 * math.log10(scale) if scale > 0 else 0.0

    processed = (audio_tensor * scale).clamp(-1.0, 1.0)
    return processed, peak_before, applied_gain_db

def initialize_model():
    """Initialize MusicGen model"""
    global model, device
    
    try:
        # Set device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device}")
        
        # Load MusicGen model (use small version to reduce memory usage)
        logger.info("Loading MusicGen model...")
        model = MusicGen.get_pretrained('facebook/musicgen-small')
        model.set_generation_params(duration=8)  # default 8 seconds
        logger.info("MusicGen model loaded successfully")
        
    except Exception as e:
        logger.error(f"Error initializing model: {e}")
        raise e

@app.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None,
        "device": str(device) if device else "unknown",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/generate', methods=['POST'])
def generate_music():
    """Music generation endpoint"""
    try:
        if model is None:
            return jsonify({"error": "Model not initialized"}), 500
        
        data = request.get_json()
        
        # Get parameters
        prompt = data.get('prompt', 'happy upbeat music')
        duration = data.get('duration', 8)  # default 8 seconds
        temperature = data.get('temperature', 1.0)
        top_k = data.get('top_k', 250)
        top_p = data.get('top_p', 0.0)
        
        logger.info(f"Generating music with prompt: '{prompt}', duration: {duration}s")
        
        # Set generation parameters
        model.set_generation_params(
            duration=duration,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p
        )
        
        # Generate music
        with torch.no_grad():
            wav = model.generate([prompt])

        # Apply output gain / peak normalization to make the result louder by default.
        # Tunable via env vars to avoid changing UX.
        target_peak = float(os.environ.get('MUSIC_TARGET_PEAK', '0.98'))
        max_gain_db = float(os.environ.get('MUSIC_MAX_GAIN_DB', '12.0'))
        audio_tensor = wav[0].detach().cpu()
        audio_tensor, peak_before, applied_gain_db = _apply_output_gain(
            audio_tensor,
            target_peak=target_peak,
            max_gain_db=max_gain_db,
        )
        logger.info(
            f"Output gain applied: peak_before={peak_before:.4f}, applied_gain_db={applied_gain_db:.2f}dB, target_peak={target_peak}"
        )
        
        # Generate filename
        filename = f"music_{uuid.uuid4().hex[:8]}.wav"
        output_path = f"/app/shared/{filename}"
        
        # Save audio file
        torchaudio.save(
            output_path,
            audio_tensor,
            sample_rate=model.sample_rate
        )
        
        logger.info(f"Music generated and saved to: {output_path}")
        
        return jsonify({
            "success": True,
            "filename": filename,
            "path": output_path,
            "prompt": prompt,
            "duration": duration,
            "sample_rate": model.sample_rate
            ,
            "applied_gain_db": applied_gain_db
        })
        
    except Exception as e:
        logger.error(f"Error generating music: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download generated music file"""
    try:
        file_path = f"/app/shared/{filename}"
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/models', methods=['GET'])
def list_models():
    """List available models"""
    models = [
        {
            "name": "facebook/musicgen-small",
            "description": "Small model (300M parameters) - faster generation",
            "current": True
        },
        {
            "name": "facebook/musicgen-medium", 
            "description": "Medium model (1.5B parameters) - better quality",
            "current": False
        },
        {
            "name": "facebook/musicgen-large",
            "description": "Large model (3.3B parameters) - best quality",
            "current": False
        }
    ]
    return jsonify({"models": models})

@app.route('/switch_model', methods=['POST'])
def switch_model():
    """Switch model (example implementation)"""
    global model
    
    try:
        data = request.get_json()
        model_name = data.get('model_name', 'facebook/musicgen-small')
        
        logger.info(f"Switching to model: {model_name}")
        
        # 新しいモデルをロード
        model = MusicGen.get_pretrained(model_name)
        model.set_generation_params(duration=8)
        
        return jsonify({
            "success": True,
            "model": model_name,
            "message": f"Successfully switched to {model_name}"
        })
        
    except Exception as e:
        logger.error(f"Error switching model: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        # Initialize model
        initialize_model()
        
        # Start server
        app.run(host='0.0.0.0', port=5003, debug=False)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise e
