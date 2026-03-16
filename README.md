# Discord Voice Bot

A Discord bot that joins voice channels, captures audio, transcribes speech via Whisper, processes through OpenClaw AI, and responds with synthesized speech via Coqui TTS.

## Architecture

```
Discord Voice → Whisper (STT) → OpenClaw AI → Coqui TTS → Discord Voice
```

## Components

- **discord-voice-bot/** - Main Discord bot (discord.py)
- **whisper-service/** - Faster Whisper HTTP API for speech-to-text
- **tts-service/** - Coqui TTS HTTP API for text-to-speech
- **docker-compose.yml** - Full stack orchestration

## Quick Start (Non-Docker)

### 1. Create virtual environments and install dependencies

```bash
# Whisper service
cd whisper-service
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# TTS service
cd tts-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# Discord bot
cd discord-voice-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 2. Set environment variables

```bash
# Discord bot
export DISCORD_BOT_TOKEN=your_bot_token_here
export OPENCLAW_URL=http://localhost:18789
export WHISPER_URL=http://localhost:8001
export TTS_URL=http://localhost:8002

# Whisper (optional, defaults shown)
export WHISPER_MODEL=small  # tiny, small, medium, large-v3
export WHISPER_DEVICE=cuda  # cuda or cpu
export IDLE_TIMEOUT=300

# TTS (optional, defaults shown)
export TTS_MODEL=coqui/vits
export TTS_DEVICE=cuda
```

### 3. Start the services

```bash
# Terminal 1 - Whisper service
cd whisper-service
source venv/bin/activate
python main.py

# Terminal 2 - TTS service  
cd tts-service
source venv/bin/activate
python main.py

# Terminal 3 - Discord bot
cd discord-voice-bot
source venv/bin/activate
python main.py
```

### 4. Use the bot

In Discord:
- `/join` - Join your voice channel
- `/voice` - Activate voice chat mode
- `/leave` - Leave the voice channel

## GPU Configuration

### WSL2 with NVIDIA GPU

1. Install NVIDIA drivers for WSL2:
   ```powershell
   wsl --update
   nvidia-smi  # Should show your GPU
   ```

2. Install CUDA toolkit in WSL2:
   ```bash
   sudo apt install cuda-wsld2-drivers
   ```

3. Set `WHISPER_DEVICE=cuda` and `TTS_DEVICE=cuda`

### Proxmox with Passthrough (1060)

1. Enable GPU passthrough in Proxmox
2. Attach 1060 to the VM
3. Install NVIDIA drivers in the VM
4. Same config as above

## Testing

### Test Whisper service
```bash
curl -X POST -F "audio=@test.wav" http://localhost:8001/transcribe
```

### Test TTS service
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test!"}' \
  http://localhost:8002/synthesize --output test_speech.wav
```

## Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create new application
3. Go to Bot section, create bot
4. Enable "Message Content Intent" in Privileged Gateway Intents
5. Copy bot token
6. Invite bot: `https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=3145728&scope=bot`

## OpenClaw Integration

The bot sends messages to OpenClaw's API endpoint. Configure `OPENCLAW_URL` to point to your OpenClaw gateway.

Example API call (in the bot):
```python
POST {OPENCLAW_URL}/api/chat
{
  "message": " transcribed text here ",
  "context": "voice conversation"
}
```

## Troubleshooting

### "No audio" errors
- Make sure bot has voice channel permissions
- Check Discord intent settings

### GPU not detected
- Verify `nvidia-smi` works in WSL2/VM
- Ensure CUDA drivers installed
- Try `WHISPER_DEVICE=cpu` as fallback

### Model loading errors
- Check disk space (Whisper models are 1-5GB)
- Ensure internet for initial model download

## License

- Whisper: MIT
- Coqui TTS: LGPL-2.1 (non-commercial) / Commercial license available
- Discord bot: Your choice
