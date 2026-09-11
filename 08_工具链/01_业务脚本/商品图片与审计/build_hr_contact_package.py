import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


CANVAS = 1000


def crop_panel(sheet: Image.Image, col: int, row: int, cols: int = 3, rows: int = 2) -> Image.Image:
    """Crop one panel from a regular contact sheet and normalize to 1000 px."""
    x0 = round(sheet.width * col / cols)
    x1 = round(sheet.width * (col + 1) / cols)
    y0 = round(sheet.height * row / rows)
    y1 = round(sheet.height * (row + 1) / rows)
    # Remove the faint grid line while keeping the generous generated margin.
    pad = max(3, round(min(sheet.width, sheet.height) * 0.004))
    panel = sheet.crop((x0 + pad, y0 + pad, x1 - pad, y1 - pad)).convert("RGB")
    return panel.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)


def save(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG", optimize=True)


def make_oem_background(colors: list[tuple[str, Image.Image]], path: Path) -> None:
    im = Image.new("RGB", (1200, 1200), (235, 240, 243))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 760, 1200, 1200), fill=(211, 220, 225))
    positions = [(610, 105, 1140, 635), (520, 400, 1050, 930), (635, 665, 1165, 1195)]
    for (_, product), box in zip(colors, positions):
        thumb = product.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
        im.paste(thumb, (box[0], box[1]))
    save(im, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()
    cfg_path = Path(args.manifest).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    root = Path(cfg["product_root"])
    model = cfg["model"]
    cols = int(cfg.get("grid_cols", 3))
    rows = int(cfg.get("grid_rows", 2))
    role_cells = cfg.get("role_cells") or {
        "hero": [0, 0], "lateral": [1, 0], "outsole": [2, 0],
        "upper": [0, 1], "lifestyle": [1, 1], "heel": [2, 1],
    }
    sheets = cfg["colors"]
    rendered: list[tuple[str, Image.Image]] = []
    for item in sheets:
        name = item["name"]
        slug = item["slug"]
        sheet_path = Path(item["sheet"]).resolve()
        color_cols = int(item.get("grid_cols", cols))
        color_rows = int(item.get("grid_rows", rows))
        color_cell = item.get("cell", role_cells["lateral"])
        with Image.open(sheet_path) as sheet:
            lateral = crop_panel(sheet, *color_cell, color_cols, color_rows)
        save(lateral, root / "03_颜色图" / f"{model}_color_{slug}.png")
        rendered.append((name, lateral))

    with Image.open(Path(sheets[0].get("main_sheet", sheets[0]["sheet"])).resolve()) as sheet:
        roles = ["hero", "lateral", "outsole", "upper", "lifestyle", "heel"]
        main_panels = [crop_panel(sheet, *role_cells[role], cols, rows) for role in roles]
    for idx, (role, panel) in enumerate(zip(roles, main_panels), start=1):
        save(panel, root / "01_主图" / f"{model}_main_{idx:02d}_{role}.png")
    save(main_panels[0], root / "05_AI候选" / f"{model}_overview_bg_v1.png")
    make_oem_background(rendered, root / "05_AI候选" / f"{model}_oem_bg_v1.png")
    print(json.dumps({"model": model, "root": str(root), "main": 6, "colors": len(rendered)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
