"""Local audio evidence for video review. No upload, download, or paid API.

ASR recovers words; signal features locate candidates. Neither certifies taste.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model-file", type=Path, help="Existing official Whisper .pt weights; never downloaded")
    p.add_argument("--language", default="zh")
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    args = p.parse_args()
    source = args.source.resolve(strict=True)
    out = args.output.resolve()
    if out == source or source in out.parents:
        p.error("Output must be a separate directory")
    if args.model_file and not args.model_file.is_file():
        p.error("Model file is missing; this command does not download models")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        p.error("FFmpeg and FFprobe must be available")
    out.mkdir(parents=True, exist_ok=True)
    identity = digest(source)
    settings = {"sha256": identity, "language": args.language, "device": args.device,
                "model_sha256": digest(args.model_file) if args.model_file else None,
                "tool_version": 1}
    manifest = out / "manifest.json"
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous.get("settings") != settings:
            p.error("Evidence belongs to other settings/source; choose a new output directory")
        if previous.get("complete"):
            print(json.dumps({"cached": True, "output": str(out)}, ensure_ascii=False))
            return
    write_json(manifest, {"settings": settings, "source": str(source), "complete": False})
    probe = json.loads(subprocess.check_output(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)], text=True, encoding="utf-8"))
    streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    if not streams:
        p.error("No audio stream; do not infer silence or fabricate a transcript")
    if abs(float(streams[0].get("start_time", 0))) > 0.001:
        p.error("Non-zero audio start needs explicit clock mapping; this tool will not silently shift it")
    write_json(out / "audio_streams.json", streams)
    wav = out / "audio.wav"
    print("Extracting first audio stream to mono 16 kHz PCM", flush=True)
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(source), "-map", "0:a:0",
                    "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], check=True)
    # Keep optional library caches within the evidence directory.
    os.environ.setdefault("NUMBA_CACHE_DIR", str(out / "_cache" / "numba"))
    os.environ.setdefault("MPLCONFIGDIR", str(out / "_cache" / "matplotlib"))
    import numpy as np
    import soundfile as sf
    import librosa
    audio, sr = sf.read(wav, dtype="float32")
    print("Computing acoustic candidates; these do not identify sound sources", flush=True)
    hop = 256
    rms = librosa.feature.rms(y=audio, frame_length=1024, hop_length=hop)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
    onsets = librosa.onset.onset_detect(y=audio, sr=sr, hop_length=hop, units="time")
    tempo, beats = librosa.beat.beat_track(y=audio, sr=sr, hop_length=hop, units="time")
    features = {"source_sha256": identity, "sample_rate": sr,
                "audio_duration_s": len(audio) / sr,
                "peak_dbfs": float(20 * np.log10(max(float(np.max(np.abs(audio))), 1e-12))),
                "rms_dbfs": float(20 * np.log10(max(float(np.sqrt(np.mean(audio ** 2))), 1e-12))),
                "near_full_scale_fraction": float(np.mean(np.abs(audio) >= 0.999)),
                "estimated_tempo_bpm": float(np.asarray(tempo).reshape(-1)[0]),
                "onset_candidates_s": onsets.tolist(), "beat_candidates_s": beats.tolist(),
                "limitations": ["Speech and music share the signal; estimated beats may follow speech.",
                                "Peaks/onsets cannot identify footsteps or prove clipping.",
                                "No music style, aesthetic score, or subjective listening claim."]}
    write_json(out / "signal_features.json", features)
    transcript = None
    if args.model_file:
        import torch
        import whisper
        if args.device == "cuda" and not torch.cuda.is_available():
            p.error("CUDA unavailable; CPU fallback must be selected explicitly")
        print("Loading existing Whisper weights; no network request", flush=True)
        started = time.perf_counter()
        model = whisper.load_model(str(args.model_file.resolve()), device=args.device)
        transcript = model.transcribe(audio, language=args.language, task="transcribe",
                                     word_timestamps=True, temperature=0.0,
                                     condition_on_previous_text=False,
                                     fp16=args.device == "cuda", verbose=False)
        write_json(out / "transcript.json", transcript)
        (out / "transcript.txt").write_text("\n".join(
            f"[{s['start']:.2f}–{s['end']:.2f}] {s['text']}" for s in transcript["segments"]), encoding="utf-8")
        features["asr_wall_seconds"] = round(time.perf_counter() - started, 3)
        features["asr_status"] = "MACHINE_TRANSCRIPT_NOT_HUMAN_VERIFIED"
        write_json(out / "signal_features.json", features)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(times, 20 * np.log10(np.maximum(rms, 1e-7)), lw=1, label="RMS dBFS")
    for i, t in enumerate(onsets):
        ax.axvline(t, color="orange", alpha=0.22, lw=0.8,
                   label="Onset candidate" if i == 0 else None)
    if transcript:
        for s in transcript["segments"]:
            ax.axvspan(s["start"], s["end"], color="steelblue", alpha=0.08)
    ax.set(xlabel="Source time (seconds)", ylabel="RMS dBFS",
           title="Acoustic timing evidence — not a listening or taste verdict")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "audio_timeline.png", dpi=120)
    plt.close(fig)
    versions = {name: importlib.metadata.version(name) for name in ["librosa", "numpy", "soundfile"]}
    if transcript:
        versions.update({name: importlib.metadata.version(name) for name in ["openai-whisper", "torch"]})
    write_json(manifest, {"settings": settings, "source": str(source), "complete": True,
                          "versions": versions, "source_clock": "unaltered source start at 0 seconds",
                          "subjective_audio_review": "NOT_PERFORMED"})
    print(json.dumps({"cached": False, "output": str(out), "features": features}, ensure_ascii=False))


if __name__ == "__main__":
    main()
