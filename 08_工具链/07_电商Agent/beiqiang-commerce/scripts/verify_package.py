"""Validate the exact local package; optional official online JSON schemas."""
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def verify(online=False):
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
    assert manifest["name"] == ROOT.name == "beiqiang-commerce"
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert 'VERSION = "' + manifest["version"] + '"' in (ROOT / "commerce/__init__.py").read_text(encoding="utf-8")
    assert len(manifest["extensions"]["com.openai"]["interface"]["shortDescription"]) <= 30
    server = mcp["mcpServers"]["beiqiang-commerce"]
    assert server["type"] == "stdio" and server["command"] == "python"
    assert server["args"] == ["-X", "utf8", "${PLUGIN_ROOT}/server.py", "--stdio"]
    assert (ROOT / "server.py").is_file()
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), str(p)
        if p.name == "SKILL.md":
            body = p.read_text(encoding="utf-8")
            assert body.startswith("---\n") and "name: " + p.parent.name in body
            assert "description:" in body.split("---", 2)[1]
    if online:
        import jsonschema
        for payload in (manifest, mcp):
            request = urllib.request.Request(payload["$schema"], headers={"User-Agent": "Beiqiang-package-validator"})
            with urllib.request.urlopen(request, timeout=20) as response:
                schema = json.load(response)
            jsonschema.Draft202012Validator(schema).validate(payload)
    return dict(ok=True, package=manifest["name"], version=manifest["version"], official_schemas_checked=online)

def package(destination):
    destination = Path(destination).resolve()
    assert not destination.is_relative_to(ROOT), "archive must be outside plugin source"
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = [p for p in ROOT.rglob("*") if p.is_file() and not any(part in ("__pycache__", ".state", ".venv", ".local") for part in p.relative_to(ROOT).parts) and p.suffix != ".pyc"]
    assert all(p.suffix in (".py", ".md", ".json") for p in files)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(files):
            archive.write(p, (Path(ROOT.name) / p.relative_to(ROOT)).as_posix())
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert all(name.startswith(ROOT.name + "/") for name in archive.namelist())
    return len(files)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online-schema", action="store_true")
    parser.add_argument("--zip")
    args = parser.parse_args()
    result = verify(args.online_schema)
    if args.zip:
        result["packaged_files"] = package(args.zip)
    print(json.dumps(result))
