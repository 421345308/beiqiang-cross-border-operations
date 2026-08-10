import math
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 48000
DURATION = 28.0
BPM = 118
BEAT = 60 / BPM
samples = int(SAMPLE_RATE * DURATION)
time = np.arange(samples) / SAMPLE_RATE
left = np.zeros(samples, dtype=np.float64)
right = np.zeros(samples, dtype=np.float64)
rng = np.random.default_rng(20260801)


def add(signal: np.ndarray, start: float, gain: float, pan: float = 0.0) -> None:
    index = int(start * SAMPLE_RATE)
    if index >= samples:
        return
    end = min(samples, index + len(signal))
    signal = signal[: end - index] * gain
    left[index:end] += signal * math.sqrt((1 - pan) / 2)
    right[index:end] += signal * math.sqrt((1 + pan) / 2)


def kick() -> np.ndarray:
    length = int(0.24 * SAMPLE_RATE)
    t = np.arange(length) / SAMPLE_RATE
    phase = 2 * np.pi * (52 * t + 38 * (1 - np.exp(-18 * t)) / 18)
    return np.sin(phase) * np.exp(-18 * t)


def clap() -> np.ndarray:
    length = int(0.18 * SAMPLE_RATE)
    t = np.arange(length) / SAMPLE_RATE
    noise = rng.normal(0, 1, length)
    return noise * np.exp(-24 * t) * (0.55 + 0.45 * np.sin(2 * np.pi * 1800 * t))


def hat() -> np.ndarray:
    length = int(0.07 * SAMPLE_RATE)
    t = np.arange(length) / SAMPLE_RATE
    noise = rng.normal(0, 1, length)
    return np.diff(np.pad(noise, (1, 0))) * np.exp(-55 * t)


def bass(frequency: float, duration: float) -> np.ndarray:
    length = int(duration * SAMPLE_RATE)
    t = np.arange(length) / SAMPLE_RATE
    envelope = (1 - np.exp(-28 * t)) * np.exp(-2.5 * t)
    return (np.sin(2 * np.pi * frequency * t) + 0.22 * np.sin(4 * np.pi * frequency * t)) * envelope


def pad(frequencies: tuple[float, ...], duration: float) -> np.ndarray:
    length = int(duration * SAMPLE_RATE)
    t = np.arange(length) / SAMPLE_RATE
    envelope = np.minimum(1, t / 0.7) * np.minimum(1, (duration - t) / 0.8)
    signal = sum(np.sin(2 * np.pi * frequency * t) for frequency in frequencies) / len(frequencies)
    shimmer = 0.18 * np.sin(2 * np.pi * 0.22 * t)
    return signal * envelope * (0.85 + shimmer)


kick_sound = kick()
clap_sound = clap()
hat_sound = hat()
notes = [65.41, 77.78, 98.00, 58.27]
chords = [
    (261.63, 311.13, 392.00),
    (233.08, 293.66, 349.23),
    (196.00, 246.94, 311.13),
    (174.61, 220.00, 261.63),
]

beat_index = 0
while beat_index * BEAT < DURATION:
    start = beat_index * BEAT
    add(kick_sound, start, 0.78)
    if beat_index % 4 in {1, 3}:
        add(clap_sound, start, 0.16)
    add(hat_sound, start, 0.055, -0.35 if beat_index % 2 == 0 else 0.35)
    add(hat_sound, start + BEAT / 2, 0.04, 0.35 if beat_index % 2 == 0 else -0.35)
    add(bass(notes[(beat_index // 4) % len(notes)], BEAT * 0.9), start, 0.18)
    if beat_index % 8 == 0:
        add(pad(chords[(beat_index // 8) % len(chords)], BEAT * 8), start, 0.08, -0.1)
    beat_index += 1

fade = np.ones(samples)
fade[: int(0.35 * SAMPLE_RATE)] = np.linspace(0, 1, int(0.35 * SAMPLE_RATE))
fade[-int(1.0 * SAMPLE_RATE) :] = np.linspace(1, 0, int(1.0 * SAMPLE_RATE))
left *= fade
right *= fade
peak = max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-6)
stereo = np.stack([left, right], axis=1) / peak * 0.88
pcm = np.int16(np.clip(stereo, -1, 1) * 32767)
output = Path(__file__).with_name("music_original_118bpm.wav")
with wave.open(str(output), "wb") as handle:
    handle.setnchannels(2)
    handle.setsampwidth(2)
    handle.setframerate(SAMPLE_RATE)
    handle.writeframes(pcm.tobytes())
