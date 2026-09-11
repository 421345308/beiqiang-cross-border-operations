"""Stage pending HR images for one browser upload and sync them back to CDN keys.

The browser uploader receives short unique filenames.  After upload, ``sync``
queries the seller photo bank, refreshes the local index, and maps each staged
filename back to the original asset stem used by the Schema publisher.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
PACK_ROOT = ROOT / "01_产品资产/01_原始数据包/热榜OEM概念款_2026-09-05"
OUTPUT_ROOT = ROOT / "02_Alibaba运营/05_扩品工程/热榜持续扩品_2026-09-05"
PHOTO_INDEX = ROOT / "02_Alibaba运营/06_图片与检查记录/API全量图片审计_2026-09-03"
URL_MAP = PACK_ROOT / "00_图片银行URL映射.json"
UPLOAD_CACHE = OUTPUT_ROOT / "upload_cache.json"
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def product_dir(model: str) -> Path:
    matches = list(PACK_ROOT.glob(f"{model}_*"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one package for {model}, found {len(matches)}")
    return matches[0]


def assets(model: str) -> list[Path]:
    folder = product_dir(model)
    main = sorted(p for p in (folder / "01_主图").glob("*.png") if not p.stem.endswith("_b2b"))
    details = sorted((folder / "02_详情页").glob("*.png"))
    colors = sorted(p for p in (folder / "03_颜色图").glob("*.png") if not p.stem.endswith("_b2b"))
    b2b = sorted(folder.rglob("*_b2b.png"))
    if (len(main), len(details), len(colors), len(b2b)) != (6, 4, 3, 3):
        raise RuntimeError(
            f"{model} asset count is main={len(main)} detail={len(details)} "
            f"color={len(colors)} b2b={len(b2b)}"
        )
    return main + details + colors + b2b


def stage(models: list[str], destination: Path, batch_size: int) -> None:
    cached = json.loads(UPLOAD_CACHE.read_text(encoding="utf-8")) if UPLOAD_CACHE.exists() else {}
    pending: list[tuple[str, Path]] = []
    for model in models:
        for source in assets(model):
            if digest(source) not in cached:
                pending.append((model, source))

    manifests: list[dict[str, str]] = []
    per_model_index: dict[str, int] = {}
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        batch_dir = destination / f"batch_{offset // batch_size + 1:02d}"
        batch_dir.mkdir(parents=True, exist_ok=True)
        mapping: dict[str, str] = {}
        for model, source in batch:
            per_model_index[model] = per_model_index.get(model, 0) + 1
            short = f"{model.lower()}_{per_model_index[model]:02d}{source.suffix.lower()}"
            if len(short) > 30:
                raise RuntimeError(f"Filename exceeds Alibaba limit: {short}")
            shutil.copy2(source, batch_dir / short)
            mapping[short] = str(source)
        manifest = batch_dir / "manifest.json"
        manifest.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        manifests.append({"batch": str(batch_dir), "images": str(len(mapping))})
    print(json.dumps({"pending": len(pending), "batches": manifests}, ensure_ascii=False, indent=2))


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def sync(destination: Path) -> None:
    staged: dict[str, str] = {}
    for manifest in destination.glob("batch_*/manifest.json"):
        staged.update(json.loads(manifest.read_text(encoding="utf-8")))
    if not staged:
        raise RuntimeError("No staged manifests found")

    client = load_client()
    config = client.load_config(CONFIG_PATH)
    found: dict[str, dict] = {}
    # A prior API attempt may already have uploaded the exact source under its
    # original stem, while the browser batch uses a short staged filename.
    # Match both names so Alibaba's de-duplication dialog can be resolved
    # without re-uploading or manually copying a CDN URL.
    source_stem_to_staged = {
        Path(source).stem.lower(): staged_name for staged_name, source in staged.items()
    }
    PHOTO_INDEX.mkdir(parents=True, exist_ok=True)
    for page in range(1, 100):
        response = client.top_call(
            config,
            "alibaba.icbu.photobank.list",
            {"current_page": page, "page_size": 500, "location_type": "ALL_GROUP"},
        )
        error = client.api_error(response)
        if error:
            raise RuntimeError(error)
        rows = (response.get("pagination_query_list") or {}).get("list", [])
        if not rows:
            break
        (PHOTO_INDEX / f"photobank_page{page}_500.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for row in rows:
            name = str(row.get("file_name") or "")
            if name in staged and name not in found:
                found[name] = row
            stem = Path(name).stem.lower()
            staged_alias = source_stem_to_staged.get(stem)
            if staged_alias and staged_alias not in found:
                found[staged_alias] = row
        if len(found) == len(staged) or len(rows) < 500:
            break

    # Alibaba's browser uploader de-duplicates byte-identical images.  In that
    # case the newly staged filename is not created in the photo bank, while a
    # sibling staged filename with the same local bytes is present.  Reuse the
    # sibling's official CDN row so product fields still resolve by their
    # original asset stem without another upload attempt.
    row_by_digest: dict[str, dict] = {}
    for staged_name, row in found.items():
        row_by_digest[digest(Path(staged[staged_name]))] = row
    for staged_name, source in staged.items():
        if staged_name not in found:
            duplicate_row = row_by_digest.get(digest(Path(source)))
            if duplicate_row:
                found[staged_name] = duplicate_row

    missing = sorted(set(staged) - set(found))
    if missing:
        raise RuntimeError(f"Photo-bank upload not complete; missing {len(missing)} files: {missing[:10]}")

    url_map = json.loads(URL_MAP.read_text(encoding="utf-8")) if URL_MAP.exists() else {}
    upload_cache = json.loads(UPLOAD_CACHE.read_text(encoding="utf-8")) if UPLOAD_CACHE.exists() else {}
    for staged_name, source in staged.items():
        row = found[staged_name]
        source_path = Path(source)
        sha = digest(source_path)
        url_map[source_path.stem] = row["url"]
        upload_cache[sha] = {
            "url": row["url"],
            "file_id": str(row["id"]),
            "source": str(source_path),
            "sha256": sha,
            "refs": {"source": "browser-photo-bank-sync"},
        }
    URL_MAP.write_text(json.dumps(url_map, ensure_ascii=False, indent=2), encoding="utf-8")
    UPLOAD_CACHE.write_text(json.dumps(upload_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"synced": len(found), "url_map": str(URL_MAP)}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("stage", "sync"))
    parser.add_argument("--models", nargs="+", default=["HR024", "HR025", "HR026", "HR027", "HR028"])
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()
    if args.mode == "stage":
        stage(args.models, args.destination, args.batch_size)
    else:
        sync(args.destination)


if __name__ == "__main__":
    main()
