#!/bin/bash
# Set DISCORD_BOT_TOKEN and OPENCLAW_URL in your environment before running
if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "ERROR: DISCORD_BOT_TOKEN not set"
    echo "Set it with: export DISCORD_BOT_TOKEN=your_token_here"
    exit 1
fi
cd /mnt/c/Users/Connor/discord-voice-bot/discord-voice-bot
python3 main.py
