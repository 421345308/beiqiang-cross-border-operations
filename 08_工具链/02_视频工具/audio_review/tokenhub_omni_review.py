"""Whole-file MiMo AV review via TokenHub; existing FREE endpoints only.

No activation, paid generation, retry, or credential in manifests/logs.
Native audio ingestion is recorded separately from semantic verification.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tokenhub_video_review import BASE, free_preflight, save, scrub


def media_block(path, modality):
    path = path.resolve(strict=True)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = [x["codec_type"] for x in probe["streams"]]
    if "audio" not in streams or (modality == "video" and "video" not in streams):
        raise ValueError("Required native media stream absent")
    if modality == "video" and path.suffix.lower() != ".mp4":
        raise ValueError("MP4 required for this verified input contract")
    mime = {".mp4": "video/mp4", ".wav": "audio/wav", ".mp3": "audio/mpeg"}[path.suffix.lower()]
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    if len(encoded) > 49 * 1024 * 1024:
        raise ValueError("Native input exceeds conservative 49MiB base64 ceiling")
    url = f"data:{mime};base64," + encoded
    block = ({"type": "video_url", "video_url": {"url": url}, "fps": 2,
              "media_resolution": "default"} if modality == "video" else
             {"type": "input_audio", "input_audio": {"data": url}})
    return block, {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                   "bytes": len(raw), "duration": float(probe["format"]["duration"]), "streams": streams}


def audio_ingestion(usage):
    count = (usage or {}).get("prompt_tokens_details", {}).get("audio_tokens")
    return {"audio_tokens": count, "ingestion_evidence": "reported" if isinstance(count, (int, float)) and count > 0 else "unconfirmed",
            "semantic_review_verified": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("media", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--prompt-file", type=Path, required=True)
    p.add_argument("--modality", choices=["video", "audio"], default="video")
    p.add_argument("--authorized-upload", action="store_true", required=True)
    p.add_argument("--direct", action="store_true")
    a = p.parse_args()
    if (a.output / "request.json").exists():
        raise ValueError("Attempt already exists; no implicit resubmission")
    block, source = media_block(a.media, a.modality)
    prompt = a.prompt_file.read_text(encoding="utf-8")
    model = "mimo-v2.6-flash"
    preflight = free_preflight(model, a.direct)
    key = json.loads((Path.home() / ".thcli/default.tokenhub.json").read_text(encoding="utf-8"))["sites"]["cn"]["gz"]["th"]["default"]
    body = {"model": model, "messages": [{"role": "user", "content": [block, {"type": "text", "text": prompt}]}],
            "max_completion_tokens": 4500, "stream": True, "stream_options": {"include_usage": True}}
    record = {"endpoint": BASE, "model": model, "modality": a.modality, "source": source,
              "prompt": prompt, "preflight": preflight, "native_video_fps": 2 if a.modality == "video" else None,
              "automatic_retries": 0, "status": "submitted", "review_verified": False}
    save(a.output / "request.json", record)
    session = requests.Session()
    session.trust_env = not a.direct
    start = time.time()
    try:
        r = session.post(BASE, json=body, headers={"Authorization": "Bearer " + key},
                         timeout=(30, 240), stream=True, allow_redirects=False)
        if r.status_code != 200:
            save(a.output / "response.json", {"status": r.status_code, "error": scrub(r.text[:10000], key)})
            record["status"] = "failed"
            return 1
        answer, usage, finish, identity = [], None, None, {}
        for line in r.iter_lines():
            if not line.startswith(b"data:"):
                continue
            value = line[5:].strip()
            if value == b"[DONE]":
                break
            chunk = json.loads(value)
            if chunk.get("error"):
                raise ValueError("Upstream stream returned error")
            for k in ("id", "model", "created"):
                if k in chunk:
                    identity[k] = chunk[k]
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices", []):
                answer.append(choice.get("delta", {}).get("content") or "")
                finish = choice.get("finish_reason") or finish
        content = "".join(answer)
        response = scrub({**identity, "content": content, "usage": usage, "finish_reason": finish,
                          "audio": audio_ingestion(usage)}, key)
        save(a.output / "response.json", response)
        record["status"] = "returned" if finish == "stop" and content.strip() else "incomplete"
        if record["status"] == "returned":
            (a.output / "model-review.md").write_text(response["content"], encoding="utf-8")
        print(json.dumps({"status": record["status"], "usage": usage, "audio": response["audio"]}, ensure_ascii=False), flush=True)
        return 0 if record["status"] == "returned" else 2
    except (requests.RequestException, ValueError) as e:
        record.update(status="failed", error=type(e).__name__)
        return 3
    finally:
        record["elapsed_seconds"] = round(time.time() - start, 2)
        save(a.output / "request.json", record)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        print("Review stopped:", type(e).__name__)
        sys.exit(4)
