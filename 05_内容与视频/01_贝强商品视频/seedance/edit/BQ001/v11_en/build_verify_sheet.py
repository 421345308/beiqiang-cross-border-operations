from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(r"C:\Users\spq\Desktop\贝强\05_内容与视频\01_贝强商品视频\seedance\edit\BQ001\v11_en\verify")
paths = sorted(ROOT.glob("frame_*.png"))
cards = []
for path in paths:
    image = Image.open(path).convert("RGB")
    image.thumbnail((240, 427))
    card = Image.new("RGB", (260, 470), "white")
    card.paste(image, ((260 - image.width) // 2, 5))
    ImageDraw.Draw(card).text((8, 440), path.stem, fill="black")
    cards.append(card)
columns = 5
rows = (len(cards) + columns - 1) // columns
sheet = Image.new("RGB", (columns * 260, rows * 470), (225, 225, 225))
for index, card in enumerate(cards):
    sheet.paste(card, ((index % columns) * 260, (index // columns) * 470))
sheet.save(ROOT / "verify_contact.jpg", quality=94)
