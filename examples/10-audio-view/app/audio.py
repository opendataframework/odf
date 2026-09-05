"""Synthetic WAV tone generation for the audio-view example."""

import io
import struct
import wave
from math import pi, sin


def synth_tone_wav(frequency: float, duration: float, sample_rate: int) -> bytes:
    """Generate a short mono 16-bit PCM WAV clip of a pure sine tone, purely
    with the stdlib ``wave``/``struct`` modules — no ffmpeg dependency, no
    binary asset to commit.
    """
    frame_count = int(duration * sample_rate)
    samples = [
        int(32767 * 0.3 * sin(2 * pi * frequency * i / sample_rate)) for i in range(frame_count)
    ]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{frame_count}h", *samples))
    return buf.getvalue()
