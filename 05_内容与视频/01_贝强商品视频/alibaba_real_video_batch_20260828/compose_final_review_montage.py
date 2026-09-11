from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\Users\spq\Desktop\贝强\05_内容与视频\01_贝强商品视频\alibaba_real_video_batch_20260828")
SHEETS = ROOT / "review_sheets"
paths = sorted(SHEETS.glob("BQ*_final.jpg"))

cell_w, image_h, label_h = 960, 135, 30
cols = 2
rows = (len(paths) + cols - 1) // cols
canvas = Image.new("RGB", (cell_w * cols, (image_h + label_h) * rows), "white")
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)

for index, path in enumerate(paths):
    image = Image.open(path).convert("RGB")
    image.thumbnail((cell_w, image_h), Image.Resampling.LANCZOS)
    x = (index % cols) * cell_w
    y = (index // cols) * (image_h + label_h)
    canvas.paste(image, (x + (cell_w - image.width) // 2, y))
    draw.text((x + 8, y + image_h + 2), path.stem.split("_")[0], fill="black", font=font)

output = SHEETS / "final_videos_montage.jpg"
canvas.save(output, quality=92)
print(output)
