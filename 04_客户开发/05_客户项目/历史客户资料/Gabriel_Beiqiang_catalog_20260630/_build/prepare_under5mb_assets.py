from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps


BUILD_DIR = Path(__file__).resolve().parent
ROOT = BUILD_DIR.parents[2]
OUTPUT_DIR = ROOT / "customers" / "Gabriel_Beiqiang_Upload_Under5MB_20260630"
MANIFEST_PATH = BUILD_DIR / "catalog_data_ready.json"
OUT_MANIFEST_PATH = BUILD_DIR / "under5_manifest.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def find_child_dir(parent: Path, predicate):
    for item in parent.iterdir():
        if item.is_dir() and predicate(item.name):
            return item
    raise FileNotFoundError(f"Missing expected folder under {parent}")


def list_images(folder: Path):
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS],
        key=lambda p: p.name,
    )


def find_product_hero(upload_dir: Path, code: str):
    product_dir = find_child_dir(upload_dir, lambda name: name.startswith(code))
    main_dir = find_child_dir(product_dir, lambda name: name.startswith("01_"))
    images = list_images(main_dir)
    for image in images:
        if image.stem.lower().replace("-", "_").startswith("01_main"):
            return image
    if not images:
        raise FileNotFoundError(f"No images for {code}")
    return images[0]


def save_thumbnail(src: Path, dest: Path, size: int, quality: int):
    dest.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(src)
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        bg = Image.new("RGB", image.size, "white")
        bg.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
        image = bg
    else:
        image = image.convert("RGB")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), "white")
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.paste(image, (x, y))
    canvas.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)


def main():
    if not str(OUTPUT_DIR).startswith(str(ROOT / "customers")):
        raise RuntimeError(f"Unsafe output path: {OUTPUT_DIR}")
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    product_thumb_dir = OUTPUT_DIR / "Compressed_Photos_Reference" / "Product_Thumbnails"
    factory_thumb_dir = OUTPUT_DIR / "Compressed_Photos_Reference" / "Factory_Thumbnails"
    product_thumb_dir.mkdir(parents=True, exist_ok=True)
    factory_thumb_dir.mkdir(parents=True, exist_ok=True)

    upload_root = find_child_dir(ROOT, lambda name: name.startswith("02_"))
    upload_dir = find_child_dir(upload_root, lambda name: name.startswith("00_"))

    products = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for product in products:
        hero = find_product_hero(upload_dir, product["code"])
        thumb = product_thumb_dir / f"{product['code']}.jpg"
        save_thumbnail(hero, thumb, 260, 48)
        product["thumbnail"] = str(thumb)

    factory_root = find_child_dir(upload_dir, lambda name: "厂家" in name)
    curated = find_child_dir(factory_root, lambda name: "精选" in name or name.startswith("00_"))
    choices = [
        ("03_", "01_workshop"),
        ("02_", "01_upper_check"),
        ("04_", "04_carton_ready"),
        ("01_", "02_color_options"),
    ]
    factory_thumbs = []
    for prefix, needle in choices:
        folder = find_child_dir(curated, lambda name, prefix=prefix: name.startswith(prefix))
        images = list_images(folder)
        src = next((p for p in images if needle in p.name), images[0])
        dest = factory_thumb_dir / f"{len(factory_thumbs) + 1}_{needle}.jpg"
        save_thumbnail(src, dest, 360, 50)
        factory_thumbs.append(str(dest))

    OUT_MANIFEST_PATH.write_text(
        json.dumps({"products": products, "factoryThumbs": factory_thumbs, "outputDir": str(OUTPUT_DIR)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"outputDir": str(OUTPUT_DIR), "products": len(products), "factoryThumbs": len(factory_thumbs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
