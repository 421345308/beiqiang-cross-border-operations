"""Submit one Ref2VA job using the official ComfyUI MiniMax H3 node graph."""
import argparse
import json
import time
import urllib.request
from urllib.error import HTTPError
from pathlib import Path


def request_json(url, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--picture-0", required=True)
    parser.add_argument("--picture-1")
    parser.add_argument("--picture-2")
    parser.add_argument("--video-0", required=True)
    parser.add_argument("--use-video-audio", action="store_true")
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--frames", type=int, default=124)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--lora")
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--workflow-out")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    reference_inputs = {
        "clip": ["4", 0], "vae": ["6", 0], "audio_vae": ["7", 0],
        "ref_images.ref_image_0": ["1", 0],
        "ref_videos.ref_video_0": ["19", 0], "prompt": prompt,
        "width": args.width, "height": args.height, "length": args.frames, "ref_image_size": "match",
    }
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": args.picture_0}},
        "3": {"class_type": "LoadVideo", "inputs": {"file": args.video_0}},
        "4": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
        "5": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "7": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "8": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": reference_inputs},
        "9": {"class_type": "BasicGuider", "inputs": {"model": ["5", 0], "conditioning": ["8", 0]}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": args.seed}},
        "11": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "12": {"class_type": "BasicScheduler", "inputs": {
            "model": ["5", 0], "scheduler": "simple", "steps": args.steps, "denoise": 1.0}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["10", 0], "guider": ["9", 0], "sampler": ["11", 0],
            "sigmas": ["12", 0], "latent_image": ["8", 1]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["6", 0]}},
        "15": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["13", 0], "vae": ["7", 0]}},
        "16": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "audio": ["15", 0], "fps": 24}},
        "17": {"class_type": "SaveVideo", "inputs": {
            "video": ["16", 0], "filename_prefix": args.output_prefix, "format": "auto", "codec": "auto"}},
        "19": {"class_type": "GetVideoComponents", "inputs": {"video": ["3", 0]}},
    }
    if args.picture_1:
        workflow["2"] = {"class_type": "LoadImage", "inputs": {"image": args.picture_1}}
        reference_inputs["ref_images.ref_image_1"] = ["2", 0]
    if args.picture_2:
        workflow["18"] = {"class_type": "LoadImage", "inputs": {"image": args.picture_2}}
        reference_inputs["ref_images.ref_image_2"] = ["18", 0]
    if args.use_video_audio:
        reference_inputs["ref_video_audios.ref_video_audio_0"] = ["19", 1]
    if args.lora:
        workflow["20"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["5", 0], "lora_name": args.lora, "strength_model": args.lora_strength}}
        workflow["9"]["inputs"]["model"] = ["20", 0]
        workflow["12"]["inputs"]["model"] = ["20", 0]
    if args.workflow_out:
        output_path = Path(args.workflow_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.prepare_only:
        print(json.dumps({"prepared": True, "workflow_out": args.workflow_out}, ensure_ascii=False), flush=True)
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
