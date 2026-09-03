#!/usr/bin/env python3
"""Alibaba.com Open Platform client for Beiqiang.

Authentication endpoints use GOP. Seller business APIs use the TOP-compatible
protocol on Alibaba.com's current gateway. Credentials and tokens stay outside
Git, and secrets are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
from pathlib import Path
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_CONFIG = Path.home() / ".config" / "beiqiang" / "alibaba-openapi.json"
API_SERVER = "https://open-api.alibaba.com"
AUTH_ENDPOINT = "https://open-api.alibaba.com/oauth/authorize"
SIGN_METHOD = "sha256"


class ClientError(RuntimeError):
    pass


def load_config(path: Path) -> dict:
    if not path.exists():
        raise ClientError(f"Credential config not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("appKey") or not data.get("appSecret"):
        raise ClientError("Credential config requires appKey and appSecret")
    return data


def save_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def scalar(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def clean_params(params: dict) -> dict[str, str]:
    return {
        str(key): scalar(value)
        for key, value in params.items()
        if value is not None and value != ""
    }


def sign_request(api_name_prefix: str, params: dict[str, str], secret: str) -> str:
    """Sign exactly as Alibaba.com's official IOP Java SDK 1.3.18."""
    canonical = api_name_prefix + "".join(
        f"{key}{value}" for key, value in sorted(params.items())
        if key != "sign" and value not in (None, "")
    )
    return hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest().upper()


def http_json(request: Request, timeout: int = 60) -> dict:
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ClientError(f"HTTP {exc.code}: {raw[:1200]}") from exc
    except URLError as exc:
        raise ClientError(f"Network error: {exc.reason}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClientError(f"Non-JSON response: {raw[:1200]}") from exc


def gop_call(config: dict, api_path: str, business: dict) -> dict:
    if not api_path.startswith("/"):
        raise ClientError("GOP API path must begin with '/'")
    params = {
        "app_key": str(config["appKey"]),
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": SIGN_METHOD,
        "simplify": "true",
        **clean_params(business),
    }
    params["sign"] = sign_request(api_path, params, config["appSecret"])
    body = urlencode(params).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    return http_json(Request(f"{API_SERVER}/rest{api_path}", data=body, headers=headers))


def top_common(config: dict, api_method: str, require_token: bool = True) -> dict[str, str]:
    params = {
        "app_key": str(config["appKey"]),
        "timestamp": str(int(time.time() * 1000)),
        "method": api_method,
        "format": "json",
        "sign_method": SIGN_METHOD,
        "simplify": "true",
    }
    if require_token:
        token = config.get("accessToken")
        if not token:
            raise ClientError("No access token. Complete OAuth authorization first.")
        # Alibaba.com's current migrated-API HTTP example names this
        # parameter access_token. Do not substitute the legacy TOP name
        # "session" when making raw HTTP requests.
        params["access_token"] = token
    return params


def top_call(config: dict, api_method: str, business: dict, require_token: bool = True) -> dict:
    biz = clean_params(business)
    common = top_common(config, api_method, require_token)
    common["sign"] = sign_request("", {**common, **biz}, config["appSecret"])
    url = f"{API_SERVER}/sync?method={api_method}&{urlencode(common)}"
    body = urlencode(biz).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    return http_json(Request(url, data=body, headers=headers))


def multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "----Beiqiang" + secrets.token_hex(12)
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"),
            b"\r\n",
        ])
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode("utf-8"),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        file_path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), boundary


def upload_image(config: dict, file_path: Path, group_id: str | None) -> dict:
    if not file_path.is_file():
        raise ClientError(f"Image not found: {file_path}")
    if file_path.stat().st_size > 5 * 1024 * 1024:
        raise ClientError("Alibaba photobank raw-image limit is 5 MB")
    api_method = "alibaba.icbu.photobank.upload"
    biz = {"file_name": file_path.name}
    if group_id:
        biz["group_id"] = group_id
    common = top_common(config, api_method, True)
    common["sign"] = sign_request("", {**common, **biz}, config["appSecret"])
    body, boundary = multipart_body(biz, "image_bytes", file_path)
    url = f"{API_SERVER}/sync?method={api_method}&{urlencode(common)}"
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    return http_json(Request(url, data=body, headers=headers), timeout=120)


def redact_tokens(value):
    if isinstance(value, dict):
        return {
            key: ("[saved]" if key in {"access_token", "refresh_token"} else redact_tokens(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_tokens(item) for item in value]
    return value


def token_summary(response: dict) -> dict:
    """Return operational token metadata without exposing account identifiers."""
    return {
        "ok": str(response.get("code", "0")) in {"0", ""},
        "accessToken": "[saved]" if response.get("access_token") else "[missing]",
        "refreshToken": "[saved]" if response.get("refresh_token") else "[missing]",
        "expiresInSeconds": response.get("expires_in"),
        "refreshExpiresInSeconds": response.get("refresh_expires_in"),
        "requestId": response.get("request_id"),
        "traceId": response.get("_trace_id_"),
    }


def api_error(value: dict) -> dict | None:
    if isinstance(value.get("error_response"), dict):
        return value["error_response"]
    if str(value.get("code", "0")) not in {"0", ""}:
        return value
    return None


def command_auth_url(config: dict) -> None:
    redirect_uri = config.get("redirectUri", "https://www.alibaba.com")
    query = urlencode({
        "response_type": "code",
        "force_auth": "true",
        "redirect_uri": redirect_uri,
        "client_id": config["appKey"],
    })
    print(f"{AUTH_ENDPOINT}?{query}")


def save_token_response(config_path: Path, config: dict, response: dict) -> None:
    if str(response.get("code", "0")) not in {"0", ""} or not response.get("access_token"):
        safe = json.dumps(redact_tokens(response), ensure_ascii=False)
        raise ClientError(f"Token API did not return an access token: {safe}")
    config["accessToken"] = response["access_token"]
    if response.get("refresh_token"):
        config["refreshToken"] = response["refresh_token"]
    now = datetime.now(timezone.utc)
    if response.get("expires_in"):
        config["accessTokenExpiresAt"] = (now + timedelta(seconds=int(response["expires_in"]))).isoformat()
    if response.get("refresh_expires_in"):
        config["refreshTokenExpiresAt"] = (now + timedelta(seconds=int(response["refresh_expires_in"]))).isoformat()
    config["authorizedAccount"] = response.get("account")
    config["authorizedAt"] = now.isoformat()
    save_config(config_path, config)


def self_test() -> dict:
    params = {
        "app_key": "12345678",
        "code": "3_500102_JxZ05Ux3cnnSSUm6dCxYg6Q26",
        "sign_method": "sha256",
        "simplify": "true",
        "timestamp": "1517820392000",
    }
    expected = "0B409A354C6FB222EE2C8095002ACDB2D30566151D1A2361AEE7D2627B9BCBEA"
    actual = sign_request("/auth/token/create", params, "helloworld")
    return {"ok": actual == expected, "signatureMatchesOfficialExample": actual == expected}


def main() -> int:
    parser = argparse.ArgumentParser(description="Beiqiang Alibaba.com OpenAPI client")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check credential/token readiness without network calls")
    sub.add_parser("self-test", help="Verify signing against Alibaba's official example")
    sub.add_parser("auth-url", help="Print the Alibaba.com OAuth authorization URL")
    exchange = sub.add_parser("exchange-code", help="Exchange an OAuth code and save tokens")
    exchange.add_argument("code")
    sub.add_parser("refresh-token", help="Refresh and save the access token")
    call = sub.add_parser("call", help="Call an Alibaba.com seller business API")
    call.add_argument("method")
    call.add_argument("params", nargs="*", help="key=value")
    call.add_argument("--params-json", type=Path)
    call.add_argument(
        "--no-token", "--no-session", dest="no_token", action="store_true",
        help="Call an API that does not require an access token (--no-session is a legacy alias)",
    )
    upload = sub.add_parser("upload-image", help="Upload one image to Alibaba image bank")
    upload.add_argument("file", type=Path)
    upload.add_argument("--group-id")
    args = parser.parse_args()

    try:
        if args.command == "self-test":
            result = self_test()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 2
        config = load_config(args.config)
        if args.command == "doctor":
            print(json.dumps({
                "ok": True,
                "config": str(args.config),
                "appKeyPresent": bool(config.get("appKey")),
                "appSecretPresent": bool(config.get("appSecret")),
                "accessTokenPresent": bool(config.get("accessToken")),
                "refreshTokenPresent": bool(config.get("refreshToken")),
            }, ensure_ascii=False, indent=2))
        elif args.command == "auth-url":
            command_auth_url(config)
        elif args.command == "exchange-code":
            response = gop_call(config, "/auth/token/create", {"code": args.code})
            save_token_response(args.config, config, response)
            print(json.dumps(token_summary(response), ensure_ascii=False, indent=2))
        elif args.command == "refresh-token":
            if not config.get("refreshToken"):
                raise ClientError("No refresh token stored")
            response = gop_call(config, "/auth/token/refresh", {"refresh_token": config["refreshToken"]})
            save_token_response(args.config, config, response)
            print(json.dumps(token_summary(response), ensure_ascii=False, indent=2))
        elif args.command == "call":
            business = {}
            if args.params_json:
                business.update(json.loads(args.params_json.read_text(encoding="utf-8")))
            for item in args.params:
                if "=" not in item:
                    raise ClientError(f"Expected key=value, got: {item}")
                key, value = item.split("=", 1)
                business[key] = value
            result = top_call(config, args.method, business, not args.no_token)
            print(json.dumps(redact_tokens(result), ensure_ascii=False, indent=2))
            if api_error(result):
                return 2
        elif args.command == "upload-image":
            result = upload_image(config, args.file.resolve(), args.group_id)
            print(json.dumps(redact_tokens(result), ensure_ascii=False, indent=2))
            if api_error(result):
                return 2
        return 0
    except (ClientError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
