"""Task recipes and deliverable contracts, not a second business policy store."""

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
           "customer": [IDENTITY, *CUSTOMER], "commerce": [IDENTITY, *COMMERCE]}
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
    return "alibaba" if value in ("alibaba", "alibaba.com", "国际站", "阿里巴巴国际站") else value

def validate_artifact(data, kind, workflow):
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
    allowed = {"workflow", "goal", "sku", "listing_id", "channel", "language", "project_path", "metrics_path", "customer_context_path"}
    require(not set(request) - allowed, "unknown request fields: " + str(sorted(set(request) - allowed)))
    require(request.get("workflow") in RECIPES, "select an explicit supported workflow")
    for name in ("goal", "channel", "language"):
        text(request.get(name), name)
    if request["workflow"] in ("title", "listing", "commerce"):
        require(normalize_channel(request["channel"]) == "alibaba", "v0.1 listing workflows support Alibaba; other platform rules are not implemented")
    if request["workflow"] != "operations":
        text(request.get("sku"), "sku")
    if request["workflow"] in ("operations", "commerce"):
        text(request.get("metrics_path"), "metrics_path")
    if request["workflow"] in ("customer", "commerce"):
        text(request.get("customer_context_path"), "customer_context_path")
    for name, value in request.items():
        text(value, name)
    return request.copy()
