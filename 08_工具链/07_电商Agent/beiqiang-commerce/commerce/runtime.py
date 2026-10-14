"""Dependency-free, local task/evidence store; no model or publication calls."""
from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sqlite3
import uuid

from .contracts import LEDGER, ENTRIES, SKILLS, RECIPES, validate_request, validate_artifact, normalize_channel
from . import VERSION

class CommerceError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

def fail(code, message):
    raise CommerceError(code, message)

def now():
    return datetime.now(timezone.utc).isoformat()

def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()

def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def discover_workspace(explicit=None):
    candidates = [explicit or os.environ.get("BEIQIANG_WORKSPACE")]
    candidates.extend([Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents, Path.home() / "Desktop/贝强"])
    for candidate in candidates:
        if candidate and (Path(candidate) / LEDGER).is_file():
            return Path(candidate).resolve()
        if explicit or os.environ.get("BEIQIANG_WORKSPACE"):
            break
    fail("WORKSPACE_NOT_FOUND", "Set BEIQIANG_WORKSPACE or --workspace to the Beiqiang workspace")

class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if not (self.root / LEDGER).is_file():
            fail("WORKSPACE_NOT_FOUND", "canonical product ledger missing")
        # Existing workspace junctions are readable; arbitrary escapes are not.
        self.read_roots = [self.root]
        for relative in ("01_产品资产", "05_内容与视频"):
            self.read_roots.append((self.root / relative).resolve())

    def file(self, relative):
        if not isinstance(relative, str) or not relative or PureWindowsPath(relative).drive:
            fail("INVALID_PATH", "a workspace-relative file path is required")
        p = Path(relative.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts:
            fail("INVALID_PATH", "path must stay inside workspace")
        forbidden = {".git", ".codex", "browser_data", "user_data"}
        if any(part.lower() in forbidden or part.lower().startswith(".env") for part in p.parts):
            fail("INVALID_PATH", "runtime credentials and host configuration are not task sources")
        resolved = (self.root / p).resolve()
        if not any(resolved.is_relative_to(base) for base in self.read_roots):
            fail("INVALID_PATH", "path resolves outside permitted workspace mounts")
        if not resolved.is_file():
            fail("FILE_NOT_FOUND", relative)
        return resolved

    def json(self, relative):
        path = self.file(relative)
        if path.stat().st_size > 30_000_000:
            fail("INPUT_TOO_LARGE", "JSON source exceeds 30MB")
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def inspect_product(self, sku, listing_id=None):
        ledger = self.json(LEDGER)
        matches = [p for p in ledger["products"] if sku == p["id"] or sku in p.get("aliases", [])]
        if len(matches) != 1:
            fail("IDENTITY_AMBIGUOUS", "SKU must resolve to exactly one canonical product")
        product = matches[0]
        listings = [p for p in ledger["listings"] if p.get("product_id") == product["id"]]
        if listing_id:
            listings = [p for p in listings if str(p["id"]) == str(listing_id)]
            if len(listings) != 1:
                fail("LISTING_MISMATCH", "listing does not belong to selected SKU")
        source_ids = [product.get(k) for k in ("adopted_source_id", "reference_source_id")]
        source_ids += product.get("candidate_source_ids", [])
        sources = [s for s in ledger.get("sources", []) if s["id"] in source_ids]
        selected = dict(product=product, listings=listings, sources=sources)
        references = list(dict.fromkeys([product.get("dossier_path"), product.get("local_assets", {}).get("current_fields_file"),
                                        *product.get("raw_packages", [])]))
        references = [p for p in references if p]
        return {
            "requested_sku": sku, "canonical_sku": product["id"], "source_state": product.get("source_state"),
            "selected_listing_id": listing_id, "listing_ids": [str(p["id"]) for p in listings],
            "product": product, "listings": listings, "sources": sources, "references": references,
            "record_hash": digest(selected), "ledger_updated_on": ledger.get("updated_on"),
            "evidence_interpretation": "Local ledger observations; not live readback, physical stock, or a publish approval",
        }

    def reference(self, relative):
        path = self.file(relative)
        return dict(path=relative, sha256=file_hash(path), bytes=path.stat().st_size)

    def plan(self, request):
        try:
            request = validate_request(request)
        except ValueError as exc:
            fail("INVALID_REQUEST", str(exc))
        if request.get("listing_id") and not re.fullmatch(r"[0-9]{6,20}", request["listing_id"]):
            fail("INVALID_REQUEST", "listing_id must be a numeric platform product ID")
        product = self.inspect_product(request["sku"], request.get("listing_id")) if request.get("sku") else None
        modules = list(dict.fromkeys(s["module"] for s in RECIPES[request["workflow"]]))
        # Identity lookup is local; it does not make every video task an Alibaba task.
        business_modules = list(dict.fromkeys(s["module"] for s in RECIPES[request["workflow"]] if s["id"] != "identity"))
        references = ["AGENTS.md"]
        for module in business_modules:
            references.extend(ENTRIES[module])
        if product:
            references += [p for p in product["references"] if (self.root / p).is_file()]
        for field in ("project_path", "metrics_path", "customer_context_path"):
            if request.get(field):
                references.append(request[field])
        if request["workflow"] in ("operations", "commerce"):
            references.append("08_工具链/01_业务脚本/funnel_metrics.py")
        refs = [self.reference(p) for p in dict.fromkeys(references)]
        steps = [{**s, "state": "pending", "output": None} for s in RECIPES[request["workflow"]]]
        return dict(request=request, modules=modules, steps=steps, source_refs=refs,
                    product_hash=product["record_hash"] if product else None,
                    canonical_sku=product["canonical_sku"] if product else None,
                    deliverable="review_package", external_execution="not_in_this_release",
                    skills={m: SKILLS[m] for m in business_modules})


class Engine:
    def __init__(self, root, state_dir=None):
        self.ws = Workspace(root)
        self.state = (Path(state_dir) if state_dir else self.ws.root / "08_工具链/07_电商Agent/.state").resolve()
        if not self.state.is_relative_to(self.ws.root):
            fail("INVALID_PATH", "task state must stay within workspace")
        self.state.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state / "tasks.sqlite"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, idem_key TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL, revision INTEGER NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, at TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _load(self, db, task_id):
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            fail("TASK_NOT_FOUND", task_id)
        return json.loads(row["data"])

    def _save(self, db, task, kind, details):
        task["revision"] += 1
        task["updated_at"] = now()
        db.execute("UPDATE tasks SET revision=?,data=? WHERE id=?", (task["revision"], encode(task), task["id"]))
        db.execute("INSERT INTO events(task_id,at,kind,data) VALUES(?,?,?,?)", (task["id"], now(), kind, encode(details)))

    def _version(self, task, revision):
        if type(revision) is not int or task["revision"] != revision:
            fail("REVISION_CONFLICT", "Reload task; expected revision no longer matches")

    def changes(self, task):
        changed = []
        if task["product_hash"]:
            product = self.ws.inspect_product(task["request"]["sku"], task["request"].get("listing_id"))
            if product["record_hash"] != task["product_hash"]:
                changed.append("product_record")
        for ref in task["source_refs"]:
            try:
                if file_hash(self.ws.file(ref["path"])) != ref["sha256"]:
                    changed.append(ref["path"])
            except CommerceError:
                changed.append(ref["path"])
        for s in task["steps"]:
            if s["output"]:
                try:
                    if file_hash(self.ws.file(s["output"]["path"])) != s["output"]["sha256"]:
                        changed.append("artifact:" + s["id"])
                except CommerceError:
                    changed.append("artifact:" + s["id"])
        return changed

    def _fresh(self, task):
        changed = self.changes(task)
        if changed:
            fail("STALE_EVIDENCE", "Sources or artifacts changed; refresh and review again: " + ", ".join(changed))

    def _step(self, task, step_id):
        matches = [s for s in task["steps"] if s["id"] == step_id]
        if not matches:
            fail("STEP_NOT_FOUND", step_id)
        s = matches[0]
        if any(next(x for x in task["steps"] if x["id"] == dependency)["state"] != "completed" for dependency in s["depends_on"]):
            fail("DEPENDENCY_PENDING", "Complete predecessor steps first")
        return s

    def _output(self, task, step_id, data):
        folder = self.state / "artifacts" / task["id"]
        folder.mkdir(parents=True, exist_ok=True)
        body = encode(data)
        path = folder / (step_id + "-" + hashlib.sha256(body.encode()).hexdigest()[:16] + ".json")
        temporary = folder / (str(uuid.uuid4()) + ".tmp")
        try:
            temporary.write_text(body + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return self.ws.reference(path.relative_to(self.ws.root).as_posix())

    def create_task(self, request, idempotency_key):
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 200:
            fail("INVALID_REQUEST", "nonempty idempotency_key up to 200 characters required")
        plan = self.ws.plan(request)
        req_hash = digest(plan["request"])
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM tasks WHERE idem_key=?", (idempotency_key,)).fetchone()
            if previous:
                if previous["request_hash"] != req_hash:
                    fail("IDEMPOTENCY_CONFLICT", "key already belongs to a different request")
                return self.get_task(previous["id"])
            task = dict(**plan, id=str(uuid.uuid4()), revision=0, created_at=now(), updated_at=now())
            db.execute("INSERT INTO tasks VALUES(?,?,?,?,?)", (task["id"], idempotency_key, req_hash, 0, encode(task)))
            db.execute("INSERT INTO events(task_id,at,kind,data) VALUES(?,?,?,?)", (task["id"], now(), "created", encode({"workflow": request["workflow"]})))
        return self.get_task(task["id"])

    def get_task(self, task_id):
        with self.connect() as db:
            task = self._load(db, task_id)
        changed = self.changes(task)
        completed = {s["id"] for s in task["steps"] if s["state"] == "completed"}
        task["stale_sources"] = changed
        task["ready_steps"] = [] if changed else [s["id"] for s in task["steps"] if s["state"] == "pending" and set(s["depends_on"]).issubset(completed)]
        task["status"] = "needs_refresh" if changed else "package_ready" if len(completed) == len(task["steps"]) else "in_progress"
        task["platform_published"] = False
        task["paid_generation_submitted"] = False
        return task

    def list_tasks(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            fail("INVALID_REQUEST", "limit must be 1..100")
        with self.connect() as db:
            rows = db.execute("SELECT id FROM tasks ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [{k: task[k] for k in ("id", "revision", "status", "canonical_sku", "request", "ready_steps")} for task in (self.get_task(r["id"]) for r in rows)]

    def context(self, task_id, step_id):
        task = self.get_task(task_id)
        self._fresh(task)
        s = self._step(task, step_id)
        refs = task["source_refs"]
        return dict(task_id=task_id, revision=task["revision"], request=task["request"], step=s,
                    sources=refs, predecessor_outputs=[p["output"] for p in task["steps"] if p["id"] in s["depends_on"]],
                    skills=task["skills"].get(s["module"], []),
                    contract="commerce/contracts.py validate_artifact; reviewer is agent, never user approval",
                    read_instruction="Read source files relevant to this step in the host. Product facts and external authorizations stay in their canonical sources.")

    def run_step(self, task_id, step_id, expected_revision):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = self._load(db, task_id)
            self._fresh(task)
            s = self._step(task, step_id)
            if s["executor"] != "runtime":
                fail("AGENT_STEP", "host agent must prepare a real artifact and call complete_step")
            if s["state"] == "completed":
                return self.get_task(task_id)
            self._version(task, expected_revision)
            if step_id == "identity":
                data = {"kind": "identity", "summary": "Canonical identity resolved; source/physical facts still require business review",
                        **self.ws.inspect_product(task["request"]["sku"], task["request"].get("listing_id"))}
            elif step_id == "metrics":
                path = task["request"].get("metrics_path")
                if not path:
                    fail("INPUT_REQUIRED", "metrics_path required; do not invent operating data")
                data = {"kind": "metrics", "summary": "Comparable funnel slice computed", **analyze_metrics(self.ws, path)}
                if normalize_channel(data["result"]["channel"]) != normalize_channel(task["request"]["channel"]):
                    fail("CHANNEL_MISMATCH", "CSV channel differs from requested operating scope")
            else:
                fail("UNSUPPORTED_STEP", step_id)
            s["output"] = self._output(task, step_id, data)
            s["state"] = "completed"
            self._save(db, task, "runtime_step_completed", {"step": step_id, "output": s["output"]})
        return self.get_task(task_id)

    def complete_step(self, task_id, step_id, artifact_path, expected_revision):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = self._load(db, task_id)
            self._fresh(task)
            s = self._step(task, step_id)
            if s["executor"] != "agent":
                fail("RUNTIME_STEP", "use run_step for runtime evidence")
            data = self.ws.json(artifact_path)
            try:
                validate_artifact(data, s["artifact_kind"], task["request"]["workflow"])
            except ValueError as exc:
                fail("INVALID_ARTIFACT", str(exc))
            if s["artifact_kind"] == "customer_draft":
                if data["context_path"] != task["request"].get("customer_context_path"):
                    fail("INVALID_ARTIFACT", "customer context must match the selected task context")
            if data.get("sku") != task["canonical_sku"] and task["canonical_sku"]:
                fail("INVALID_ARTIFACT", "artifact sku must match canonical identity")
            if data.get("task_id") != task_id:
                fail("INVALID_ARTIFACT", "artifact must carry its task_id")
            ref = self.ws.reference(artifact_path)
            if s["state"] == "completed":
                if s["output"]["sha256"] != ref["sha256"]:
                    fail("STEP_ALREADY_COMPLETED", "refresh task before replacing completed artifacts")
                return self.get_task(task_id)
            self._version(task, expected_revision)
            s["output"] = {**ref, "authority": "agent_declared", "kind": s["artifact_kind"]}
            s["state"] = "completed"
            self._save(db, task, "agent_step_completed", {"step": step_id, "output": s["output"]})
        return self.get_task(task_id)

    def refresh_task(self, task_id, expected_revision, reason):
        if not isinstance(reason, str) or not reason.strip():
            fail("INVALID_REQUEST", "refresh reason required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = self._load(db, task_id)
            self._version(task, expected_revision)
            plan = self.ws.plan(task["request"])
            prior = [{"step": s["id"], "output": s["output"]} for s in task["steps"] if s["output"]]
            task.update(plan)
            self._save(db, task, "sources_refreshed", {"reason": reason, "superseded_outputs": prior})
        return self.get_task(task_id)

    def submit_artifact(self, task_id, step_id, artifact, expected_revision):
        """Chat-friendly submission. Caller supplies the actual professional judgment."""
        task = self.get_task(task_id)
        self._fresh(task)
        s = self._step(task, step_id)
        if s["executor"] != "agent" or not isinstance(artifact, dict):
            fail("INVALID_ARTIFACT", "an agent step and object artifact are required")
        if artifact.get("task_id", task_id) != task_id or artifact.get("sku", task["canonical_sku"]) != task["canonical_sku"]:
            fail("INVALID_ARTIFACT", "artifact identity mismatch")
        artifact = {**artifact, "task_id": task_id, "sku": task["canonical_sku"]}
        try:
            validate_artifact(artifact, s["artifact_kind"], task["request"]["workflow"])
        except ValueError as exc:
            fail("INVALID_ARTIFACT", str(exc))
        # The transaction in complete_step checks revision/source again after writing the local draft.
        if s["state"] != "completed":
            self._version(task, expected_revision)
        ref = self._output(task, step_id, artifact)
        return self.complete_step(task_id, step_id, ref["path"], expected_revision)

    def events(self, task_id):
        with self.connect() as db:
            self._load(db, task_id)
            rows = db.execute("SELECT at,kind,data FROM events WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
        return [dict(at=r["at"], kind=r["kind"], data=json.loads(r["data"])) for r in rows]

    def capabilities(self):
        return dict(version=VERSION, workflows=list(RECIPES), model_execution="host Codex reasoning and existing skills",
                    runtime_actions=["canonical_product_lookup", "task_plan", "durable_tasks", "artifact_version_checks", "comparable_metrics"],
                    platform_reads=["alibaba.product.get", "libtv.node"],
                    external_writes=[], paid_generation=False,
                    extension_contract="Add a recipe, artifact contract and official platform adapter; do not duplicate product ledger or CRM")

    def doctor(self):
        client = self.ws.root / ".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py"
        libtv = Path.home() / ".libtv/libtv.exe"
        return dict(workspace=str(self.ws.root), version=VERSION, state_directory=str(self.state),
                    ledger_available=True, alibaba_client_available=client.is_file(), libtv_cli_available=libtv.is_file(),
                    platform_authentication="not_checked", model_provider="host", extra_model_api_key_required=False)


def analyze_metrics(ws, relative):
    path = ws.file(relative)
    if path.stat().st_size > 5_000_000:
        fail("INPUT_TOO_LARGE", "metrics CSV exceeds 5MB")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    try:
        for row in rows:
            start, end = date.fromisoformat(row["period_start"]), date.fromisoformat(row["period_end"])
            if start > end or not Decimal(row["spend"]).is_finite():
                raise ValueError("invalid period or non-finite spend")
        module_path = ws.file("08_工具链/01_业务脚本/funnel_metrics.py")
        spec = importlib.util.spec_from_file_location("bq_funnel_metrics", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.aggregate(rows)
    except (KeyError, ValueError, InvalidOperation) as exc:
        fail("INCOMPARABLE_METRICS", str(exc))
    return dict(result=result, source=ws.reference(relative), implementation=ws.reference("08_工具链/01_业务脚本/funnel_metrics.py"),
                interpretation="Arithmetic only; causal or growth claims require agent analysis and buyer evidence")
