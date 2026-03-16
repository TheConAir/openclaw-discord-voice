#!/bin/bash
cd /mnt/c/Users/Connor/discord-voice-bot/discord-voice-bot
nohup ./venv/bin/python3 main.py > /tmp/bot.log 2>&1 &
echo "Bot started with PID $!"