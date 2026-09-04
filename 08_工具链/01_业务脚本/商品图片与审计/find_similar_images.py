from __future__ import annotations

import argparse
import heapq
from pathlib import Path
from PIL import Image, ImageOps


EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def dhash(path: Path, size: int = 16) -> int:
    with Image.open(path) as image:
        gray = ImageOps.grayscale(image).resize((size + 1, size), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())
    value = 0
    for y in range(size):
        row = y * (size + 1)
        for x in range(size):
            value = (value << 1) | int(pixels[row + x] > pixels[row + x + 1])
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("targets", nargs="+", type=Path)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()
    target_hashes = {target: dhash(target) for target in args.targets}
    heaps = {target: [] for target in args.targets}
    for path in args.root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        try:
            value = dhash(path)
        except Exception:
            continue
        for target, target_hash in target_hashes.items():
            distance = (value ^ target_hash).bit_count()
            item = (-distance, str(path))
            heap = heaps[target]
            if len(heap) < args.top:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
    for target, heap in heaps.items():
        print(f"TARGET\t{target}")
        for neg_distance, path in sorted(heap, reverse=True):
            print(f"{abs(neg_distance)}\t{path}")


if __name__ == "__main__":
    main()
