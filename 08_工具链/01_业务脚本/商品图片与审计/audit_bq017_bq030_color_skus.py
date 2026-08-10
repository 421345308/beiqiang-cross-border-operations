from __future__ import annotations

from pathlib import Path
import csv
import importlib.util
import io
import re
import sys

from PIL import Image, ImageDraw, ImageFont


TARGET_RE = re.compile(r"^BQ0(1[7-9]|2[0-9]|30)_")
ORG_SCRIPT_NAME = "organize_20260616_new_packages.py"
QA_NAME = "BQ017_BQ030_color_sku_audit_20260621"


def workspace_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "AGENTS.md").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = workspace_root()


def child_by_prefix(parent: Path, prefix: str) -> Path:
    return next(p for p in parent.iterdir() if p.is_dir() and p.name.startswith(prefix))


ASSET_ROOT = child_by_prefix(ROOT, "02_")
FINAL_ROOT = child_by_prefix(ASSET_ROOT, "00_")
ARCHIVE_ROOT = child_by_prefix(ASSET_ROOT, "99_")
SCRIPT_ROOT = child_by_prefix(ROOT, "90_") / "scripts"
QA_ROOT = ARCHIVE_ROOT / QA_NAME


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def save_jpg(image: Image.Image, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, subsampling=1)
    path.write_bytes(buffer.getvalue())


def product_dirs() -> list[Path]:
    return sorted([p for p in FINAL_ROOT.iterdir() if p.is_dir() and TARGET_RE.match(p.name)], key=lambda p: p.name)


def optional_dir(product_dir: Path, prefix: str) -> Path | None:
    matches = [p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith(prefix)]
    return matches[0] if matches else None


def load_metadata() -> dict[str, object]:
    script = SCRIPT_ROOT / ORG_SCRIPT_NAME
    if not script.exists():
        return {}
    spec = importlib.util.spec_from_file_location("color_audit_metadata", script)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {product.folder_name: product for product in module.PRODUCTS}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def image_files(folder: Path | None) -> list[Path]:
    if folder is None:
        return []
    return sorted(
        [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ],
        key=lambda p: p.name.lower(),
    )


def dimensions(path: Path) -> str:
    try:
        with Image.open(path) as opened:
            return f"{opened.width}x{opened.height}"
    except OSError:
        return "unreadable"


def paste_thumb(canvas: Image.Image, path: Path, box: tuple[int, int, int, int], label: str) -> None:
    draw = ImageDraw.Draw(canvas)
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=10, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    draw.text((x0 + 8, y0 + 8), label[:34], fill=(30, 41, 59), font=font(12, True))
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        image.thumbnail((x1 - x0 - 18, y1 - y0 - 44), Image.Resampling.LANCZOS)
        canvas.paste(image, (x0 + (x1 - x0 - image.width) // 2, y0 + 34 + (y1 - y0 - 44 - image.height) // 2))
    except OSError:
        draw.text((x0 + 12, y0 + 54), "unreadable", fill=(185, 28, 28), font=font(14, True))


def make_product_sheet(product_dir: Path, product: object | None, rows: list[dict[str, object]]) -> Path:
    main_dir = optional_dir(product_dir, "01_")
    detail_dir = optional_dir(product_dir, "02_")
    color_dir = optional_dir(product_dir, "03_")
    ref_dir = optional_dir(product_dir, "04_")
    sku_files = image_files(color_dir)
    swatches = [name for name, _ in getattr(product, "colors", [])] if product else []

    tile_w = 220
    tile_h = 245
    cols = 5
    gallery_paths = []
    if main_dir and (main_dir / "05_colors.jpg").exists():
        gallery_paths.append((main_dir / "05_colors.jpg", "main/05_colors"))
    if detail_dir and (detail_dir / "05_colors.jpg").exists():
        gallery_paths.append((detail_dir / "05_colors.jpg", "detail/05_colors"))
    gallery_paths.extend((p, f"sku/{p.name}") for p in sku_files)
    if ref_dir and (ref_dir / "source_contact.jpg").exists():
        gallery_paths.append((ref_dir / "source_contact.jpg", "source_contact"))

    rows_needed = max(1, (len(gallery_paths) + cols - 1) // cols)
    canvas = Image.new("RGB", (cols * tile_w + 28, 118 + rows_needed * tile_h + 24), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((16, 14), product_dir.name, fill=(18, 25, 38), font=font(22, True))
    draw.text((16, 46), "Expected colors: " + (", ".join(swatches) if swatches else "not found"), fill=(71, 85, 105), font=font(15))
    draw.text((16, 72), f"SKU files: {', '.join(p.name for p in sku_files) if sku_files else 'missing'}", fill=(71, 85, 105), font=font(14))

    for i, (path, label) in enumerate(gallery_paths):
        col = i % cols
        row = i // cols
        x0 = 14 + col * tile_w
        y0 = 108 + row * tile_h
        paste_thumb(canvas, path, (x0, y0, x0 + tile_w - 12, y0 + tile_h - 12), label)

    out = QA_ROOT / "product_sheets" / f"{product_dir.name}_color_audit.jpg"
    save_jpg(canvas, out)

    expected = {normalize(name) for name in swatches}
    actual = {p.stem.lower() for p in sku_files}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    issue_parts: list[str] = []
    if len(sku_files) != len(swatches):
        issue_parts.append(f"count mismatch expected {len(swatches)} got {len(sku_files)}")
    if missing:
        issue_parts.append("missing " + ", ".join(missing))
    if extra:
        issue_parts.append("extra " + ", ".join(extra))
    if not issue_parts:
        issue_parts.append("file count/name match; visual check still required")
    rows.append(
        {
            "product": product_dir.name,
            "expected_colors": ", ".join(swatches),
            "sku_files": ", ".join(p.name for p in sku_files),
            "main_05": str(main_dir / "05_colors.jpg") if main_dir and (main_dir / "05_colors.jpg").exists() else "",
            "detail_05": str(detail_dir / "05_colors.jpg") if detail_dir and (detail_dir / "05_colors.jpg").exists() else "",
            "issue": "; ".join(issue_parts),
            "sheet": str(out),
        }
    )
    return out


def make_overview(sheets: list[Path], out: Path, title: str) -> None:
    cols = 2
    cell_w = 560
    cell_h = 430
    rows = (len(sheets) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, 56 + rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((16, 14), title, fill=(18, 25, 38), font=font(22, True))
    for i, sheet in enumerate(sheets):
        with Image.open(sheet) as opened:
            image = opened.convert("RGB")
        image.thumbnail((cell_w - 16, cell_h - 16), Image.Resampling.LANCZOS)
        x = (i % cols) * cell_w + (cell_w - image.width) // 2
        y = 56 + (i // cols) * cell_h + (cell_h - image.height) // 2
        canvas.paste(image, (x, y))
    save_jpg(canvas, out, quality=90)


def write_csv(rows: list[dict[str, object]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["product", "expected_colors", "sku_files", "issue", "main_05", "detail_05", "sheet"],
        )
        writer.writeheader()
        writer.writerows(rows)


def run() -> None:
    QA_ROOT.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata()
    rows: list[dict[str, object]] = []
    sheets = [make_product_sheet(product_dir, metadata.get(product_dir.name), rows) for product_dir in product_dirs()]
    make_overview(sheets[:7], QA_ROOT / "color_sku_audit_overview_17_23.jpg", "BQ017-BQ023 color SKU audit")
    make_overview(sheets[7:], QA_ROOT / "color_sku_audit_overview_24_30.jpg", "BQ024-BQ030 color SKU audit")
    write_csv(rows, QA_ROOT / "color_sku_audit.csv")
    print(f"products={len(rows)}")
    print(f"qa={QA_ROOT}")
    print(f"overview1={QA_ROOT / 'color_sku_audit_overview_17_23.jpg'}")
    print(f"overview2={QA_ROOT / 'color_sku_audit_overview_24_30.jpg'}")


if __name__ == "__main__":
    run()
