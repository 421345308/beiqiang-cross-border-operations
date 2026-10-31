"""Explicit, read-only JSON boundary around the existing authorized client."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

METHODS = {"products": "alibaba.icbu.product.list", "product": "alibaba.icbu.product.get",
           "connection-check": "alibaba.icbu.product.list", "orders": "alibaba.seller.order.list",
           "order": "alibaba.seller.order.get"}
SENSITIVE = re.compile(r"token|secret|password|authorization|cookie|session|app.?key|sign(?:ature)?$", re.I)


def project_product(row):
    """Only verified catalog summary fields cross the connector boundary."""
    allowed = ("id", "product_id", "subject", "status", "display", "red_model", "group_name",
               "category_id", "language", "pc_detail_url")
    result = {key: row[key] for key in allowed if key in row and isinstance(row[key], (str, int, bool))}
    numeric = exact_numeric_id(row)
    if numeric is None:
        match = re.fullmatch(r"https://www\.alibaba\.com/product-detail/[^/?]+_(\d+)\.html", str(row.get("pc_detail_url", "")))
        numeric = match.group(1) if match else None
    if numeric:
        result["id"] = numeric
    if isinstance(row.get("pc_detail_url"), str):
        result["platformUrl"] = row["pc_detail_url"]
    images = row.get("main_image", {}).get("images") if isinstance(row.get("main_image"), dict) else None
    if isinstance(images, list) and all(isinstance(value, str) for value in images):
        result["main_image"] = {"images": images}
    return result


def exact_numeric_id(row):
    value = row.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"\d+", str(value)):
        return None
    return str(value)


def matches_requested_product(row, requested):
    numeric = exact_numeric_id(row)
    if numeric is not None:
        return numeric == requested
    # product_id may be encrypted. The established formal readback uses the
    # public detail URL's exact numeric suffix when no numeric id is returned.
    url = row.get("pc_detail_url")
    return isinstance(url, str) and bool(re.fullmatch(
        r"https://www\.alibaba\.com/product-detail/[^/?]+_" + re.escape(requested) + r"\.html", url))


class ExistingClient:
    """Loading credentials and any network access happen only on explicit call."""
    def __init__(self, config_path=None):
        self.config_path = config_path
        self.config = None

    def call(self, method, params):
        path = Path(__file__).resolve().parents[4] / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
        spec = importlib.util.spec_from_file_location("beiqiang_authorized_alibaba", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.config = module.load_config(Path(self.config_path) if self.config_path else module.DEFAULT_CONFIG)
        return module.top_call(self.config, method, params)

    def safe(self, value):
        secrets = [str(v) for k, v in (self.config or {}).items() if SENSITIVE.search(k) and v]
        return sanitize(value, secrets)


def sanitize(value, secrets=()):
    if isinstance(value, dict):
        return {k: sanitize(v, secrets) for k, v in value.items() if not SENSITIVE.search(k)}
    if isinstance(value, list):
        return [sanitize(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, "[redacted]")
        # Signed or credential-bearing URLs must not escape through API fields.
        if re.search(r"(?:access_token|refresh_token|app_secret|app_key|sign)=", value, re.I):
            return "[redacted credential-bearing text]"
    return value


def project_order(row):
    result = {"id": str(row["trade_id"]), "trade_id": str(row["trade_id"])}
    for key in ("status", "trade_status"):
        if isinstance(row.get(key), str):
            result[key] = row[key]
    for key in ("create_date", "modify_date"):
        if isinstance(row.get(key), dict):
            result[key] = {k: v for k, v in row[key].items()
                           if k in ("timestamp", "format_date") and type(v) in (str, int)}
    return result


def capabilities():
    def item(status, reason, methods=(), entry=None):
        return {"status": status, "reason": reason, "methods": list(methods), "entry": entry}
    return {"read": list(METHODS), "write": [], "writeStatus": "not-integrated",
            "automaticCollection": False, "cloudReady": False,
            "business": {
                "products": item("supported", "2026-10-31本机已实测商品列表与详情；仅显式只读查询", (METHODS['products'], METHODS['product'])),
                "orders": item("supported", "2026-10-31本机已实测订单列表与详情；其他环境仍须按真实响应验证", (METHODS['orders'], METHODS['order'])),
                "inquiries": item("not-verified", "既有权限清单（2026-09复核）未记录询盘读取接口，本轮未实测；不据此判定当前未授权", entry="04_客户开发/README.md"),
                "quotations": item("not-integrated", "既有权限清单（2026-09复核）未记录已验证的RFQ报价接口，本轮未实测；沿用原本地流程", entry="04_客户开发/07_RFQ专岗/README.md"),
                "metrics": item("permission-required", "既有权限清单（2026-09复核）记录数据管家需单独授权及聚石塔，2026-09探测返回InsufficientPermission；本轮未实测，广告报表另计", entry="02_Alibaba运营/04_周报与数据"),
                "images": item("authorized-not-integrated", "既有权限清单（2026-09复核）记录读取权限；本适配器未接入，本轮未实测", ('alibaba.icbu.photobank.list',)),
                "videos": item("authorized-not-integrated", "既有权限清单（2026-09复核）记录视频查询与关联读取权限、未记录上传权限；本轮未实测", ('alibaba.icbu.video.query', 'alibaba.icbu.video.relation.product.list')),
                "showcase": item("authorized-not-integrated", "既有权限清单（2026-09复核）记录读取权限；本适配器未接入，本轮未实测", ('alibaba.scbp.showcase.status','alibaba.scbp.showcase.list'))}}


def execute(command, *, client=None, page=1, page_size=50, product_id=None, order_id=None):
    result = {"ok": False, "operation": command, "data": None, "error": None,
              "source": {"provider": "alibaba-openapi", "method": METHODS.get(command),
                         "collectedAt": None, "attemptedAt": None,
                         "account": {"id": "beiqiang-alibaba-primary", "kind": "configured-connection-alias", "identityVerified": False}},
              "pagination": None}
    if command == "capabilities":
        result.update(ok=True, data=capabilities())
        return result
    if command not in METHODS:
        result["error"] = {"code": "UNSUPPORTED_OPERATION"}
        return result
    if (type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 50
            or (command == "product" and (not isinstance(product_id, str) or not re.fullmatch(r"\d{1,32}", product_id)))
            or (command == "order" and (not isinstance(order_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", order_id)))):
        result["error"] = {"code": "INVALID_ARGUMENT"}
        return result
    params = {"language": "ENGLISH"}
    if command == "orders":
        params = {"param_trade_ecology_order_list_query": json.dumps({"role": "seller", "start_page": page - 1, "page_size": page_size})}
    elif command == "order":
        params = {"e_trade_id": order_id, "language": "en_US"}
    elif command == "product":
        params["product_id"] = product_id
    else:
        params.update(current_page=1 if command == "connection-check" else page,
                      page_size=1 if command == "connection-check" else page_size)
    result["source"]["attemptedAt"] = datetime.now(timezone.utc).isoformat()
    try:
        client = client or ExistingClient()
        raw = client.call(METHODS[command], params)
        if not isinstance(raw, dict):
            raise ValueError("invalid response")
        for target, key in (("requestId", "request_id"), ("traceId", "_trace_id_")):
            candidate = raw.get(key)
            if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,160}", candidate):
                cleaned = client.safe(candidate) if hasattr(client, "safe") else candidate
                if cleaned == candidate:
                    result["source"][target] = candidate
        # Do not serialize platform error text, exceptions, or transport URLs.
        error = raw.get("error_response")
        if isinstance(error, dict) or str(raw.get("code", "0")) not in {"0", ""} or raw.get("success") is False:
            result["error"] = {"code": "PLATFORM_ERROR"}
            candidate = (error or raw).get("code")
            if isinstance(candidate, (str, int)) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", str(candidate)):
                cleaned = client.safe(str(candidate)) if hasattr(client, "safe") else str(candidate)
                if cleaned == str(candidate):
                    result["error"]["platformCode"] = str(candidate)
            return result
        if command in ("orders", "order"):
            body = raw.get("result") if command == "orders" else raw
            if not isinstance(body, dict):
                raise ValueError("missing order result")
            if body.get("success") is False:
                result["error"] = {"code": "PLATFORM_ERROR"}
                candidate = body.get("error_code")
                if isinstance(candidate, (str, int)) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", str(candidate)):
                    cleaned = client.safe(str(candidate)) if hasattr(client, "safe") else str(candidate)
                    if cleaned == str(candidate):
                        result["error"]["platformCode"] = str(candidate)
                return result
            value = body.get("value")
            if not isinstance(value, dict):
                raise ValueError("missing value")
            if command == "order":
                if str(value.get("trade_id")) != order_id:
                    raise ValueError("order identity mismatch")
                data = project_order(value)
            else:
                if body.get("success") is not True:
                    raise ValueError("missing positive business success")
                items, total = value.get("order_list"), value.get("total_count")
                if not isinstance(items, list) or type(total) is not int or total < 0:
                    raise ValueError("invalid orders")
                ids = [r.get("trade_id") if isinstance(r, dict) else None for r in items]
                more = page * page_size < total
                if (any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids)
                        or len(items) > page_size or total < len(items)
                        or (more and len(items) != page_size)
                        or (not items and (page-1)*page_size < total)):
                    raise ValueError("invalid order pagination")
                data = [project_order(row) for row in items]
                result['pagination'] = {'page':page,'pageSize':page_size,'total':total,'returned':len(items),'hasMore':more,'nextPage':page+1 if more else None}
        elif command == "product":
            if not isinstance(raw.get("product"), dict) or not raw["product"]:
                raise ValueError("missing product")
            if not matches_requested_product(raw["product"], product_id):
                raise ValueError("product identity mismatch")
            data = project_product(raw["product"])
        else:
            items = raw.get("products")
            total = raw.get("total_item")
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise ValueError("missing products")
            if isinstance(total, bool) or not re.fullmatch(r"\d+", str(total)):
                raise ValueError("missing total")
            total = int(total)
            effective_size = int(raw.get("page_size", params["page_size"]))
            current = int(raw.get("current_page", params["current_page"]))
            if (effective_size < 1 or current != params["current_page"] or len(items) > effective_size
                    or total < len(items) or (not items and (current - 1) * effective_size < total)):
                raise ValueError("invalid pagination")
            more = current * effective_size < total
            ids = [exact_numeric_id(item) or item.get("product_id") for item in items]
            if (any(not isinstance(value, str) or not value for value in ids)
                    or len(set(ids)) != len(ids) or (more and len(items) != effective_size)):
                raise ValueError("incomplete or duplicate page")
            result["pagination"] = {"page": current, "pageSize": effective_size, "total": total,
                                    "returned": len(items), "hasMore": more, "nextPage": current + 1 if more else None}
            data = {"reachable": True, "scope": "product-list-read"} if command == "connection-check" else [project_product(item) for item in items]
        result["data"] = client.safe(data) if hasattr(client, "safe") else sanitize(data)
        result["ok"] = True
        result["source"]["collectedAt"] = datetime.now(timezone.utc).isoformat()
    except ValueError:
        result["error"] = {"code": "INVALID_RESPONSE"}
    except Exception:
        result["error"] = {"code": "CLIENT_FAILURE", "action": "Check the existing client connection privately; no token refresh is performed."}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="External existing-client credential path; never copied")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("connection-check")
    listing = sub.add_parser("products")
    listing.add_argument("--page", type=int, default=1)
    listing.add_argument("--page-size", type=int, default=50)
    detail = sub.add_parser("product")
    detail.add_argument("--product-id", required=True)
    orders = sub.add_parser("orders")
    orders.add_argument("--page", type=int, default=1)
    orders.add_argument("--page-size", type=int, default=20)
    order = sub.add_parser("order")
    order.add_argument("--order-id", required=True)
    args = parser.parse_args(argv)
    result = execute(args.command, client=ExistingClient(args.config), page=getattr(args, "page", 1),
                     page_size=getattr(args, "page_size", 50), product_id=getattr(args, "product_id", None), order_id=getattr(args, "order_id", None))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
