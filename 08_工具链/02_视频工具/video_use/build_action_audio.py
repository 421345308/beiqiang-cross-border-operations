"""Render editable procedural Foley events. No API, model, voice, or music input."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt
import soundfile as sf


def render(spec):
    sr = 48000
    mix = np.zeros((round(spec['duration'] * sr), 2), dtype=np.float64)
    rng = np.random.default_rng(spec.get('seed', 21))
    for e in spec['events']:
        duration = e.get('duration', 0.18)
        t = np.arange(round(duration * sr)) / sr
        if e['type'] == 'contact':
            noise = sosfilt(butter(3, [90, 1900], btype='bandpass', fs=sr, output='sos'), rng.normal(size=len(t)))
            envelope = (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.035)
            tone = np.sin(2 * np.pi * (95 * t - 60 * t * t)) * np.exp(-t / 0.025)
            sound = (noise * 0.65 + tone * 0.35) * envelope
        elif e['type'] == 'fabric':
            noise = sosfilt(butter(2, [700, 5800], btype='bandpass', fs=sr, output='sos'), rng.normal(size=len(t)))
            sound = noise * np.sin(np.pi * np.minimum(t / duration, 1)) ** 2
        else:
            raise ValueError('Unsupported Foley type')
        sound *= 10 ** (e['peak_dbfs'] / 20) / max(float(np.max(np.abs(sound))), 1e-9)
        pan = e.get('pan', 0)
        stereo = sound[:, None] * np.array([np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)])
        start = round(e['time'] * sr)
        if start < 0 or start + len(sound) > len(mix):
            raise ValueError('Event outside timeline')
        mix[start:start + len(sound)] += stereo
    if np.max(np.abs(mix)) >= 0.95:
        raise ValueError('Clipping risk')
    return mix, sr


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('spec', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Do not overwrite prior evidence')
    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    audio, rate = render(spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, audio, rate, subtype='PCM_24')
    print(json.dumps({'output': str(args.output), 'seconds': len(audio) / rate,
                      'peak_dbfs': float(20 * np.log10(max(np.max(np.abs(audio)), 1e-12))),
                      'events': len(spec['events']), 'kind': 'procedural_foley_not_original_sound'}))
