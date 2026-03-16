#!/usr/bin/env python3
import os
import sys

# Use the venv python
python = "/mnt/c/Users/Connor/discord-voice-bot/discord-voice-bot/venv/bin/python3"

os.chdir("/mnt/c/Users/Connor/discord-voice-bot/discord-voice-bot")

# Set environment variables
os.environ["DISCORD_BOT_TOKEN"] = os.getenv("DISCORD_BOT_TOKEN", "")
os.environ["OPENCLAW_URL"] = os.getenv("OPENCLAW_URL", "http://localhost:18789")
os.environ["WHISPER_URL"] = os.getenv("WHISPER_URL", "http://localhost:8001")
os.environ["TTS_URL"] = os.getenv("TTS_URL", "http://localhost:8002")

if not os.environ["DISCORD_BOT_TOKEN"]:
    print("ERROR: DISCORD_BOT_TOKEN not set")
    print("Set it with: export DISCORD_BOT_TOKEN=your_token_here")
    sys.exit(1)

import subprocess
subprocess.run([python, "main.py"])
