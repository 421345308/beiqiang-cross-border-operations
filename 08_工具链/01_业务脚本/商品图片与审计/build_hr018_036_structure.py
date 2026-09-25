"""Build two product-true HR018/036 structure panels from supplier pixels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "99_临时区/HR018_候选核验/路崎036_详情原图"
OUT = ROOT / "02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/06_确定性图稿/HR018_036"
BOLD = "C:/Windows/Fonts/arialbd.ttf"
REG = "C:/Windows/Fonts/arial.ttf"


def header(draw: ImageDraw.ImageDraw, title: str, sub: str) -> None:
    draw.text((50, 43), title, font=ImageFont.truetype(BOLD, 43), fill=(31, 45, 55))
    draw.text((52, 102), sub, font=ImageFont.truetype(REG, 25), fill=(89, 102, 110))


def save(panel: Image.Image, name: str, source: Path, crop: tuple[int, int, int, int], note: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    panel.save(path, format="PNG", optimize=True)
    return {
        "output": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source": str(source.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_crop": list(crop),
        "method": note,
    }


def main() -> None:
    reports = []
    top_path = SRC / "es4kmcjclgjv1vv08q0a7zdci7b5k1tq.jpg"
    top = Image.open(top_path).convert("RGB")
    top_crop = (0, 340, 790, 1102)  # Only real shoes; source's wide-foot text is above.
    top_photo = ImageOps.contain(top.crop(top_crop), (900, 820), Image.Resampling.LANCZOS)
    m3 = Image.new("RGB", (1000, 1000), (250, 250, 248))
    m3_draw = ImageDraw.Draw(m3)
    header(m3_draw, "MESH UPPER", "Lace-up closure | Black colorway")
    m3.paste(top_photo, ((1000 - top_photo.width) // 2, 170))
    reports.append(save(m3, "HR018_036_M3_upper_lace.png", top_path, top_crop,
                        "deterministic crop, scale, English labels; shoe pixels not redrawn"))

    sole_path = SRC / "gynr7vooge3wrg4qtabeni6b75xim6pe.jpg"
    sole = Image.open(sole_path).convert("RGB")
    sole_crop = (0, 400, 790, 1130)
    sole_photo = ImageOps.contain(sole.crop(sole_crop), (900, 820), Image.Resampling.LANCZOS)
    m4 = Image.new("RGB", (1000, 1000), (250, 250, 248))
    m4_draw = ImageDraw.Draw(m4)
    header(m4_draw, "OUTSOLE TREAD", "Actual underside view | Original product photo")
    origin = ((1000 - sole_photo.width) // 2, 170)
    m4.paste(sole_photo, origin)
    # A source-side Chinese performance claim/logo sits in the empty rock area,
    # not on the outsole. Cover that area with a neutral English evidence card.
    card = (650, 770, 965, 982)
    m4_draw.rounded_rectangle(card, radius=15, fill=(250, 250, 248), outline=(205, 214, 215), width=2)
    m4_draw.text((678, 831), "REAL SHOE", font=ImageFont.truetype(BOLD, 31), fill=(31, 45, 55))
    m4_draw.text((678, 876), "TREAD VIEW", font=ImageFont.truetype(REG, 27), fill=(89, 102, 110))
    reports.append(save(m4, "HR018_036_M4_outsole.png", sole_path, sole_crop,
                        "deterministic crop, scale and card over background-only Chinese claim; outsole pixels unchanged"))
    print(json.dumps({"status": "LOCAL_QA_REQUIRED_NOT_UPLOADED", "assets": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
