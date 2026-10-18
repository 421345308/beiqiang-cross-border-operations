import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_runtime as fixtures
from commerce.catalogs import PLATFORMS, LENSES, ROUTES, CHANNEL_SCOPE_PATH
from commerce.strategy import catalog, experiment_outline
from commerce.business import snapshot
from commerce.runtime import Engine, CommerceError

class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.RuntimeTests()
        self.f.setUp()
        self.engine = self.f.engine

    def tearDown(self):
        self.f.tearDown()

    def request(self):
        return dict(workflow="campaign", goal="Synthetic multi-platform preparation", sku="TEST001", channel="multi", language="zh-CN",
                    category="footwear", affordances=["wearable", "in_use", "visual_detail"], creative={"count": 2, "no_face": True},
                    targets=[dict(platform="alibaba", placement="listing", goal_type="inquiry", language="en"),
                             dict(platform="douyin", placement="short_video", language="zh-CN"),
                             dict(platform="xiaohongshu", placement="note", goal_type="consideration", language="zh-CN"),
                             dict(platform="amazon", placement="listing", language="en", market="US"),
                             dict(platform="storefront", placement="landing_page", business_model="b2b", language="en")])

    def error(self, code, fn):
        self.f.assert_code(code, fn)

    def begin(self):
        t = self.engine.create_task(self.request(), "v2-test")
        t = self.engine.run_step(t["id"], "identity", t["revision"])
        t = self.engine.run_step(t["id"], "strategy", t["revision"])
        data = dict(kind="positioning", summary="Fixture positioning", audiences=["Fixture audience"], use_cases=["Fixture use"],
                    claim_evidence=[{"source": "fixture"}], unconfirmed=["source still HOLD_SOURCE"], product_role="Fixture use",
                    channel_differences={p["target"]["id"]: p["focus"] for p in t["strategy"]["targets"]})
        return self.engine.submit_artifact(t["id"], "positioning", data, t["revision"])

    def artifact(self, step, task):
        target = step["target"]
        data = dict(kind=step["artifact_kind"], summary="Synthetic fixture, not marketing validation", target_id=target["id"],
                    platform=target["platform"], placement=target["placement"], language=target["language"],
                    claim_evidence=[{"source": "fixture"}], unconfirmed=["actual facts/connection require verification"])
        if data["kind"] == "channel_listing":
            data.update(fields={"title": "Fixture " + target["platform"]}, image_roles=["full product"], schema_status="not_retrieved")
        elif data["kind"] == "landing_page":
            data.update(sections=["Fixture headline", "Fixture evidence"], cta="Fixture inquiry", message_match="Fixture promise-to-page")
        else:
            p = step["target_profile"]
            data["variants"] = [{"variant_id": v["variant_id"], "hook": "Fixture event " + v["style"], "product_role": "Fixture usage",
                                 "ending": "Fixture conclusion", "sound": "Fixture environment", "cta": "Fixture next step", "beats": ["Specific fixture action"],
                                 "asset_plan": ["Fixture source"], "production_checks": {"motion": "Fixture review"}} for v in p["variants"]]
        return data

    def test_scope_templates_and_placements_are_distinct(self):
        visible = {p["id"] for p in catalog()["platforms"]}
        self.assertNotIn("amazon", visible)
        self.assertTrue({"wechat", "linkedin", "facebook"}.issubset(visible))
        self.assertIn("amazon", {p["id"] for p in catalog(include_future=True)["platforms"]})
        self.assertEqual(len(LENSES), 8)
        self.assertEqual(len(ROUTES), 12)
        note = PLATFORMS["xiaohongshu"]["placements"]["note"]
        listing = PLATFORMS["xiaohongshu"]["placements"]["listing"]
        self.assertNotEqual(note["artifact_kind"], listing["artifact_kind"])

    def test_all_platforms_can_prepare_without_claiming_connection(self):
        for platform in PLATFORMS:
            r = dict(workflow="title", goal="Fixture draft", sku="TEST001", channel=platform, language="en")
            p = self.engine.ws.plan(r)
            self.assertEqual(p["strategy"]["targets"][0]["target"]["platform"], platform)
        self.assertEqual(PLATFORMS["amazon"]["live_status"]["write"], "not_connected")
        self.assertEqual(self.engine.capabilities()["external_writes"], [])

    def scope(self):
        return {"schema_version": 1, "source": "Synthetic scope fixture, not company evidence", "channels": {
            "douyin": {"status": "started", "market_scope": "domestic", "progress": "Fixture started"},
            "xiaohongshu": {"status": "planned_not_started", "market_scope": "domestic", "progress": "Fixture not started"},
            "wechat": {"status": "planned_not_started", "market_scope": "domestic", "progress": "Fixture not started"},
            "amazon": {"status": "future_option", "market_scope": "international", "progress": "Fixture future only"}}}

    def test_company_operating_scope_is_loaded_not_inferred_from_templates(self):
        self.assertTrue(all(p["operating_scope"]["status"] == "unverified" for p in self.engine.ws.catalog()["platforms"]))
        self.f.write_json(CHANNEL_SCOPE_PATH, self.scope())
        profiles = {p["id"]: p for p in self.engine.ws.catalog()["platforms"]}
        self.assertEqual(profiles["douyin"]["operating_scope"]["status"], "started")
        self.assertEqual(profiles["wechat"]["operating_scope"]["status"], "planned_not_started")
        self.assertNotIn("amazon", profiles)
        self.assertEqual(self.engine.capabilities()["future_options"][0]["id"], "amazon")

    def test_same_channel_routes_consumers_domestic_procurement_and_brand_buyers(self):
        r = self.request()
        r["targets"] = [{"platform": "wechat"}]
        consumer = self.engine.ws.strategy(r)["targets"][0]
        r["targets"] = [{"platform": "wechat", "business_model": "b2b"}]
        procurement = self.engine.ws.strategy(r)["targets"][0]
        self.assertEqual(consumer["target"]["customer_segment"], "consumer")
        self.assertEqual(procurement["target"]["customer_segment"], "domestic_business_buyer")
        self.assertNotEqual(consumer["customer_route"]["cta"], procurement["customer_route"]["cta"])
        self.assertNotEqual(consumer["variants"][0]["style"], procurement["variants"][0]["style"])
        r["targets"][0]["customer_segment"] = "brand_buyer"
        self.assertEqual(self.engine.ws.strategy(r)["targets"][0]["customer_route"]["name"], "品牌开发客户")
        r["targets"][0]["business_model"] = "retail"
        self.error("INVALID_REQUEST", lambda: self.engine.ws.strategy(r))

    def test_language_does_not_determine_customer_geography(self):
        r = self.request()
        r["targets"] = [{"platform": "wechat", "business_model": "b2b", "language": "en"}]
        target = self.engine.ws.strategy(r)["targets"][0]["target"]
        self.assertEqual(target["market_scope"], "domestic")
        self.assertEqual(target["customer_segment"], "domestic_business_buyer")
        r["targets"] = [{"platform": "linkedin", "language": "zh-CN"}]
        target = self.engine.ws.strategy(r)["targets"][0]["target"]
        self.assertEqual(target["customer_segment"], "overseas_business_buyer")

    def test_scope_correction_invalidates_previous_task_without_auto_refresh(self):
        self.f.write_json(CHANNEL_SCOPE_PATH, self.scope())
        t = self.engine.create_task(self.request(), "scope-version")
        changed = self.scope()
        changed["channels"]["douyin"]["progress"] = "Fixture corrected status"
        self.f.write_json(CHANNEL_SCOPE_PATH, changed)
        self.assertEqual(self.engine.get_task(t["id"])["status"], "needs_refresh")

    def test_wechat_surfaces_do_not_invent_product_upload_or_messaging(self):
        profile = catalog(platform="微信")["selected_platform"]
        self.assertEqual(profile["placements"]["moments"]["media_type"], "image_text")
        self.assertEqual(profile["placements"]["official_article"]["media_type"], "text")
        self.assertEqual(profile["placements"]["video_channel"]["media_type"], "video")
        self.assertNotIn("listing", profile["placements"])
        self.assertEqual(profile["live_status"]["write"], "not_connected")

    def test_same_product_gets_multiple_creative_families(self):
        result = self.engine.ws.strategy(self.request())
        douyin = next(p for p in result["targets"] if p["target"]["platform"] == "douyin")
        self.assertEqual(len(douyin["variants"]), 2)
        self.assertEqual(len({v["family"] for v in douyin["variants"]}), 2)
        self.assertIn("no conversion", result["scoring_basis"])

    def test_category_is_not_a_claim_or_confirmed_affordance(self):
        r = self.request()
        del r["affordances"]
        strategy = self.engine.ws.strategy(r)
        self.assertEqual(strategy["declared_affordances"], [])
        self.assertIn("wearable", strategy["category_affordances_unverified"])
        self.assertEqual(self.engine.ws.inspect_product("TEST001")["source_state"], "HOLD_SOURCE")

    def test_electronics_and_food_use_different_lenses(self):
        a, b = self.request(), self.request()
        a.update(category="electronics", affordances=["setup_steps", "in_use"])
        b.update(category="food_beverage", affordances=["sensory", "routine"])
        sa, sb = self.engine.ws.strategy(a), self.engine.ws.strategy(b)
        self.assertNotEqual(sa["category_lens"]["questions"], sb["category_lens"]["questions"])
        self.assertNotEqual(sa["targets"][1]["variants"][0]["style"], sb["targets"][1]["variants"][0]["style"])

    def test_unsupported_factory_and_test_routes_are_excluded(self):
        strategy = self.engine.ws.strategy(self.request())
        for plan in strategy["targets"]:
            self.assertNotIn("factory_process", {v["style"] for v in plan["variants"]})
            self.assertIn("factory_process", {r["style"] for r in plan["excluded_routes"]})
        r = self.request()
        r["creative"] = {"count": 1, "styles": ["test_evidence"]}
        self.error("INVALID_REQUEST", lambda: self.engine.ws.strategy(r))

    def test_evidence_has_to_resolve_a_real_file_and_basis(self):
        r = self.request()
        r["creative"] = {"count": 1, "styles": ["test_evidence"]}
        r["supporting_evidence"] = [{"kind": "test", "path": "02_Alibaba运营/产品档案.md", "basis": "Fixture declaration, not verified physical test"}]
        strategy = self.engine.ws.strategy(r)
        self.assertEqual(strategy["targets"][0]["variants"][0]["style"], "test_evidence")
        r["supporting_evidence"][0]["path"] = "missing.txt"
        self.error("FILE_NOT_FOUND", lambda: self.engine.ws.strategy(r))

    def test_user_selected_style_is_preserved_not_overruled_by_score(self):
        r = self.request()
        r["creative"] = {"count": 1, "styles": ["unboxing_asmr"], "speech_mode": "music_sfx"}
        strategy = self.engine.ws.strategy(r)
        self.assertTrue(all(p["variants"][0]["style"] == "unboxing_asmr" for p in strategy["targets"]))
        self.assertEqual(strategy["targets"][0]["variants"][0]["sound_direction"], "music_sfx")

    def test_production_complexity_limits_options_without_claiming_quality(self):
        r = self.request()
        r["creative"]["max_complexity"] = 1
        result = self.engine.ws.strategy(r)
        self.assertTrue(all(v["complexity"] <= 1 for p in result["targets"] for v in p["variants"]))
        self.assertIn("guarantee", result["scoring_basis"])

    def test_duplicate_target_aliases_and_cross_binding_rejected(self):
        r = self.request()
        r["targets"] = [{"platform": "douyin"}, {"platform": "抖音"}]
        self.error("INVALID_REQUEST", lambda: self.engine.ws.plan(r))
        r = self.request()
        r["listing_id"] = "1600000000001"
        self.error("INVALID_REQUEST", lambda: self.engine.ws.plan(r))

    def test_platform_placement_and_business_model_do_not_merge(self):
        r = self.request()
        r["targets"] = [{"platform": "douyin", "placement": "product_video"}]
        self.error("INVALID_REQUEST", lambda: self.engine.ws.plan(r))
        r["targets"] = [{"platform": "alibaba", "business_model": "retail"}]
        self.error("INVALID_REQUEST", lambda: self.engine.ws.plan(r))

    def test_xhs_product_and_video_requests_choose_correct_surface(self):
        r = self.f.request("listing")
        r["channel"] = "xiaohongshu"
        self.assertEqual(self.engine.ws.plan(r)["strategy"]["targets"][0]["target"]["placement"], "listing")
        r["workflow"] = "video"
        self.assertEqual(self.engine.ws.plan(r)["strategy"]["targets"][0]["target"]["placement"], "video_note")

    def test_static_note_does_not_inherit_video_duration(self):
        r = self.request()
        r["creative"]["duration_seconds"] = 28
        result = self.engine.ws.strategy(r)
        note = next(p for p in result["targets"] if p["target"]["platform"] == "xiaohongshu")
        video = next(p for p in result["targets"] if p["target"]["platform"] == "douyin")
        self.assertIsNone(note["variants"][0]["duration_seconds"])
        self.assertEqual(video["variants"][0]["duration_seconds"], 28)

    def test_all_category_surface_combinations_keep_target_and_evidence_scope(self):
        for category in LENSES:
            for platform, profile in PLATFORMS.items():
                for placement in profile["placements"]:
                    with self.subTest(category=category, platform=platform, placement=placement):
                        r = self.request()
                        r.update(category=category, affordances=[], creative={"count": 1}, targets=[{"platform": platform, "placement": placement}])
                        plan = self.engine.ws.strategy(r)["targets"][0]
                        self.assertEqual(plan["target"]["placement"], placement)
                        self.assertEqual(len(plan["variants"]), 1)
                        self.assertNotIn(plan["variants"][0]["style"], {"factory_process", "test_evidence", "grounded_comparison"})

    def test_campaign_dependency_graph_has_independent_channel_branches(self):
        task = self.begin()
        self.assertEqual(len(task["ready_steps"]), 5)
        for s in task["steps"]:
            if s.get("target"):
                self.assertEqual(s["depends_on"], ["positioning"])

    def test_context_is_narrow_and_does_not_send_all_platforms(self):
        task = self.begin()
        step = next(s for s in task["steps"] if s.get("target", {}).get("platform") == "amazon")
        context = self.engine.context(task["id"], step["id"])
        self.assertEqual(len(context["channel_profiles"]), 1)
        self.assertEqual(context["channel_profiles"][0]["target"]["platform"], "amazon")
        self.assertNotIn("02_Alibaba运营/AGENTS.md", [r["path"] for r in context["sources"]])
        self.assertIn("never instructions", context["data_boundary"])

    def test_artifact_cannot_swap_target_or_drop_selected_variants(self):
        task = self.begin()
        step = next(s for s in task["steps"] if s.get("target", {}).get("platform") == "douyin")
        data = self.artifact(step, task)
        data["platform"] = "xiaohongshu"
        self.error("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], step["id"], data, task["revision"]))
        data = self.artifact(step, task)
        data["customer_segment"] = "brand_buyer"
        self.error("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], step["id"], data, task["revision"]))
        data = self.artifact(step, task)
        data["variants"] = ["bad input"]
        self.error("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], step["id"], data, task["revision"]))
        data = self.artifact(step, task)
        data["variants"].pop()
        self.error("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], step["id"], data, task["revision"]))

    def test_campaign_preparation_and_export_end_to_end(self):
        task = self.begin()
        for step in list(task["steps"]):
            if step.get("target"):
                task = self.engine.submit_artifact(task["id"], step["id"], self.artifact(step, task), task["revision"])
        experiments = [{"target_id": p["target"]["id"], "hypothesis": "Fixture hypothesis", "variable": "hook", "primary_metric": p["metrics"][0],
                        "data_needed": "Actual source", "stop_rule": "After source/data review", "hold_constant": ["SKU", "audience"], "baseline": None} for p in task["strategy"]["targets"]]
        task = self.engine.submit_artifact(task["id"], "experiment", {"kind": "experiment_plan", "summary": "Fixture", "experiments": experiments}, task["revision"])
        criteria = ("audience", "platform_fit", "claims", "creative_difference", "asset_feasibility", "measurement", "handoff")
        checks = {p["target"]["id"]: {c: {"status": "pass", "evidence": "Fixture check"} for c in criteria} for p in task["strategy"]["targets"]}
        task = self.engine.submit_artifact(task["id"], "review", {"kind": "campaign_review", "summary": "Fixture", "reviewer": "agent", "decision": "ready_for_user_review", "target_checks": checks}, task["revision"])
        self.assertEqual(task["status"], "package_ready")
        exported = self.engine.export_task(task["id"])
        self.assertTrue(Path(exported["absolute_path"]).is_file())
        self.assertIn("amazon", Path(exported["absolute_path"]).read_text(encoding="utf-8"))
        self.assertFalse(task["platform_published"])

    def test_staged_change_is_exact_diff_deduplicated_and_not_applied(self):
        task = self.begin()
        step = next(s for s in task["steps"] if s.get("target", {}).get("platform") == "amazon")
        data = self.artifact(step, task)
        task = self.engine.submit_artifact(task["id"], step["id"], data, task["revision"])
        path = "02_Alibaba运营/baseline.json"
        self.f.write_json(path, {"platform": "amazon", "sku": "TEST001", "target_id": step["target"]["id"], "fields": {"title": "Previous fixture"}})
        change = self.engine.stage_change(task["id"], step["id"], "change-test", task["revision"], path)
        self.assertEqual(change["diff"], [{"field": "title", "before": "Previous fixture", "before_known": True, "after": "Fixture amazon"}])
        again = self.engine.stage_change(task["id"], step["id"], "change-test", task["revision"], path)
        self.assertEqual(again["id"], change["id"])
        self.assertEqual(change["execution"], "not_applied")
        self.f.write_json(path, {"changed": True})
        self.assertEqual(self.engine.get_change(change["id"])["status"], "needs_refresh")

    def test_wrong_namespace_baseline_cannot_be_used(self):
        task = self.begin()
        step = next(s for s in task["steps"] if s.get("target", {}).get("platform") == "amazon")
        task = self.engine.submit_artifact(task["id"], step["id"], self.artifact(step, task), task["revision"])
        path = "02_Alibaba运营/wrong.json"
        self.f.write_json(path, {"platform": "alibaba", "sku": "TEST001", "target_id": step["target"]["id"], "fields": {}})
        self.error("BASELINE_MISMATCH", lambda: self.engine.stage_change(task["id"], step["id"], "wrong", task["revision"], path))

    def test_strategy_data_change_invalidates_existing_task(self):
        task = self.engine.create_task(self.request(), "catalog-version")
        route = copy.deepcopy(ROUTES["everyday_story"])
        route["hook"] = "Updated direction"
        with patch.dict(ROUTES, {"everyday_story": route}):
            self.assertEqual(self.engine.get_task(task["id"])["status"], "needs_refresh")

    def test_missing_dashboard_is_null_not_zero(self):
        result = snapshot(self.engine.ws)
        self.assertIsNone(result["figures"]["orders"])
        self.assertEqual(result["slices"], [])

    def observations(self):
        base = dict(placement="listing", entity_id="fixture", period_start="2026-10-01", period_end="2026-10-07", timezone="UTC", currency="USD", attribution="unknown")
        return {"schema_version": 1, "slices": [dict(base, id="b2b", platform="alibaba", business_model="b2b", metrics={"impressions": 1000, "clicks": 20, "qualified_inquiries": 2, "spend": None}),
                                               dict(base, id="retail", platform="amazon", business_model="retail", metrics={"impressions": 1000, "clicks": 40, "orders": 3, "spend": 20})]}

    def test_retail_orders_b2b_inquiries_and_unknown_attribution_remain_separate(self):
        path = "99_临时区/observations.json"
        self.f.write_json(path, self.observations())
        result = snapshot(self.engine.ws, path)
        self.assertIsNone(result["pooled_totals"])
        self.assertIsNone(result["slices"][0]["metrics"]["spend"])
        self.assertIsNone(result["slices"][1]["derived"]["cost_per_order"])
        self.assertEqual(result["slices"][1]["derived"]["ctr"], "0.0400")

    def test_duplicate_data_slice_rejected(self):
        path = "99_临时区/duplicates.json"
        data = self.observations()
        data["slices"].append(copy.deepcopy(data["slices"][0]))
        self.f.write_json(path, data)
        self.error("OVERLAPPING_METRICS", lambda: snapshot(self.engine.ws, path))

    def test_inquiry_goal_uses_business_outcome_not_views_as_primary(self):
        rows = experiment_outline(self.engine.ws.strategy(self.request()))["rows"]
        self.assertEqual(rows[0]["primary_metric"], "qualified_inquiries")
        self.assertIsNone(rows[0]["baseline"])

    def test_malformed_options_return_input_error(self):
        for option in ({"affordances": [{}]}, {"creative": {"styles": [{}]}}, {"creative": {"max_complexity": True}}, {"targets": [{"platform": "amazon", "market": {}}]}, {"customer_segment": {}}, {"market_scope": {}}):
            r = self.request()
            r.update(option)
            self.error("INVALID_REQUEST", lambda: self.engine.ws.strategy(r))

if __name__ == "__main__":
    unittest.main()
