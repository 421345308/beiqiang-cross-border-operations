from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 1920
FPS = 24
ROOT = Path(__file__).resolve().parent
FONT_PATH = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT = ImageFont.truetype(str(FONT_PATH), 50)
SMALL_FONT = ImageFont.truetype(str(FONT_PATH), 36)
YELLOW = (255, 221, 73, 235)
CYAN = (68, 224, 228, 220)
WHITE = (255, 255, 255, 240)
DARK = (18, 18, 18, 210)


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def label(draw: ImageDraw.ImageDraw, text: str, y: int, color=WHITE) -> None:
    box = draw.textbbox((0, 0), text, font=FONT)
    width = box[2] - box[0]
    x = (WIDTH - width) // 2
    draw.rounded_rectangle((x - 26, y - 14, x + width + 26, y + 66), 24, fill=DARK)
    draw.text((x, y), text, font=FONT, fill=color)


def save_frames(name: str, duration: float, painter) -> None:
    directory = ROOT / "overlays" / name
    directory.mkdir(parents=True, exist_ok=True)
    frame_count = round(duration * FPS)
    for frame in range(frame_count):
        image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        painter(ImageDraw.Draw(image), frame, frame_count)
        image.save(directory / f"frame_{frame:04d}.png")


def draw_partial(draw: ImageDraw.ImageDraw, points, progress: float, fill, width: int) -> None:
    progress = ease(progress)
    segment_count = max(1, round((len(points) - 1) * progress))
    draw.line(points[: segment_count + 1], fill=fill, width=width, joint="curve")


def toe_painter(draw: ImageDraw.ImageDraw, frame: int, count: int) -> None:
    label(draw, "WIDE, ROUNDED FRONT", 112, YELLOW)
    progress = min(1.0, frame / (FPS * 1.4))
    left = [(105, 1260), (90, 1380), (105, 1515), (175, 1640), (295, 1695), (430, 1650), (490, 1540)]
    right = [(590, 1540), (650, 1650), (785, 1695), (905, 1640), (975, 1515), (990, 1380), (975, 1260)]
    draw_partial(draw, left, progress, YELLOW, 11)
    draw_partial(draw, right, progress, YELLOW, 11)
    if progress >= 0.95:
        pulse = 5 + round(3 * math.sin(frame / FPS * math.pi * 2))
        draw.ellipse((262 - pulse, 1730 - pulse, 282 + pulse, 1750 + pulse), fill=YELLOW)
        draw.ellipse((798 - pulse, 1730 - pulse, 818 + pulse, 1750 + pulse), fill=YELLOW)


def knit_painter(draw: ImageDraw.ImageDraw, frame: int, count: int) -> None:
    label(draw, "BREATHABLE KNITTED UPPER", 112, CYAN)
    for column, x in enumerate((230, 420, 620, 810)):
        phase = (frame / FPS * 0.75 + column * 0.17) % 1.0
        for dot in range(4):
            local = (phase + dot * 0.22) % 1.0
            y = int(1370 - local * 680)
            radius = 5 + int(3 * (1.0 - local))
            alpha = int(210 * math.sin(local * math.pi))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(68, 224, 228, alpha))
        draw.line((x, 1370, x, 650), fill=(68, 224, 228, 70), width=3)


def collar_painter(draw: ImageDraw.ImageDraw, frame: int, count: int) -> None:
    label(draw, "CLEAN SLIP-ON OPENING", 112, YELLOW)
    progress = min(1.0, frame / (FPS * 1.2))
    start = -90
    end = start + int(360 * ease(progress))
    draw.arc((570, 390, 1010, 900), start=start, end=end, fill=YELLOW, width=12)
    if progress > 0.85:
        draw.rounded_rectangle((86, 1510, 510, 1620), 24, fill=DARK)
        draw.text((116, 1535), "NO LACES TO ADJUST", font=SMALL_FONT, fill=WHITE)


def sole_painter(draw: ImageDraw.ImageDraw, frame: int, count: int) -> None:
    label(draw, "LIGHTWEIGHT EVA SOLE", 112, CYAN)
    progress = min(1.0, frame / (FPS * 1.4))
    sole = [(85, 1290), (190, 1350), (350, 1390), (530, 1400), (710, 1360), (900, 1270), (1000, 1150)]
    draw_partial(draw, sole, progress, CYAN, 12)
    if progress > 0.9:
        for x in (250, 500, 750):
            offset = int(10 * math.sin(frame / FPS * math.pi * 2 + x))
            draw.line((x, 1450 + offset, x, 1510 + offset), fill=CYAN, width=7)
            draw.polygon(((x - 12, 1492 + offset), (x + 12, 1492 + offset), (x, 1516 + offset)), fill=CYAN)


save_frames("toe", 6.0, toe_painter)
save_frames("knit", 5.5, knit_painter)
save_frames("collar", 4.5, collar_painter)
save_frames("sole", 4.0, sole_painter)
