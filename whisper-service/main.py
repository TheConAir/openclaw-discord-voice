"""
Whisper STT Service
HTTP server that transcribes audio using Faster Whisper.
Loads model on first request, unloads after idle timeout.
"""

import os
import io
import logging
import threading
import time
from flask import Flask, request, jsonify, send_file
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Config
MODEL_NAME = os.getenv("WHISPER_MODEL", "small")  # tiny, small, medium, large-v3
DEVICE = os.getenv("WHISPER_DEVICE", "cuda")  # cuda or cpu
IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "300"))  # 5 minutes

model = None
model_lock = threading.Lock()
last_used = time.time()
model_loaded = False


def load_model():
    """Load Whisper model on demand"""
    global model, model_loaded
    
    with model_lock:
        if model is None:
            logger.info(f"Loading Whisper model: {MODEL_NAME} on {DEVICE}")
            try:
                model = WhisperModel(
                    MODEL_NAME,
                    device=DEVICE if DEVICE == "cuda" else "cpu",
                    compute_type="float16" if DEVICE == "cuda" else "int8"
                )
                model_loaded = True
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                # Fallback to CPU
                logger.info("Falling back to CPU")
                model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
                model_loaded = True


def unload_model():
    """Unload model after idle timeout"""
    global model, model_loaded
    
    with model_lock:
        if model is not None:
            logger.info("Unloading Whisper model (idle timeout)")
            del model
            model = None
            model_loaded = False


def check_idle():
    """Background thread to check idle timeout"""
    global last_used
    
    while True:
        time.sleep(60)  # Check every minute
        if model_loaded and (time.time() - last_used) > IDLE_TIMEOUT:
            logger.info("Model idle timeout reached, unloading...")
            unload_model()


# Start idle checker thread
idle_thread = threading.Thread(target=check_idle, daemon=True)
idle_thread.start()


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """Transcribe audio file"""
    global last_used
    last_used = time.time()
    
    # Load model if not loaded
    if not model_loaded:
        load_model()
    
    data = request.get_json(silent=True) or {}

    if "audio" not in request.files:
        if data and "audio_url" in data:
            # Download audio from URL
            import requests
            resp = requests.get(data["audio_url"])
            audio_data = resp.content
        else:
            return jsonify({"error": "No audio file provided"}), 400
    else:
        audio_file = request.files["audio"]
        audio_data = audio_file.read()

    try:
        # Write to temp file for faster-whisper
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        # Transcribe
        segments, info = model.transcribe(
            temp_path,
            language=data.get("language", "en"),
            beam_size=5,
            vad_filter=True
        )

        os.unlink(temp_path)

        text = " ".join([seg.text for seg in segments])
        
        logger.info(f"Transcribed: {text[:100]}...")
        
        return jsonify({
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability
        })
        
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "model_loaded": model_loaded,
        "model_name": MODEL_NAME,
        "device": DEVICE,
        "idle_timeout": IDLE_TIMEOUT
    })


@app.route("/load", methods=["POST"])
def load():
    """Manually load the model"""
    load_model()
    return jsonify({"status": "loaded", "model": MODEL_NAME})


@app.route("/unload", methods=["POST"])
def unload():
    """Manually unload the model"""
    unload_model()
    return jsonify({"status": "unloaded"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    logger.info(f"Starting Whisper service on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
