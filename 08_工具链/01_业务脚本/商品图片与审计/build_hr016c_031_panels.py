"""Build HR016-C panels from exact supplier photographs without changing shoe pixels."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "99_临时区/HR016_031_公开货源图_2026-09-24"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR016_031"
KHAKI = SRC / "03_卡其_白底_来源图.jpg"
BLACK = SRC / "02_黑色_白底_来源图.jpg"
EARTH = SRC / "01_土黄_白底_来源图.jpg"
TREAD = SRC / "04_展示图_来源.jpg"
WEAR = SRC / "06_穿着图_来源.jpg"
COMPANY = ROOT / "02_Alibaba运营/06_图片与检查记录/公司图复用模板_v4_2026-09-21/C2_custom_project_flow.jpg"
REG = Path("C:/Windows/Fonts/arial.ttf")
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
BG = (250, 249, 245)
INK = (42, 49, 44)
SUB = (95, 104, 95)
GREEN = (21, 100, 75)
TINT = (232, 241, 234)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD if bold else REG), size)


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sheet(size: int, title: str, line: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(image)
    draw.text((48, 42), title, font=font(39 if size == 1000 else 49, True), fill=INK)
    draw.text((49, 105), line, font=font(21 if size == 1000 else 27), fill=SUB)
    return image, draw


def photo(image: Image.Image, path: Path, rect: tuple[int, int, int, int]) -> None:
    original = Image.open(path).convert("RGB")
    if path != COMPANY and original.size != (800, 800):
        raise ValueError(f"Unexpected source size: {path}: {original.size}")
    x, y, width, height = rect
    scaled = ImageOps.contain(original, (width, height), Image.Resampling.LANCZOS)
    image.paste(scaled, (x + (width - scaled.width) // 2, y + (height - scaled.height) // 2))


def save(image: Image.Image, name: str, role: str, sources: list[Path]) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    image.save(path, "PNG", optimize=True)
    return {
        "file": str(path.relative_to(ROOT)),
        "sha256": hash_file(path),
        "role": role,
        "sources": [{"file": str(p.relative_to(ROOT)), "sha256": hash_file(p)} for p in sources],
        "method": "deterministic layout and scaling of original supplier photographs; no shoe redraw",
    }


def main() -> None:
    rows: list[dict] = []

    m2, d = sheet(1000, "SOURCE PHOTO | OUTDOOR LOOK", "Actual 031 earth-yellow pair shown on foot")
    photo(m2, WEAR, (115, 165, 770, 770))
    d.text((209, 947), "Appearance reference only  |  No performance claim", font=font(24), fill=INK)
    rows.append(save(m2, "H16C_M2_wear.png", "real wear image without a performance claim", [WEAR]))

    m3, d = sheet(1000, "MID-TOP FORM + VISIBLE TREAD", "Source photographs | same supplier article 031")
    photo(m3, KHAKI, (35, 235, 455, 455))
    photo(m3, TREAD, (510, 235, 455, 455))
    d.text((128, 710), "KHAKI SIDE", font=font(29, True), fill=GREEN)
    d.text((629, 710), "SOLE VIEW", font=font(29, True), fill=GREEN)
    d.text((77, 825), "Lace-up collar and outsole pattern are visible.", font=font(28), fill=INK)
    d.text((77, 884), "No tested grip, durability or cushioning grade claimed.", font=font(24), fill=SUB)
    rows.append(save(m3, "H16C_M3_structure.png", "side profile versus visible sole", [KHAKI, TREAD]))

    m4, d = sheet(1000, "BUILD YOUR COLOR-SIZE MIX", "031 source lists three colors and EU 39-48")
    photo(m4, KHAKI, (35, 220, 535, 535))
    d.rounded_rectangle((575, 238, 965, 755), radius=20, fill=TINT)
    d.text((605, 279), "COLOR CHOICE", font=font(28, True), fill=GREEN)
    for i, label in enumerate(("Black", "Khaki", "Earth Yellow")):
        d.text((607, 344 + i * 75), label, font=font(31), fill=INK)
    d.text((605, 613), "EU 39-48", font=font(34, True), fill=GREEN)
    d.text((112, 827), "Tell us the requested mix and quantity for a current quote.", font=font(27), fill=INK)
    d.text((133, 882), "Supplier availability is reconfirmed for each order.", font=font(24), fill=SUB)
    rows.append(save(m4, "H16C_M4_mix.png", "buyer color-size mix and availability check", [KHAKI]))

    m5, d = sheet(1000, "BEIQIANG BUYER-BRIEF FLOW", "General company process | style 031 is externally sourced")
    photo(m5, COMPANY, (105, 177, 790, 790))
    rows.append(save(m5, "H16C_M5_brief.png", "general company project discussion, not 031 production", [COMPANY]))

    d1, d = sheet(1200, "HR016-C | SOURCE STYLE 031", "Khaki-first view | mid-top lace-up outdoor walking shoe")
    photo(d1, KHAKI, (45, 215, 755, 755))
    d.rounded_rectangle((813, 250, 1152, 880), radius=20, fill=TINT)
    for i, (key, value) in enumerate((("SOURCE", "Luqi 031"), ("CLOSURE", "Lace-up"), ("SIZES", "EU 39-48"), ("COLORS", "Three listed"))):
        y = 285 + i * 147
        d.text((842, y), key, font=font(25, True), fill=GREEN)
        d.text((842, y + 45), value, font=font(26), fill=INK)
    d.text((105, 1045), "Externally sourced style; confirm final order availability.", font=font(29), fill=SUB)
    rows.append(save(d1, "H16C_D1_overview.png", "C-specific product identity and sourcing", [KHAKI]))

    d2, d = sheet(1200, "REAL COLOR OPTIONS | EU 39-48", "Three photographs of one supplier article, not three shoe models")
    for i, (path, label) in enumerate(((KHAKI, "KHAKI"), (BLACK, "BLACK"), (EARTH, "EARTH YELLOW"))):
        x = 29 + 393 * i
        photo(d2, path, (x, 290, 362, 362))
        width = d.textbbox((0, 0), label, font=font(31, True))[2]
        d.text((x + (362 - width) // 2, 680), label, font=font(31, True), fill=INK)
    d.rounded_rectangle((198, 806, 1000, 923), radius=16, fill=GREEN)
    d.text((265, 844), "EU 39  40  41  42  43  44  45  46  47  48", font=font(29, True), fill="white")
    d.text((216, 1007), "Specify the required color-size ratio when requesting a quote.", font=font(27), fill=SUB)
    rows.append(save(d2, "H16C_D2_colors.png", "actual source colors and labels", [KHAKI, BLACK, EARTH]))

    d3, d = sheet(1200, "CLOSURE, LINING AND SOLE", "Supplier-stated material layers; actual photos show form")
    photo(d3, TREAD, (35, 250, 605, 605))
    d.rounded_rectangle((664, 256, 1163, 876), radius=20, fill=TINT)
    for i, line in enumerate(("Lace-up / Mid-top", "Mesh lining", "EVA midsole", "Rubber outsole")):
        d.text((696, 303 + i * 130), line, font=font(31, True), fill=INK)
    d.text((83, 1010), "Photos are appearance proof, not independent material tests.", font=font(28), fill=SUB)
    rows.append(save(d3, "H16C_D3_structure.png", "supplier materials and visible construction", [TREAD]))

    d4, d = sheet(1200, "REQUEST A STYLE 031 QUOTATION", "HR016-C | source availability and options checked per order")
    photo(d4, WEAR, (49, 235, 535, 535))
    d.rounded_rectangle((610, 241, 1152, 830), radius=20, fill=TINT)
    for i, line in enumerate(("01  Quantity + destination", "02  Color / EU size ratio", "03  Bag or box preference", "04  Logo / sample question")):
        d.text((639, 303 + i * 121), line, font=font(29), fill=INK)
    d.text((74, 960), "Price, customization, packing and lead time require confirmation.", font=font(27), fill=SUB)
    rows.append(save(d4, "H16C_D4_quote.png", "C-specific sourcing quote inputs", [WEAR]))

    manifest = {
        "made_at": datetime.now().astimezone().isoformat(),
        "state": "LOCAL_CANDIDATES_UNREVIEWED_NOT_UPLOADED",
        "source": "https://luqi.sooxie.com/detail/2454935",
        "items": rows,
    }
    manifest_path = OUT / "H16C_031_panels_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"images": [r["file"] for r in rows], "manifest": str(manifest_path.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
