"""Native, interactive whole-video review using an existing FREE TokenHub endpoint.

Credentials are read in memory from thcli's local configuration, never from arguments.
No resource activation, postpaid enablement, automatic retry, or Token Plan routing.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import requests

BASE = "https://tokenhub.tencentmaas.com/v1/chat/completions"


def review_budget(spec):
    """Keep review verbosity bounded without changing endpoint/cost safeguards."""
    effort = spec.get("reasoning_effort", "medium")
    maximum = spec.get("max_completion_tokens", 3500)
    if effort not in ("low", "medium", "high"):
        raise ValueError("Unsupported review reasoning effort")
    if type(maximum) is not int or not 500 <= maximum <= 9000:
        raise ValueError("Review completion budget must be an integer in 500..9000")
    return effort, maximum


def review_completed(answer, finish):
    return bool(answer.strip()) and finish == "stop"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def scrub(value, key):
    # Response/error strings must never leak a reflected credential or binary input.
    s = json.dumps(value, ensure_ascii=False).replace(key, "[REDACTED]")
    s = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[REDACTED]", s)
    s = re.sub(r"data:(?:video|audio|image)/[^\s\"]+", "[MEDIA REDACTED]", s)
    return json.loads(s)


def free_preflight(model, direct):
    env = os.environ.copy()
    if direct:
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env.pop(name, None)
    cli = Path(os.environ["APPDATA"]) / "npm/node_modules/tencent-tokenhub-cli/dist/main.cjs"
    run = subprocess.run(["node", str(cli), "endpoint", "list", "--model-id", model, "--json"],
                         capture_output=True, text=True, encoding="utf-8", env=env, timeout=45)
    if run.returncode:
        raise RuntimeError("Read-only endpoint check failed; inference not sent.")
    data = json.loads(run.stdout)
    matches = [e for e in data.get("ModelEndpointSet", []) if e.get("EndpointId") == model]
    if len(matches) != 1:
        raise RuntimeError("No unique default endpoint; inference not sent.")
    e = matches[0]
    quota = json.loads(e.get("ChargeDetail", "{}" )).get("FreeQuota", {})
    remaining = quota.get("TotalQuota", 0) - quota.get("UsedQuota", 0)
    if e.get("Status") != "ACTIVE" or e.get("ChargeType") != "FREE" or e.get("PaymentEnabled") is not False:
        raise RuntimeError("Endpoint is not active/free with postpaid disabled; inference not sent.")
    if remaining < 200000:
        raise RuntimeError("Free quota below 200,000-token reserve; inference not sent.")
    return {"model": model, "status": e["Status"], "charge_type": e["ChargeType"],
            "payment_enabled": False, "free_remaining_before": remaining,
            "free_total": quota.get("TotalQuota"), "request_id": data.get("RequestId")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--direct", action="store_true", help="Ignore the broken environment proxy; retain TLS verification")
    a = p.parse_args()
    spec = json.loads(a.manifest.read_text(encoding="utf-8"))
    effort, maximum = review_budget(spec)
    model = spec.get("model", "kimi-k3")
    preflight = free_preflight(model, a.direct)
    keyfile = Path.home() / ".thcli/default.tokenhub.json"
    key = json.loads(keyfile.read_text(encoding="utf-8"))["sites"]["cn"]["gz"]["th"]["default"]
    blocks, sources = [], []
    for item in spec["videos"]:
        path = (a.manifest.parent / item["path"]).resolve()
        raw = path.read_bytes()
        if path.suffix.lower() != ".mp4":
            raise ValueError("Verified MP4 source required")
        sources.append({"label": item["label"], "path": item["path"], "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(), "duration": item["duration"]})
        blocks.append({"type": "text", "text": f'{item["label"]}: verified duration {item["duration"]} seconds. Local timestamps start at 0.'})
        blocks.append({"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + base64.b64encode(raw).decode("ascii")}})
    for item in spec.get("images", []):
        path = (a.manifest.parent / item["path"]).resolve()
        raw = path.read_bytes()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(path.suffix.lower())
        if not mime:
            raise ValueError("PNG/JPEG review image required")
        sources.append({"label": item["label"], "path": item["path"], "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(), "type": "supplementary_image"})
        blocks.append({"type": "text", "text": item["label"]})
        blocks.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")}})
    blocks.append({"type": "text", "text": spec["prompt"]})
    body = {"model": model, "messages": [{"role": "user", "content": blocks}],
            "reasoning_effort": effort, "max_completion_tokens": maximum,
            "stream": True, "stream_options": {"include_usage": True}}
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if len(payload) > 95 * 1024 * 1024:
        raise ValueError("Body exceeds conservative 95MiB limit; inference not sent")
    save(a.output_dir / "request.json", {"endpoint": BASE, "model": model, "input_type": "native video_url base64",
         "sources": sources, "prompt": spec["prompt"], "request_body_bytes": len(payload),
         "reasoning_effort": effort, "max_completion_tokens": maximum, "stream": True,
         "preflight": preflight, "audio_review": "not assumed", "automatic_retries": 0})
    session = requests.Session()
    if a.direct:
        session.trust_env = False
    started = time.time()
    print(f"Submitting {len(spec['videos'])} whole videos; free endpoint verified; no automatic retry.", flush=True)
    # TLS remains verified. Redirects are disabled so authentication stays at the exact official host.
    r = session.post(BASE, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                     data=payload, timeout=(30, 240), stream=True, allow_redirects=False)
    print("HTTP", r.status_code, flush=True)
    if r.status_code != 200:
        error = scrub(r.text[:10000], key)
        save(a.output_dir / "response.json", {"http_status": r.status_code, "error": error})
        print(error)
        return 1
    content, reasoning, usage, finish, identity = [], [], None, None, {}
    for line in r.iter_lines():
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            break
        chunk = json.loads(data)
        for k in ("id", "model", "created"):
            if k in chunk:
                identity[k] = chunk[k]
        if chunk.get("usage"):
            usage = chunk["usage"]
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {})
            if delta.get("content"):
                content.append(delta["content"])
            if delta.get("reasoning_content"):
                reasoning.append(delta["reasoning_content"])
            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
    answer = "".join(content)
    response = scrub({**identity, "finish_reason": finish, "usage": usage, "content": answer,
                      "elapsed_seconds": round(time.time() - started, 2),
                      "reasoning_chars": sum(map(len, reasoning))}, key)
    save(a.output_dir / "response.json", response)
    # Only final answer is kept; no private reasoning or headers are persisted.
    if not review_completed(answer, finish):
        print("Incomplete answer; not a completed review. Response preserved. No retry.")
        return 2
    a.output_dir.joinpath("model-review.md").write_text(response["content"], encoding="utf-8")
    print(json.dumps({"id": identity.get("id"), "finish_reason": finish, "usage": usage,
                      "elapsed_seconds": response["elapsed_seconds"]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (requests.RequestException, KeyError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        # No traceback/request dump because it may contain authentication or binary content.
        print("Review stopped:", type(exc).__name__, flush=True)
        sys.exit(3)
