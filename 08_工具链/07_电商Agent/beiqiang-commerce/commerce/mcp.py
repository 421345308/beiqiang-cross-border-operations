"""Small MCP stdio server implementing only negotiated tools and ping.

No HTTP listener, sampling, arbitrary shell, resources or background tasks.
JSON-RPC UTF-8 lines follow MCP 2025-11-25 stdio/lifecycle/tools contracts.
"""
import json
import sys

from . import VERSION
from .runtime import CommerceError
from .service import call, tool_list, validate_arguments

SUPPORTED = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

class Session:
    def __init__(self, engine):
        self.engine = engine
        self.initialized = False
        self.negotiated = False

    def handle(self, message):
        request_id = message.get("id") if isinstance(message, dict) else None
        def error(code, text):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": text}}
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return error(-32600, "Invalid Request")
        method, params = message["method"], message.get("params", {})
        if not isinstance(params, dict):
            return error(-32602, "Invalid params")
        if "id" not in message:
            if method == "notifications/initialized" and self.negotiated:
                self.initialized = True
            return None
        if type(request_id) not in (int, str):
            return error(-32600, "Invalid request ID")
        if method == "ping":
            result = {}
        elif method == "initialize":
            if self.negotiated:
                return error(-32600, "Already initialized")
            if not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("clientInfo"), dict) or not isinstance(params.get("capabilities"), dict):
                return error(-32602, "Initialization parameters required")
            version = params["protocolVersion"]
            self.negotiated = True
            result = dict(protocolVersion=version if version in SUPPORTED else SUPPORTED[0], capabilities={"tools": {}},
                          serverInfo={"name": "beiqiang-commerce", "version": VERSION},
                          instructions="Local commerce preparation and readback tools. Read the commerce skill. No publish, send, ad or paid generation tool is exposed.")
        elif not self.initialized:
            return error(-32000, "Initialization required")
        elif method == "tools/list":
            result = {"tools": tool_list()}
        elif method == "tools/call":
            name, args = params.get("name"), params.get("arguments", {})
            try:
                validate_arguments(name, args)
            except (ValueError, TypeError):
                return error(-32602, "Unknown tool or invalid arguments")
            try:
                value = call(self.engine, name, args)
                payload = {"ok": True, "result": value}
                result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, allow_nan=False)}], "structuredContent": payload, "isError": False}
            except (CommerceError, ValueError, OSError) as exc:
                payload = {"ok": False, "code": getattr(exc, "code", "INVALID_INPUT"), "message": str(exc)}
                result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}], "isError": True}
            except Exception:
                print("Unhandled commerce tool error; inspect local runtime", file=sys.stderr)
                payload = {"ok": False, "code": "INTERNAL_ERROR", "message": "Local runtime failed; no automatic external retry"}
                result = {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": True}
        else:
            return error(-32601, "Method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

def serve(engine):
    session = Session(engine)
    for line in sys.stdin.buffer:
        try:
            if len(line) > 2_000_000:
                raise ValueError("request too large")
            message = json.loads(line.decode("utf-8"))
            result = session.handle(message)
        except (ValueError, UnicodeError):
            result = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if result is not None:
            sys.stdout.buffer.write((json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()
