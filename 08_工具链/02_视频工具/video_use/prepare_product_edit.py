from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def load_metadata(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a Beiqiang video-use project from Seedance outputs."
    )
    parser.add_argument("--sku", required=True)
    parser.add_argument(
        "--seedance-dir",
        type=Path,
        default=Path("05_内容与视频/01_贝强商品视频/seedance"),
    )
    args = parser.parse_args()

    seedance_dir = args.seedance_dir.resolve()
    if not seedance_dir.is_dir():
        raise SystemExit(f"Seedance directory not found: {seedance_dir}")

    source_videos = sorted(seedance_dir.glob(f"{args.sku}_*.mp4"))
    if not source_videos:
        raise SystemExit(f"No videos found for SKU {args.sku} in {seedance_dir}")

    edit_dir = seedance_dir / "edit" / args.sku
    verify_dir = edit_dir / "verify"
    verify_dir.mkdir(parents=True, exist_ok=True)

    sources = []
    for video in source_videos:
        metadata_path = video.with_suffix(".json")
        metadata = load_metadata(metadata_path)
        sources.append(
            {
                "name": video.stem,
                "video": str(video),
                "metadata": str(metadata_path) if metadata_path.exists() else None,
                "task_id": metadata.get("id"),
                "model": metadata.get("model"),
                "duration": metadata.get("duration"),
                "resolution": metadata.get("resolution"),
                "ratio": metadata.get("ratio"),
                "audio": metadata.get("generate_audio"),
            }
        )

    manifest = {
        "sku": args.sku,
        "seedance_dir": str(seedance_dir),
        "edit_dir": str(edit_dir),
        "sources": sources,
    }
    (edit_dir / "sources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    project_path = edit_dir / "project.md"
    if not project_path.exists():
        source_lines = "\n".join(
            f"- `{source['name']}` — {source['duration']}s, "
            f"{source['resolution']}, {source['model']}"
            for source in sources
        )
        project_path.write_text(
            f"# {args.sku} Video Edit\n\n"
            f"## Session 1 — {date.today().isoformat()}\n\n"
            "**Strategy:** Prepare Seedance outputs for product-identity-first "
            "TikTok and Alibaba.com post-production.\n\n"
            "**Sources:**\n"
            f"{source_lines}\n\n"
            "**Decisions:** Pending visual inventory and edit strategy approval.\n\n"
            "**Outstanding:** Choose target platform, runtime, captions, music, "
            "CTA, and source ranges.\n",
            encoding="utf-8",
        )

    print(f"Prepared: {edit_dir}")
    print(f"Sources: {len(source_videos)}")


if __name__ == "__main__":
    main()
