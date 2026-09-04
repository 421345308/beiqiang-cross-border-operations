from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"C:\Users\spq\Desktop\贝强")
WRAPPER_PATH = ROOT / "08_工具链/01_业务脚本/商品图片与审计/replace_global_company_gallery_v3.py"
STATE_PATH = ROOT / "02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/公司图v3/批量替换状态.json"
PREFLIGHT_PATH = STATE_PATH.parent / "批量替换预检.json"


def load_wrapper():
    spec = importlib.util.spec_from_file_location("replace_global_company_gallery_v3", WRAPPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Maximum writes in this run; 0 means all")
    args = parser.parse_args()

    wrapper = load_wrapper()
    base = wrapper.configure(wrapper.load_base())
    client = base.load_client()
    config = client.load_config(base.CONFIG_PATH)
    assets = base.load_or_upload(client, config)
    expected = sorted(base.image_key(row["url"]) for row in assets)

    state = {"completed": {}, "skipped_review": {}, "failed": {}}
    if STATE_PATH.is_file():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
    for key in ("completed", "skipped_review", "failed"):
        state.setdefault(key, {})
    for product_id in list(state["completed"]):
        state["failed"].pop(product_id, None)
        state["skipped_review"].pop(product_id, None)

    if not args.dry_run and PREFLIGHT_PATH.is_file():
        product_ids = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8-sig")).get("candidate_ids", [])
    else:
        product_ids = [str(row.get("id", "")) for row in base.list_products(client, config)]

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        candidates = []
        for product_id in product_ids:
            try:
                _, product = base.get_product(client, config, product_id)
            except Exception as exc:
                state["failed"][product_id] = {"stage": "get", "error": str(exc)}
                continue
            current = sorted(base.company_keys(product))
            if current == expected:
                state["completed"].setdefault(product_id, {"result": "already_v3"})
            elif len(current) == 5 and set(current).issubset(base.OLD_KEYS):
                candidates.append(product_id)
        report = {
            "candidate_count": len(candidates),
            "already_v3": len(state["completed"]),
            "candidate_ids": candidates,
        }
        PREFLIGHT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    written = 0
    examined = 0
    for product_id in product_ids:
        if args.limit and written >= args.limit:
            break
        if product_id in state["completed"]:
            continue
        examined += 1
        try:
            _, before = base.get_product(client, config, product_id)
        except Exception as exc:
            state["failed"][product_id] = {"stage": "get", "error": str(exc)}
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            continue
        current = sorted(base.company_keys(before))
        if current == expected:
            state["completed"][product_id] = {"result": "already_v3"}
            state["failed"].pop(product_id, None)
            state["skipped_review"].pop(product_id, None)
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            continue
        if len(current) != 5 or not set(current).issubset(base.OLD_KEYS):
            state["failed"][product_id] = {"stage": "eligibility", "error": "gallery is neither accepted legacy/v2 nor current v3"}
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            continue
        snapshot = base.stable_snapshot(before)
        xml_root = ET.Element("itemSchema")
        base.append_gallery(xml_root, assets)
        xml = ET.tostring(xml_root, encoding="unicode")
        try:
            response = base.top_call_retry(client, config, "alibaba.icbu.product.schema.update", {
                "param_product_top_publish_request": {
                    "cat_id": int(before["category_id"]),
                    "language": "en_US",
                    "product_id": int(product_id),
                    "xml": xml,
                }
            })
            if base.failed(client, response):
                message = str(response.get("message") or response.get("msg_code") or response)
                if "AUDITING" in message.upper() or "UNDER REVIEW" in message.upper():
                    state["skipped_review"][product_id] = {"message": message}
                    continue
                raise RuntimeError(message)
            _, after = base.get_product(client, config, product_id)
            verification = {
                "company_gallery_exact": sorted(base.company_keys(after)) == expected,
                "other_fields_preserved": base.stable_snapshot(after) == snapshot,
                "status": after.get("status"),
                "display": after.get("display"),
            }
            if not all((verification["company_gallery_exact"], verification["other_fields_preserved"])):
                raise RuntimeError(f"readback verification failed: {verification}")
            state["completed"][product_id] = verification
            state["skipped_review"].pop(product_id, None)
            state["failed"].pop(product_id, None)
            written += 1
        except Exception as exc:
            state["failed"][product_id] = {"stage": "update", "error": str(exc)}
        finally:
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "written_this_run": written,
        "examined_this_run": examined,
        "completed_total": len(state["completed"]),
        "skipped_review_total": len(state["skipped_review"]),
        "failed_total": len(state["failed"]),
        "remaining_preflight_count": max(0, len(product_ids) - len(state["completed"])),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
