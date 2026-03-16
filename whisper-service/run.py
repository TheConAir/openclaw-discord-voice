#!/usr/bin/env python3
import os
import sys
import subprocess

os.chdir("/mnt/c/Users/Connor/discord-voice-bot/whisper-service")
os.environ["WHISPER_MODEL"] = "small"
os.environ["WHISPER_DEVICE"] = "cuda"

# Use the venv python
python = "/mnt/c/Users/Connor/discord-voice-bot/whisper-service/venv/bin/python3"
subprocess.run([python, "main.py"])
