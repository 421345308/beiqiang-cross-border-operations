"""Submit one I2VA or FL2VA job using the official ComfyUI MiniMax H3 graph."""
import argparse
import json
import time
import urllib.request
from urllib.error import HTTPError
from pathlib import Path


def request_json(url, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--first-frame", required=True)
    parser.add_argument("--last-frame")
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1344)
    parser.add_argument("--frames", type=int, default=107)
    parser.add_argument("--workflow-out")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": args.first_frame}},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
            "type": "minimax", "device": "default"}},
        "3": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
            "weight_dtype": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {
            "vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "5": {"class_type": "VAELoader", "inputs": {
            "vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["4", 0],
            "first_frame": ["1", 0], "prompt": prompt,
            "width": args.width, "height": args.height, "length": args.frames}},
        "7": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["3", 0],
            "lora_name": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
            "strength_model": 1.0}},
        "8": {"class_type": "BasicGuider", "inputs": {
            "model": ["7", 0], "conditioning": ["6", 0]}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": args.seed}},
        "10": {"class_type": "KSamplerSelect", "inputs": {
            "sampler_name": "res_multistep"}},
        "11": {"class_type": "BasicScheduler", "inputs": {
            "model": ["7", 0], "scheduler": "simple", "steps": 8, "denoise": 1.0}},
        "12": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["9", 0], "guider": ["8", 0], "sampler": ["10", 0],
            "sigmas": ["11", 0], "latent_image": ["6", 1]}},
        "13": {"class_type": "VAEDecode", "inputs": {
            "samples": ["12", 0], "vae": ["4", 0]}},
        "14": {"class_type": "VAEDecodeAudio", "inputs": {
            "samples": ["12", 0], "vae": ["5", 0]}},
        "15": {"class_type": "CreateVideo", "inputs": {
            "images": ["13", 0], "audio": ["14", 0], "fps": 24}},
        "16": {"class_type": "SaveVideo", "inputs": {
            "video": ["15", 0], "filename_prefix": args.output_prefix,
            "format": "auto", "codec": "auto"}},
    }

    if args.last_frame:
        workflow["17"] = {
            "class_type": "LoadImage",
            "inputs": {"image": args.last_frame},
        }
        workflow["6"]["inputs"]["last_frame"] = ["17", 0]

    if args.workflow_out:
        workflow_path = Path(args.workflow_out)
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if args.prepare_only:
        print(json.dumps({"prepared": True, "workflow_out": args.workflow_out}, ensure_ascii=False))
        return

    result = request_json(args.server + "/prompt", {"prompt": workflow})
    prompt_id = result["prompt_id"]
    print(json.dumps({"prompt_id": prompt_id}, ensure_ascii=False), flush=True)
    while True:
        history = request_json(args.server + "/history/" + prompt_id)
        item = history.get(prompt_id)
        if item:
            status = item.get("status", {})
            if status.get("completed"):
                print(json.dumps(item, ensure_ascii=False), flush=True)
                return
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(item, ensure_ascii=False))
        time.sleep(10)


if __name__ == "__main__":
    main()
