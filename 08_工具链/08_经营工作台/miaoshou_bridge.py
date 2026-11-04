"""In-memory, read-only browser bridge. HTTP routing and target lookup live elsewhere.

No vendor credentials or raw vendor responses belong in this module. Callers must
derive expected_shop_id from the existing private store configuration.
"""
import re
import secrets
import threading
import time


_ORIGIN = re.compile(r"chrome-extension://[a-p]{32}\Z")
_ID = re.compile(r"[0-9]{1,40}\Z")
_SIZES = {20, 40, 50, 100, 200, 500, 1000}
_ERRORS = {"session_expired", "shop_mismatch", "schema_changed", "request_failed"}


class BridgeError(ValueError):
    pass


class MiaoshouBridge:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.pending_pair = None
        self.pairing = None
        self.tasks = {}

    def issue_pairing(self, expected_shop_id):
        if not isinstance(expected_shop_id, str) or not _ID.fullmatch(expected_shop_id):
            raise BridgeError("invalid_input")
        with self.lock:
            code = secrets.token_urlsafe(32)
            self.pending_pair = {"code": code, "expected": expected_shop_id, "expires": self.clock() + 300}
            return {"code": code, "expires_in": 300}

    def pair(self, code, origin, shop_id):
        with self.lock:
            p = self.pending_pair
            if (not p or self.clock() >= p["expires"] or not isinstance(code, str)
                    or not secrets.compare_digest(code, p["code"]) or not isinstance(origin, str)
                    or not _ORIGIN.fullmatch(origin) or shop_id != p["expected"]):
                raise BridgeError("pairing_failed")
            self.pending_pair = None
            token = secrets.token_urlsafe(32)
            self.pairing = {"token": token, "origin": origin, "expected": p["expected"], "last_seen": self.clock()}
            self.tasks = {}
            return {"token": token}

    def _auth(self, origin, token):
        p = self.pairing
        if (not p or origin != p["origin"] or not isinstance(token, str)
                or not secrets.compare_digest(token, p["token"])):
            raise BridgeError("unauthorized")
        p["last_seen"] = self.clock()
        return p

    def status(self):
        with self.lock:
            return {"paired": bool(self.pairing), "online": bool(self.pairing and self.clock() - self.pairing["last_seen"] < 30)}

    def submit(self, operation, params=None):
        params = {} if params is None else params
        if not isinstance(params, dict) or operation not in ("connection-check", "products"):
            raise BridgeError("invalid_input")
        if operation == "connection-check":
            if params:
                raise BridgeError("invalid_input")
            clean = {}
        else:
            if set(params) - {"page", "pageSize", "isDraft"}:
                raise BridgeError("invalid_input")
            page, size, draft = params.get("page", 1), params.get("pageSize", 100), params.get("isDraft")
            if type(page) is not int or page < 1 or type(size) is not int or size not in _SIZES or (draft is not None and type(draft) is not bool):
                raise BridgeError("invalid_input")
            clean = {"page": page, "pageSize": size}
            if draft is not None:
                clean["isDraft"] = draft
        with self.lock:
            if not self.status()["online"]:
                raise BridgeError("bridge_disconnected")
            task_id = secrets.token_urlsafe(18)
            self.tasks[task_id] = {"operation": operation, "params": clean, "state": "queued", "created": self.clock()}
            return {"task_id": task_id}

    def poll(self, origin, token):
        with self.lock:
            self._auth(origin, token)
            for task_id, task in self.tasks.items():
                self._expire(task)
                if task["state"] == "queued":
                    task["state"] = "running"
                    return {"task_id": task_id, "operation": task["operation"], "params": dict(task["params"]), "expected_shop_id": self.pairing["expected"]}
            return None

    def complete(self, origin, token, task_id, payload):
        with self.lock:
            p = self._auth(origin, token)
            task = self.tasks.get(task_id)
            if task:
                self._expire(task)
            if not task or task["state"] != "running" or not isinstance(payload, dict):
                raise BridgeError("invalid_input")
            error = payload.get("error")
            if isinstance(error, str) and error in _ERRORS:
                result = {"ok": False, "error": error}
            elif error is not None:
                result = {"ok": False, "error": "schema_changed"}
            elif payload.get("shop_id_before") != p["expected"] or payload.get("shop_id_after") != p["expected"]:
                result = {"ok": False, "error": "shop_mismatch"}
            elif task["operation"] == "connection-check":
                result = {"ok": True, "data": {"shopId": p["expected"], "readable": True, "writable": False}}
            else:
                try:
                    result = self._products(task, payload, p["expected"])
                except (BridgeError, TypeError):
                    result = {"ok": False, "error": "schema_changed"}
            task.update(state="done", result=result)
            return {"accepted": True}

    @staticmethod
    def _products(task, payload, expected):
        rows, total = payload.get("items"), payload.get("total")
        page, size = task["params"]["page"], task["params"]["pageSize"]
        if (not isinstance(rows, list) or type(total) is not int or total < 0 or len(rows) > size
                or total < len(rows) or (not rows and (page - 1) * size < total)
                or (page * size < total and len(rows) != size)):
            raise BridgeError("schema_changed")
        clean, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("productId"), str) or not _ID.fullmatch(row["productId"]) or row["productId"] in seen:
                raise BridgeError("schema_changed")
            seen.add(row["productId"])
            item = {"productId": row["productId"]}
            for key in ("name", "title", "status", "cid", "cateId"):
                value = row.get(key)
                if isinstance(value, str) and len(value) <= 500:
                    item[key] = value
                elif type(value) in (int, bool) and abs(value) <= 9007199254740991:
                    item[key] = value
            clean.append(item)
        has_more = page * size < total
        return {"ok": True, "data": {"shopId": expected, "items": clean}, "pagination": {"page": page, "pageSize": size, "total": total, "returned": len(clean), "hasMore": has_more, "nextPage": page + 1 if has_more else None, "scope": "platform-default" if "isDraft" not in task["params"] else "drafts" if task["params"]["isDraft"] else "products"}}

    def get_result(self, task_id):
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                raise BridgeError("invalid_input")
            self._expire(task)
            return {"state": task["state"], **({"result": task["result"]} if task["state"] == "done" else {})}

    def _expire(self, task):
        if task["state"] != "done" and self.clock() - task["created"] >= 60:
            task.update(state="done", result={"ok": False, "error": "bridge_disconnected"})
