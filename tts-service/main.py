"""
Kokoro TTS Service
HTTP server that synthesizes speech using Kokoro TTS.
Loads model on first request, unloads after idle timeout.
"""

import os
import io
import logging
import threading
import time
import base64

import re
import numpy as np
import soundfile as sf
from flask import Flask, request, jsonify, send_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Config
VOICE = os.getenv("KOKORO_VOICE", "af_heart")
SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
DEVICE = os.getenv("TTS_DEVICE", "cuda")
IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "0"))  # 0 = never unload
SAMPLE_RATE = 24000

# Clamp speed to valid range
SPEED = max(0.5, min(2.0, SPEED))

pipeline = None
tts_lock = threading.Lock()
last_used = time.time()
model_loaded = False

# Available voices for reference
VOICES = [
    "af_heart", "af_bella", "af_sarah", "af_nova", "af_sky",
    "am_adam", "am_michael",
    "bf_emma",
    "bm_george",
]


def load_model():
    """Load Kokoro pipeline on demand"""
    global pipeline, model_loaded

    with tts_lock:
        if pipeline is None:
            logger.info(f"Loading Kokoro pipeline: voice={VOICE}, device={DEVICE}")
            try:
                import torch
                from kokoro import KPipeline

                device = DEVICE
                if device == "cuda" and not torch.cuda.is_available():
                    logger.warning("CUDA not available, falling back to CPU")
                    device = "cpu"

                pipeline = KPipeline(lang_code="a", device=device)
                model_loaded = True
                logger.info("Kokoro pipeline loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Kokoro pipeline: {e}")
                raise


def unload_model():
    """Unload model after idle timeout"""
    global pipeline, model_loaded

    with tts_lock:
        if pipeline is not None:
            logger.info("Unloading Kokoro pipeline (idle timeout)")
            pipeline = None
            model_loaded = False

            # Release GPU memory
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass


def clean_text(text):
    """Strip markdown formatting so TTS doesn't read asterisks, hashes, etc."""
    text = re.sub(r'\*+', '', text)       # **bold**, *italic*
    text = re.sub(r'_+', ' ', text)       # __underline__, _italic_
    text = re.sub(r'~+', '', text)        # ~~strikethrough~~
    text = re.sub(r'`+', '', text)        # `code`, ```blocks```
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # # headers
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)   # [links](url)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def synthesize_audio(text, voice=None, speed=None):
    """Run Kokoro synthesis, return concatenated audio as numpy array"""
    text = clean_text(text)
    voice = voice or VOICE
    speed = speed or SPEED
    speed = max(0.5, min(2.0, speed))  # Clamp to valid range

    # Validate voice, fall back to default
    if voice not in VOICES:
        logger.warning(f"Unknown voice '{voice}', falling back to af_heart")
        voice = "af_heart"

    with tts_lock:
        # Kokoro yields chunks (one per sentence) - concatenate them
        chunks = []
        for result in pipeline(text, voice=voice, speed=speed):
            if result.audio is not None:
                chunks.append(result.audio)

    if not chunks:
        raise ValueError("Kokoro produced no audio output")

    return np.concatenate(chunks)


def audio_to_wav_buffer(audio):
    """Write numpy audio array to a WAV BytesIO buffer"""
    buffer = io.BytesIO()
    sf.write(buffer, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    buffer.seek(0)
    return buffer


def check_idle():
    """Background thread to check idle timeout"""
    while True:
        time.sleep(60)
        if IDLE_TIMEOUT > 0 and model_loaded and (time.time() - last_used) > IDLE_TIMEOUT:
            logger.info("Model idle timeout reached, unloading...")
            unload_model()


# Start idle checker thread
idle_thread = threading.Thread(target=check_idle, daemon=True)
idle_thread.start()


@app.route("/synthesize", methods=["POST"])
def synthesize():
    """Synthesize speech from text, return WAV"""
    global last_used

    last_used = time.time()

    if not model_loaded:
        load_model()

    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    text = data["text"]
    voice = data.get("voice", VOICE)
    speed = data.get("speed", SPEED)

    try:
        audio = synthesize_audio(text, voice=voice, speed=speed)
        buffer = audio_to_wav_buffer(audio)

        logger.info(f"Synthesized: {text[:50]}...")

        return send_file(
            buffer,
            mimetype="audio/wav",
            as_attachment=False,
            download_name="speech.wav"
        )

    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/synthesize_json", methods=["POST"])
def synthesize_json():
    """Synthesize speech, return as base64 JSON"""
    global last_used

    last_used = time.time()

    if not model_loaded:
        load_model()

    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    text = data["text"]
    voice = data.get("voice", VOICE)
    speed = data.get("speed", SPEED)

    try:
        audio = synthesize_audio(text, voice=voice, speed=speed)
        buffer = audio_to_wav_buffer(audio)
        audio_b64 = base64.b64encode(buffer.read()).decode()

        return jsonify({
            "audio": audio_b64,
            "sample_rate": SAMPLE_RATE
        })

    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "model_loaded": model_loaded,
        "voice": VOICE,
        "speed": SPEED,
        "device": DEVICE,
        "idle_timeout": IDLE_TIMEOUT
    })


@app.route("/models", methods=["GET"])
def list_models():
    """List available Kokoro voices"""
    return jsonify({
        "voices": VOICES,
        "current_voice": VOICE,
        "current_speed": SPEED
    })


@app.route("/load", methods=["POST"])
def load():
    """Manually load the model"""
    load_model()
    return jsonify({"status": "loaded", "voice": VOICE})


@app.route("/unload", methods=["POST"])
def unload():
    """Manually unload the model"""
    unload_model()
    return jsonify({"status": "unloaded"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    logger.info(f"Starting Kokoro TTS service on port {port}")
    logger.info(f"Voice: {VOICE}, Speed: {SPEED}, Device: {DEVICE}")
    app.run(host="0.0.0.0", port=port)
