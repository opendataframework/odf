"""Synthetic WAV melody generation for the streaming-audio-view example."""

import io
import struct
import wave
from collections.abc import Sequence
from math import sin, tau


def synth_melody_wav(
    notes: Sequence[tuple[float | None, float]], sample_rate: int, phase: float = 0.0
) -> tuple[bytes, float]:
    """Generate a mono 16-bit PCM WAV clip playing ``notes`` back-to-back,
    purely with the stdlib ``wave``/``struct`` modules — no ffmpeg
    dependency, no binary asset to commit.

    Each entry in ``notes`` is ``(frequency_hz, duration_seconds)`` — or
    ``(None, duration_seconds)`` for a silent rest. ``phase`` carries the
    running phase across notes and across calls instead of restarting at
    0 — a discontinuous *phase* is what causes an audible click; a
    discontinuous *frequency* (moving to the next note) alone just sounds
    like the melody moving, not a pop. A rest resets ``phase`` to 0 so the
    note that follows it starts cleanly at a zero-crossing, matching the
    rest's own silence.

    Returns:
        The WAV bytes, and the phase to pass back in on the next call to
        stay sample-continuous with this one.
    """
    samples = []
    for frequency, duration in notes:
        frame_count = int(duration * sample_rate)
        if frequency is None:
            samples.extend([0] * frame_count)
            phase = 0.0
            continue
        step = tau * frequency / sample_rate
        for _ in range(frame_count):
            phase += step
            samples.append(int(32767 * 0.3 * sin(phase)))
    phase %= tau
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buf.getvalue(), phase
