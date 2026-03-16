# Openclaw to Discord Voice Bot

A Discord bot that joins voice channels, transcribes speech via Whisper, processes through OpenClaw AI, and responds with synthesized speech via Kokoro TTS.

## Architecture

```
Discord Voice → Whisper (STT) → OpenClaw AI → Kokoro TTS → Discord Voice
```

## Components

- **discord-voice-bot/** - Main Discord bot (discord.py) — auto-joins voice, handles DAVE E2EE
- **whisper-service/** - Faster Whisper HTTP API for speech-to-text (port 8001)
- **tts-service/** - Kokoro TTS HTTP API for text-to-speech (port 8002)

## Requirements

- Python 3.10+
- OpenClaw instance
- Discord bot token
- NVIDIA GPU recommended (CPU supported but slower)

## Quick Start

### 1. Install dependencies

```bash
pip install -r whisper-service/requirements.txt
pip install -r tts-service/requirements.txt
pip install -r discord-voice-bot/requirements.txt
```

### 2. GPU support (optional)

CPU works out of the box. For GPU acceleration, install PyTorch with CUDA:

```bash
# CUDA 12.x (recommended)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

VRAM requirements: Whisper small (~1GB) + Kokoro (~300MB) = ~1.3GB total. Any modern GPU works.

### 3. Set environment variables

Required:
```bash
export DISCORD_BOT_TOKEN=your_bot_token_here
export OPENCLAW_TOKEN=your_openclaw_token_here
export OPENCLAW_URL=https://your-openclaw-host:18789
```

Optional (defaults shown):
```bash
# Whisper
export WHISPER_MODEL=small       # tiny, base, small, medium, large-v3
export WHISPER_DEVICE=cuda       # cuda or cpu

# Kokoro TTS
export KOKORO_VOICE=af_heart     # see voices below
export KOKORO_SPEED=1.15         # 0.5–2.0
export TTS_DEVICE=cuda           # cuda or cpu
```

### 4. Start services

```bash
# Terminal 1 - Whisper STT
cd whisper-service && python3 main.py

# Terminal 2 - Kokoro TTS
cd tts-service && python3 main.py

# Terminal 3 - Discord bot
cd discord-voice-bot && python3 main.py
```

Or all at once:
```bash
export DISCORD_BOT_TOKEN=your_token_here
bash start_all.sh
```

The bot auto-joins your voice channel when you connect. Just start talking.

## Kokoro TTS Voices

Set via `KOKORO_VOICE` environment variable:

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

## OpenClaw Integration

Uses OpenClaw's OpenAI-compatible chat completions endpoint with the `speech` agent — optimized for voice with concise responses and no markdown formatting.

```
POST {OPENCLAW_URL}/v1/chat/completions
model: openclaw:speech
x-openclaw-agent-id: speech
```

A new session ID is generated each time the bot joins a voice channel, maintaining conversation context within a session and resetting on leave/rejoin.

## Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a new application and add a bot
3. Enable **Message Content Intent** and **Server Members Intent** under Privileged Gateway Intents
4. Copy the bot token and set as `DISCORD_BOT_TOKEN`
5. Invite the bot:
   `https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=3145728&scope=bot`

## Testing

```bash
# Check service health
curl http://localhost:8001/health
curl http://localhost:8002/health

# Test Whisper
curl -X POST -F "audio=@test.wav" http://localhost:8001/transcribe

# Test Kokoro TTS
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test!"}' \
  http://localhost:8002/synthesize --output test.wav
```

## Troubleshooting

**Bot doesn't respond**
- Confirm all three services are running and healthy
- Verify the bot has voice channel permissions in Discord

**GPU not detected**
- Run `nvidia-smi` to confirm drivers are installed
- Fall back to CPU: `WHISPER_DEVICE=cpu TTS_DEVICE=cpu`

**Slow first response**
- Normal — models lazy-load on first request. Subsequent requests are fast.

**OpenClaw errors**
- Confirm `OPENCLAW_TOKEN` is set
- The bot disables SSL verification for self-signed certificates on local OpenClaw instances

## License

- Faster-Whisper: MIT
- Kokoro TTS: Apache 2.0
- Discord bot: MIT
