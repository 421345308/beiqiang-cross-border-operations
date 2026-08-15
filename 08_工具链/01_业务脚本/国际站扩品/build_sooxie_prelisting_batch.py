#!/usr/bin/env python3
"""Build upload-ready Alibaba.com asset folders from audited Sooxie packages.

This is a deterministic production script: it only crops, normalizes and
composes real source images. It does not generate or alter shoe structures.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


MAIN_NAMES = [
    "01_main.jpg",
    "02_upper.jpg",
    "03_structure.jpg",
    "04_sole.jpg",
    "05_colors.jpg",
    "06_scene.jpg",
]
DETAIL_NAMES = [
    "01_product_overview.jpg",
    "02_specifications.jpg",
    "03_size_range.jpg",
    "04_color_options.jpg",
    "05_order_support.jpg",
    "06_oem_inquiry.jpg",
]
FORBIDDEN_PUBLIC_TERMS = [
    "wide toe",
    "wide fit",
    "orthopedic",
    "medical",
    "diabetic",
    "bunion",
    "barefoot",
    "waterproof",
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return value or "color"


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=face) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    face: ImageFont.ImageFont,
    fill: str | tuple[int, int, int],
    width: int,
    spacing: int = 10,
) -> int:
    x, y = xy
    line_height = face.getbbox("Ag")[3] - face.getbbox("Ag")[1]
    for line in wrap(draw, text, face, width):
        draw.text((x, y), line, font=face, fill=fill)
        y += line_height + spacing
    return y


def source_path(raw_root: Path, source: str, index: int) -> Path:
    folder = raw_root / source / "原图"
    matches = sorted(folder.glob(f"{index:02d}.*"))
    if not matches:
        raise FileNotFoundError(f"Missing source image: {source}/{index:02d}")
    return matches[0]


def open_source(raw_root: Path, default_source: str, spec: int | dict[str, Any]) -> tuple[Image.Image, Path]:
    if isinstance(spec, int):
        source = default_source
        index = spec
        crop = None
    else:
        source = str(spec.get("source", default_source))
        index = int(spec["index"])
        crop = spec.get("crop")
    path = source_path(raw_root, source, index)
    with Image.open(path) as image:
        result = ImageOps.exif_transpose(image).convert("RGB")
    if crop:
        if len(crop) != 4 or not all(0 <= float(value) <= 1 for value in crop):
            raise ValueError(f"Invalid normalized crop for {source}/{index}: {crop}")
        left = int(result.width * float(crop[0]))
        top = int(result.height * float(crop[1]))
        right = int(result.width * float(crop[2]))
        bottom = int(result.height * float(crop[3]))
        if right <= left or bottom <= top:
            raise ValueError(f"Empty crop for {source}/{index}: {crop}")
        result = result.crop((left, top, right, bottom))
    return result, path


def fit_on_white(image: Image.Image, size: tuple[int, int], margin: int = 36) -> Image.Image:
    canvas = Image.new("RGB", size, "white")
    fitted = ImageOps.contain(
        image,
        (size[0] - margin * 2, size[1] - margin * 2),
        Image.Resampling.LANCZOS,
    )
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def save_jpg(image: Image.Image, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "JPEG", quality=quality, optimize=True, progressive=True)


def draw_header(draw: ImageDraw.ImageDraw, eyebrow: str, title: str, subtitle: str = "") -> int:
    draw.text((70, 54), eyebrow.upper(), font=font(24, True), fill="#16705a")
    y = draw_wrapped(draw, (70, 94), title, font(54, True), "#17212b", 1060, 8)
    if subtitle:
        y = draw_wrapped(draw, (70, y + 10), subtitle, font(28), "#53606d", 1060, 8)
    return y


def paste_image(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    width = box[2] - box[0]
    height = box[3] - box[1]
    fitted = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
    x = box[0] + (width - fitted.width) // 2
    y = box[1] + (height - fitted.height) // 2
    canvas.paste(fitted, (x, y))


def color_card(
    product: dict[str, Any],
    raw_root: Path,
    size: tuple[int, int],
    show_header: bool = True,
) -> Image.Image:
    canvas = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(canvas)
    width, height = size
    top = 48
    if show_header:
        draw.text((50, 38), "AVAILABLE COLOR OPTIONS", font=font(32, True), fill="#17212b")
        draw.text((50, 84), "Select colors and size ratio when sending an inquiry", font=font(20), fill="#66737f")
        top = 126
    colors = product["colors"]
    sources = product["color_sources"]
    columns = 4 if len(colors) > 6 else 3
    rows = (len(colors) + columns - 1) // columns
    gap = 16
    cell_w = (width - 100 - gap * (columns - 1)) // columns
    cell_h = (height - top - 42 - gap * (rows - 1)) // rows
    for idx, (name, spec) in enumerate(zip(colors, sources, strict=True)):
        row, col = divmod(idx, columns)
        x = 50 + col * (cell_w + gap)
        y = top + row * (cell_h + gap)
        draw.rounded_rectangle((x, y, x + cell_w, y + cell_h), radius=18, fill="#f5f7f8", outline="#dce2e6", width=2)
        source, _ = open_source(raw_root, product["sources"][0], spec)
        image_height = max(80, cell_h - 58)
        fitted = ImageOps.contain(source, (cell_w - 18, image_height - 12), Image.Resampling.LANCZOS)
        px = x + (cell_w - fitted.width) // 2
        py = y + 8 + (image_height - fitted.height) // 2
        canvas.paste(fitted, (px, py))
        label = name
        face = font(18, True)
        while draw.textlength(label, font=face) > cell_w - 16 and getattr(face, "size", 18) > 12:
            face = font(getattr(face, "size", 18) - 1, True)
        draw.text((x + cell_w // 2, y + cell_h - 34), label, anchor="mm", font=face, fill="#27333e")
    return canvas


def make_overview(product: dict[str, Any], hero: Image.Image, sizes: list[str]) -> Image.Image:
    canvas = Image.new("RGB", (1200, 1200), "white")
    draw = ImageDraw.Draw(canvas)
    y = draw_header(draw, product["code"], product["group"], "Factory supply for importers, wholesalers, online sellers and private-label buyers")
    paste_image(canvas, hero, (70, y + 30, 1130, 890))
    chips = ["REGULAR FIT", product["closure"].upper(), f"EU {sizes[0]}-{sizes[-1]}"]
    x = 70
    for chip in chips:
        chip_width = int(draw.textlength(chip, font=font(24, True))) + 46
        draw.rounded_rectangle((x, 1020, x + chip_width, 1080), radius=30, fill="#e9f5f1")
        draw.text((x + chip_width // 2, 1050), chip, anchor="mm", font=font(24, True), fill="#16705a")
        x += chip_width + 18
    draw.text((70, 1122), f"Model: {product['code']} / {product['model']}", font=font(24), fill="#53606d")
    return canvas


def make_specs(product: dict[str, Any], hero: Image.Image, sizes: list[str]) -> Image.Image:
    canvas = Image.new("RGB", (1200, 1200), "white")
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "PRODUCT FACTS", "Product Specifications", "Materials, sizes and colors for this style")
    paste_image(canvas, hero, (650, 260, 1130, 900))
    rows = [
        ("Fit Type", "Regular Fit"),
        ("Upper", product["upper"]),
        ("Sole", product["sole"]),
        ("Closure", product["closure"]),
        ("Toe", product["toe"]),
        ("Size Range", f"EU {sizes[0]}-{sizes[-1]}"),
        ("Available Colors", str(len(product["colors"]))),
    ]
    y = 280
    for key, value in rows:
        draw.text((70, y), key.upper(), font=font(20, True), fill="#16705a")
        y = draw_wrapped(draw, (70, y + 34), value, font(29, True), "#1e2933", 500, 5) + 24
        draw.line((70, y, 580, y), fill="#e4e8eb", width=2)
        y += 22
    draw.text((70, 1115), "Final quotation follows the selected size ratio, colors, packing and customization.", font=font(23), fill="#53606d")
    return canvas


def make_size(product: dict[str, Any], hero: Image.Image, sizes: list[str]) -> Image.Image:
    canvas = Image.new("RGB", (1200, 1200), "white")
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "SIZE RANGE", f"Available {product['size_system']} sizes", "Final size selection and size ratio are confirmed before production")
    paste_image(canvas, hero, (710, 250, 1130, 850))
    x0, y0 = 70, 310
    cell_w, cell_h = 145, 92
    columns = 4
    for idx, value in enumerate(sizes):
        row, col = divmod(idx, columns)
        x = x0 + col * (cell_w + 14)
        y = y0 + row * (cell_h + 14)
        draw.rounded_rectangle((x, y, x + cell_w, y + cell_h), radius=16, fill="#f3f7f6", outline="#b9d8ce", width=2)
        draw.text((x + cell_w // 2, y + cell_h // 2), value, anchor="mm", font=font(38, True), fill="#16705a")
    draw.rounded_rectangle((70, 920, 1130, 1110), radius=24, fill="#f5f7f8")
    draw.text((105, 958), "BUYER CHECKLIST", font=font(22, True), fill="#17212b")
    draw.text((105, 1005), "Please send target market, selected sizes, pairs per size and fit reference.", font=font(27), fill="#46535f")
    draw.text((105, 1055), "A detailed foot-length chart can be confirmed against the final sample.", font=font(27), fill="#46535f")
    return canvas


def make_order(product: dict[str, Any], commercial: dict[str, Any], hero: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (1200, 1200), "white")
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "WHOLESALE ORDER", "Wholesale Order Terms", "MOQ, tier pricing, lead time and packing for wholesale buyers")
    paste_image(canvas, hero, (720, 250, 1130, 850))
    prices = commercial["ladder_prices_usd"]
    items = [
        ("MOQ", f"{commercial['moq_pairs']} pairs"),
        ("2-49 pairs", f"USD {prices[0]['unit_price']:.2f} / pair"),
        ("50-99 pairs", f"USD {prices[1]['unit_price']:.2f} / pair"),
        ("100+ pairs", f"USD {prices[2]['unit_price']:.2f} / pair"),
        ("Lead Time", commercial["lead_time"]),
        ("Packing", commercial["packing_options"]),
        ("Package Reference", commercial["package"]),
    ]
    y = 270
    for label, value in items:
        draw.rounded_rectangle((70, y, 650, y + 92), radius=18, fill="#f3f7f6")
        draw.text((96, y + 23), label.upper(), font=font(19, True), fill="#16705a")
        draw.text((330, y + 46), value, anchor="lm", font=font(25, True), fill="#26323c")
        y += 108
    draw.text((70, 1115), "Freight is quoted separately after the destination and quantity are confirmed.", font=font(23), fill="#53606d")
    return canvas


def make_oem(product: dict[str, Any], commercial: dict[str, Any], hero: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (1200, 1200), "white")
    draw = ImageDraw.Draw(canvas)
    draw_header(draw, "OEM / ODM DISCUSSION", "Turn the product into a buyer-ready quotation", "Customization is confirmed against quantity and final requirements")
    paste_image(canvas, hero, (660, 260, 1130, 850))
    bullets = [
        "Logo and branding placement",
        "Removable insole and labeling",
        "Color assortment and size ratio",
        "Standard shoe box or plastic bag",
        "Sample and courier arrangement",
    ]
    y = 300
    for item in bullets:
        draw.ellipse((76, y + 7, 94, y + 25), fill="#16705a")
        y = draw_wrapped(draw, (112, y), item, font(30, True), "#25313b", 500, 6) + 26
    draw.rounded_rectangle((70, 880, 1130, 1110), radius=28, fill="#17212b")
    draw.text((105, 925), "SEND YOUR INQUIRY", font=font(28, True), fill="#76d7bb")
    cta = "Please share your market, quantity, size ratio, colors, logo/packing request and required delivery date."
    draw_wrapped(draw, (105, 980), cta, font(30, True), "white", 970, 10)
    return canvas


def read_source_metadata(raw_root: Path, sources: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    sizes: list[str] = []
    metadata: list[dict[str, Any]] = []
    for source in sources:
        path = raw_root / source / "source.json"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        metadata.append(data)
        for value in str(data["sizes"]).split(";"):
            value = value.strip()
            if value and value not in sizes:
                sizes.append(value)
    return sorted(sizes, key=lambda value: int(value)), metadata


def write_form(
    out_dir: Path,
    product: dict[str, Any],
    sizes: list[str],
    metadata: list[dict[str, Any]],
    commercial: dict[str, Any],
) -> None:
    colors = " / ".join(product["colors"])
    source_links = "\n".join(f"- `{item['artno']}`: {item['detail_url']}" for item in metadata)
    keyword_rows = "\n".join(f"{index}. `{value}`" for index, value in enumerate(product["keywords"], 1))
    price_rows = "\n".join(
        f"- {item['min_pairs']}{'-' + str(item['max_pairs']) if item['max_pairs'] else '+'} pairs: `USD {item['unit_price']:.2f}/pair`"
        for item in commercial["ladder_prices_usd"]
    )
    content = f"""# {product['code']} / {product['model']} Alibaba.com 上架填写表

状态：`ASSETS_READY`。未登录国际站后台，尚未创建草稿或提交发布。

## 1. 产品定位

- 内部编码：`{product['code']}`
- 来源货号：`{product['model']}`
- 建议分组：`{product['group']}`
- 采购人群：`{product['audience']}`
- 鞋楦类型：`Regular Fit / 常规楦型`（负责人已确认，本批全部不使用宽楦、医疗或矫形类宣称）
- 独立链接理由：独立实物鞋型、闭合/外底/鞋面结构或尺码段与已有款不同；不是仅换标题和主图。

## 2. 标题

`{product['title']}`

## 3. 关键词

{keyword_rows}

## 4. 属性

| 字段 | 建议值 | 证据口径 |
| --- | --- | --- |
| Model Number | `{product['code']} / {product['model']}` | 内部编码 + 来源货号 |
| Fit Type | `Regular Fit` | 负责人 2026-08-14 确认 |
| Upper Material | `{product['upper']}` | 来源包产品信息与实物图 |
| Sole Material | `{product['sole']}` | 来源包产品信息；不外推未说明的配方 |
| Closure Type | `{product['closure']}` | 以实物图为准，已纠正部分国内标题的“一脚蹬”冲突 |
| Toe Style | `{product['toe']}` | 实物图 |
| Size System | `{product['size_system']}` | 来源包 |
| Size Range | `{', '.join(sizes)}` | 来源包 |
| Colors | `{colors}` | 来源包，已剔除“源头工厂”等非颜色词 |
| Origin | `Fujian, China` | 贝强公司信息 |

内部证据备注（禁止复制到对外页面）：{product['evidence_note']}

## 5. 交易、交期与包装（负责人确认本批沿用）

- MOQ: `{commercial['moq_pairs']} pairs`
{price_rows}
- Lead time: `{commercial['lead_time']}`
- Package reference: `{commercial['package']}`
- Cargo type: `{commercial['cargo_type']}`
- Packing: `{commercial['packing_options']}`
- Sample: `{commercial['sample_policy']}`
- Customization: `{commercial['customization']}`
- Freight: 不包含在上述单价中；根据数量、目的地、邮编和时效单独查询。

## 6. 图片上传顺序

- 主图：`01_主图/`内 6 张，按文件名顺序上传。
- 详情产品模块：`02_详情页/`内 6 张，必须替换老款所有产品图片。
- 颜色 SKU：`03_颜色图/`与上述颜色名一一对应。
- 公司、质检、包装、物流等非产品模块后台沿用 BQ030 已审核模块。
- 国内中文详情图只用作证据，不直接上传。

## 7. 后台执行参照

- 成人款：只读参照 BQ031 的类目、交易、包装、物流和非产品详情模块；产品字段必须使用本表。
- 童鞋款：只读参照 BQ030 的童鞋类目结构，尺码和图片使用本表。
- 创建草稿后必须回读：标题、关键词、属性、主图 6 张、颜色×尺码 SKU、价格、MOQ、交期、包装、详情图和物流。

## 8. 来源

{source_links}

## 9. 登录后最后一步

读取当前国际站动态 schema 和在线/草稿库→再次确认无同款→批量上传本地图至图片银行→创建唯一草稿→字段回读验收。不在未回读时直接判定“已上线”。
"""
    (out_dir / "00_上架填写表.md").write_text(content, encoding="utf-8")


def build_product(
    product: dict[str, Any],
    raw_root: Path,
    upload_root: Path,
    commercial: dict[str, Any],
) -> dict[str, Any]:
    if len(product["gallery"]) != 6:
        raise ValueError(f"{product['code']}: gallery must contain six sources")
    if len(product["colors"]) != len(product["color_sources"]):
        raise ValueError(f"{product['code']}: color/source count mismatch")

    public_text = " ".join([product["group"], product["title"], *product["keywords"]]).lower()
    bad = [term for term in FORBIDDEN_PUBLIC_TERMS if term in public_text]
    if bad:
        raise ValueError(f"{product['code']}: forbidden public terms: {bad}")
    if not 60 <= len(product["title"]) <= 128:
        raise ValueError(f"{product['code']}: title length {len(product['title'])} is outside 60-128")

    sizes, metadata = read_source_metadata(raw_root, product["sources"])
    out_dir = upload_root / f"{product['code']}_{product['model']}"
    main_dir = out_dir / "01_主图"
    detail_dir = out_dir / "02_详情页"
    color_dir = out_dir / "03_颜色图"
    reference_dir = out_dir / "04_参考预览"
    for folder in [main_dir, detail_dir, color_dir, reference_dir]:
        if folder.exists():
            for child in folder.iterdir():
                if child.is_file():
                    child.unlink()
        folder.mkdir(parents=True, exist_ok=True)

    opened_gallery: list[Image.Image] = []
    source_manifest: list[str] = []
    for spec in product["gallery"]:
        image, path = open_source(raw_root, product["sources"][0], spec)
        opened_gallery.append(image)
        source_manifest.append(str(path.relative_to(raw_root.parents[2])))

    for idx, filename in enumerate(MAIN_NAMES[:4]):
        save_jpg(fit_on_white(opened_gallery[idx], (1000, 1000), 24), main_dir / filename)
    save_jpg(color_card(product, raw_root, (1000, 1000)), main_dir / MAIN_NAMES[4])
    save_jpg(fit_on_white(opened_gallery[5], (1000, 1000), 24), main_dir / MAIN_NAMES[5])

    hero = opened_gallery[0]
    detail_images = [
        make_overview(product, hero, sizes),
        make_specs(product, opened_gallery[1], sizes),
        make_size(product, opened_gallery[2], sizes),
        color_card(product, raw_root, (1200, 1200)),
        make_order(product, commercial, opened_gallery[3]),
        make_oem(product, commercial, opened_gallery[5]),
    ]
    for filename, image in zip(DETAIL_NAMES, detail_images, strict=True):
        save_jpg(image, detail_dir / filename)

    for index, (name, spec) in enumerate(zip(product["colors"], product["color_sources"], strict=True), 1):
        image, path = open_source(raw_root, product["sources"][0], spec)
        source_manifest.append(str(path.relative_to(raw_root.parents[2])))
        filename = f"{index:02d}_{slug(name)}.jpg"
        save_jpg(fit_on_white(image, (1000, 1000), 28), color_dir / filename)

    contact = raw_root / "_全部候选详情联系表" / f"{product['model']}.jpg"
    if contact.exists():
        shutil.copy2(contact, reference_dir / "source_contact.jpg")
    (reference_dir / "source_manifest.txt").write_text(
        "\n".join(dict.fromkeys(source_manifest)), encoding="utf-8"
    )
    (reference_dir / "README_来源与禁用.md").write_text(
        "\n".join(
            [
                f"# {product['code']} 图片来源与禁用说明",
                "",
                "- 上传图全部来自当前货号真实来源包，只做裁切、留白、尺寸归一和英文信息排版。",
                "- 不得直接上传中文国内详情图、第三方标识、参考证书、买家评论或未确认功能图。",
                "- 用于上架的正式文件仅为 01_主图、02_详情页和 03_颜色图。",
            ]
        ),
        encoding="utf-8",
    )
    write_form(out_dir, product, sizes, metadata, commercial)

    expected = {
        "main": (main_dir, 6, (1000, 1000)),
        "detail": (detail_dir, 6, (1200, 1200)),
        "color": (color_dir, len(product["colors"]), (1000, 1000)),
    }
    for role, (folder, count, dimensions) in expected.items():
        files = sorted(folder.glob("*.jpg"))
        if len(files) != count:
            raise RuntimeError(f"{product['code']}: {role} expected {count}, found {len(files)}")
        for path in files:
            with Image.open(path) as image:
                if image.size != dimensions:
                    raise RuntimeError(f"{product['code']}: {path.name} has size {image.size}, expected {dimensions}")

    return {
        "batch_id": "2026-08-14-B",
        "bq_code": product["code"],
        "source_artno": "+".join(product["sources"]),
        "source_url": " + ".join(str(item["detail_url"]) for item in metadata),
        "product_group": product["group"],
        "fit_type": "Regular Fit",
        "closure": product["closure"],
        "upper": product["upper"],
        "sole": product["sole"],
        "sizes": ";".join(sizes),
        "colors": ";".join(product["colors"]),
        "main_images": 6,
        "detail_images": 6,
        "color_images": len(product["colors"]),
        "status": "ASSETS_READY",
        "next_action": "登录国际站后批量上传图片、建立唯一草稿并回读验收",
        "last_updated": "2026-08-14",
    }


def write_batch_outputs(workspace: Path, rows: list[dict[str, Any]], output_root: Path) -> None:
    data_root = workspace / "02_Alibaba运营" / "05_扩品工程" / "数据"
    data_root.mkdir(parents=True, exist_ok=True)
    csv_path = data_root / "国际站预上架商品总表_2026-08-14.csv"
    # Asset regeneration must not erase statuses written back after browser publishing.
    # Preserve the three operational fields for any SKU that has moved beyond ASSETS_READY.
    previous_by_code: dict[str, dict[str, str]] = {}
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            previous_by_code = {
                item["bq_code"]: item
                for item in csv.DictReader(handle)
                if item.get("bq_code")
            }
    for row in rows:
        previous = previous_by_code.get(row["bq_code"])
        if previous and previous.get("status") not in (None, "", "ASSETS_READY"):
            for field in ("status", "next_action", "last_updated"):
                if previous.get(field):
                    row[field] = previous[field]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    qa_path = workspace / "02_Alibaba运营" / "05_扩品工程" / "预检" / "20款国际站预上架包验收_2026-08-14.md"
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    table = "\n".join(
        f"| {row['bq_code']} | {row['source_artno']} | {row['fit_type']} | {row['sizes'].replace(';', ', ')} | {row['main_images']}/{row['detail_images']}/{row['color_images']} | ASSETS_READY |"
        for row in rows
    )
    qa_path.write_text(
        f"""# 20 款国际站预上架包验收

日期：2026-08-14

结论：20 款独立安全候选已生成完整预上架包。每款包含填写表、6 张主图、6 张英文详情图、按颜色对应的 SKU 图和来源清单。本轮未连接国际站后台，所以状态是 `ASSETS_READY`，不是已发布。

## 批次验收表

| 编码 | 来源货号 | 鞋楦类型 | 尺码 | 主图/详情/颜色图 | 状态 |
| --- | --- | --- | --- | --- | --- |
{table}

## 自动验收项

- 公开标题、分组和关键词未出现宽楦、医疗、矫形、糖尿病足、拇囊炎、赤足或防水等未确认宣称。
- 所有主图为 1000×1000 JPG，详情图为 1200×1200 JPG，颜色图为 1000×1000 JPG。
- 每款颜色名和颜色图数量一致，尺码从来源 `source.json` 直接读取。
- 价格、MOQ、交期、包装和定制边界使用负责人本轮明确授权的继承值。
- 图片只做裁切、留白、尺寸归一和英文排版，没有生成或改变鞋型、颜色和结构。

## 后台最终验收

登录后仍需对每个草稿做一次回读：类目、标题、属性、图片 URL、颜色×尺码 SKU、价格、MOQ、交期、包装、详情和物流必须一致。回读前不宣称“已上架”。

本地交付根目录：`{output_root}`
""",
        encoding="utf-8",
    )

    preview_root = output_root / "99_批次视觉验收_2026-08-14"
    preview_root.mkdir(parents=True, exist_ok=True)
    for role, subdir in [("主图", "01_主图"), ("详情", "02_详情页"), ("颜色", "03_颜色图")]:
        for part, subset in enumerate((rows[:10], rows[10:]), 1):
            columns = 8
            thumb_w, thumb_h = 150, 150
            label_h, gap = 34, 10
            row_h = thumb_h + label_h + gap
            canvas = Image.new("RGB", (columns * (thumb_w + gap) + gap, len(subset) * row_h + gap), "white")
            draw = ImageDraw.Draw(canvas)
            for row_index, row in enumerate(subset):
                product_dir = output_root / f"{row['bq_code']}_{str(row['source_artno']).split('+')[0]}" / subdir
                files = sorted(product_dir.glob("*.jpg"))[:columns]
                y = gap + row_index * row_h
                draw.text((gap, y + 4), row["bq_code"], font=font(20, True), fill="#17212b")
                for image_index, path in enumerate(files):
                    with Image.open(path) as source:
                        fitted = ImageOps.contain(source.convert("RGB"), (thumb_w, thumb_h), Image.Resampling.LANCZOS)
                    x = gap + image_index * (thumb_w + gap)
                    py = y + label_h + (thumb_h - fitted.height) // 2
                    canvas.paste(fitted, (x + (thumb_w - fitted.width) // 2, py))
            save_jpg(canvas, preview_root / f"{role}_验收_{part}.jpg", quality=88)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path(__file__).with_name("sooxie_prelisting_profiles_2026-08-14.json"),
    )
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    profiles = json.loads(args.profiles.read_text(encoding="utf-8"))
    raw_root = workspace / "01_产品资产" / "01_原始数据包" / "待审_搜鞋网_2026-08-14"
    upload_root = workspace / "02_可上传素材" / "00_最终上传"
    rows = [
        build_product(product, raw_root, upload_root, profiles["owner_confirmed"])
        for product in profiles["products"]
    ]
    write_batch_outputs(workspace, rows, upload_root)
    print(f"products={len(rows)} status=ASSETS_READY")
    print(upload_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
