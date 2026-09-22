from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WORKSPACE = Path(r"C:\Users\spq\Desktop\贝强")
SOURCE = WORKSPACE / (
    "01_产品资产/01_原始数据包/"
    "已整理_BQ003_R1218_贝强鞋业2026夏季R1218镂空包头板鞋35-45批55元/"
    "贝强鞋业2026夏季R1218镂空包头板鞋35-45批55元/800X800主图"
)
OUTPUT = WORKSPACE / (
    "02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/"
    "BQ003_原始实拍筛选_2026-09-15"
)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = sorted(
        [p for p in SOURCE.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}],
        key=lambda p: p.name.lower(),
    )
    per_page = 30
    cols, rows = 5, 6
    cell_w, cell_h = 340, 330
    font = ImageFont.load_default()

    for page_index, start in enumerate(range(0, len(files), per_page), start=1):
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(sheet)
        for offset, path in enumerate(files[start : start + per_page]):
            row, col = divmod(offset, cols)
            x, y = col * cell_w, row * cell_h
            with Image.open(path) as source:
                image = source.convert("RGB")
                image.thumbnail((cell_w - 20, cell_h - 48), Image.Resampling.LANCZOS)
                px = x + (cell_w - image.width) // 2
                py = y + 8 + (cell_h - 48 - image.height) // 2
                sheet.paste(image, (px, py))
            draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline="#b8b8b8", width=1)
            draw.text((x + 8, y + cell_h - 34), path.name, fill="black", font=font)
        sheet.save(OUTPUT / f"BQ003_source_contact_{page_index}.jpg", quality=92)


if __name__ == "__main__":
    main()
