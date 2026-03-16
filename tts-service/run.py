#!/usr/bin/env python3
import os
os.chdir("/mnt/c/Users/Connor/discord-voice-bot/tts-service")
os.environ["KOKORO_VOICE"] = "af_heart"
os.environ["TTS_DEVICE"] = "cuda"
import subprocess
subprocess.run(["python3", "main.py"])
