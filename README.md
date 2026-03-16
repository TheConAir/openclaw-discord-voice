# Discord Voice Bot

A Discord bot that joins voice channels, captures audio, transcribes speech via Whisper, processes through OpenClaw AI, and responds with synthesized speech via Kokoro TTS.

## Architecture

```
Discord Voice → Whisper (STT) → OpenClaw AI (speech agent) → Kokoro TTS → Discord Voice
```

## Components

- **discord-voice-bot/** - Main Discord bot (discord.py) - auto-joins voice, handles DAVE E2EE
- **whisper-service/** - Faster Whisper HTTP API for speech-to-text (port 8001)
- **tts-service/** - Kokoro TTS HTTP API for text-to-speech (port 8002)

## Quick Start

### 1. Install dependencies

No virtual environments needed - install globally or in your preferred environment:

```bash
pip install -r whisper-service/requirements.txt
pip install -r tts-service/requirements.txt
pip install -r discord-voice-bot/requirements.txt
```

### 2. Set environment variables

```bash
export DISCORD_BOT_TOKEN=your_bot_token_here
export OPENCLAW_TOKEN=your_openclaw_token_here
export OPENCLAW_URL=https://your-openclaw-host:18789  # defaults to https://192.168.0.124:18789
```

Optional overrides (defaults shown):
```bash
# Whisper
export WHISPER_MODEL=small       # tiny, base, small, medium, large-v3
export WHISPER_DEVICE=cuda       # cuda or cpu
export IDLE_TIMEOUT=300

# Kokoro TTS
export KOKORO_VOICE=af_heart     # see voices below
export KOKORO_SPEED=1.15         # 0.5–2.0
export TTS_DEVICE=cuda           # cuda or cpu
```

### 3. Start services

**Three separate terminals:**

```bash
# Terminal 1 - Whisper STT
cd whisper-service && python3 main.py

# Terminal 2 - Kokoro TTS
cd tts-service && python3 main.py

# Terminal 3 - Discord bot
cd discord-voice-bot && python3 main.py
```

**Or all at once:**
```bash
export DISCORD_BOT_TOKEN=your_token_here
bash start_all.sh
```

### 4. Use the bot

The bot auto-joins your voice channel when you connect. Just start talking.

## Kokoro TTS Voices

Available voices (set via `KOKORO_VOICE`):

| Voice ID | Description |
|----------|-------------|
| `af_heart` | American female (default) |
| `af_bella` | American female |
| `af_sarah` | American female |
| `af_nova` | American female |
| `af_sky` | American female |
| `am_adam` | American male |
| `am_michael` | American male |
| `bf_emma` | British female |
| `bm_george` | British male |

To switch voices, change `KOKORO_VOICE` and restart the TTS service.

## OpenClaw Integration

The bot uses OpenClaw's OpenAI-compatible chat completions endpoint with the `speech` agent (optimized for voice - concise responses, no markdown formatting).

```
POST {OPENCLAW_URL}/v1/chat/completions
model: openclaw:speech
x-openclaw-agent-id: speech
```

A new session ID is generated each time the bot joins a voice channel, maintaining conversation context within a session and resetting on leave/rejoin.

## GPU Setup

### WSL2 (dev - RTX 5080)

Requires PyTorch with CUDA 12.8+:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

### Proxmox VM (prod - GTX 1060 6GB)

Both Whisper (small, ~1GB VRAM) and Kokoro (~300MB VRAM) fit comfortably in 6GB. Enable GPU passthrough in Proxmox and install NVIDIA drivers in the VM.

## Testing

```bash
# Test Whisper
curl -X POST -F "audio=@test.wav" http://localhost:8001/transcribe

# Test Kokoro TTS
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test!"}' \
  http://localhost:8002/synthesize --output test.wav

# Check service health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

## Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a new application and add a bot
3. Enable **Message Content Intent** and **Server Members Intent** under Privileged Gateway Intents
4. Copy the bot token → set as `DISCORD_BOT_TOKEN`
5. Invite the bot with voice + message permissions:
   `https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=3145728&scope=bot`

## Troubleshooting

**Bot doesn't respond / no audio**
- Check all three services are running and healthy (`/health` endpoints)
- Verify bot has voice channel permissions in Discord

**GPU not detected**
- Run `nvidia-smi` to confirm drivers are working
- For RTX 5080 (Blackwell), requires PyTorch cu128 (see GPU Setup above)
- Fall back to CPU: `WHISPER_DEVICE=cpu TTS_DEVICE=cpu`

**Slow first response**
- Normal - models lazy-load on first request (~6-8s). Subsequent requests are fast (~0.1s TTS, ~0.05s STT).

**OpenClaw errors**
- Confirm `OPENCLAW_TOKEN` is set
- The bot uses HTTPS with self-signed cert (SSL verification disabled for local OpenClaw)

## License

- Whisper / Faster-Whisper: MIT
- Kokoro TTS: Apache 2.0
- Discord bot: MIT
