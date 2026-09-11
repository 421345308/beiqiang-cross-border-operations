from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = ROOT / "outputs" / "20260830_full_excel_rebuild" / "candidate_index.json"
VARIANTS = {
    "W1": {"order": (0, 1, 2, 3, 4, 5), "top": (255, 255, 255), "bottom": (247, 249, 250)},
    "R1": {"order": (2, 3, 4, 5, 0, 1), "top": (252, 249, 244), "bottom": (241, 237, 230)},
    "O1": {"order": (4, 5, 0, 1, 2, 3), "top": (246, 250, 252), "bottom": (231, 238, 242)},
}

# Six real-photo sources per SKU.  The indexes refer to the visually reviewed
# contact sheets in 02_Alibaba运营/05_扩品工程/批量发品/历史批次执行产物_2026-08-28至09-02/20260830_full_excel_rebuild/candidate_sheets.
SOURCE_INDEXES: dict[str, list[int]] = {
    "BQ001": [0, 1, 6, 7, 24, 30], "BQ002": [0, 1, 6, 7, 24, 30],
    "BQ003": [0, 8, 16, 24, 32, 40], "BQ004": [60, 63, 66, 69, 72, 75],
    "BQ005": [18, 19, 20, 21, 22, 23], "BQ006": [42, 43, 44, 45, 46, 47],
    "BQ007": [45, 44, 47, 46, 48, 43], "BQ008": [0, 6, 18, 24, 30, 36],
    "BQ009": [0, 6, 18, 24, 30, 36], "BQ010": [18, 24, 30, 48, 54, 60],
    "BQ011": [7, 4, 8, 5, 9, 11], "BQ012": [72, 75, 78, 81, 84, 87],
    "BQ013": [2, 5, 9, 12, 15, 18], "BQ014": [72, 73, 74, 75, 76, 77],
    "BQ015": [120, 123, 126, 129, 132, 135], "BQ016": [2, 5, 10, 8, 15, 18],
    "BQ017": [73, 74, 76, 78, 79, 81], "BQ018": [55, 60, 64, 68, 69, 71],
    "BQ019": [8, 9, 10, 11, 12, 13], "BQ020": [96, 100, 98, 101, 97, 99],
    "BQ021": [10, 13, 16, 19, 22, 25], "BQ022": [0, 1, 2, 3, 4, 5],
    "BQ023": [13, 14, 18, 21, 24, 26], "BQ024": [0, 3, 6, 9, 12, 15],
    "BQ025": [13, 14, 15, 16, 17, 18], "BQ026": [0, 3, 6, 9, 12, 15],
    "BQ027": [0, 3, 6, 9, 12, 15], "BQ028": [34, 35, 36, 37, 38, 74],
    "BQ029": [38, 39, 40, 41, 55, 56], "BQ030": [53, 54, 55, 56, 57, 60],
    "BQ031": [0, 5, 10, 14, 18, 23], "BQ032": [0, 2, 3, 18, 4, 22],
    "BQ033": [0, 2, 1, 3, 12, 13], "BQ034": [14, 17, 8, 18, 11, 19],
    "BQ035": [3, 13, 5, 15, 25, 29], "BQ036": [10, 11, 12, 23, 24, 25],
    "BQ037": [3, 4, 12, 13, 24, 29], "BQ038": [12, 13, 15, 14, 17, 16],
    "BQ039": [2, 4, 9, 10, 11, 16], "BQ040": [11, 8, 5, 12, 10, 13],
    "BQ041": [11, 13, 14, 4, 12, 18], "BQ042": [8, 5, 2, 9, 10, 7],
    "BQ043": [14, 15, 19, 7, 17, 16], "BQ044": [22, 23, 24, 25, 26, 27],
    "BQ045": [11, 12, 13, 14, 15, 16], "BQ046": [15, 16, 17, 18, 0, 19],
    "BQ047": [14, 15, 16, 17, 18, 19], "BQ048": [11, 18, 12, 19, 10, 23],
    "BQ049": [14, 8, 15, 9, 16, 17], "BQ050": [20, 21, 22, 24, 11, 12],
    "BQ051": [11, 13, 12, 14, 6, 17], "BQ052": [1, 2, 3, 11, 4, 12],
    "BQ059": [18, 19, 20, 23, 21, 22],
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        mix = y / max(1, size - 1)
        color = tuple(round(a * (1 - mix) + b * mix) for a, b in zip(top, bottom))
        draw.line((0, y, size, y), fill=color)
    return image


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        raise RuntimeError("background removal returned an empty mask")
    return bbox


def prepare_cutout(code: str, source: Path, remove, session) -> Image.Image:
    source_bytes = source.read_bytes()
    # A few domestic detail cards place the useful product photo in one half
    # of a tall composition. Crop to the real product area before segmentation
    # so text, outsole diagrams and duplicated panels cannot leak into a hero.
    if code == "BQ041" and "最终上传" in str(source):
        with Image.open(io.BytesIO(source_bytes)) as original:
            original = original.convert("RGB")
            original = original.crop((0, 0, original.width, round(original.height * 0.53)))
            buffer = io.BytesIO()
            original.save(buffer, format="PNG")
            source_bytes = buffer.getvalue()
    elif code == "BQ042" and source.name == "01_main.jpg":
        with Image.open(io.BytesIO(source_bytes)) as original:
            original = original.convert("RGB")
            original = original.crop(
                (round(original.width * 0.20), round(original.height * 0.28),
                 round(original.width * 0.96), round(original.height * 0.82))
            )
            buffer = io.BytesIO()
            original.save(buffer, format="PNG")
            source_bytes = buffer.getvalue()
    elif code == "BQ052":
        with Image.open(io.BytesIO(source_bytes)) as original:
            original = original.convert("RGB")
            original = original.crop((0, round(original.height * 0.42), original.width, original.height))
            buffer = io.BytesIO()
            original.save(buffer, format="PNG")
            source_bytes = buffer.getvalue()
    result = remove(source_bytes, session=session, alpha_matting=False, post_process_mask=True)
    image = Image.open(io.BytesIO(result)).convert("RGBA")
    # Domestic source cards often contain one large product plus small angle
    # thumbnails. Keep only the largest connected foreground component so the
    # rebuilt main image is a single shoe, never a multi-view collage.
    import numpy as np
    from scipy import ndimage

    alpha = np.asarray(image.getchannel("A"))
    labels, count = ndimage.label(alpha > 48)
    if count:
        sizes = ndimage.sum(alpha > 48, labels, range(1, count + 1))
        if code in {"BQ035", "BQ052"}:
            centers = ndimage.center_of_mass(alpha > 48, labels, range(1, count + 1))
            viable = [i for i, size in enumerate(sizes) if size >= max(sizes) * 0.18]
            chosen = max(viable, key=lambda i: centers[i][0]) + 1
        else:
            chosen = int(np.argmax(sizes)) + 1
        keep = labels == chosen
        clean_alpha = np.where(keep, alpha, 0).astype("uint8")
        image.putalpha(Image.fromarray(clean_alpha, mode="L"))
    return image.crop(alpha_bbox(image))


def compose(cutout: Image.Image, variant: str, slot: int) -> Image.Image:
    spec = VARIANTS[variant]
    canvas = gradient(1000, spec["top"], spec["bottom"])
    # The first image is the clean, high-occupancy hero.  Other gallery images
    # vary crop and position gently without adding copy, badges or collages.
    max_w = (820, 760, 790, 735, 800, 750)[slot]
    max_h = (660, 700, 650, 720, 660, 700)[slot]
    scale = min(max_w / cutout.width, max_h / cutout.height)
    size = (max(1, round(cutout.width * scale)), max(1, round(cutout.height * scale)))
    product = cutout.resize(size, Image.Resampling.LANCZOS)
    x_shift = {"W1": 0, "R1": -24, "O1": 24}[variant]
    y_shift = (8, -6, 14, 0, 10, -4)[slot]
    x = (1000 - product.width) // 2 + x_shift
    y = 510 - product.height // 2 + y_shift
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    sx1 = max(90, x + round(product.width * 0.10))
    sx2 = min(910, x + round(product.width * 0.90))
    sy = min(865, y + product.height - 10)
    shadow_draw.ellipse((sx1, sy - 22, sx2, sy + 24), fill=(40, 48, 54, 42))
    shadow = shadow.filter(ImageFilter.GaussianBlur(15))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)
    canvas.alpha_composite(product, (x, y))
    return canvas.convert("RGB")


def make_preview(code: str, files: list[Path], destination: Path) -> None:
    thumb = 220
    label_h = 28
    cols = 6
    canvas = Image.new("RGB", (cols * thumb, 3 * (thumb + label_h)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, path in enumerate(files):
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((thumb, thumb))
            row, col = divmod(index, cols)
            x = col * thumb + (thumb - image.width) // 2
            y = row * (thumb + label_h) + (thumb - image.height) // 2
            canvas.paste(image, (x, y))
            draw.text((col * thumb + 6, row * (thumb + label_h) + thumb + 4), path.stem, fill="black", font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=88)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codes", nargs="*")
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args()

    sys.path.insert(0, str(args.package_dir))
    os.environ["U2NET_HOME"] = str(args.model_dir)
    from rembg import new_session, remove

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    codes = [code.upper() for code in (args.codes or SOURCE_INDEXES.keys())]
    unknown = sorted(set(codes) - set(SOURCE_INDEXES))
    if unknown:
        raise RuntimeError(f"missing reviewed source indexes: {unknown}")

    args.output.mkdir(parents=True, exist_ok=True)
    session = new_session("u2netp")
    manifest_path = args.output / "重制主图清单.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("model", "u2netp")
        manifest.setdefault("products", {})
    else:
        manifest = {"model": "u2netp", "products": {}}
    for code in codes:
        entries = index[code]
        selected = [Path(entries[position]["path"]) for position in SOURCE_INDEXES[code]]
        if len(selected) != 6 or len({sha256(path) for path in selected}) != 6:
            raise RuntimeError(f"{code}: six content-distinct reviewed sources required")
        cutouts = [prepare_cutout(code, path, remove, session) for path in selected]
        product_dir = args.output / "main" / code
        product_dir.mkdir(parents=True, exist_ok=True)
        outputs: dict[str, list[str]] = {}
        all_files: list[Path] = []
        for variant, spec in VARIANTS.items():
            variant_files: list[str] = []
            for slot, base_index in enumerate(spec["order"], 1):
                destination = product_dir / f"{code.lower()}_{variant.lower()}_m{slot}.jpg"
                compose(cutouts[base_index], variant, slot - 1).save(
                    destination, format="JPEG", quality=94, subsampling=0, optimize=True
                )
                variant_files.append(str(destination))
                all_files.append(destination)
            outputs[variant] = variant_files
        preview = args.output / "previews" / f"{code}_18张重制主图.jpg"
        make_preview(code, all_files, preview)
        manifest["products"][code] = {
            "source_indexes": SOURCE_INDEXES[code],
            "sources": [str(path) for path in selected],
            "main": outputs,
            "preview": str(preview),
            "visual_qa": {variant: "PENDING" for variant in VARIANTS},
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"code": code, "outputs": 18}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
