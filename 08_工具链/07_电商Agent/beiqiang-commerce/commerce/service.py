"""Shared tool surface for MCP and CLI."""
from .runtime import analyze_metrics
from .platforms import read_platform
from .strategy import catalog
from .business import snapshot

def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}

STR = {"type": "string", "minLength": 1}
INT = {"type": "integer", "minimum": 0}
TASK = {"task_id": STR}
STEP = {**TASK, "step_id": STR}
TOOLS = [
    ("commerce_capabilities", "Inspect preparation vs connected execution; platform profiles do not imply authenticated accounts.", obj({}), True),
    ("commerce_catalog", "Discover platform placements, category lenses and creative routes; optionally read a selected profile.", obj({"platform": STR, "category": STR}), True),
    ("commerce_strategy", "Prepare evidence-aware creative alternatives and channel-specific objectives/assets/metrics for a product request.", obj({"request": {"type": "object"}}, ("request",)), True),
    ("commerce_doctor", "Check local files and runtime, without reading or printing credentials.", obj({}), True),
    ("commerce_product", "Resolve SKU/alias and all selected listing/source evidence from the canonical local ledger.", obj({"sku": STR, "listing_id": STR}, ("sku",)), True),
    ("commerce_plan", "Plan only an explicit workflow; preserve requested scope and actual sources.", obj({"request": {"type": "object"}}, ("request",)), True),
    ("commerce_create", "Create a durable local task; reusing the same key/request recovers the original task.", obj({"request": {"type": "object"}, "idempotency_key": STR}, ("request", "idempotency_key")), False),
    ("commerce_task", "Read progress, ready steps, stale sources and exact evidence. Package readiness is not publishing.", obj(TASK, ("task_id",)), True),
    ("commerce_tasks", "List local tasks, including pending and resumable work.", obj({"limit": {"type": "integer", "minimum": 1, "maximum": 100}}), True),
    ("commerce_context", "Get relevant source paths, predecessor evidence, skills and artifact contract for a step.", obj(STEP, ("task_id", "step_id")), True),
    ("commerce_run", "Run a local identity or metrics step. Model-authored steps require a real artifact.", obj({**STEP, "expected_revision": INT}, (*STEP, "expected_revision")), False),
    ("commerce_complete", "Validate and register an agent-authored JSON artifact; requires matching task, SKU, dependencies and revision.", obj({**STEP, "artifact_path": STR, "expected_revision": INT}, (*STEP, "artifact_path", "expected_revision")), False),
    ("commerce_submit_artifact", "Save a real agent-authored artifact from chat and complete its local step; no external publication.", obj({**STEP, "artifact": {"type": "object"}, "expected_revision": INT}, (*STEP, "artifact", "expected_revision")), False),
    ("commerce_refresh", "Explicitly refresh source versions and reset steps for review; preserves superseded evidence in events.", obj({**TASK, "expected_revision": INT, "reason": STR}, (*TASK, "expected_revision", "reason")), False),
    ("commerce_events", "Read task history and superseded evidence references.", obj(TASK, ("task_id",)), True),
    ("commerce_stage_change", "Stage the exact field diff of a completed draft, with optional namespace-bound baseline. Saves preview only; never applies a write.", obj({**STEP, "idempotency_key": STR, "expected_revision": INT, "baseline_path": STR}, (*STEP, "idempotency_key", "expected_revision")), False),
    ("commerce_change", "Read staged field changes and detect stale task/baseline evidence.", obj({"change_id": STR}, ("change_id",)), True),
    ("commerce_export", "Render a local review package with actual channel variants and step evidence; does not publish it.", obj(TASK, ("task_id",)), False),
    ("commerce_metrics", "Compute a comparable dated funnel CSV with the existing central implementation; mixed slices fail.", obj({"metrics_path": STR}, ("metrics_path",)), True),
    ("commerce_business_snapshot", "Read normalized multi-channel observations in separate slices; unknown figures stay null and retail/B2B outcomes are not pooled.", obj({"metrics_path": STR}), True),
    ("commerce_platform_read", "Read a specific Alibaba product or LibTV node via its official existing client; saves local evidence, no canonical sync.", obj({"platform": {"type": "string", "enum": ["alibaba", "libtv"]}, "target_id": STR, "sku": STR, "project_id": STR}, ("platform", "target_id")), False),
]

def tool_list():
    return [dict(name=name, description=description, inputSchema=schema,
                 annotations={"readOnlyHint": readonly, "destructiveHint": False,
                              "idempotentHint": name != "commerce_platform_read", "openWorldHint": name == "commerce_platform_read"})
            for name, description, schema, readonly in TOOLS]

def validate_arguments(name, args):
    schemas = {t[0]: t[2] for t in TOOLS}
    if not isinstance(name, str) or name not in schemas:
        raise ValueError("unknown tool")
    schema = schemas[name]
    if not isinstance(args, dict) or set(args) - set(schema["properties"]) or set(schema["required"]) - set(args):
        raise ValueError("missing or unknown arguments")
    for key, value in args.items():
        rule = schema["properties"][key]
        valid = {"string": isinstance(value, str) and bool(value.strip()), "integer": type(value) is int,
                 "object": isinstance(value, dict)}[rule["type"]]
        if not valid or ("enum" in rule and value not in rule["enum"]):
            raise ValueError("invalid argument: " + key)
        if type(value) is int and (value < rule.get("minimum", value) or value > rule.get("maximum", value)):
            raise ValueError("argument out of range: " + key)

def call(engine, name, args):
    validate_arguments(name, args)
    handlers = {
        "commerce_capabilities": engine.capabilities, "commerce_doctor": engine.doctor,
        "commerce_catalog": catalog, "commerce_strategy": engine.ws.strategy,
        "commerce_product": engine.ws.inspect_product, "commerce_plan": engine.ws.plan,
        "commerce_create": engine.create_task, "commerce_task": engine.get_task, "commerce_tasks": engine.list_tasks,
        "commerce_context": engine.context, "commerce_run": engine.run_step, "commerce_complete": engine.complete_step,
        "commerce_submit_artifact": engine.submit_artifact,
        "commerce_refresh": engine.refresh_task, "commerce_events": engine.events,
        "commerce_stage_change": engine.stage_change, "commerce_change": engine.get_change, "commerce_export": engine.export_task,
        "commerce_metrics": lambda metrics_path: analyze_metrics(engine.ws, metrics_path),
        "commerce_business_snapshot": lambda metrics_path=None: snapshot(engine.ws, metrics_path),
        "commerce_platform_read": lambda **kwargs: read_platform(engine, **kwargs),
    }
    return handlers[name](**args)
