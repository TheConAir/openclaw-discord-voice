# -*- coding: utf-8 -*-
"""
Discord Voice Bot - discord.py 2.7+ with DAVE E2EE support
Listens in voice, transcribes via Whisper, responds via OpenClaw + TTS
"""

import discord
from discord.ext import commands
import os
import io
import json
import re
import ssl
import struct
import logging
import asyncio
import aiohttp
import tempfile
import time
import uuid
import wave
import nacl.secret
import davey

if not discord.opus.is_loaded():
    discord.opus.load_opus('libopus.so.0')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

fh = logging.FileHandler('/tmp/discord_bot.log', mode='w')
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
logging.getLogger().addHandler(fh)

# Config
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENCLAW_URL = os.getenv("OPENCLAW_URL", "https://192.168.0.124:18789")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_TOKEN")
WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:8001")
TTS_URL = os.getenv("TTS_URL", "http://localhost:8002")
AUTO_JOIN_USER_ID = 158027264015990786

# Session ID for OpenClaw - resets each time bot joins a voice channel
voice_session_id = str(uuid.uuid4())

# Audio params
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2  # 16-bit
SILENCE_TIMEOUT = 1.5  # seconds of silence before processing
MAX_RECORDING_SECS = 30

# Intents
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# State
voice_clients = {}
processing_lock = asyncio.Lock()

# Reusable SSL context for OpenClaw (self-signed cert)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def pcm_to_wav(pcm_data: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)
    return buf.getvalue()


async def transcribe_audio(audio_data: bytes) -> str:
    try:
        wav_data = pcm_to_wav(audio_data)
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('audio', wav_data, filename='audio.wav', content_type='audio/wav')
            async with session.post(
                f"{WHISPER_URL}/transcribe", data=form,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("text", "")
    except Exception as e:
        logger.error(f"Transcribe error: {e}")
    return ""


def strip_markdown(text: str) -> str:
    """Remove markdown formatting for TTS (bold, italic, headers, etc.)"""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.+?)\*', r'\1', text)        # *italic*
    text = re.sub(r'__(.+?)__', r'\1', text)         # __underline__
    text = re.sub(r'_(.+?)_', r'\1', text)           # _italic_
    text = re.sub(r'~~(.+?)~~', r'\1', text)         # ~~strikethrough~~
    text = re.sub(r'`(.+?)`', r'\1', text)           # `code`
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # headers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)  # list bullets
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)  # numbered lists
    return text.strip()


# Sentence boundary pattern for chunking streamed text
_SENTENCE_END = re.compile(r'[.!?:]\s+|[.!?:]$|\n')


async def stream_ai_response(text: str):
    """Stream AI response, yielding sentence chunks as they arrive."""
    buffer = ""
    try:
        connector = aiohttp.TCPConnector(ssl=_ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                f"{OPENCLAW_URL}/v1/chat/completions",
                json={
                    "model": "openclaw:speech",
                    "messages": [{"role": "user", "content": text}],
                    "user": f"voice-{voice_session_id}",
                    "stream": True,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENCLAW_TOKEN}",
                    "x-openclaw-agent-id": "main",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"OpenClaw returned {resp.status}: {body[:200]}")
                    yield "Sorry, I had an error."
                    return

                async for line in resp.content:
                    line = line.decode('utf-8', errors='ignore').strip()
                    if not line.startswith('data: '):
                        continue
                    payload = line[6:]
                    if payload == '[DONE]':
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        token = delta.get('content', '')
                        if not token:
                            continue
                        buffer += token

                        # Check for sentence boundary
                        match = _SENTENCE_END.search(buffer)
                        if match:
                            # Find the last sentence boundary in buffer
                            last_match = None
                            for m in _SENTENCE_END.finditer(buffer):
                                last_match = m
                            if last_match:
                                sentence = buffer[:last_match.end()].strip()
                                buffer = buffer[last_match.end():]
                                if sentence:
                                    yield strip_markdown(sentence)
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue

        # Yield any remaining text
        if buffer.strip():
            yield strip_markdown(buffer.strip())

    except Exception as e:
        logger.error(f"AI stream error: {e}")
        if buffer.strip():
            yield strip_markdown(buffer.strip())
        else:
            yield "Sorry, I had an error."


async def get_ai_response(text: str) -> str:
    """Non-streaming fallback for AI response."""
    chunks = []
    async for chunk in stream_ai_response(text):
        chunks.append(chunk)
    return " ".join(chunks)


async def synthesize_speech(text: str) -> bytes:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TTS_URL}/synthesize", json={"text": text},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        logger.error(f"TTS error: {e}")
    return b""


async def play_audio(vc: discord.VoiceClient, audio_data: bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_data)
            temp_file = f.name

        source = discord.FFmpegPCMAudio(temp_file)
        transform = discord.PCMVolumeTransformer(source)
        transform.volume = 0.5
        vc.play(transform)

        while vc.is_playing():
            await asyncio.sleep(0.1)

        os.unlink(temp_file)
    except Exception as e:
        logger.error(f"Play error: {e}")


class VoiceReceiver:
    """Receives and decrypts voice audio from Discord using low-level socket listener."""

    def __init__(self, vc: discord.VoiceClient):
        self.vc = vc
        self._connection = vc._connection
        self._decoder = discord.opus.Decoder()
        self._aead_box = nacl.secret.Aead(bytes(self._connection.secret_key))
        self._ssrc_to_user: dict[int, int] = {}
        self._audio_buffer = bytearray()
        self._last_audio_time = 0.0
        self._listening = False
        self._packet_count = 0
        self._decode_errors = 0

    def start(self):
        self._listening = True
        self._last_audio_time = time.monotonic()
        self._connection.add_socket_listener(self._on_packet)
        logger.info("Voice receiver started")

    def stop(self):
        self._listening = False
        try:
            self._connection.remove_socket_listener(self._on_packet)
        except Exception:
            pass
        logger.info(f"Voice receiver stopped ({self._packet_count} packets processed)")

    def _on_packet(self, data: bytes):
        if not self._listening or len(data) < 12:
            return

        # RTP version must be 2
        if (data[0] & 0xC0) >> 6 != 2:
            return

        # Skip RTCP (payload types 72-76 after masking)
        pt = data[1] & 0x7F
        if 72 <= pt <= 76:
            return

        self._packet_count += 1

        try:
            pcm = self._decrypt_and_decode(data)
            if pcm:
                self._audio_buffer.extend(pcm)
                self._last_audio_time = time.monotonic()

                max_bytes = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * MAX_RECORDING_SECS
                if len(self._audio_buffer) > max_bytes:
                    self._audio_buffer = self._audio_buffer[-max_bytes:]
        except Exception as e:
            self._decode_errors += 1
            if self._decode_errors <= 5:
                logger.debug(f"Packet error #{self._decode_errors}: {e}")

    def _decrypt_and_decode(self, data: bytes) -> bytes:
        has_extension = bool(data[0] & 0x10)
        cc = data[0] & 0x0F
        ssrc = struct.unpack_from('>I', data, 8)[0]

        # Skip our own audio
        if ssrc == self._connection.ssrc:
            return b""

        # aead_xchacha20_poly1305_rtpsize decryption:
        #   AAD = RTP header + CSRCs + extension PREAMBLE (4 bytes)
        #   Ciphertext = extension VALUES + opus payload
        #   Last 4 bytes of packet = nonce suffix
        header_len = 12 + cc * 4
        after_header = data[header_len:]

        nonce = bytearray(24)
        nonce[:4] = after_header[-4:]

        if has_extension and len(after_header) > 8:
            aad = data[:header_len] + after_header[:4]
            ciphertext = bytes(after_header[4:-4])
        else:
            aad = data[:header_len]
            ciphertext = bytes(after_header[:-4])

        if len(ciphertext) < 16:
            return b""

        # Decrypt transport layer
        secret_key = self._connection.secret_key
        if secret_key is None or secret_key is discord.utils.MISSING:
            return b""

        decrypted = self._aead_box.decrypt(ciphertext, bytes(aad), bytes(nonce))

        # Strip encrypted extension values to get opus data
        opus_data = decrypted
        if has_extension and len(aad) > header_len:
            ext_length = struct.unpack_from('>H', aad, header_len + 2)[0]
            ext_values_size = ext_length * 4
            if ext_values_size <= len(decrypted):
                opus_data = decrypted[ext_values_size:]
            else:
                return b""

        if not opus_data:
            return b""

        # DAVE E2EE decryption
        if self._connection.dave_session and self._connection.can_encrypt:
            user_id = self._ssrc_to_user.get(ssrc)
            if user_id is None:
                return b""
            result = self._connection.dave_session.decrypt(
                user_id, davey.MediaType.audio, opus_data
            )
            if result is None:
                return b""
            opus_data = result

        # Decode Opus to PCM
        return self._decoder.decode(opus_data)

    def get_and_clear_buffer(self) -> bytes:
        data = bytes(self._audio_buffer)
        self._audio_buffer.clear()
        return data

    def has_audio(self) -> bool:
        min_bytes = int(SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * 0.5)
        return len(self._audio_buffer) >= min_bytes

    def silence_duration(self) -> float:
        return time.monotonic() - self._last_audio_time


async def voice_listen_loop(guild_id: int, vc: discord.VoiceClient, text_channel):
    """Listen for speech, detect silence, then process."""
    receiver = VoiceReceiver(vc)

    # Hook voice WebSocket to capture SPEAKING events for SSRC → user_id mapping
    ws = vc._connection.ws
    original_hook = ws._hook

    async def voice_ws_hook(ws_obj, msg):
        if msg.get('op') == 5:  # SPEAKING
            d = msg['d']
            ssrc = d.get('ssrc')
            user_id = int(d.get('user_id', 0))
            if ssrc and user_id:
                receiver._ssrc_to_user[ssrc] = user_id
                logger.info(f"SSRC {ssrc} -> user {user_id}")
        if original_hook:
            await original_hook(ws_obj, msg)

    ws._hook = voice_ws_hook
    vc._connection.hook = voice_ws_hook
    receiver.start()

    logger.info(f"Voice listen loop started for guild {guild_id}")

    try:
        while vc.is_connected() and guild_id in voice_clients:
            await asyncio.sleep(0.2)

            if receiver.has_audio() and receiver.silence_duration() > SILENCE_TIMEOUT:
                audio_data = receiver.get_and_clear_buffer()
                duration = len(audio_data) / (SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH)
                if duration < 0.5:
                    continue

                async with processing_lock:
                    text = await transcribe_audio(audio_data)
                    if not text or len(text.strip()) < 3:
                        continue

                    logger.info(f"Heard: {text}")
                    t0 = time.time()
                    first_chunk = True
                    full_response = []

                    async for sentence in stream_ai_response(text):
                        if not sentence or not vc.is_connected():
                            break

                        if first_chunk:
                            t_first = time.time()
                            logger.info(f"First sentence ({t_first-t0:.2f}s): {sentence}")
                            first_chunk = False

                        full_response.append(sentence)
                        audio = await synthesize_speech(sentence)
                        if audio and vc.is_connected():
                            await play_audio(vc, audio)

                    t_end = time.time()
                    logger.info(f"Total ({t_end-t0:.2f}s), response: {' '.join(full_response)}")

    except Exception as e:
        logger.error(f"Voice listen loop error: {e}", exc_info=True)
    finally:
        receiver.stop()
        logger.info(f"Voice listen loop ended for guild {guild_id}")


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")


@bot.event
async def on_voice_state_update(member, before, after):
    guild = member.guild

    if member.id == AUTO_JOIN_USER_ID:
        if after.channel and before.channel != after.channel:
            if guild.id not in voice_clients:
                try:
                    global voice_session_id
                    voice_session_id = str(uuid.uuid4())
                    logger.info(f"New voice session: {voice_session_id}")
                    vc = await after.channel.connect()
                    voice_clients[guild.id] = vc
                    logger.info(f"Auto-joined {after.channel.name}")

                    text_channel = guild.system_channel or next(
                        (ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages),
                        None
                    )
                    if text_channel:
                        await text_channel.send(f"Joined {after.channel.name}! Listening...")

                    bot.loop.create_task(voice_listen_loop(guild.id, vc, text_channel))

                except Exception as e:
                    logger.error(f"Auto-join failed: {e}", exc_info=True)

        elif before.channel and not after.channel:
            if guild.id in voice_clients:
                try:
                    vc = voice_clients[guild.id]
                    await vc.disconnect()
                except Exception:
                    pass
                del voice_clients[guild.id]
                logger.info("Auto-left")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
