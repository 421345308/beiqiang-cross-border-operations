"""Validate reference-package structure; never claim to inspect image content."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def inspect_image(record: dict, root: Path, errors: list[str], label: str,
                  inside_project: bool = True) -> None:
    value = record.get("file")
    if not isinstance(value, str) or not value:
        errors.append(f"{label}: missing file")
        return
    path = (root / value).resolve()
    if inside_project and not path.is_relative_to(root.resolve()):
        errors.append(f"{label}: selected output is outside project")
        return
    if not path.is_file():
        errors.append(f"{label}: missing file {value}")
        return
    try:
        with Image.open(path) as im:
            width, height = im.size
            im.verify()
    except (OSError, ValueError, SyntaxError) as exc:
        errors.append(f"{label}: unreadable image: {exc}")
        return
    for key, actual in (("width", width), ("height", height)):
        if key in record and record[key] != actual:
            errors.append(f"{label}: stale {key}")
    if record.get("sha256"):
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if record["sha256"] != actual:
            errors.append(f"{label}: stale sha256")


def validate(assets: dict, root: Path, shots: dict | None = None,
             require_reviewed: bool = False) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    registry: dict[str, dict] = {}
    paths: set[Path] = set()
    selected = assets.get("selected_assets")
    if not isinstance(selected, list) or not selected:
        return {"ok": False, "errors": ["selected_assets must be a nonempty list"],
                "warnings": [], "pixel_review_performed": False}
    for item in selected:
        if not isinstance(item, dict):
            errors.append("selected_assets contains a non-object")
            continue
        asset_id = item.get("id")
        if not isinstance(asset_id, str) or not asset_id:
            errors.append("selected asset missing id")
            continue
        if asset_id in registry:
            errors.append(f"duplicate active id: {asset_id}")
        registry[asset_id] = item
        if item.get("file"):
            path = (root / item["file"]).resolve()
            if path in paths:
                errors.append(f"{asset_id}: duplicate active file")
            paths.add(path)
        if not item.get("role"):
            errors.append(f"{asset_id}: missing reference role")
        for field in ("inherit", "exclude"):
            if not isinstance(item.get(field), list) or not item[field]:
                errors.append(f"{asset_id}: missing {field} responsibilities")
        inspect_image(item, root, errors, asset_id)
    product = assets.get("product_reference")
    if isinstance(product, dict) and product.get("id"):
        if product["id"] in registry:
            errors.append("product_reference id conflicts with selected asset")
        registry[product["id"]] = product
        inspect_image(product, root, errors, product["id"], inside_project=False)
    for source in assets.get("input_only_sources", []):
        if not isinstance(source, dict) or not source.get("file"):
            errors.append("input_only_sources contains an invalid source")
        elif not (root / source["file"]).is_file():
            errors.append(f"missing input source: {source['file']}")
    checked_shots = 0
    if shots is not None:
        seen_shots: set[str] = set()
        output_paths: set[Path] = set()
        records = shots.get("shots")
        if not isinstance(records, list) or not records:
            errors.append("shots must be a nonempty list")
            records = []
        for shot in records:
            if not isinstance(shot, dict):
                errors.append("shots contains a non-object")
                continue
            sid = shot.get("id", "UNNAMED")
            if sid in seen_shots:
                errors.append(f"duplicate shot id: {sid}")
            seen_shots.add(sid)
            checked_shots += 1
            refs = shot.get("reference_ids")
            if not isinstance(refs, list) or not refs:
                errors.append(f"{sid}: missing reference_ids")
            else:
                for rid in refs:
                    if rid not in registry:
                        errors.append(f"{sid}: unknown active reference {rid}")
            inspect_image(shot, root, errors, sid)
            if shot.get("file"):
                output_path = (root / shot["file"]).resolve()
                if output_path in output_paths:
                    errors.append(f"{sid}: duplicate selected shot output")
                output_paths.add(output_path)
                if output_path in paths:
                    errors.append(f"{sid}: reusable asset used as composed shot output")
            for field in ("purpose", "prompt", "action_start", "action_end"):
                if not shot.get(field):
                    errors.append(f"{sid}: missing {field}")
            states = shot.get("states")
            if not isinstance(states, dict) or not states:
                errors.append(f"{sid}: missing scene/wardrobe/object states")
                states = {}
            for rule in assets.get("continuity_rules", []):
                affected = rule.get("shot_ids", [])
                if affected != "*" and sid not in affected:
                    continue
                key = rule.get("field")
                if key and states.get(key) != rule.get("equals"):
                    errors.append(f"{sid}: continuity violation {key}: "
                                  f"expected {rule.get('equals')!r}, got {states.get(key)!r}")
            frame_id = shot.get("frame_asset_id")
            if shot.get("frame_role") in ("first_frame", "last_frame") and frame_id:
                frame = registry.get(frame_id)
                if frame is None:
                    errors.append(f"{sid}: unknown frame asset {frame_id}")
                elif frame.get("view_kind") == "multiview_sheet":
                    errors.append(f"{sid}: multi-view sheet assigned as a video frame")
            review = shot.get("visual_review", {})
            if not isinstance(review, dict):
                review = {}
            if review.get("status") != "passed" or not review.get("notes"):
                target = errors if require_reviewed else warnings
                target.append(f"{sid}: visual review not recorded as passed with notes")
        if shots.get("require_all_planned_shots"):
            expected = set(shots.get("planned_shot_ids", []))
            if expected != seen_shots:
                errors.append("current shots do not match planned_shot_ids")
    return {"ok": not errors, "asset_count": len(selected), "shot_count": checked_shots,
            "errors": errors, "warnings": warnings, "pixel_review_performed": False,
            "scope": "Files, metadata and declared continuity only; not image/video quality or permission."}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Current asset manifest JSON")
    parser.add_argument("--project-root", type=Path, required=True,
                        help="Directory containing PROJECT.md; file paths resolve here")
    parser.add_argument("--shots", type=Path, help="Current composed-shot manifest JSON")
    parser.add_argument("--require-reviewed", action="store_true",
                        help="Fail if a shot's human/assistant pixel review is not passed with notes")
    args = parser.parse_args()
    try:
        report = validate(read_json(args.manifest), args.project_root,
                          read_json(args.shots) if args.shots else None, args.require_reviewed)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {"ok": False, "errors": [str(exc)], "pixel_review_performed": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
