from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(r"C:\Users\spq\Desktop\贝强\05_内容与视频\01_贝强商品视频\seedance\edit\BQ001\v11_en\inspect")
PHOTO_DIR = Path(
    r"C:\Users\spq\Desktop\贝强\01_产品资产\01_原始数据包\已整理_BQ001_5.13贝强1数据包\800X800主图"
)


def card(image_path: Path, size: tuple[int, int], image_box: tuple[int, int]) -> Image.Image:
    image = Image.open(image_path).convert("RGB")
    image.thumbnail(image_box)
    output = Image.new("RGB", size, "white")
    output.paste(image, ((size[0] - image.width) // 2, 8))
    ImageDraw.Draw(output).text((8, size[1] - 28), image_path.name, fill="black")
    return output


def contact_sheet(images: list[Image.Image], columns: int, background: tuple[int, int, int]) -> Image.Image:
    width, height = images[0].size
    rows = (len(images) + columns - 1) // columns
    output = Image.new("RGB", (columns * width, rows * height), background)
    for index, image in enumerate(images):
        output.paste(image, ((index % columns) * width, (index // columns) * height))
    return output


ROOT.mkdir(parents=True, exist_ok=True)
video_cards = [card(path, (260, 405), (240, 360)) for path in sorted(ROOT.glob("v*.png"))]
contact_sheet(video_cards, 4, (230, 230, 230)).save(ROOT / "video_contact.jpg", quality=92)

photo_paths = [
    path
    for path in sorted(PHOTO_DIR.iterdir())
    if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
]
photo_cards = [card(path, (240, 255), (220, 220)) for path in photo_paths]
contact_sheet(photo_cards, 5, (230, 230, 230)).save(ROOT / "photos_contact.jpg", quality=92)
