from pathlib import Path

from PIL import Image, ImageDraw


root = Path(__file__).parent
frames = sorted(root.glob("inspect_*.png"))
cards = []
for path in frames:
    image = Image.open(path).convert("RGB")
    image.thumbnail((216, 384))
    card = Image.new("RGB", (232, 425), "white")
    card.paste(image, ((232 - image.width) // 2, 4))
    ImageDraw.Draw(card).text((6, 398), path.stem, fill="black")
    cards.append(card)
columns = 5
rows = (len(cards) + columns - 1) // columns
sheet = Image.new("RGB", (columns * 232, rows * 425), (225, 225, 225))
for index, card in enumerate(cards):
    sheet.paste(card, ((index % columns) * 232, (index // columns) * 425))
sheet.save(root / "source_contact.jpg", quality=94)
