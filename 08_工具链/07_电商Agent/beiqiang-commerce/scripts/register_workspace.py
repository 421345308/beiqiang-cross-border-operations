"""Register this source plugin in this workspace, preserving unrelated entries."""
import json
from pathlib import Path
import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
from commerce.runtime import discover_workspace
from verify_package import verify

def register():
    verify()
    root = discover_workspace()
    if not PLUGIN.is_relative_to(root):
        raise ValueError("registration must run from the workspace source plugin")
    catalog_path = root / ".agents/plugins/marketplace.json"
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    else:
        catalog = {"name": "beiqiang-workspace", "interface": {"displayName": "贝强工作台"}, "plugins": []}
    entry = {"name": "beiqiang-commerce", "source": {"source": "local", "path": "./" + PLUGIN.relative_to(root).as_posix()},
             "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}
    matches = [e for e in catalog["plugins"] if e["name"] == entry["name"]]
    if matches and matches != [entry]:
        raise ValueError("existing plugin entry differs; inspect before changing it")
    if not matches:
        catalog["plugins"].append(entry)
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config = root / ".codex/config.toml"
    body = config.read_text(encoding="utf-8") if config.exists() else ""
    section = '[plugins."beiqiang-commerce@' + catalog["name"] + '"]'
    if section not in body:
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(body.rstrip() + ("\n\n" if body.strip() else "") + section + "\nenabled = true\n", encoding="utf-8")
    print(json.dumps({"registered": True, "marketplace": catalog["name"], "plugin": entry["name"], "scope": "workspace"}))

if __name__ == "__main__":
    register()
