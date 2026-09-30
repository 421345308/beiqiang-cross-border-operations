"""Compose HR016/031 buyer-question panels from exact supplier/company photos."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "99_临时区/HR016_031_公开货源图_2026-09-24"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR016_031_buyer_v2"
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

    m2, d = new("THREE COLOR OPTIONS", "Black, Khaki and Earth Yellow | EU 39-48")
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
    rows.append(save(m2, "H16_M2_colors.png", [x[0] for x in shoes],
                     "exact source photos; uniform scale and English layout; no generated shoe"))

    manifest = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "status": "LOCAL_CANDIDATES_ONLY_NOT_UPLOADED",
        "source_product": "Sooxie Luqi 031",
        "items": rows,
    }
    path = OUT / "H16_M2_manifest.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
