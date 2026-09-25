"""Compose HR016-B buyer panels without generating or repainting the shoe."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "99_临时区/HR016_031_公开货源图_2026-09-24"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR016_031"
COMPANY = ROOT / "02_Alibaba运营/06_图片与检查记录/公司图复用模板_v4_2026-09-21/C3_real_production_organization.jpg"
FONT = Path("C:/Windows/Fonts/arial.ttf")
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
BLACK = SRC / "02_黑色_白底_来源图.jpg"
KHAKI = SRC / "03_卡其_白底_来源图.jpg"
EARTH = SRC / "01_土黄_白底_来源图.jpg"
TREAD = SRC / "04_展示图_来源.jpg"
WEAR = SRC / "05_展示图_来源.jpg"
TOP = SRC / "06_穿着图_来源.jpg"
BG = (249, 250, 248)
INK = (28, 43, 48)
MUTED = (83, 101, 106)
GREEN = (23, 89, 72)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canvas(size: int, title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(image)
    draw.text((48, 42), title, font=font(42 if size == 1000 else 49, True), fill=INK)
    draw.text((50, 106), subtitle, font=font(22 if size == 1000 else 27), fill=MUTED)
    return image, draw


def photo(image: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    original = Image.open(path).convert("RGB")
    if path != COMPANY and original.size != (800, 800):
        raise ValueError((path, original.size))
    x, y, w, h = box
    scaled = ImageOps.contain(original, (w, h), Image.Resampling.LANCZOS)
    image.paste(scaled, (x + (w - scaled.width) // 2, y + (h - scaled.height) // 2))


def record(image: Image.Image, name: str, role: str, inputs: list[Path]) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    image.save(path, "PNG", optimize=True)
    return {
        "file": str(path.relative_to(ROOT)),
        "sha256": sha(path),
        "role": role,
        "sources": [{"file": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in inputs],
        "method": "deterministic text/layout plus exact source photographs; no generative shoe redraw",
    }


def main() -> None:
    rows: list[dict] = []

    m2, d = canvas(1000, "MID-TOP SHOE | VISIBLE TREAD", "Actual supplier 031 photograph; no performance test claim")
    photo(m2, TREAD, (115, 158, 770, 770))
    d.text((220, 948), "Lace-up closure  |  outsole pattern", font=font(27, True), fill=INK)
    rows.append(record(m2, "H16B_M2_tread.png", "shoe structure and visible outsole", [TREAD]))

    m3, d = canvas(1000, "031 MATERIALS AT A GLANCE", "Supplier-stated layers | verify final order specification")
    photo(m3, BLACK, (40, 220, 600, 600))
    d.rounded_rectangle((638, 228, 958, 824), radius=20, fill=(226, 241, 235))
    for i, (key, value) in enumerate([("LINING", "Mesh"), ("MIDSOLE", "EVA"), ("OUTSOLE", "Rubber")]):
        y = 275 + i * 175
        d.text((664, y), key, font=font(25, True), fill=GREEN)
        d.text((664, y + 48), value, font=font(37, True), fill=INK)
    d.text((70, 919), "Black color shown | Confirm materials for your order", font=font(25), fill=MUTED)
    rows.append(record(m3, "H16B_M3_materials.png", "verified source-stated material layers", [BLACK]))

    m4, d = canvas(1000, "SOURCE COLOR CHOICES", "Same source style 031 | EU 39-48")
    for i, (path, label) in enumerate([(BLACK, "BLACK"), (EARTH, "EARTH YELLOW"), (KHAKI, "KHAKI")]):
        x = 28 + 328 * i
        photo(m4, path, (x, 285, 300, 300))
        width = d.textbbox((0, 0), label, font=font(26, True))[2]
        d.text((x + (300 - width) // 2, 605), label, font=font(26, True), fill=INK)
    d.rounded_rectangle((135, 735, 865, 833), radius=18, fill=GREEN)
    d.text((212, 757), "EU 39 40 41 42 43 44 45 46 47 48", font=font(25, True), fill="white")
    d.text((157, 890), "Send your color-size mix for supplier availability check.", font=font(24), fill=MUTED)
    rows.append(record(m4, "H16B_M4_colors.png", "three actual colors and EU labels", [BLACK, EARTH, KHAKI]))

    m5, d = canvas(1000, "BEIQIANG WORKSHOP CONTEXT", "General company operations; 031 is externally sourced")
    photo(m5, COMPANY, (90, 177, 820, 780))
    rows.append(record(m5, "H16B_M5_company.png", "company context, explicitly not 031 manufacture", [COMPANY]))

    d1, d = canvas(1200, "HR016-B | SUPPLIER STYLE 031", "Men's mid-top lace-up shoe | Black-first product overview")
    photo(d1, BLACK, (45, 200, 725, 725))
    d.rounded_rectangle((780, 225, 1155, 930), radius=20, fill=(226, 241, 235))
    for i, (key, val) in enumerate([("CLOSURE", "Lace-up"), ("HEIGHT", "Mid-top"), ("COLORS", "Three source colors"), ("EU SIZES", "39-48")]):
        y = 270 + i * 156
        d.text((812, y), key, font=font(26, True), fill=GREEN)
        d.text((812, y + 46), val, font=font(25), fill=INK)
    d.text((91, 1050), "Exact color-size availability is checked for each order.", font=font(31), fill=MUTED)
    rows.append(record(d1, "H16B_D1_overview.png", "B-specific model and product identity", [BLACK]))

    d2, d = canvas(1200, "MATERIALS REPORTED BY SOURCE", "031 sourcing page statements; not independent test results")
    photo(d2, KHAKI, (612, 230, 540, 540))
    d.rounded_rectangle((60, 250, 590, 845), radius=20, fill=(232, 243, 239))
    for i, line in enumerate(["Lining  /  Mesh", "Midsole  /  EVA", "Outsole  /  Rubber", "Closure  /  Lace-up"]):
        d.text((90, 290 + i * 130), line, font=font(31, True), fill=INK)
    d.text((76, 963), "For quotation, confirm the final material and packing requirements.", font=font(27), fill=MUTED)
    rows.append(record(d2, "H16B_D2_materials.png", "source-stated materials without upper trademark claim", [KHAKI]))

    d3, d = canvas(1200, "STRUCTURE FROM REAL PHOTOS", "Supplier 031: visible lace-up collar and outsole pattern")
    photo(d3, TREAD, (38, 210, 550, 550))
    photo(d3, WEAR, (612, 210, 550, 550))
    d.text((90, 807), "OUTSOLE VIEW", font=font(27, True), fill=GREEN)
    d.text((687, 807), "BLACK ON FOOT", font=font(27, True), fill=GREEN)
    d.text((110, 986), "Photos show appearance, not tested traction or cushioning.", font=font(28), fill=MUTED)
    rows.append(record(d3, "H16B_D3_structure.png", "two real structural views, no performance promise", [TREAD, WEAR]))

    d4, d = canvas(1200, "QUOTE THE HR016-B / 031 STYLE", "Send the details needed to check the actual supplier order")
    photo(d4, TOP, (48, 230, 570, 570))
    d.rounded_rectangle((633, 230, 1150, 831), radius=19, fill=(226, 241, 235))
    for i, line in enumerate(["01  Order quantity", "02  Color and EU size mix", "03  Bag or box preference", "04  Delivery destination", "05  Logo/sample request"]):
        d.text((665, 276 + i * 110), line, font=font(27), fill=INK)
    d.text((74, 962), "Availability, customization and delivery are confirmed per order.", font=font(27), fill=MUTED)
    rows.append(record(d4, "H16B_D4_quote.png", "B-specific inquiry brief without stock promise", [TOP]))

    manifest = {
        "made_at": datetime.now().astimezone().isoformat(),
        "state": "LOCAL_CANDIDATES_UNREVIEWED_NOT_UPLOADED",
        "source": "https://luqi.sooxie.com/detail/2454935",
        "items": rows,
    }
    output = OUT / "H16B_031_panels_manifest.json"
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"outputs": [row["file"] for row in rows], "manifest": str(output.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
