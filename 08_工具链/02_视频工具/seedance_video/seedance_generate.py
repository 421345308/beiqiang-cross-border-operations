#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx


DEFAULT_MODEL = "doubao-seedance-2-0-260128"
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or query Volcengine Ark Seedance video tasks."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a video task")
    create_parser.add_argument("--prompt-file", required=True)
    create_parser.add_argument(
        "--model",
        default=os.environ.get("SEEDANCE_MODEL", DEFAULT_MODEL),
    )
    create_parser.add_argument("--image-url", action="append", default=[])
    create_parser.add_argument("--image-file", action="append", default=[])
    create_parser.add_argument("--first-frame-file")
    create_parser.add_argument("--last-frame-file")
    create_parser.add_argument("--video-url", action="append", default=[])
    create_parser.add_argument("--audio-url", action="append", default=[])
    create_parser.add_argument(
        "--ratio",
        choices=["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"],
        default="9:16",
    )
    create_parser.add_argument(
        "--resolution",
        choices=["480p", "720p", "1080p", "4k"],
        default="720p",
    )
    create_parser.add_argument("--duration", type=int, default=8)
    create_parser.add_argument(
        "--generate-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    create_parser.add_argument(
        "--watermark",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    create_parser.add_argument("--poll-interval", type=int, default=20)
    create_parser.add_argument("--timeout", type=int, default=1800)
    create_parser.add_argument("--output-dir", default="05_内容与视频/01_贝强商品视频/seedance")
    create_parser.add_argument(
        "--submit-only",
        action="store_true",
        help="Return after task creation without polling.",
    )

    get_parser = subparsers.add_parser("get", help="Query an existing task")
    get_parser.add_argument("task_id")
    get_parser.add_argument("--output-dir", default="05_内容与视频/01_贝强商品视频/seedance")
    get_parser.add_argument("--download", action="store_true")
    return parser


def get_api_key() -> str:
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key and sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Environment",
            ) as environment_key:
                api_key = winreg.QueryValueEx(environment_key, "ARK_API_KEY")[0]
        except (FileNotFoundError, OSError):
            api_key = None
    if not api_key:
        raise SystemExit(
            "ARK_API_KEY is not set. Set it in the current terminal; "
            "do not write the key into this script."
        )
    return api_key


def api_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = get_api_key()
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=120.0, trust_env=False) as client:
                response = client.request(
                    method,
                    f"{BASE_URL}{path}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=body,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as error:
            raise SystemExit(
                f"Ark API returned HTTP {error.response.status_code}: "
                f"{error.response.text}"
            ) from error
        except httpx.HTTPError as error:
            if attempt == 3:
                raise SystemExit(f"Could not reach Ark API: {error}") from error
            wait_seconds = attempt * 3
            print(
                f"Ark connection attempt {attempt} failed; "
                f"retrying in {wait_seconds}s: {error}",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)
    raise RuntimeError("Ark request retry loop ended unexpectedly.")


def to_plain_data(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_data(item) for item in value]
    if hasattr(value, "model_dump"):
        return to_plain_data(value.model_dump())
    if hasattr(value, "to_dict"):
        return to_plain_data(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            key: to_plain_data(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def get_field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def find_video_url(value: Any) -> str | None:
    if isinstance(value, dict):
        preferred_keys = ("video_url", "url")
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and (
                ".mp4" in candidate.lower() or "video" in key
            ):
                return candidate
        for item in value.values():
            candidate = find_video_url(item)
            if candidate:
                return candidate
    elif isinstance(value, list):
        for item in value:
            candidate = find_video_url(item)
            if candidate:
                return candidate
    return None


def save_result(result: Any, output_dir: Path, download: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plain_result = to_plain_data(result)
    task_id = get_field(result, "id") or plain_result.get("id", "unknown-task")
    metadata_path = output_dir / f"{task_id}.json"
    metadata_path.write_text(
        json.dumps(plain_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Metadata: {metadata_path.resolve()}")

    if not download:
        return
    video_url = find_video_url(plain_result)
    if not video_url:
        print("No downloadable video URL found in the response.", file=sys.stderr)
        return
    video_path = output_dir / f"{task_id}.mp4"
    for attempt in range(1, 6):
        try:
            video_path.unlink(missing_ok=True)
            with httpx.Client(timeout=180.0, trust_env=False) as client:
                with client.stream("GET", video_url) as response:
                    response.raise_for_status()
                    with video_path.open("wb") as video_file:
                        for chunk in response.iter_bytes():
                            video_file.write(chunk)
            break
        except httpx.HTTPError as error:
            video_path.unlink(missing_ok=True)
            if attempt == 5:
                raise SystemExit(
                    f"Could not download generated video: {error}"
                ) from error
            wait_seconds = attempt * 5
            print(
                f"Video download attempt {attempt} failed; "
                f"retrying in {wait_seconds}s: {error}",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)
    print(f"Video: {video_path.resolve()}")


def build_content(args: argparse.Namespace, prompt: str) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

    def local_image_url(file_name: str) -> str:
        image_path = Path(file_name)
        media_type = mimetypes.guess_type(image_path.name)[0]
        if not media_type or not media_type.startswith("image/"):
            raise SystemExit(f"Unsupported image type: {image_path}")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{encoded}"

    if args.first_frame_file:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": local_image_url(args.first_frame_file)},
                "role": "first_frame",
            }
        )
    if args.last_frame_file:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": local_image_url(args.last_frame_file)},
                "role": "last_frame",
            }
        )

    image_urls = list(args.image_url)
    for file_name in args.image_file:
        image_urls.append(local_image_url(file_name))
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": url},
            "role": "reference_image",
        }
        for url in image_urls
    )
    content.extend(
        {
            "type": "video_url",
            "video_url": {"url": url},
            "role": "reference_video",
        }
        for url in args.video_url
    )
    content.extend(
        {
            "type": "audio_url",
            "audio_url": {"url": url},
            "role": "reference_audio",
        }
        for url in args.audio_url
    )
    return content


def validate_create_args(args: argparse.Namespace) -> None:
    if not 4 <= args.duration <= 15:
        raise SystemExit("--duration must be between 4 and 15 seconds.")
    if args.resolution == "4k" and not args.model.startswith(
        "doubao-seedance-2-0-260128"
    ):
        raise SystemExit("4k output requires doubao-seedance-2-0-260128.")
    for url in args.image_url + args.video_url + args.audio_url:
        if not url.startswith(("https://", "http://", "asset://")):
            raise SystemExit(
                "Media inputs must be downloadable URLs or asset:// IDs. "
                f"Invalid input: {url}"
            )
    local_image_files = list(args.image_file)
    if args.first_frame_file:
        local_image_files.append(args.first_frame_file)
    if args.last_frame_file:
        local_image_files.append(args.last_frame_file)
    for file_name in local_image_files:
        image_path = Path(file_name)
        if not image_path.is_file():
            raise SystemExit(f"Image file does not exist: {image_path}")
        if image_path.stat().st_size >= 30 * 1024 * 1024:
            raise SystemExit(f"Image file must be smaller than 30 MB: {image_path}")


def create_task(args: argparse.Namespace) -> int:
    validate_create_args(args)
    prompt_path = Path(args.prompt_file)
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise SystemExit("Prompt file is empty.")

    result = api_request(
        "POST",
        "/contents/generations/tasks",
        {
            "model": args.model,
            "content": build_content(args, prompt),
            "generate_audio": args.generate_audio,
            "ratio": args.ratio,
            "resolution": args.resolution,
            "duration": args.duration,
            "watermark": args.watermark,
        },
    )
    output_dir = Path(args.output_dir)
    save_result(result, output_dir, download=False)
    task_id = get_field(result, "id")
    if not task_id:
        raise SystemExit("Task was created but no task ID was returned.")
    print(f"Task ID: {task_id}")
    if args.submit_only:
        return 0

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        task = api_request(
            "GET",
            f"/contents/generations/tasks/{task_id}",
        )
        status = get_field(task, "status")
        print(f"Status: {status}")
        if status == "succeeded":
            save_result(task, output_dir, download=True)
            return 0
        if status == "failed":
            save_result(task, output_dir, download=False)
            error = get_field(task, "error")
            print(f"Seedance task failed: {error}", file=sys.stderr)
            return 1
        time.sleep(args.poll_interval)

    print(
        f"Polling timed out. Resume with: "
        f"python {Path(__file__).name} get {task_id} --download",
        file=sys.stderr,
    )
    return 2


def get_task(args: argparse.Namespace) -> int:
    result = api_request(
        "GET",
        f"/contents/generations/tasks/{args.task_id}",
    )
    print(f"Status: {get_field(result, 'status')}")
    save_result(
        result,
        Path(args.output_dir),
        download=args.download and get_field(result, "status") == "succeeded",
    )
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "create":
        return create_task(args)
    return get_task(args)


if __name__ == "__main__":
    raise SystemExit(main())
