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

# Log configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Keep model in global variables
model = None
device = None

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
        
        # Convert result to numpy
        audio = wav[0].cpu().numpy()
        
        # Generate filename
        filename = f"music_{uuid.uuid4().hex[:8]}.wav"
        output_path = f"/app/shared/{filename}"
        
        # Save audio file
        torchaudio.save(
            output_path,
            torch.from_numpy(audio),
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
