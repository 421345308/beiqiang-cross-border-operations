#!/usr/bin/env python3
"""Replace legacy Alibaba detail-image URLs with official photobank URLs."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = Path(__file__).resolve().parent
PRIMARY_AUDIT = AUDIT_DIR.parent / "API全量图片审计_2026-09-03"
CLIENT_PATH = ROOT / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
CONFIG_PATH = Path.home() / ".config/beiqiang/alibaba-openapi.json"
TARGETS = [10000047127570, 12000003229472]
URL_RE = re.compile(
    r"(?:https?:)?//sc\d+\.alicdn\.com/kf/"
    r"([A-Za-z0-9]+\.(?:png|jpg|jpeg|webp))"
    r"(?:_[^\s\"'<>?]+)?",
    re.IGNORECASE,
)


def load_client():
    spec = importlib.util.spec_from_file_location("alibaba_openapi", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def image_key(url: str) -> str | None:
    match = URL_RE.search(url)
    return match.group(1) if match else None


def load_bank_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(PRIMARY_AUDIT.glob("photobank_page*_500.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        stack = [data]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                url = next((value.get(k) for k in ("url", "image_url", "imageUrl") if value.get(k)), None)
                if isinstance(url, str):
                    key = image_key(url)
                    if key:
                        result[key] = url if url.startswith("http") else "https:" + url
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
    return result


def response_xml(response: dict) -> str:
    data = response.get("data")
    if isinstance(data, str):
        return data
    for value in response.values():
        if isinstance(value, dict):
            found = response_xml(value)
            if found:
                return found
    return ""


def render(client, config: dict, product_id: int) -> tuple[dict, ET.Element, str]:
    params = {
        "param_product_top_publish_request": {
            "product_id": product_id,
            "language": "en_US",
        }
    }
    response = client.top_call(config, "alibaba.icbu.product.schema.render", params)
    xml_text = response_xml(response)
    if not xml_text:
        raise RuntimeError(f"No schema XML returned for {product_id}: {response}")
    return response, ET.fromstring(xml_text), xml_text


def field_value(root: ET.Element, field_id: str) -> str:
    field = root.find(f".//field[@id='{field_id}']")
    if field is None:
        raise RuntimeError(f"Missing schema field {field_id}")
    value = field.find("value")
    return "" if value is None or value.text is None else value.text


def make_update_xml(html: str) -> str:
    root = ET.Element("itemSchema")
    desc_type = ET.SubElement(root, "field", {"id": "productDescType", "type": "singleCheck"})
    ET.SubElement(desc_type, "value").text = "2"
    super_text = ET.SubElement(root, "field", {"id": "superText", "type": "input"})
    ET.SubElement(super_text, "value").text = html
    return ET.tostring(root, encoding="unicode")


def normalized_html(html: str) -> str:
    return URL_RE.sub("//IMAGE", html)


def main() -> None:
    client = load_client()
    config = client.load_config(CONFIG_PATH)
    bank = load_bank_map()
    manifest = []

    for product_id in TARGETS:
        before_response, before_root, before_xml = render(client, config, product_id)
        before_html = field_value(before_root, "superText")
        urls = URL_RE.findall(before_html)
        missing = sorted({key for key in urls if key not in bank})
        if missing:
            raise RuntimeError(f"{product_id}: image IDs not found in bank: {missing}")

        replacements = 0
        after_html = before_html
        for match in list(URL_RE.finditer(before_html)):
            old_url = match.group(0)
            key = match.group(1)
            new_url = bank[key]
            if old_url != new_url:
                after_html = after_html.replace(old_url, new_url)
                replacements += 1

        if normalized_html(before_html) != normalized_html(after_html):
            raise RuntimeError(f"{product_id}: HTML changed beyond image URLs")

        request = {
            "param_product_top_publish_request": {
                "product_id": product_id,
                "language": "en_US",
                "xml": make_update_xml(after_html),
            }
        }
        update_response = client.top_call(config, "alibaba.icbu.product.schema.update", request)
        if client.api_error(update_response):
            raise RuntimeError(f"{product_id}: update failed: {update_response}")

        readback_response, readback_root, readback_xml = render(client, config, product_id)
        readback_html = field_value(readback_root, "superText")
        readback_urls = [m.group(0) for m in URL_RE.finditer(readback_html)]
        all_official = bool(readback_urls) and all(image_key(url) in bank for url in readback_urls)
        structure_preserved = normalized_html(before_html) == normalized_html(readback_html)
        if not all_official or not structure_preserved or len(readback_urls) != len(urls):
            (AUDIT_DIR / f"{product_id}_failed_readback.xml").write_text(readback_xml, encoding="utf-8")
            raise RuntimeError(
                f"{product_id}: readback verification failed: "
                f"official={all_official}, structure={structure_preserved}, "
                f"before={len(urls)}, after={len(readback_urls)}, urls={readback_urls}"
            )

        (AUDIT_DIR / f"{product_id}_schema_before.xml").write_text(before_xml, encoding="utf-8")
        (AUDIT_DIR / f"{product_id}_schema_after.xml").write_text(readback_xml, encoding="utf-8")
        (AUDIT_DIR / f"{product_id}_update_response.json").write_text(
            json.dumps(update_response, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.append({
            "productId": product_id,
            "replacements": replacements,
            "imageCount": len(readback_urls),
            "allUrlsResolveToPhotobankAssets": all_official,
            "structurePreserved": structure_preserved,
            "updateResponse": update_response,
        })

    (AUDIT_DIR / "详情HTML图片银行URL修复记录.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
