from pathlib import Path
from PIL import Image


ROOT = Path(r"E:\贝强大文件\03_国际站批量发品临时\全量三链接_2026-08-29")


def main() -> None:
    converted = 0
    for batch_no in range(7, 12):
        batch = next(ROOT.glob(f"批次{batch_no:02d}_*"))
        upload_dir = batch / "01_上传文件"
        for source in upload_dir.glob("*.webp"):
            target = source.with_suffix(".jpg")
            with Image.open(source) as image:
                rgb = image.convert("RGB")
                rgb.save(target, "JPEG", quality=94, optimize=True)
            converted += 1
    print(f"converted={converted}")


if __name__ == "__main__":
    main()
