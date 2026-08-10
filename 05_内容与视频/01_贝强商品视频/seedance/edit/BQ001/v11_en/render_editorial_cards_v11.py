import argparse
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1080
HEIGHT = 1920
FPS = 24
BACKGROUND = (244, 240, 232)
INK = (35, 34, 31)
MUTED = (103, 99, 91)
ACCENT = (204, 158, 67)
PANEL = (252, 250, 246)
FONT_REGULAR = r"C:\Windows\Fonts\segoeui.ttf"
FONT_BOLD = r"C:\Windows\Fonts\bahnschrift.ttf"
ROOT = Path(r"C:\Users\spq\Desktop\贝强\05_内容与视频\01_贝强商品视频\seedance\edit\BQ001\v11_en")
PHOTO_DIR = Path(
    r"C:\Users\spq\Desktop\贝强\01_产品资产\01_原始数据包\已整理_BQ001_5.13贝强1数据包\800X800主图"
)
COLOR_DIR = Path(
    r"C:\Users\spq\Desktop\贝强\01_产品资产\02_可发布素材\00_最终上传\BQ001_数据包1\03_颜色图"
)
FFMPEG = Path(
    r"C:\Users\spq\AppData\Roaming\Python\Python311\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def ease_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


def ease_in_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value < 0.5:
        return 4 * value**3
    return 1 - (-2 * value + 2) ** 3 / 2


def with_opacity(layer: Image.Image, opacity: float) -> Image.Image:
    layer = layer.copy()
    alpha = layer.getchannel("A").point(lambda value: round(value * opacity))
    layer.putalpha(alpha)
    return layer


def rounded_panel(canvas: Image.Image, box: tuple[int, int, int, int], radius: int = 34) -> None:
    left, top, right, bottom = box
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((left + 2, top + 14, right + 2, bottom + 14), radius, fill=(28, 25, 20, 35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    canvas.alpha_composite(shadow)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius, fill=PANEL + (255,))


def paste_contain(
    canvas: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
    zoom: float = 1.0,
    offset: tuple[int, int] = (0, 0),
) -> None:
    left, top, right, bottom = box
    available_width = right - left
    available_height = bottom - top
    scale = min(available_width / source.width, available_height / source.height) * zoom
    size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    resized = source.resize(size, Image.Resampling.LANCZOS)
    x = left + (available_width - resized.width) // 2 + offset[0]
    y = top + (available_height - resized.height) // 2 + offset[1]
    canvas.alpha_composite(resized, (x, y))


def paste_cover(
    canvas: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
    zoom: float = 1.0,
    focus: tuple[float, float] = (0.5, 0.5),
) -> None:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    scale = max(width / source.width, height / source.height) * zoom
    resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    crop_left = round((resized.width - width) * focus[0])
    crop_top = round((resized.height - height) * focus[1])
    crop_left = max(0, min(crop_left, resized.width - width))
    crop_top = max(0, min(crop_top, resized.height - height))
    canvas.alpha_composite(resized.crop((crop_left, crop_top, crop_left + width, crop_top + height)), (left, top))


def header_layer(number: str, title: str, subtitle: str) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.text((74, 88), number, font=font(30, True), fill=ACCENT + (255,))
    draw.line((132, 108, 1004, 108), fill=(189, 182, 168, 255), width=2)
    draw.multiline_text((74, 168), title, font=font(69, True), fill=INK + (255,), spacing=0)
    draw.multiline_text((74, 345), subtitle, font=font(35), fill=MUTED + (255,), spacing=10)
    return layer


def label(canvas: Image.Image, text: str, x: int, y: int) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((x, y, x + 246, y + 58), 29, fill=(37, 35, 31, 235))
    draw.text((x + 22, y + 15), text, font=font(23, True), fill=(255, 255, 255, 255))


def open_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def render_video(name: str, duration: float, frame_builder) -> None:
    output = ROOT / name
    command = [
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-pix_fmt", "yuv420p",
        "-g", "48", "-keyint_min", "48", "-sc_threshold", "0", "-movflags", "+faststart", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    frame_count = round(duration * FPS)
    for frame_index in range(frame_count):
        time = frame_index / FPS
        process.stdin.write(frame_builder(time, duration).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"Failed to render {output}")


def build_shape(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND + (255,))
    header = header_layer("01", "A WIDER,\nROUNDED FRONT", "More room where the forefoot needs it.")
    canvas.alpha_composite(with_opacity(header, ease_out(time / 0.55)))
    reveal = ease_out((time - 0.18) / 0.72)
    float_offset = round(6 * math.sin(time * 1.1))
    top_y = round(530 + (1 - reveal) * 110)
    side_y = round(1130 + (1 - ease_out((time - 0.36) / 0.72)) * 110)
    top_box = (70, top_y, 1010, top_y + 530)
    side_box = (70, side_y, 1010, side_y + 520)
    rounded_panel(canvas, top_box)
    rounded_panel(canvas, side_box)
    paste_contain(canvas, open_rgba(PHOTO_DIR / "5M4A1124.JPG"), (105, top_y + 15, 975, top_y + 500), 1.12, (0, float_offset))
    paste_contain(canvas, open_rgba(PHOTO_DIR / "5M4A1119.JPG"), (105, side_y + 10, 975, side_y + 485), 1.10, (0, -float_offset))
    label(canvas, "TOP VIEW", 96, top_y + 34)
    label(canvas, "SIDE PROFILE", 96, side_y + 34)
    return canvas


def build_knit(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND + (255,))
    header = header_layer("02", "SOFT KNITTED\nUPPER", "Flexible texture with visible breathable zones.")
    canvas.alpha_composite(with_opacity(header, ease_out(time / 0.55)))
    main_reveal = ease_out((time - 0.18) / 0.75)
    main_y = round(540 + (1 - main_reveal) * 120)
    main_box = (70, main_y, 1010, main_y + 1010)
    rounded_panel(canvas, main_box)
    macro = open_rgba(ROOT / "inspect" / "v2_3_2.png")
    mask = Image.new("L", (940, 1010), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 940, 1010), 34, fill=255)
    image_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    paste_cover(image_layer, macro, main_box, 1.02 + 0.015 * ease_in_out(time / duration), (0.49, 0.48))
    image_layer.putalpha(Image.new("L", canvas.size, 0))
    cropped = Image.new("RGBA", (940, 1010), (0, 0, 0, 0))
    paste_cover(cropped, macro, (0, 0, 940, 1010), 1.08, (0.49, 0.46))
    cropped.putalpha(mask)
    canvas.alpha_composite(cropped, (70, main_y))
    inset_reveal = ease_out((time - 0.68) / 0.65)
    inset_x = round(544 + (1 - inset_reveal) * 170)
    inset_box = (inset_x, main_y + 655, inset_x + 402, main_y + 962)
    rounded_panel(canvas, inset_box, 28)
    inset = Image.new("RGBA", (402, 307), (0, 0, 0, 0))
    paste_cover(inset, macro, (0, 0, 402, 307), 2.6, (0.51, 0.56))
    inset_mask = Image.new("L", inset.size, 0)
    ImageDraw.Draw(inset_mask).rounded_rectangle((0, 0, 402, 307), 28, fill=255)
    inset.putalpha(inset_mask)
    canvas.alpha_composite(inset, (inset_x, main_y + 655))
    label(canvas, "REAL KNIT DETAIL", 96, main_y + 58)
    return canvas


def build_slipon(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND + (255,))
    header = header_layer("03", "CLEAN SLIP-ON\nOPENING", "No laces to adjust for everyday wear.")
    canvas.alpha_composite(with_opacity(header, ease_out(time / 0.55)))
    reveal = ease_out((time - 0.2) / 0.7)
    top_y = round(550 + (1 - reveal) * 110)
    top_box = (70, top_y, 1010, top_y + 630)
    rounded_panel(canvas, top_box)
    paste_contain(canvas, open_rgba(PHOTO_DIR / "5M4A1119.JPG"), (95, top_y + 20, 985, top_y + 590), 1.16, (0, round(5 * math.sin(time))))
    detail_reveal = ease_out((time - 0.55) / 0.7)
    detail_y = round(1250 + (1 - detail_reveal) * 120)
    detail_box = (70, detail_y, 1010, detail_y + 430)
    rounded_panel(canvas, detail_box)
    top_view = open_rgba(PHOTO_DIR / "5M4A1124.JPG").crop((0, 150, 470, 650))
    detail = Image.new("RGBA", (940, 430), (0, 0, 0, 0))
    paste_cover(detail, top_view, (0, 0, 940, 430), 1.05, (0.48, 0.5))
    detail_mask = Image.new("L", detail.size, 0)
    ImageDraw.Draw(detail_mask).rounded_rectangle((0, 0, 940, 430), 34, fill=255)
    detail.putalpha(detail_mask)
    canvas.alpha_composite(detail, (70, detail_y))
    label(canvas, "OPEN COLLAR", 96, detail_y + 32)
    return canvas


def build_sole(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND + (255,))
    header = header_layer("04", "LIGHTWEIGHT\nEVA SOLE", "Built for daily walking, commuting, and travel.")
    canvas.alpha_composite(with_opacity(header, ease_out(time / 0.55)))
    reveal = ease_out((time - 0.18) / 0.72)
    side_y = round(560 + (1 - reveal) * 120)
    side_box = (70, side_y, 1010, side_y + 620)
    rounded_panel(canvas, side_box)
    paste_contain(canvas, open_rgba(PHOTO_DIR / "5M4A1120.JPG"), (90, side_y + 15, 990, side_y + 575), 1.12)
    sole_reveal = ease_out((time - 0.5) / 0.75)
    sole_y = round(1260 + (1 - sole_reveal) * 120)
    sole_box = (70, sole_y, 1010, sole_y + 410)
    rounded_panel(canvas, sole_box)
    paste_contain(canvas, open_rgba(PHOTO_DIR / "5M4A1121.JPG"), (105, sole_y + 20, 975, sole_y + 380), 1.2)
    label(canvas, "OUTSOLE VIEW", 96, sole_y + 30)
    return canvas


def build_colors(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND + (255,))
    header = header_layer("05", "THREE PRACTICAL\nCOLORS", "Black, black/white, and white.")
    canvas.alpha_composite(with_opacity(header, ease_out(time / 0.4)))
    paths = [COLOR_DIR / "all_black.jpg", COLOR_DIR / "black_white.jpg", COLOR_DIR / "white.jpg"]
    names = ["BLACK", "BLACK / WHITE", "WHITE"]
    positions = [(70, 555, 1010, 885), (70, 945, 1010, 1275), (70, 1335, 1010, 1665)]
    for index, (path, name, target_box) in enumerate(zip(paths, names, positions)):
        reveal = ease_out((time - 0.12 - index * 0.16) / 0.5)
        left, top, right, bottom = target_box
        animated_left = round(left + (1 - reveal) * (180 if index % 2 == 0 else -180))
        animated_right = animated_left + (right - left)
        box = (animated_left, top, animated_right, bottom)
        rounded_panel(canvas, box)
        paste_contain(canvas, open_rgba(path), (animated_left + 210, top + 10, animated_right - 20, bottom - 10), 0.9)
        draw = ImageDraw.Draw(canvas)
        draw.text((animated_left + 44, top + 117), f"0{index + 1}", font=font(25, True), fill=ACCENT + (255,))
        draw.text((animated_left + 44, top + 166), name, font=font(31, True), fill=INK + (255,))
    return canvas


ROOT.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("--only", choices=["shape", "knit", "slipon", "sole", "colors"])
args = parser.parse_args()
renders = {
    "shape": ("02_shape_card.mp4", 5.5, build_shape),
    "knit": ("03_knit_card.mp4", 5.0, build_knit),
    "slipon": ("04_slipon_card.mp4", 4.5, build_slipon),
    "sole": ("05_sole_card.mp4", 4.0, build_sole),
    "colors": ("07_colors_card.mp4", 2.5, build_colors),
}
for key, render in renders.items():
    if args.only is None or args.only == key:
        render_video(*render)
