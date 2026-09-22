from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "BQ019_W1_D7整组候选_2026-09-15" / "候选六图"
OUTPUT = ROOT / "BQ019_W1_D7整组候选_2026-09-15" / "BQ019-W1候选六图联系表.jpg"


def main() -> None:
    paths = sorted(SOURCE.glob("M*.jpg"))
    if len(paths) != 6:
        raise RuntimeError(f"Expected 6 images, found {len(paths)}")

    canvas = Image.new("RGB", (1800, 1240), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((560, 540), Image.Resampling.LANCZOS)
            col = index % 3
            row = index // 3
            x = col * 600 + (600 - image.width) // 2
            y = row * 620 + 20 + (540 - image.height) // 2
            canvas.paste(image, (x, y))
            draw.text((col * 600 + 20, row * 620 + 570), path.name, fill="black", font=font)

    canvas.save(OUTPUT, quality=92, subsampling=0)
    print(OUTPUT)


if __name__ == "__main__":
    main()
