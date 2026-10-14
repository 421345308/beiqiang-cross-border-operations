"""Multi-platform editorial planning. Scores are transparent heuristics, never performance predictions."""
import hashlib
import json

from .catalogs import CATALOG_VERSION, PLATFORMS, LENSES, ROUTES, SOURCES, CUSTOMER_SEGMENTS

GOALS = ("discovery", "consideration", "purchase", "inquiry", "retention", "brand")
AFFORDANCES = {a for lens in LENSES.values() for a in lens["candidate_affordances"]} | {a for route in ROUTES.values() for a in route["affordances"]}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def platform_id(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return next((key for key, profile in PLATFORMS.items() if value == key or value in profile["aliases"]), None)

def scope_for(platform, operating_scope=None):
    record = (operating_scope or {}).get("channels", {}).get(platform)
    if record:
        return record
    return dict(status="future_option" if PLATFORMS[platform].get("extension_only") else "unverified",
                market_scope=None, progress="Company operating progress not loaded; a template is not an operating channel")

def targets_for(request, operating_scope=None):
    raw_targets = request.get("targets")
    if raw_targets is None:
        platform = platform_id(request.get("platform") or request.get("channel"))
        if not platform:
            require(not request.get("platform"), "unknown platform")
            return []  # v0.1 generic video-channel requests remain usable.
        raw_targets = [{k: request[k] for k in ("placement", "business_model", "market", "audience", "goal_type", "market_scope", "customer_segment") if k in request} | {"platform": platform}]
    require(isinstance(raw_targets, list) and 1 <= len(raw_targets) <= 8, "targets must contain 1..8 placements")
    result, seen = [], set()
    for item in raw_targets:
        require(isinstance(item, dict) and not set(item) - {"platform", "placement", "business_model", "market", "audience", "goal_type", "language", "market_scope", "customer_segment"}, "invalid target fields")
        require(all(isinstance(value, str) and value.strip() for value in item.values()), "target values must be nonempty text")
        platform = platform_id(item.get("platform"))
        require(platform is not None, "unknown target platform")
        profile = PLATFORMS[platform]
        default = profile["default_placement"]
        if request["workflow"] == "video":
            default = next((k for k, v in profile["placements"].items() if v["media_type"] == "video"), default)
        elif request["workflow"] in ("listing", "commerce"):
            default = next((k for k, v in profile["placements"].items() if v["artifact_kind"] == "channel_listing"), default)
        surface = item.get("placement", default)
        require(surface in profile["placements"], "placement is not part of selected platform")
        if request["workflow"] in ("listing", "commerce"):
            require(profile["placements"][surface]["artifact_kind"] == "channel_listing", "selected placement is not a product listing")
        model = item.get("business_model", profile["default_business_model"])
        require(model in profile["business_models"], "unsupported business model for platform")
        operating = scope_for(platform, operating_scope)
        market_scope = item.get("market_scope") or request.get("market_scope") or operating.get("market_scope") or ("domestic" if platform in ("douyin", "xiaohongshu", "wechat") else "international")
        require(market_scope in ("domestic", "international"), "market_scope must be domestic or international")
        default_customer = ("domestic_business_buyer" if market_scope == "domestic" else "overseas_business_buyer") if model == "b2b" else "consumer"
        customer = item.get("customer_segment") or request.get("customer_segment") or default_customer
        require(customer in CUSTOMER_SEGMENTS, "unknown customer_segment")
        require(model in CUSTOMER_SEGMENTS[customer]["business_models"], "customer segment and business model disagree")
        if customer in ("domestic_business_buyer", "overseas_business_buyer"):
            require(market_scope == ("domestic" if customer == "domestic_business_buyer" else "international"), "procurement customer geography and market scope disagree")
        goal = item.get("goal_type", "inquiry" if model == "b2b" else "discovery" if profile["placements"][surface]["artifact_kind"] == "channel_content" else "purchase")
        require(goal in GOALS, "unknown goal_type")
        language = item.get("language", request["language"])
        for value in item.values():
            require(isinstance(value, str) and bool(value.strip()), "target values must be nonempty text")
        identity = (platform, surface, item.get("market"), language)
        require(identity not in seen, "duplicate platform/placement/market/language target")
        seen.add(identity)
        result.append(dict(id=f"{platform}_{surface}_{len(result)+1}", platform=platform, placement=surface,
                           business_model=model, goal_type=goal, language=language, market=item.get("market"),
                           market_scope=market_scope, customer_segment=customer, operating_status=operating["status"], operating_progress=operating["progress"],
                           audience=item.get("audience") or request.get("audience") or profile["audience"], media_type=profile["placements"][surface]["media_type"]))
    return result

def validate_options(request):
    for field in ("market_scope", "customer_segment"):
        if field in request:
            require(isinstance(request[field], str) and request[field].strip(), field + " must be nonempty text")
    if "market_scope" in request:
        require(request["market_scope"] in ("domestic", "international"), "unknown market_scope")
    if "customer_segment" in request:
        require(request["customer_segment"] in CUSTOMER_SEGMENTS, "unknown customer_segment")
    if request.get("category"):
        require(request["category"] in LENSES, "unsupported category lens")
    features = request.get("affordances", [])
    require(isinstance(features, list) and all(isinstance(f, str) for f in features) and len(features) == len(set(features)) and all(f in AFFORDANCES for f in features), "unknown/duplicate affordances")
    creative = request.get("creative", {})
    require(isinstance(creative, dict) and not set(creative) - {"count", "styles", "duration_seconds", "speech_mode", "no_face", "max_complexity"}, "invalid creative options")
    count = creative.get("count", 3)
    require(type(count) is int and 1 <= count <= 6, "creative.count must be 1..6")
    styles = creative.get("styles", [])
    require(isinstance(styles, list) and all(isinstance(s, str) for s in styles) and len(styles) == len(set(styles)) and all(s in ROUTES for s in styles), "unknown/duplicate creative styles")
    if styles:
        require(len(styles) <= count, "creative.count cannot omit explicitly selected styles")
    if "duration_seconds" in creative:
        d = creative["duration_seconds"]
        require(type(d) in (int, float) and 0 < d <= 600, "invalid creative duration")
    if "speech_mode" in creative:
        require(creative["speech_mode"] in ("onscreen", "voiceover", "music_sfx", "mixed"), "invalid speech mode")
    if "no_face" in creative:
        require(type(creative["no_face"]) is bool, "no_face must be a boolean")
    require(type(creative.get("max_complexity", 3)) is int and creative.get("max_complexity", 3) in (1, 2, 3), "max_complexity must be 1..3")
    evidence = request.get("supporting_evidence", [])
    require(isinstance(evidence, list), "supporting_evidence must be a list")
    for e in evidence:
        require(isinstance(e, dict) and set(e) == {"kind", "path", "basis"}, "evidence needs kind/path/basis")
        require(e["kind"] in ("test", "factory", "comparison", "specification", "visual"), "unknown evidence kind")
        require(all(isinstance(v, str) and v.strip() for v in e.values()), "evidence basis is required")

def catalog(platform=None, category=None, include_future=False, operating_scope=None):
    require(type(include_future) is bool, "include_future must be a boolean")
    profiles = [{"id": k, "name": p["name"], "placements": list(p["placements"]), "live_status": p["live_status"], "operating_scope": scope_for(k, operating_scope)} for k, p in PLATFORMS.items()]
    result = dict(version=CATALOG_VERSION, platforms=[p for p in profiles if include_future or p["operating_scope"]["status"] != "future_option"],
                  future_options=[p for p in profiles if p["operating_scope"]["status"] == "future_option"],
                  operating_scope_source=(operating_scope or {}).get("source"),
                  customer_segments=[{"id": k, **v} for k, v in CUSTOMER_SEGMENTS.items()],
                  categories=[{"id": k, "name": v["name"]} for k, v in LENSES.items()],
                  styles=[{"id": k, "name": v["name"], "family": v["family"]} for k, v in ROUTES.items()],
                  distinction="template support != current company scope != started operations != connected execution")
    if platform:
        key = platform_id(platform)
        require(key is not None, "unknown platform")
        result["selected_platform"] = {"id": key, **PLATFORMS[key], "operating_scope": scope_for(key, operating_scope)}
    if category:
        require(category in LENSES, "unknown category")
        result["selected_category"] = {"id": category, **LENSES[category], "basis": "category questions/candidates; not verified SKU properties"}
    return result

def strategy_for(request, evidence_refs=(), operating_scope=None):
    validate_options(request)
    targets = targets_for(request, operating_scope)
    category = request.get("category", "general")
    lens = LENSES[category]
    confirmed_inputs = set(request.get("affordances", []))
    # Evidence types count only after the workspace has actually resolved their files.
    available_evidence = {e["kind"] for e in evidence_refs}
    creative = request.get("creative", {})
    plans = []
    for target in targets:
        profile = PLATFORMS[target["platform"]]
        surface = profile["placements"][target["placement"]]
        ranked, excluded = [], []
        for key, route in ROUTES.items():
            missing = sorted(set(route["required_evidence"]) - available_evidence)
            if missing or route["complexity"] > creative.get("max_complexity", 3) or creative.get("no_face") and route["face_required"]:
                excluded.append(dict(style=key, reason="required_evidence_or_production_constraint", missing_evidence=missing))
                continue
            parts = {
                "category": 6 if category in route["category_fit"] else 0,
                "goal": 3 if target["goal_type"] in route["goal_fit"] else 0,
                "placement": surface["family_preferences"].get(route["family"], 0),
                "customer": CUSTOMER_SEGMENTS[target["customer_segment"]]["family_preferences"].get(route["family"], 0),
                "declared_affordances": len(confirmed_inputs.intersection(route["affordances"])) * 2,
            }
            ranked.append(dict(style=key, name=route["name"], family=route["family"], score=sum(parts.values()), score_components=parts, complexity=route["complexity"]))
        ranked.sort(key=lambda row: (-row["score"], row["complexity"], row["style"]))
        selected = []
        styles = creative.get("styles", [])
        eligible = {row["style"]: row for row in ranked}
        for style in styles:
            require(style in eligible, "selected style needs missing evidence or exceeds production constraint: " + style)
            selected.append(eligible[style])
        if not styles:
            # Prefer different ways of persuading, not three aliases of one aesthetic.
            remaining = ranked.copy()
            while remaining and len(selected) < creative.get("count", 3):
                families = {s["family"] for s in selected}
                choice = max(remaining, key=lambda row: (row["score"] - (3 if row["family"] in families else 0), -row["complexity"]))
                selected.append(choice)
                remaining.remove(choice)
        variants = []
        for row in selected:
            route = ROUTES[row["style"]]
            variants.append({**row, "variant_id": target["id"] + "__" + row["style"],
                "angle": route["hook"], "story_beats": route["story_beats"], "proof_method": route["proof"],
                "sound_direction": creative.get("speech_mode") or route["audio"], "ending_direction": route["ending"],
                "duration_seconds": creative.get("duration_seconds") if surface["media_type"] == "video" else None,
                "duration_basis": "not_applicable_to_this_surface" if surface["media_type"] != "video" else "user_selected" if creative.get("duration_seconds") else "choose per event and placement; not a platform limit",
                "asset_roles": ["真实商品身份/细节原件", "对应场景与动作参考", "角色/手部参考（按创意需要）", "道具与接触/支撑（按镜头需要）"],
                "production_notes": lens["failure_modes"],
                "fixed": ["SKU/外观与有效主张证据", "target platform/placement/audience/goal", "明确的授权与生成状态"],
                "vary": ["开头问题/事件", "场景", "镜头动作", "声音形式", "收尾及CTA"],
                "interpretation": "director starting point; host must write specific events/dialogue and check actual evidence"})
        metrics = surface["metrics"]
        if target["business_model"] == "b2b":
            metrics = [m for m in metrics if m not in ("paid_orders", "checkout_conversion", "refund_rate", "return_rate")] + ["qualified_inquiries", "sample_discussions"]
        elif target["business_model"] == "retail":
            metrics = [m for m in metrics if m not in ("qualified_inquiries", "sample_discussions")]
        plans.append(dict(target=target, customer_route=CUSTOMER_SEGMENTS[target["customer_segment"]], focus=surface["focus"], deliverable_kind=surface["artifact_kind"], sections=surface["sections"],
                          cta=surface["cta"], metrics=list(dict.fromkeys(metrics)), schema_basis=profile["schema_basis"],
                          execution=profile["live_status"], variants=variants, excluded_routes=excluded,
                          source_refs=[SOURCES[s] for s in profile["source_ids"]],
                          missing_for_live_execution=["verified account/object mapping", "current platform schema/permissions", "exact payload and applicable authorization"],
                          additional_questions=["marketplace/productType/variation theme"] if target["platform"] == "amazon" else ["site stack and B2B/retail offer"] if target["platform"] == "storefront" else []))
    relevant_routes = {v["style"] for p in plans for v in p["variants"]} | {e["style"] for p in plans for e in p["excluded_routes"]}
    fingerprint_data = dict(platforms={p["target"]["platform"]: PLATFORMS[p["target"]["platform"]] for p in plans}, lens=lens,
                            operating_scope={p["target"]["platform"]: scope_for(p["target"]["platform"], operating_scope) for p in plans},
                            customer_routes={p["target"]["customer_segment"]: p["customer_route"] for p in plans},
                            routes={r: ROUTES[r] for r in relevant_routes}, catalog_version=CATALOG_VERSION)
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return dict(category=category, category_lens=lens, declared_affordances=sorted(confirmed_inputs),
                category_affordances_unverified=lens["candidate_affordances"], targets=plans,
                evidence_refs=list(evidence_refs), catalog_version=CATALOG_VERSION, strategy_hash=fingerprint,
                scoring_basis="internal editorial heuristic; no conversion prediction or model-success guarantee",
                actor_constraint="no_face" if creative.get("no_face") else "choose per creative and actual references")

def campaign_steps(strategy):
    def step(key, module, executor, kind, depends):
        return dict(id=key, module=module, executor=executor, artifact_kind=kind, depends_on=depends, state="pending", output=None)
    steps = [step("identity", "product", "runtime", "identity", []),
             step("strategy", "operations", "runtime", "strategy", ["identity"]),
             step("positioning", "operations", "agent", "positioning", ["strategy"])]
    deliverables = []
    for plan in strategy["targets"]:
        key = plan["target"]["id"]
        kind = plan["deliverable_kind"]
        s = step(key, "product" if kind == "channel_listing" else "content", "agent", kind, ["positioning"])
        s["target"] = plan["target"]
        s["target_profile"] = plan
        steps.append(s)
        deliverables.append(key)
    steps += [step("experiment", "operations", "agent", "experiment_plan", deliverables),
              step("review", "operations", "agent", "campaign_review", [*deliverables, "experiment"])]
    return steps

def experiment_outline(strategy):
    def primary(p):
        choices = {"inquiry": ["qualified_inquiries"], "purchase": ["paid_orders", "detail_conversion", "checkout_conversion"],
                   "consideration": ["product_clicks", "consultations", "saves", "landing_engagement"], "discovery": ["early_retention", "search_impressions", "search_ctr"],
                   "brand": ["completion_rate", "video_completion", "landing_engagement"], "retention": ["return_rate", "qualified_comments"]}
        return next((m for m in choices[p["target"]["goal_type"]] if m in p["metrics"]), p["metrics"][0] if p["metrics"] else None)
    return dict(kind="experiment_outline", causal_status="hypotheses_only", rows=[dict(target_id=p["target"]["id"],
        primary_metric=primary(p), metrics=p["metrics"], baseline=None,
        variants=[v["variant_id"] for v in p["variants"]], variable="creative approach OR hook; select one for a controlled comparison",
        hold_constant=["same SKU and evidence", "audience", "placement", "offer", "comparable measurement window"],
        data_needed=["actual metric definition/source", "denominators and comparable window", "attribution and qualified outcome"],
        stop_rule="Set against actual budget/data; no invented universal ROI threshold") for p in strategy["targets"]],
        comparison_rule="Within comparable target slices. Cross-platform metrics/retail orders/B2B inquiries are not pooled.")
