#!/bin/bash
# Discord Voice Bot - Master startup script

set -e

cd ~/discord-voice-bot

export DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN:-}"
export OPENCLAW_URL="${OPENCLAW_URL:-http://localhost:18789}"
export WHISPER_URL="${WHISPER_URL:-http://localhost:8001}"
export TTS_URL="${TTS_URL:-http://localhost:8002}"
export WHISPER_MODEL="${WHISPER_MODEL:-small}"
export WHISPER_DEVICE="${WHISPER_DEVICE:-cuda}"
export TTS_MODEL="${TTS_MODEL:-coqui/vits}"
export TTS_DEVICE="${TTS_DEVICE:-cuda}"

echo "Discord Voice Bot - Starting services..."
echo "========================================="
echo "OPENCLAW_URL: $OPENCLAW_URL"
echo "WHISPER_URL: $WHISPER_URL"
echo "TTS_URL: $TTS_URL"
echo ""

# Check for Discord token
if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "ERROR: DISCORD_BOT_TOKEN not set!"
    echo "Set it with: export DISCORD_BOT_TOKEN=your_token_here"
    exit 1
fi

echo "Starting Whisper STT service..."
cd whisper-service
./venv/bin/python main.py &
WHISPER_PID=$!
echo "  Whisper PID: $WHISPER_PID"
cd ..

sleep 2

echo "Starting Coqui TTS service..."
cd tts-service
# Load packages from global pip for torch dependencies
python3 main.py &
TTS_PID=$!
echo "  TTS PID: $TTS_PID"
cd ..

sleep 2

echo "Starting Discord bot..."
cd discord-voice-bot
./venv/bin/python main.py &
BOT_PID=$!
echo "  Discord bot PID: $BOT_PID"
cd ..

echo ""
echo "All services started!"
echo "Press Ctrl+C to stop all services."
echo ""

# Trap Ctrl+C to kill all child processes
trap "kill $WHISPER_PID $TTS_PID $BOT_PID 2>/dev/null; exit 0" INT

wait
