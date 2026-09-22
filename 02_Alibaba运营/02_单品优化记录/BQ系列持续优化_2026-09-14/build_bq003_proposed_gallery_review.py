from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
PLAN = HERE / "BQ003标题六图执行计划_2026-09-15.json"
OUT = HERE / "BQ003_原始实拍筛选_2026-09-15"


def main() -> None:
    payload = json.loads(PLAN.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    for product in payload["products"]:
        canvas = Image.new("RGB", (1800, 650), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((18, 10), f'{product["product_id"]}  {product["expected_model"]}', fill="black", font=font)
        for i, raw in enumerate(product["image_files"], start=1):
            path = Path(raw)
            with Image.open(path) as source:
                image = source.convert("RGB")
                image.thumbnail((286, 550), Image.Resampling.LANCZOS)
            x = (i - 1) * 300 + (300 - image.width) // 2
            y = 42 + (550 - image.height) // 2
            canvas.paste(image, (x, y))
            draw.rectangle(((i - 1) * 300, 34, i * 300 - 1, 649), outline="#a0a0a0")
            draw.text(((i - 1) * 300 + 8, 606), f'M{i} {path.name}', fill="black", font=font)
        canvas.save(OUT / f'{product["product_id"]}_proposed_six.jpg', quality=94)


if __name__ == "__main__":
    main()
