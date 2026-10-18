#!/usr/bin/env python3
"""CLI and stdio entry point. Requires Python 3.11+; standard library only."""
import argparse
import json
import sys

from commerce.runtime import CommerceError, Engine, discover_workspace
from commerce.service import call, tool_list
from commerce.mcp import serve

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace")
    parser.add_argument("--state-dir", help="workspace-contained local runtime directory")
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--tools", action="store_true")
    parser.add_argument("--tool", help="one commerce_* tool name")
    parser.add_argument("--args-file", help="JSON argument file; preferable to shell interpolation")
    args = parser.parse_args()
    try:
        engine = Engine(discover_workspace(args.workspace), args.state_dir)
        if args.stdio:
            serve(engine)
            return 0
        if args.tools:
            result = tool_list()
        elif args.tool:
            payload = json.loads(open(args.args_file, encoding="utf-8-sig").read()) if args.args_file else {}
            result = call(engine, args.tool, payload)
        else:
            result = engine.doctor()
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (CommerceError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "INVALID_INPUT"), "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
