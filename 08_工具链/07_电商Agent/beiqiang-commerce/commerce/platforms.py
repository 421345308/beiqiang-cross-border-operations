"""Explicit official read adapters. No arbitrary command, raw HTTP, or write API."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from .runtime import CommerceError, fail, now, encode

def redact(value):
    if isinstance(value, dict):
        return {k: "[redacted]" if any(s in k.lower().replace("_", "") for s in ("token", "secret", "password", "authorization")) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9_.-]+", r"\1[redacted]", value)
    return value

def read_platform(engine, platform, target_id, sku=None, project_id=None):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if platform == "alibaba":
        if not re.fullmatch(r"[0-9]{6,20}", target_id or "") or not sku:
            fail("INVALID_REQUEST", "Alibaba read requires SKU and numeric listing ID")
        identity = engine.ws.inspect_product(sku, target_id)
        client = engine.ws.file(".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py")
        cmd = [sys.executable, "-X", "utf8", str(client), "call", "alibaba.icbu.product.get", "product_id=" + target_id, "language=ENGLISH"]
    elif platform == "libtv":
        if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", target_id or "") or not re.fullmatch(r"[0-9a-fA-F-]{32,36}", project_id or ""):
            fail("INVALID_REQUEST", "LibTV read requires explicit project and node UUID")
        cli = Path.home() / ".libtv/libtv.exe"
        if not cli.is_file():
            fail("TOOL_UNAVAILABLE", "official LibTV CLI not found")
        cmd = [str(cli), "node", target_id, "-p", project_id]
    else:
        fail("UNSUPPORTED_PLATFORM", "only Alibaba product.get and official LibTV node reads are implemented")
    try:
        result = subprocess.run(cmd, cwd=engine.ws.root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=60, env=env, shell=False)
    except subprocess.TimeoutExpired:
        fail("READ_TIMEOUT", "Read query timed out; no external write occurred")
    except OSError:
        fail("TOOL_UNAVAILABLE", "official read command could not be launched")
    if len(result.stdout) > 20_000_000:
        fail("RESPONSE_TOO_LARGE", "read response exceeds 20MB")
    try:
        payload = json.loads(result.stdout.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        # Do not reflect arbitrary child stderr (which could include authentication material).
        fail("READ_FAILED", "official client returned no valid JSON; diagnose the client directly")
    payload = redact(payload)
    receipt = dict(platform=platform, target_id=target_id, project_id=project_id, observed_at=now(), exit_code=result.returncode, response=payload)
    folder = engine.state / "platform_reads"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (str(uuid.uuid4()) + ".json")
    path.write_text(encode(receipt) + "\n", encoding="utf-8")
    ref = engine.ws.reference(path.relative_to(engine.ws.root).as_posix())
    if result.returncode != 0:
        error = payload.get("error_response", payload) if isinstance(payload, dict) else {}
        code = str(error.get("sub_code") or error.get("code") or "unknown")
        code = code if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", code) else "unknown"
        fail("READ_FAILED", "official client failure " + code + "; local receipt: " + ref["path"])
    if platform == "alibaba":
        product = payload.get("product") if isinstance(payload, dict) else None
        if not isinstance(product, dict):
            fail("READ_FAILED", "product.get response has no product; local receipt: " + ref["path"])
        returned_id = str(product.get("product_id", ""))
        verification = "numeric_product_id_match"
        baseline_ref = None
        if returned_id != target_id:
            # Product.get may return an encrypted product ID. Bind it using this exact
            # listing's previous formal receipt, never another SKU or a guessed decode.
            baseline_path = identity["listings"][0].get("formal_fields", {}).get("file")
            baseline = engine.ws.json(baseline_path) if baseline_path else {}
            expected_product = baseline.get("response", {}).get("product", {})
            if str(baseline.get("requested_product_id")) != target_id or not returned_id or returned_id != str(expected_product.get("product_id")):
                fail("IDENTITY_UNVERIFIED", "encrypted product ID not bound by this listing's formal receipt; local receipt: " + ref["path"])
            baseline_ref = engine.ws.reference(baseline_path)
            verification = "same_listing_formal_encrypted_id_match"
        summary = {k: product.get(k) for k in ("subject", "status", "display", "category_id")}
        summary.update(requested_listing_id=target_id, identity_verification=verification, baseline=baseline_ref)
    else:
        if not isinstance(payload, dict) or str(payload.get("nodeKey")) != target_id:
            fail("IDENTITY_UNVERIFIED", "LibTV read did not return the requested node; local receipt: " + ref["path"])
        summary = {"node_id_requested": target_id, "project_id_requested": project_id,
                   "identity_verification": "node_key_match",
                   "interpretation": "Requested node read back; not generated output or creative QA"}
    return dict(summary=summary, evidence=ref,
                scope="read_only", local_ledger_updated=False)
