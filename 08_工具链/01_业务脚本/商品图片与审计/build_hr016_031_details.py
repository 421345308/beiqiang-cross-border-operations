"""Build four HR016-A detail modules from the exact Luqi 031 photographs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "99_临时区/HR016_031_公开货源图_2026-09-24"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR016_031"
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
REG = Path("C:/Windows/Fonts/arial.ttf")
INK = (25, 43, 52)
MUTED = (86, 102, 111)
GREEN = (20, 86, 71)
BG = (250, 250, 248)


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD if bold else REG), size)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def card(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (1200, 1200), BG)
    draw = ImageDraw.Draw(image)
    draw.text((62, 54), title, font=f(49, True), fill=INK)
    draw.text((64, 124), subtitle, font=f(28), fill=MUTED)
    return image, draw


def show(image: Image.Image, source: Path, xy: tuple[int, int], max_size: tuple[int, int]) -> None:
    photo = Image.open(source).convert("RGB")
    if photo.size != (800, 800):
        raise ValueError((source, photo.size))
    fitted = ImageOps.contain(photo, max_size, Image.Resampling.LANCZOS)
    image.paste(fitted, xy)


def save(image: Image.Image, name: str, sources: list[Path], purpose: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    image.save(path, format="PNG", optimize=True)
    return {
        "output": str(path.relative_to(ROOT)),
        "output_sha256": sha(path),
        "output_bytes": path.stat().st_size,
        "source_photos": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in sources],
        "purpose": purpose,
        "method": "deterministic uniform scale and English graphic layout; shoe geometry not redrawn",
    }


def main() -> None:
    earth = RAW / "01_土黄_白底_来源图.jpg"
    black = RAW / "02_黑色_白底_来源图.jpg"
    khaki = RAW / "03_卡其_白底_来源图.jpg"
    wearing = RAW / "06_穿着图_来源.jpg"
    rows: list[dict] = []

    d1, d = card("MODEL HR016-A | MID-TOP LACE-UP", "Wholesale overview | Supplier style 031")
    show(d1, earth, (40, 220), (730, 730))
    d.rounded_rectangle((785, 225, 1145, 955), radius=18, fill=(232, 244, 240))
    fields = [("SHOE", "Mid-top outdoor style"), ("COLORS", "Black / Khaki / Earth Yellow"),
              ("SIZE RANGE", "EU 39-48"), ("CLOSURE", "Lace-up")]
    for i, (head, value) in enumerate(fields):
        y = 270 + i * 170
        d.text((813, y), head, font=f(27, True), fill=GREEN)
        d.text((813, y + 45), value, font=f(22), fill=INK)
    d.text((67, 1053), "Confirm exact color-size availability for each order.", font=f(28), fill=MUTED)
    rows.append(save(d1, "HR016-A_031_D1_overview.png", [earth], "product identity and orderable range"))

    d2, d = card("SUPPLIER-REPORTED MATERIALS", "Material names are from the current 031 sourcing page")
    show(d2, khaki, (40, 245), (600, 600))
    d.rounded_rectangle((640, 245, 1142, 868), radius=18, fill=(235, 246, 242))
    materials = [("UPPER", "Textile"), ("LINING", "Mesh"), ("MIDSOLE", "EVA"), ("OUTSOLE", "Rubber")]
    for i, (head, value) in enumerate(materials):
        y = 287 + i * 143
        d.text((676, y), head, font=f(27, True), fill=GREEN)
        d.text((907, y), value, font=f(28), fill=INK)
    d.text((63, 949), "Materials are supplier statements, not independent test results.", font=f(27), fill=MUTED)
    d.text((63, 1002), "Confirm final order specification before production or shipment.", font=f(27), fill=MUTED)
    rows.append(save(d2, "HR016-A_031_D2_materials.png", [khaki], "four sourcing-page material layers"))

    d3, d = card("THREE COLORS | EU 39-48", "Photographed supplier colors; no unverified country-size conversion")
    for i, (source, label) in enumerate([(black, "BLACK"), (khaki, "KHAKI"), (earth, "EARTH YELLOW")]):
        x = 45 + i * 386
        show(d3, source, (x, 272), (340, 340))
        label_w = d.textbbox((0, 0), label, font=f(29, True))[2]
        d.text((x + (340 - label_w) // 2, 658), label, font=f(29, True), fill=INK)
    d.rounded_rectangle((74, 780, 1126, 1009), radius=20, fill=GREEN)
    d.text((132, 814), "EU 39   40   41   42   43", font=f(40, True), fill=(255, 255, 255))
    d.text((132, 922), "EU 44   45   46   47   48", font=f(40, True), fill=(255, 255, 255))
    d.text((169, 1070), "Send your preferred size ratio with the inquiry.", font=f(29), fill=MUTED)
    rows.append(save(d3, "HR016-A_031_D3_colors_sizes.png", [black, khaki, earth],
                     "three actual colors and ten EU labels"))

    d4, d = card("SEND YOUR ORDER BRIEF", "For the photographed HR016-A / 031 shoe")
    show(d4, wearing, (48, 250), (610, 610))
    d.rounded_rectangle((675, 250, 1140, 862), radius=18, fill=(232, 244, 240))
    questions = ["01  Target quantity", "02  Color and EU size mix", "03  Bag / box preference",
                 "04  Destination", "05  Trade and forwarding terms"]
    for i, question in enumerate(questions):
        d.text((700, 288 + i * 112), question, font=f(25), fill=INK)
    d.rounded_rectangle((65, 960, 1135, 1090), radius=20, fill=GREEN)
    d.text((117, 981), "Final packing, availability and timing", font=f(35, True), fill=(255, 255, 255))
    d.text((117, 1032), "are confirmed for each actual order.", font=f(32), fill=(255, 255, 255))
    rows.append(save(d4, "HR016-A_031_D4_order_brief.png", [wearing], "B2B quote inputs without stock/lead-time promise"))

    manifest = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "status": "LOCAL_CANDIDATES_ONLY_NOT_UPLOADED",
        "model": "HR016-A / supplier 031",
        "items": rows,
    }
    path = OUT / "HR016-A_031_D1_D4_来源与方法.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
