#!/bin/bash
# Set DISCORD_BOT_TOKEN in your environment before running, or use a .env file
if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "ERROR: DISCORD_BOT_TOKEN not set"
    echo "Set it with: export DISCORD_BOT_TOKEN=your_token_here"
    exit 1
fi
cd /mnt/c/Users/Connor/discord-voice-bot/discord-voice-bot
exec python3 main.py
