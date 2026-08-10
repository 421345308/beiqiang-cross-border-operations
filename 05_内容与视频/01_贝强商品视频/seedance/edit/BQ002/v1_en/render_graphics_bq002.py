import argparse
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1080
HEIGHT = 1920
FPS = 24
BG = (239, 242, 240)
INK = (22, 24, 24)
MUTED = (91, 96, 94)
ACCENT = (216, 255, 82)
WHITE = (255, 255, 255)
FONT_BOLD = r"C:\Windows\Fonts\bahnschrift.ttf"
FONT_REGULAR = r"C:\Windows\Fonts\segoeui.ttf"
ROOT = Path(r"C:\Users\spq\Desktop\贝强\05_内容与视频\01_贝强商品视频\seedance\edit\BQ002\v1_en")
PHOTO_DIR = Path(
    r"C:\Users\spq\Desktop\贝强\01_产品资产\01_原始数据包\已整理_BQ002_5.13贝强2数据包\800X800主图"
)
COLOR_DIR = Path(
    r"C:\Users\spq\Desktop\贝强\01_产品资产\02_可发布素材\00_最终上传\BQ002_数据包2\03_颜色图"
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


def open_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def draw_pill(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, inverse: bool = False) -> None:
    text_font = font(27, True)
    box = draw.textbbox((0, 0), text, font=text_font)
    width = box[2] - box[0] + 50
    fill = ACCENT if inverse else INK
    color = INK if inverse else ACCENT
    draw.rounded_rectangle((x, y, x + width, y + 60), radius=30, fill=fill)
    draw.text((x + 25, y + 14), text, font=text_font, fill=color)


def paste_contain(
    canvas: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    zoom: float = 1.0,
    offset: tuple[int, int] = (0, 0),
) -> None:
    left, top, right, bottom = box
    available_width = right - left
    available_height = bottom - top
    scale = min(available_width / image.width, available_height / image.height) * zoom
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x = left + (available_width - resized.width) // 2 + offset[0]
    y = top + (available_height - resized.height) // 2 + offset[1]
    canvas.alpha_composite(resized, (x, y))


def paste_cover(
    canvas: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    zoom: float = 1.0,
    focus: tuple[float, float] = (0.5, 0.5),
) -> None:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    scale = max(width / image.width, height / image.height) * zoom
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x = max(0, min(round((resized.width - width) * focus[0]), resized.width - width))
    y = max(0, min(round((resized.height - height) * focus[1]), resized.height - height))
    canvas.alpha_composite(resized.crop((x, y, x + width, y + height)), (left, top))


def rounded_image(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width, image.height), radius, fill=255)
    result = image.copy()
    result.putalpha(mask)
    return result


def render(name: str, duration: float, builder) -> None:
    output = ROOT / name
    command = [
        str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-pix_fmt", "yuv420p",
        "-g", "48", "-keyint_min", "48", "-sc_threshold", "0", "-movflags", "+faststart", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame_index in range(round(duration * FPS)):
        process.stdin.write(builder(frame_index / FPS, duration).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"Failed to render {output}")


def base_header(canvas: Image.Image, kicker: str, title: str, subtitle: str | None = None) -> None:
    draw = ImageDraw.Draw(canvas)
    draw_pill(draw, kicker, 66, 88, inverse=True)
    draw.multiline_text((66, 188), title, font=font(76, True), fill=INK, spacing=-5)
    if subtitle:
        draw.text((68, 380), subtitle, font=font(34), fill=MUTED)


def build_hook(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 86), "PICK YOUR", font=font(74, True), fill=INK)
    draw.text((64, 166), "SOLE COLOR", font=font(102, True), fill=INK)
    draw.rectangle((64, 302, 620, 318), fill=ACCENT)
    slot = min(2, int(time / 0.8))
    paths = [COLOR_DIR / "grey_white.jpg", COLOR_DIR / "grey_black.jpg", COLOR_DIR / "grey_khaki.jpg"]
    labels = ["01  GREY / WHITE", "02  GREY / BLACK", "03  GREY / KHAKI"]
    colors = [(229, 232, 229), (205, 209, 208), (224, 215, 194)]
    local = (time - slot * 0.8) / 0.8
    slide = round((1 - ease_out(local / 0.35)) * 120)
    panel = Image.new("RGBA", (956, 1030), colors[slot] + (255,))
    product = open_image(paths[slot])
    paste_contain(panel, product, (25, 45, 931, 930), 1.05, (slide, round(12 * math.sin(time * 3))))
    panel = rounded_image(panel, 48)
    canvas.alpha_composite(panel, (62, 390))
    draw_pill(draw, labels[slot], 72, 1465)
    draw.text((68, 1582), "ONE UPPER. THREE DIRECTIONS.", font=font(36, True), fill=INK)
    return canvas


def build_toe(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    base_header(canvas, "DETAIL CHECK", "ROOMY,\nROUNDED FRONT", "A clear comfort-shoe silhouette.")
    reveal = ease_out(time / 0.55)
    top_x = round(52 + (1 - reveal) * 180)
    top_panel = Image.new("RGBA", (976, 730), WHITE + (255,))
    paste_contain(top_panel, open_image(PHOTO_DIR / "5M4A1148.JPG"), (20, 20, 956, 710), 1.18, (round(10 * math.sin(time)), 0))
    canvas.alpha_composite(rounded_image(top_panel, 42), (top_x, 510))
    side_reveal = ease_out((time - 0.28) / 0.55)
    side_y = round(1320 + (1 - side_reveal) * 120)
    side_panel = Image.new("RGBA", (760, 380), WHITE + (255,))
    paste_contain(side_panel, open_image(PHOTO_DIR / "5M4A1145.JPG"), (10, 0, 750, 370), 1.08)
    canvas.alpha_composite(rounded_image(side_panel, 38), (258, side_y))
    ImageDraw.Draw(canvas).text((68, 1608), "TOP VIEW  +  SIDE PROFILE", font=font(29, True), fill=MUTED)
    return canvas


def build_upper(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), INK + (255,))
    draw = ImageDraw.Draw(canvas)
    draw_pill(draw, "TEXTURE", 62, 88, inverse=True)
    draw.multiline_text((62, 190), "KNITTED\nSLIP-ON UPPER", font=font(72, True), fill=WHITE, spacing=-4)
    source = open_image(PHOTO_DIR / "5M4A1148.JPG")
    upper_panel = Image.new("RGBA", (956, 900), (0, 0, 0, 0))
    paste_cover(upper_panel, source, (0, 0, 956, 900), 1.72 + 0.03 * ease_in_out(time / duration), (0.58, 0.46))
    canvas.alpha_composite(rounded_image(upper_panel, 42), (62, 530))
    heel_source = open_image(PHOTO_DIR / "5M4A1145.JPG")
    detail = Image.new("RGBA", (470, 340), (0, 0, 0, 0))
    paste_cover(detail, heel_source, (0, 0, 470, 340), 2.35, (0.88, 0.36))
    detail = rounded_image(detail, 34)
    x = round(548 + (1 - ease_out((time - 0.45) / 0.6)) * 190)
    canvas.alpha_composite(detail, (x, 1260))
    draw_pill(draw, "HEEL PULL TAB", 72, 1490)
    return canvas


def build_sole(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    base_header(canvas, "UNDERFOOT", "TEXTURED,\nCUSHIONED SOLE", "Visible profile and outsole pattern.")
    ImageDraw.Draw(canvas).rectangle((68, 452, 248 + round(96 * time / duration), 464), fill=ACCENT)
    side = Image.new("RGBA", (956, 620), WHITE + (255,))
    paste_contain(side, open_image(PHOTO_DIR / "5M4A1145.JPG"), (16, 0, 940, 600), 1.12)
    side_x = round(62 + (1 - ease_out(time / 0.55)) * -180)
    canvas.alpha_composite(rounded_image(side, 42), (side_x, 520))
    outsole = Image.new("RGBA", (956, 500), WHITE + (255,))
    paste_contain(outsole, open_image(PHOTO_DIR / "5M4A1146.JPG"), (25, 10, 931, 480), 1.2)
    outsole_x = round(62 + (1 - ease_out((time - 0.3) / 0.6)) * 180)
    canvas.alpha_composite(rounded_image(outsole, 42), (outsole_x, 1210))
    return canvas


def build_poll(time: float, duration: float) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 82), "1, 2 OR 3?", font=font(104, True), fill=INK)
    draw.text((68, 208), "COMMENT YOUR PICK", font=font(42, True), fill=MUTED)
    paths = [COLOR_DIR / "grey_white.jpg", COLOR_DIR / "grey_black.jpg", COLOR_DIR / "grey_khaki.jpg"]
    labels = ["1  CLEAN", "2  PRACTICAL", "3  WARM"]
    top_positions = [365, 825, 1285]
    for index, (path, label, top) in enumerate(zip(paths, labels, top_positions)):
        reveal = ease_out((time - index * 0.18) / 0.6)
        left = round(62 + (1 - reveal) * (180 if index % 2 == 0 else -180))
        panel = Image.new("RGBA", (956, 390), WHITE + (255,))
        ImageDraw.Draw(panel).text((42, 52), label, font=font(36, True), fill=INK)
        paste_contain(panel, open_image(path), (260, 0, 930, 375), 0.95)
        canvas.alpha_composite(rounded_image(panel, 38), (left, top))
    return canvas


ROOT.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("--only", choices=["hook", "toe", "upper", "sole", "poll"])
args = parser.parse_args()
renders = {
    "hook": ("01_hook.mp4", 59 / 24, build_hook),
    "toe": ("05_toe.mp4", 73 / 24, build_toe),
    "upper": ("06_upper.mp4", 68 / 24, build_upper),
    "sole": ("07_sole.mp4", 68 / 24, build_sole),
    "poll": ("08_poll.mp4", 4.4, build_poll),
}
for key, spec in renders.items():
    if args.only is None or args.only == key:
        render(*spec)
