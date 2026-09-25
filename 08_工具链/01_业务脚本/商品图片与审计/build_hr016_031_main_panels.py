"""Compose HR016/031 buyer-question panels from exact supplier/company photos."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "99_临时区/HR016_031_公开货源图_2026-09-24"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR016_031"
COMPANY = ROOT / "02_Alibaba运营/06_图片与检查记录/公司图复用模板_v4_2026-09-21/C4_real_quality_checkpoints.jpg"
FONT = Path("C:/Windows/Fonts/arial.ttf")
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
INK = (25, 43, 52)
MUTED = (90, 104, 111)
BG = (250, 250, 248)


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (1000, 1000), BG)
    draw = ImageDraw.Draw(img)
    draw.text((46, 42), title, font=f(43, True), fill=INK)
    draw.text((48, 105), subtitle, font=f(23), fill=MUTED)
    return img, draw


def save(img: Image.Image, name: str, sources: list[Path], method: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    img.save(path, format="PNG", optimize=True)
    return {
        "output": str(path.relative_to(ROOT)),
        "output_sha256": digest(path),
        "output_bytes": path.stat().st_size,
        "sources": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in sources],
        "method": method,
    }


def main() -> None:
    shoes = [
        (SRC / "02_黑色_白底_来源图.jpg", "BLACK"),
        (SRC / "03_卡其_白底_来源图.jpg", "KHAKI"),
        (SRC / "01_土黄_白底_来源图.jpg", "EARTH YELLOW"),
    ]
    rows: list[dict] = []

    m2, d = new("THREE PHOTOGRAPHED COLORS", "One source style | EU 39-48")
    for i, (path, label) in enumerate(shoes):
        photo = Image.open(path).convert("RGB")
        if photo.size != (800, 800):
            raise ValueError((path, photo.size))
        resized = ImageOps.contain(photo, (300, 300), Image.Resampling.LANCZOS)
        x = 20 + i * 330
        m2.paste(resized, (x + (300 - resized.width) // 2, 245))
        width = d.textbbox((0, 0), label, font=f(27, True))[2]
        d.text((x + (300 - width) // 2, 590), label, font=f(27, True), fill=INK)
    d.rounded_rectangle((100, 735, 900, 825), radius=18, fill=INK)
    d.text((254, 758), "EU 39 40 41 42 43 44 45 46 47 48", font=f(26, True), fill=(255, 255, 255))
    d.text((171, 879), "Confirm your color and size mix per order.", font=f(28), fill=MUTED)
    rows.append(save(m2, "HR016_031_M2_colors.png", [x[0] for x in shoes],
                     "exact source photos; uniform scale and English layout; no generated shoe"))

    outdoor = SRC / "04_展示图_来源.jpg"
    original = Image.open(outdoor).convert("RGB")
    if original.size != (800, 800):
        raise ValueError((outdoor, original.size))
    m3, d = new("VISIBLE SHOE CONSTRUCTION", "Actual same-style upper and outsole view")
    m3.paste(original, (100, 155))
    d.text((69, 962), "Mid-top collar | Lace-up closure | Visible tread", font=f(27), fill=INK)
    rows.append(save(m3, "HR016_031_M3_construction.png", [outdoor],
                     "original 800x800 photo pasted without resampling; English labels outside photo"))

    wearing = SRC / "05_展示图_来源.jpg"
    original = Image.open(wearing).convert("RGB")
    if original.size != (800, 800):
        raise ValueError((wearing, original.size))
    m4, d = new("BLACK COLOR ON FOOT", "Real outdoor wear photo of this supplier style")
    m4.paste(original, (100, 155))
    d.text((153, 962), "Request your target size ratio and quantity.", font=f(27), fill=INK)
    rows.append(save(m4, "HR016_031_M4_black_wear.png", [wearing],
                     "original 800x800 photo pasted without resampling; English labels outside photo"))

    company = Image.open(COMPANY).convert("RGB")
    m5, d = new("BEIQIANG ORDER REVIEW", "General company workflow; not production of Luqi 031")
    fitted = ImageOps.contain(company, (790, 790), Image.Resampling.LANCZOS)
    m5.paste(fitted, ((1000 - fitted.width) // 2, 160))
    rows.append(save(m5, "HR016_031_M5_company_context.png", [COMPANY],
                     "real Beiqiang company photo collage with explicit sourced-shoe distinction"))

    manifest = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "status": "LOCAL_CANDIDATES_ONLY_NOT_UPLOADED",
        "source_product": "Sooxie Luqi 031",
        "items": rows,
    }
    path = OUT / "HR016_031_M2_M5_来源与方法.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
