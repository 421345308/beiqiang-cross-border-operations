from __future__ import annotations

from pathlib import Path
import csv
import importlib.util
import io
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont


TARGET_RE = re.compile(r"^BQ0(1[7-9]|2[0-9]|30)_")
GALLERY_FILES = ["01_main.jpg", "02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "05_colors.jpg", "06_scene.jpg"]
REPEAT_CHECK_FILES = ["02_upper.jpg", "03_fit.jpg", "04_sole.jpg", "06_scene.jpg"]


def workspace_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "AGENTS.md").exists() and any(p.is_dir() and p.name.startswith("02_") for p in cwd.iterdir()):
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = workspace_root()
UPLOAD_PARENT = next(p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("02_"))
UPLOAD_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("00_"))
ARCHIVE_ROOT = next(p for p in UPLOAD_PARENT.iterdir() if p.is_dir() and p.name.startswith("99_"))
QA_ROOT = ARCHIVE_ROOT / "BQ017_BQ030_gallery_role_audit_20260621"
ORG_SCRIPT = Path(__file__).with_name("organize_20260616_new_packages.py")


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def save_jpg(image: Image.Image, path: Path, quality: int = 93) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, subsampling=1)
    path.write_bytes(buffer.getvalue())


def product_dirs() -> list[Path]:
    return sorted([p for p in UPLOAD_ROOT.iterdir() if p.is_dir() and TARGET_RE.match(p.name)], key=lambda p: p.name)


def main_dir(product_dir: Path) -> Path:
    return next(p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("01_"))


def ref_dir(product_dir: Path) -> Path | None:
    refs = [p for p in product_dir.iterdir() if p.is_dir() and p.name.startswith("04_")]
    return refs[0] if refs else None


def source_count(product_dir: Path) -> int:
    refs = ref_dir(product_dir)
    if not refs:
        return 0
    manifest = refs / "source_manifest.txt"
    if not manifest.exists():
        return 0
    return len([line for line in manifest.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()])


def load_metadata() -> dict[str, object]:
    if not ORG_SCRIPT.exists():
        return {}
    spec = importlib.util.spec_from_file_location("newpkg_metadata_for_audit", ORG_SCRIPT)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {product.folder_name: product for product in module.PRODUCTS}


def central_signature(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        image = opened.convert("L")
    # Ignore title and bottom pills. The middle zone should change if the image role is real.
    w, h = image.size
    crop = image.crop((int(w * 0.08), int(h * 0.24), int(w * 0.92), int(h * 0.82)))
    crop = crop.resize((96, 96), Image.Resampling.LANCZOS)
    arr = np.asarray(crop).astype(np.float32)
    arr -= arr.mean()
    std = float(arr.std())
    if std > 0:
        arr /= std
    return arr


def repeat_score(product_dir: Path) -> tuple[float, int]:
    paths = [main_dir(product_dir) / name for name in REPEAT_CHECK_FILES]
    paths = [p for p in paths if p.exists()]
    if len(paths) < 2:
        return 0.0, 0
    sigs = [central_signature(p) for p in paths]
    sims: list[float] = []
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            sims.append(float((sigs[i] * sigs[j]).mean()))
    high_pairs = sum(1 for score in sims if score >= 0.985)
    return max(sims) if sims else 0.0, high_pairs


def role_status(max_similarity: float, high_pairs: int) -> str:
    if high_pairs >= 3 or max_similarity >= 0.995:
        return "FAIL"
    if high_pairs >= 1 or max_similarity >= 0.965:
        return "WEAK"
    return "PASS"


def role_plan(product_name: str, product: object | None) -> str:
    plans = {
        "BQ017_A008": "2 quilted upper close-up; 3 lace-up fit/detail; 4 sole/cushion proof; 5 real colors; 6 commuting/daily use",
        "BQ018_A116": "2 knit upper; 3 lace-up fit; 4 walking sole/side support; 5 colors; 6 travel/commuting scene",
        "BQ019_A206": "2 breathable knit texture; 3 men/women couple style or lace-up detail; 4 outsole/sole profile; 5 colors; 6 daily walking scene",
        "BQ020_A218": "2 hollow knit airflow proof; 3 lace-up stability; 4 sole/cushion; 5 colors; 6 summer walking/use scene",
        "BQ021_K6212": "2 stretch textile upper; 3 slip-on opening; 4 sole/tread; 5 colors; 6 winter/fleece only if confirmed, otherwise daily use",
        "BQ022_A2208": "2 striped knit upper; 3 sock-like slip-on opening; 4 side/sole structure; 5 colors; 6 travel/commuting scene",
        "BQ023_A505": "2 soft knit upper; 3 low-cut slip-on fit; 4 sole profile; 5 black/grey/brown colors; 6 daily walking scene",
        "BQ024_A830": "2 men soft knit upper; 3 slip-on fit; 4 sole/yellow-sole variant proof if available; 5 colors; 6 men commuting/daily use",
        "BQ025_A1689": "2 low-cut opening; 3 slip-on fit/top view; 4 outsole/side sole; 5 colors; 6 couple/daily walking scene",
        "BQ026_T5828": "2 breathable knit/mesh; 3 lace-up lightweight fit; 4 177g evidence only if source image is used; 5 colors; 6 women's daily walking scene",
        "BQ027_K6116": "2 knit upper; 3 lace-up fit; 4 chunky sole proof; 5 colors; 6 casual walking scene",
        "BQ028_BISCUIT": "2 biscuit sole texture; 3 slip-on opening; 4 autumn/winter or fleece only if confirmed; 5 colors; 6 daily use/order support",
        "BQ029_A025": "2 high-top sock upper; 3 ankle opening; 4 wave pattern sole/upper; 5 black variants; 6 autumn/winter casual use",
        "BQ030_A811": "2 breathable mesh upper; 3 kids lace-up fit; 4 cushion sole; 5 child color options; 6 school/daily walking scene",
    }
    if product_name in plans:
        return plans[product_name]
    if product is None:
        return "Define 2 differentiator; 3 material/structure; 4 use/comfort; 5 colors; 6 buyer decision support."
    return f"2 {product.feature_title}; 3 {product.fit_title}; 4 {product.sole_title}; 5 colors; 6 daily use/order support"


def make_current_gallery_overview(rows: list[dict[str, object]], out: Path) -> None:
    thumb = 166
    label_h = 48
    left = 178
    top = 92
    canvas = Image.new("RGB", (left + len(GALLERY_FILES) * thumb + 24, top + len(rows) * (thumb + label_h) + 24), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((16, 16), "BQ017-BQ030 current main gallery role audit", fill=(18, 25, 38), font=load_font(21, True))
    for col, file_name in enumerate(GALLERY_FILES):
        draw.text((left + col * thumb + 42, 58), Path(file_name).stem, fill=(71, 85, 105), font=load_font(14, True))
    for row_idx, row in enumerate(rows):
        product_dir = Path(row["path"])
        y = top + row_idx * (thumb + label_h)
        name = str(row["product"])
        status = str(row["status"])
        color = {"FAIL": (185, 28, 28), "WEAK": (180, 83, 9), "PASS": (22, 101, 52)}.get(status, (30, 41, 59))
        draw.text((12, y + 58), name, fill=(30, 41, 59), font=load_font(13, True))
        draw.text((12, y + 82), status, fill=color, font=load_font(13, True))
        folder = main_dir(product_dir)
        for col, file_name in enumerate(GALLERY_FILES):
            path = folder / file_name
            if not path.exists():
                continue
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            image.thumbnail((thumb - 14, thumb - 14), Image.Resampling.LANCZOS)
            x = left + col * thumb + (thumb - image.width) // 2
            canvas.paste(image, (x, y + 6))
    save_jpg(canvas, out)


def make_source_contact_overview(products: list[Path], out: Path) -> None:
    cell_w = 360
    cell_h = 260
    cols = 2
    rows = (len(products) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, 58 + rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((14, 14), "BQ017-BQ030 source contact previews", fill=(18, 25, 38), font=load_font(21, True))
    for i, product_dir in enumerate(products):
        refs = ref_dir(product_dir)
        contact = refs / "source_contact.jpg" if refs else None
        x0 = (i % cols) * cell_w
        y0 = 58 + (i // cols) * cell_h
        draw.text((x0 + 10, y0 + 4), product_dir.name, fill=(30, 41, 59), font=load_font(15, True))
        if contact and contact.exists():
            with Image.open(contact) as opened:
                image = opened.convert("RGB")
            image.thumbnail((cell_w - 20, cell_h - 36), Image.Resampling.LANCZOS)
            canvas.paste(image, (x0 + (cell_w - image.width) // 2, y0 + 30))
    save_jpg(canvas, out)


def write_csv(rows: list[dict[str, object]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["product", "group", "status", "max_similarity", "high_repeat_pairs", "source_count", "issue", "recommended_plan"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in writer.fieldnames})


def write_markdown(rows: list[dict[str, object]], out: Path) -> None:
    fail_count = sum(1 for row in rows if row["status"] == "FAIL")
    weak_count = sum(1 for row in rows if row["status"] == "WEAK")
    pass_count = sum(1 for row in rows if row["status"] == "PASS")
    if fail_count == 0 and weak_count == 0:
        conclusion = "结论：当前 BQ017-BQ030 的主图组已通过角色差异审计。`02_upper.jpg`、`03_fit.jpg`、`04_sole.jpg`、`06_scene.jpg` 的中心画面已经不再是同图换标题，图组可以分别承担鞋面、穿脱/结构、鞋底/支撑、颜色和使用/采购决策等角色。"
    elif fail_count == 0:
        conclusion = "结论：当前 BQ017-BQ030 没有发现严重同图换标题问题，但仍有部分 WEAK 产品需要人工复核图组角色是否足够明确。"
    else:
        conclusion = "结论：当前 BQ017-BQ030 的主图组仍存在同一产品图重复使用的问题。部分产品的 `02_upper.jpg`、`03_fit.jpg`、`04_sole.jpg`、`06_scene.jpg` 只是替换标题和标签，中心产品画面高度重复，不能有效承担阿里主图组的转化角色。"
    lines = [
        "# BQ017-BQ030 主图角色审计",
        "",
        "审计日期：2026-06-21",
        "",
        "## 审计结论",
        "",
        f"- 检查产品：{len(rows)} 个",
        f"- FAIL：{fail_count} 个",
        f"- WEAK：{weak_count} 个",
        f"- PASS：{pass_count} 个",
        "",
        conclusion,
        "",
        "## 审计标准",
        "",
        "- `01_main.jpg`：搜索点击图，干净白底或浅底，产品完整清晰。",
        "- `02_upper.jpg`：核心差异点或鞋面/材料证据。",
        "- `03_fit.jpg`：闭合方式、穿脱方式、鞋口/脚感结构。",
        "- `04_sole.jpg`：鞋底、缓震、纹理、弯折或结构证据。",
        "- `05_colors.jpg`：真实颜色/SKU 选项，标签必须和图片一致。",
        "- `06_scene.jpg`：使用场景或 B2B 采购决策支持，如样品、尺码、订单支持。不要做重复填充图。",
        "",
        "## 逐款结果",
        "",
        "| 产品 | 分组 | 状态 | 源图数量 | 主要问题 | 建议重做方向 |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['product']} | {row['group']} | {row['status']} | {row['source_count']} | {row['issue']} | {row['recommended_plan']} |"
        )
    lines.extend(
        [
            "",
            "## 优先级建议",
            "",
            "1. 先修 `BQ017-BQ020`：这几款是常规透气/针织/夏季款，最适合建立一套可复用的主图角色模板。",
            "2. 再修 `BQ021-BQ028`：这里有冬季、套脚、饼干底、低帮等差异，需要按产品特征分模板处理。",
            "3. 最后修 `BQ029-BQ030`：高帮袜鞋和儿童鞋应分别做季节/鞋口/颜色/学校场景图，不能套用成人慢走鞋模板。",
            "",
            "## 操作原则",
            "",
            "- 不直接上传国内中文详情图；只能截取真实产品画面并重排英文 B2B 版式。",
            "- 不使用未确认的 `orthopedic`、`waterproof`、证书、销量、工厂产能等表述。",
            "- `EVA`、加绒、重量等信息只有在源图或供应商确认支持时才可放到图上；不确定时放到待确认清单。",
            "- 每款至少保留 4 张强图；6 张弱图不如 4 张强图。",
            "",
            "## QA 文件",
            "",
            f"- 当前主图组总览：`{(QA_ROOT / 'current_gallery_audit.jpg')}`",
            f"- 源图预览总览：`{(QA_ROOT / 'source_contact_overview.jpg')}`",
            f"- 结构化 CSV：`{(QA_ROOT / 'gallery_role_audit.csv')}`",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> None:
    QA_ROOT.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata()
    rows: list[dict[str, object]] = []
    for product_dir in product_dirs():
        product = metadata.get(product_dir.name)
        max_sim, high_pairs = repeat_score(product_dir)
        status = role_status(max_sim, high_pairs)
        issue = "2/3/4/6 中心产品画面高度重复，主要是同图换标题" if status == "FAIL" else "图组差异不足，需要人工复核"
        if status == "PASS":
            issue = "图组角色基本有差异"
        rows.append(
            {
                "product": product_dir.name,
                "path": str(product_dir),
                "group": getattr(product, "group", ""),
                "status": status,
                "max_similarity": f"{max_sim:.4f}",
                "high_repeat_pairs": high_pairs,
                "source_count": source_count(product_dir),
                "issue": issue,
                "recommended_plan": role_plan(product_dir.name, product),
            }
        )
    make_current_gallery_overview(rows, QA_ROOT / "current_gallery_audit.jpg")
    make_source_contact_overview(product_dirs(), QA_ROOT / "source_contact_overview.jpg")
    write_csv(rows, QA_ROOT / "gallery_role_audit.csv")
    write_markdown(rows, QA_ROOT / "BQ017-BQ030-main-gallery-role-audit.md")
    print(f"products={len(rows)}")
    print(f"qa={QA_ROOT}")


if __name__ == "__main__":
    run()
