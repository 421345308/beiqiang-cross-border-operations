"""Task recipes and deliverable contracts, not a second business policy store."""

from .strategy import platform_id, targets_for, validate_options

LEDGER = "02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json"
ENTRIES = {
    "product": ["02_Alibaba运营/AGENTS.md", "02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md"],
    "content": ["05_内容与视频/AGENTS.md", "05_内容与视频/README.md"],
    "operations": ["00_总控台/全渠道增长总控.md", "06_市场研究/README.md"],
    "customer": ["04_客户开发/README.md"],
}
SKILLS = {
    "product": ["alibaba-product-optimizer", "alibaba-international-operations", "alibaba-openapi-operator"],
    "content": ["tiktok-b2b-content", "video-reference-assets", "beiqiang-seedance-video", "ai-video-learning-system", "libtv-cli", "video-use"],
    "operations": ["weekly-data-review", "market-demand-research", "p4p-keyword-testing"],
    "customer": ["rfq-quote-assistant", "inquiry-follow-up"],
}

def step(key, module, executor, kind, depends=()):
    return dict(id=key, module=module, executor=executor, artifact_kind=kind, depends_on=list(depends))

IDENTITY = step("identity", "product", "runtime", "identity")
TITLE = [step("title", "product", "agent", "title_draft", ("identity",)),
         step("review", "product", "agent", "review", ("title",))]
LISTING = [step("listing", "product", "agent", "listing_draft", ("identity",)),
           step("review", "product", "agent", "review", ("listing",))]
VIDEO = [step("brief", "content", "agent", "video_brief", ("identity",)),
         step("review", "content", "agent", "review", ("brief",))]
OPERATIONS = [step("metrics", "operations", "runtime", "metrics", ()),
              step("recommendation", "operations", "agent", "operations_plan", ("metrics",)),
              step("review", "operations", "agent", "review", ("recommendation",))]
CUSTOMER = [step("followup", "customer", "agent", "customer_draft", ("identity",)),
            step("review", "customer", "agent", "review", ("followup",))]
COMMERCE = [step("listing", "product", "agent", "listing_draft", ("identity",)),
            step("brief", "content", "agent", "video_brief", ("identity",)),
            step("metrics", "operations", "runtime", "metrics"),
            step("recommendation", "operations", "agent", "operations_plan", ("metrics", "listing", "brief")),
            step("followup", "customer", "agent", "customer_draft", ("recommendation",)),
            step("review", "operations", "agent", "review", ("listing", "brief", "recommendation", "followup"))]
RECIPES = {"title": [IDENTITY, *TITLE], "listing": [IDENTITY, *LISTING],
           "video": [IDENTITY, *VIDEO], "operations": OPERATIONS,
           "customer": [IDENTITY, *CUSTOMER], "commerce": [IDENTITY, *COMMERCE], "campaign": []}
REVIEWS = {
    "title": ["identity", "claims", "buyer_language", "scope"],
    "listing": ["identity", "claims", "fields", "images", "inquiry_hook"],
    "video": ["story", "dialogue", "acting", "product", "motion", "props", "audio", "continuity"],
    "operations": ["comparable_data", "attribution", "business_outcome", "next_action"],
    "customer": ["buyer_context", "terms", "product_evidence", "stop_contact", "next_action"],
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + " must be nonempty text")

def normalize_channel(channel):
    value = channel.strip().lower()
    return platform_id(value) or value

def validate_artifact(data, kind, workflow, target=None, strategy=None):
    require(isinstance(data, dict) and data.get("kind") == kind, "artifact kind mismatch")
    text(data.get("summary"), "summary")
    # These are explicit agent reports. Structural checks cannot establish truth or aesthetics.
    if kind == "title_draft":
        text(data.get("title"), "title")
        text(data.get("rationale"), "rationale")
        require(isinstance(data.get("claim_evidence"), list), "claim_evidence must be a list")
    elif kind == "listing_draft":
        require(isinstance(data.get("fields"), dict) and data["fields"], "fields required")
        for name in ("claim_evidence", "image_roles", "unconfirmed"):
            require(isinstance(data.get(name), list), name + " must be a list")
    elif kind == "video_brief":
        for name in ("objective", "audience", "channel", "language", "product_role"):
            text(data.get(name), name)
        duration = data.get("duration_seconds")
        require(type(duration) in (int, float) and 0 < duration <= 600, "invalid duration")
        scenes = data.get("scenes")
        require(isinstance(scenes, list) and bool(scenes), "scenes required")
        cursor = 0
        for scene in scenes:
            require(isinstance(scene, dict), "scene must be an object")
            start, end = scene.get("start"), scene.get("end")
            require(type(start) in (int, float) and type(end) in (int, float)
                    and abs(start - cursor) < 0.001 and end > start, "scenes must form a contiguous timeline")
            cursor = end
            for name in ("action", "cause_and_effect", "product_visibility"):
                text(scene.get(name), name)
            require(isinstance(scene.get("dialogue"), list), "dialogue must be a list")
        require(abs(cursor - duration) < 0.001, "scene timeline does not match duration")
        for name in ("acting", "motion", "props", "audio", "continuity"):
            text(data.get("production_checks", {}).get(name), "production_checks." + name)
    elif kind == "operations_plan":
        for name in ("observations", "hypotheses", "actions", "missing_data"):
            require(isinstance(data.get(name), list), name + " must be a list")
    elif kind == "customer_draft":
        for name in ("context_path", "channel", "message", "next_action"):
            text(data.get(name), name)
        require(data.get("sent") is False, "this release prepares messages; sent must be false")
        require(isinstance(data.get("unconfirmed_terms"), list), "unconfirmed_terms must be a list")
    elif kind == "positioning":
        for name in ("audiences", "use_cases", "claim_evidence", "unconfirmed"):
            require(isinstance(data.get(name), list) and (data[name] or name == "unconfirmed"), name + " required")
        text(data.get("product_role"), "product_role")
        require(isinstance(data.get("channel_differences"), dict), "channel_differences required")
        require(set(data["channel_differences"]) == {p["target"]["id"] for p in strategy["targets"]}, "positioning must cover exact requested targets")
    elif kind in ("channel_listing", "channel_content", "landing_page"):
        require(target is not None, "target-scoped step required")
        require(data.get("target_id") == target["id"] and data.get("platform") == target["platform"] and data.get("placement") == target["placement"], "artifact target mismatch")
        require(data.get("language") == target["language"], "target language mismatch")
        for field in ("market_scope", "customer_segment"):
            if field in data:
                require(data[field] == target[field], "artifact " + field + " mismatch")
        for name in ("claim_evidence", "unconfirmed"):
            require(isinstance(data.get(name), list), name + " required")
        if kind == "channel_listing":
            require(isinstance(data.get("fields"), dict) and data["fields"], "channel-specific fields required")
            require(isinstance(data.get("image_roles"), list) and data["image_roles"], "image roles required")
            text(data.get("schema_status"), "schema_status")
        elif kind == "landing_page":
            require(isinstance(data.get("sections"), list) and data["sections"], "landing sections required")
            text(data.get("cta"), "cta")
            text(data.get("message_match"), "message_match")
        else:
            variants = data.get("variants")
            require(isinstance(variants, list) and variants, "concrete creative variants required")
            require(all(isinstance(v, dict) for v in variants), "each creative variant must be an object")
            expected = next(p for p in strategy["targets"] if p["target"]["id"] == target["id"])["variants"]
            require(len(variants) == len(expected), "duplicate or extra variants cannot stand in for complete coverage")
            require({v.get("variant_id") for v in variants} == {v["variant_id"] for v in expected}, "creative variants must cover selected strategy, not silently drop routes")
            for variant in variants:
                for name in ("hook", "product_role", "ending", "sound", "cta"):
                    text(variant.get(name), name)
                require(isinstance(variant.get("beats"), list) and variant["beats"], "specific events/steps required")
                require(isinstance(variant.get("asset_plan"), list) and variant["asset_plan"], "role-bound asset plan required")
                require(isinstance(variant.get("production_checks"), dict) and variant["production_checks"], "production checks required")
    elif kind == "experiment_plan":
        rows = data.get("experiments")
        require(isinstance(rows, list), "experiments required")
        require(all(isinstance(r, dict) for r in rows), "each experiment must be an object")
        require(len(rows) == len(strategy["targets"]), "one experiment per target required; duplicate rows are not coverage")
        require({r.get("target_id") for r in rows} == {p["target"]["id"] for p in strategy["targets"]}, "experiments must cover exact targets")
        for row in rows:
            for name in ("hypothesis", "variable", "primary_metric", "data_needed", "stop_rule"):
                text(row.get(name), name)
            require(isinstance(row.get("hold_constant"), list) and row["hold_constant"], "comparison conditions required")
            require("baseline" in row, "unknown baseline must be explicit null, not an invented zero")
    elif kind == "campaign_review":
        require(data.get("reviewer") == "agent" and data.get("decision") == "ready_for_user_review", "agent campaign review required")
        expected = {p["target"]["id"] for p in strategy["targets"]}
        require(isinstance(data.get("target_checks"), dict) and set(data["target_checks"]) == expected, "exact channel coverage required")
        for checks in data["target_checks"].values():
            for criterion in ("audience", "platform_fit", "claims", "creative_difference", "asset_feasibility", "measurement", "handoff"):
                check = checks.get(criterion, {})
                require(check.get("status") in ("pass", "not_applicable"), criterion + " unresolved")
                text(check.get("evidence"), criterion + " evidence")
    elif kind == "review":
        require(data.get("decision") == "ready_for_user_review", "unresolved review cannot complete a step")
        criteria = list(dict.fromkeys(c for w in (REVIEWS if workflow == "commerce" else [workflow]) for c in REVIEWS[w]))
        checks = data.get("checks", {})
        for criterion in criteria:
            check = checks.get(criterion, {})
            require(check.get("status") in ("pass", "not_applicable"), criterion + " review unresolved")
            text(check.get("evidence"), criterion + " evidence/reason")
        require(data.get("reviewer") == "agent", "agent review is not user approval")

def validate_request(request):
    require(isinstance(request, dict), "request must be an object")
    allowed = {"workflow", "goal", "sku", "listing_id", "channel", "language", "project_path", "metrics_path", "customer_context_path",
               "platform", "placement", "business_model", "market", "audience", "goal_type", "market_scope", "customer_segment", "category", "affordances", "creative", "supporting_evidence", "targets"}
    require(not set(request) - allowed, "unknown request fields: " + str(sorted(set(request) - allowed)))
    require(request.get("workflow") in RECIPES, "select an explicit supported workflow")
    for name in ("goal", "channel", "language"):
        text(request.get(name), name)
    validate_options(request)
    targets = targets_for(request)
    if request["workflow"] in ("title", "listing", "commerce", "campaign"):
        require(bool(targets), "select a supported platform for preparation")
    if request["workflow"] != "campaign":
        require(len(targets) <= 1, "multiple targets use campaign workflow")
    if request.get("listing_id") and request["workflow"] in ("title", "listing", "commerce", "campaign"):
        require(all(t["platform"] == "alibaba" for t in targets), "listing_id selects an Alibaba link; do not bind that ID to another platform")
    if request["workflow"] != "operations":
        text(request.get("sku"), "sku")
    if request["workflow"] in ("operations", "commerce"):
        text(request.get("metrics_path"), "metrics_path")
    if request["workflow"] in ("customer", "commerce"):
        text(request.get("customer_context_path"), "customer_context_path")
    for name, value in request.items():
        if name not in ("targets", "affordances", "creative", "supporting_evidence"):
            text(value, name)
    return request.copy()
