import concurrent.futures
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
from commerce.contracts import LEDGER, ENTRIES, REVIEWS, validate_artifact
from commerce.runtime import Engine, CommerceError, analyze_metrics, discover_workspace
from commerce.platforms import read_platform, redact
from commerce.mcp import Session
from commerce.service import call, tool_list

ROOT = PLUGIN.parents[2]

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temp_parent = ROOT / "99_临时区/电商Agent验证"
        temp_parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.root = Path(self.temp.name)
        self.write("AGENTS.md", "Test workspace boundaries; this is synthetic fixture data.")
        for entries in ENTRIES.values():
            for entry in entries:
                self.write(entry, "Fixture business policy")
        self.write("02_Alibaba运营/产品档案.md", "Fixture product evidence, not a real commercial claim")
        self.ledger = {
            "updated_on": "2026-10-14", "sources": [],
            "products": [{"id": "TEST001", "aliases": ["TEST_ALIAS"], "source_state": "HOLD_SOURCE",
                          "raw_packages": [], "dossier_path": "02_Alibaba运营/产品档案.md"},
                         {"id": "TEST002", "source_state": "MAPPED"}],
            "listings": [{"id": "1600000000001", "product_id": "TEST001", "source_relation": "SOURCE_EVIDENCE_MISSING"},
                         {"id": "1600000000002", "product_id": "TEST002"}]}
        self.write_json(LEDGER, self.ledger)
        script = "08_工具链/01_业务脚本/funnel_metrics.py"
        target = self.root / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / script, target)
        self.write("04_客户开发/fixture.md", "Synthetic buyer request: sample information only; no customer or contact address")
        self.metrics = "99_临时区/metrics.csv"
        self.write(self.metrics,
                   "row_id,period_start,period_end,timezone,currency,channel,plan_mode,scope_id,impressions,clicks,spend,qualified_inquiries,attribution\n"
                   "a,2026-10-01,2026-10-07,Asia/Shanghai,CNY,alibaba,manual,test,1000,25,10,2,click_linked\n"
                   "b,2026-10-01,2026-10-07,Asia/Shanghai,CNY,alibaba,manual,test,1000,25,10,1,click_linked\n")
        self.engine = Engine(self.root)

    def tearDown(self):
        self.assertTrue(self.root.resolve().is_relative_to((ROOT / "99_临时区/电商Agent验证").resolve()))
        self.temp.cleanup()

    def write(self, relative, body):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")

    def write_json(self, relative, data):
        self.write(relative, json.dumps(data, ensure_ascii=False))

    def request(self, workflow="title"):
        r = dict(workflow=workflow, goal="Fixture local preparation", sku="TEST001", channel="alibaba", language="en")
        if workflow in ("operations", "commerce"):
            r["metrics_path"] = self.metrics
        if workflow in ("customer", "commerce"):
            r["customer_context_path"] = "04_客户开发/fixture.md"
        return r

    def task(self, workflow="title", key="test"):
        return self.engine.create_task(self.request(workflow), key)

    def assert_code(self, code, fn):
        with self.assertRaises(CommerceError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def identity(self, task):
        return self.engine.run_step(task["id"], "identity", task["revision"])

    def title(self):
        return {"kind": "title_draft", "summary": "Fixture title", "title": "Test walking shoe draft",
                "rationale": "Test only", "claim_evidence": []}

    def review(self, workflow="title"):
        keys = list(dict.fromkeys(c for w in (REVIEWS if workflow == "commerce" else [workflow]) for c in REVIEWS[w]))
        return {"kind": "review", "summary": "Fixture review", "reviewer": "agent", "decision": "ready_for_user_review",
                "checks": {k: {"status": "pass", "evidence": "Synthetic fixture assertion only"} for k in keys}}

    def video(self):
        return {"kind": "video_brief", "summary": "Fixture video brief", "objective": "Show an everyday event",
                "audience": "Fixture audience", "channel": "douyin", "language": "zh", "product_role": "Motivates walking",
                "duration_seconds": 4, "scenes": [{"start": 0, "end": 4, "action": "Actor takes two steps",
                    "cause_and_effect": "Tries the shoe before giving a subjective reaction", "product_visibility": "side view",
                    "dialogue": [{"speaker": "actor", "text": "诶，穿着挺舒服。", "mode": "现场"}]}],
                "production_checks": {k: "Explicit fixture check" for k in ("acting", "motion", "props", "audio", "continuity")}}

    def test_alias_and_multi_listing_identity_do_not_change_source_status(self):
        product = self.engine.ws.inspect_product("TEST_ALIAS")
        self.assertEqual(product["canonical_sku"], "TEST001")
        self.assertEqual(product["source_state"], "HOLD_SOURCE")
        self.assertEqual(product["listing_ids"], ["1600000000001"])
        self.assert_code("LISTING_MISMATCH", lambda: self.engine.ws.inspect_product("TEST001", "1600000000002"))

    def test_ambiguous_alias_is_rejected(self):
        self.ledger["products"][1]["aliases"] = ["TEST_ALIAS"]
        self.write_json(LEDGER, self.ledger)
        self.assert_code("IDENTITY_AMBIGUOUS", lambda: self.engine.ws.inspect_product("TEST_ALIAS"))

    def test_title_scope_reads_only_product_entries(self):
        plan = self.engine.ws.plan(self.request())
        self.assertEqual(plan["modules"], ["product"])
        self.assertNotIn("content", plan["skills"])
        self.assertNotIn("04_客户开发/README.md", [p["path"] for p in plan["source_refs"]])

    def test_video_does_not_load_alibaba_policy(self):
        plan = self.engine.ws.plan(self.request("video"))
        self.assertNotIn("02_Alibaba运营/AGENTS.md", [p["path"] for p in plan["source_refs"]])

    def test_idempotency_recovers_and_conflicts(self):
        task = self.task()
        self.assertEqual(self.task()["id"], task["id"])
        other = self.request()
        other["goal"] = "Different scope"
        self.assert_code("IDEMPOTENCY_CONFLICT", lambda: self.engine.create_task(other, "test"))

    def test_concurrent_create_has_one_task(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: self.task(key="concurrent")["id"], range(4)))
        self.assertEqual(len(set(ids)), 1)

    def test_dependency_and_revision_conflicts(self):
        task = self.task()
        self.assert_code("DEPENDENCY_PENDING", lambda: self.engine.context(task["id"], "title"))
        task = self.identity(task)
        self.assert_code("REVISION_CONFLICT", lambda: self.engine.submit_artifact(task["id"], "title", self.title(), 0))

    def test_title_package_resume_and_repeat_are_not_publish(self):
        task = self.identity(self.task())
        task = self.engine.submit_artifact(task["id"], "title", self.title(), task["revision"])
        revision = task["revision"]
        task = self.engine.submit_artifact(task["id"], "title", self.title(), revision - 1)
        self.assertEqual(task["revision"], revision)
        reopened = Engine(self.root).get_task(task["id"])
        task = self.engine.submit_artifact(reopened["id"], "review", self.review(), reopened["revision"])
        self.assertEqual(task["status"], "package_ready")
        self.assertFalse(task["platform_published"])
        self.assertFalse(task["paid_generation_submitted"])

    def test_product_change_invalidates_but_unrelated_product_does_not(self):
        task = self.task()
        self.ledger["products"][1]["source_state"] = "OTHER_STATE"
        self.write_json(LEDGER, self.ledger)
        self.assertEqual(self.engine.get_task(task["id"])["status"], "in_progress")
        self.ledger["products"][0]["source_state"] = "MAPPED"
        self.write_json(LEDGER, self.ledger)
        self.assertEqual(self.engine.get_task(task["id"])["status"], "needs_refresh")
        self.assert_code("STALE_EVIDENCE", lambda: self.identity(task))

    def test_policy_change_requires_refresh(self):
        task = self.identity(self.task())
        self.write("AGENTS.md", "Changed rule")
        task = self.engine.refresh_task(task["id"], task["revision"], "Rule updated")
        self.assertEqual(task["ready_steps"], ["identity"])
        events = self.engine.events(task["id"])
        self.assertEqual(events[-1]["kind"], "sources_refreshed")
        self.assertTrue(events[-1]["data"]["superseded_outputs"])

    def test_modified_output_is_not_accepted_as_original(self):
        task = self.identity(self.task())
        task = self.engine.submit_artifact(task["id"], "title", self.title(), task["revision"])
        ref = next(s for s in task["steps"] if s["id"] == "title")["output"]
        self.write(ref["path"], "replaced")
        self.assertEqual(self.engine.get_task(task["id"])["status"], "needs_refresh")

    def test_artifact_must_match_task_and_canonical_sku(self):
        task = self.identity(self.task())
        artifact = {**self.title(), "task_id": "other"}
        self.assert_code("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], "title", artifact, task["revision"]))
        artifact = {**self.title(), "sku": "TEST002"}
        self.assert_code("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], "title", artifact, task["revision"]))

    def test_unresolved_review_cannot_finish(self):
        task = self.identity(self.task())
        task = self.engine.submit_artifact(task["id"], "title", self.title(), task["revision"])
        review = self.review()
        review["checks"]["claims"]["status"] = "needs_changes"
        self.assert_code("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], "review", review, task["revision"]))

    def test_video_missing_motion_or_timeline_gap_is_rejected(self):
        data = self.video()
        validate_artifact(data, "video_brief", "video")
        data["scenes"][0]["start"] = 1
        with self.assertRaises(ValueError):
            validate_artifact(data, "video_brief", "video")
        data = self.video()
        del data["production_checks"]["motion"]
        with self.assertRaises(ValueError):
            validate_artifact(data, "video_brief", "video")

    def test_metrics_known_counts_and_unknown_attribution(self):
        result = analyze_metrics(self.engine.ws, self.metrics)["result"]
        self.assertEqual(result["impressions"], 2000)
        self.assertEqual(result["qualified_inquiries"], 3)
        self.assertEqual(result["click_to_qualified_rate"], "0.0600")
        body = (self.root / self.metrics).read_text().replace("click_linked", "unknown")
        self.write(self.metrics, body)
        result = analyze_metrics(self.engine.ws, self.metrics)["result"]
        self.assertIsNone(result["cost_per_qualified"])

    def test_metrics_mixed_dimensions_and_nan_rejected(self):
        original = (self.root / self.metrics).read_text()
        self.write(self.metrics, original.replace("b,2026-10-01", "b,2026-10-02"))
        self.assert_code("INCOMPARABLE_METRICS", lambda: analyze_metrics(self.engine.ws, self.metrics))
        self.write(self.metrics, original.replace(",10,2,", ",NaN,2,"))
        self.assert_code("INCOMPARABLE_METRICS", lambda: analyze_metrics(self.engine.ws, self.metrics))

    def test_customer_draft_cannot_claim_sent_or_change_buyer_context(self):
        task = self.identity(self.task("customer"))
        data = {"kind": "customer_draft", "summary": "Fixture draft", "context_path": "04_客户开发/fixture.md",
                "channel": "email", "message": "Fixture inquiry draft", "next_action": "Review", "unconfirmed_terms": [], "sent": True}
        self.assert_code("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], "followup", data, task["revision"]))
        data.update(sent=False, context_path="04_客户开发/other.md")
        self.assert_code("INVALID_ARTIFACT", lambda: self.engine.submit_artifact(task["id"], "followup", data, task["revision"]))

    def test_missing_operating_and_buyer_inputs_fail_before_creation(self):
        r = self.request("operations")
        del r["metrics_path"]
        self.assert_code("INVALID_REQUEST", lambda: self.engine.ws.plan(r))
        r = self.request("customer")
        del r["customer_context_path"]
        self.assert_code("INVALID_REQUEST", lambda: self.engine.ws.plan(r))

    def test_amazon_preparation_does_not_silently_use_alibaba_rules(self):
        r = self.request()
        r["channel"] = "amazon"
        plan = self.engine.ws.plan(r)
        self.assertEqual(plan["strategy"]["targets"][0]["target"]["platform"], "amazon")
        self.assertNotIn("02_Alibaba运营/AGENTS.md", [p["path"] for p in plan["source_refs"]])
        self.assertEqual(plan["skills"]["product"], [])

    def test_operating_scope_must_match_csv_channel(self):
        r = self.request("operations")
        r["channel"] = "facebook"
        task = self.engine.create_task(r, "channel-test")
        self.assert_code("CHANNEL_MISMATCH", lambda: self.engine.run_step(task["id"], "metrics", task["revision"]))

    def test_libtv_query_matches_explicit_node_and_does_not_run(self):
        self.write(".libtv/libtv.exe", "fixture")
        target = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        project = "11111111222233334444555555555555"
        payload = {"nodeKey": target, "nodeType": "fixture"}
        with patch("commerce.platforms.Path.home", return_value=self.root), patch("commerce.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b"")) as runner:
            result = read_platform(self.engine, "libtv", target, project_id=project)
        self.assertEqual(result["summary"]["identity_verification"], "node_key_match")
        self.assertEqual(runner.call_args.args[0][1:], ["node", target, "-p", project])
        payload["nodeKey"] = "other-node"
        with patch("commerce.platforms.Path.home", return_value=self.root), patch("commerce.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b"")):
            self.assert_code("IDENTITY_UNVERIFIED", lambda: read_platform(self.engine, "libtv", target, project_id=project))
    def test_commerce_full_local_preparation_flow(self):
        task = self.identity(self.task("commerce"))
        for step_id, data in [
            ("listing", {"kind": "listing_draft", "summary": "Fixture", "fields": {"subject": "Fixture"}, "claim_evidence": [], "image_roles": [], "unconfirmed": ["source"]}),
            ("brief", self.video()),
        ]:
            task = self.engine.submit_artifact(task["id"], step_id, data, task["revision"])
        task = self.engine.run_step(task["id"], "metrics", task["revision"])
        data = {"kind": "operations_plan", "summary": "Fixture", "observations": ["Synthetic data"], "hypotheses": [], "actions": ["Collect actual data"], "missing_data": ["Actual conversion"]}
        task = self.engine.submit_artifact(task["id"], "recommendation", data, task["revision"])
        data = {"kind": "customer_draft", "summary": "Fixture", "context_path": "04_客户开发/fixture.md", "channel": "email",
                "message": "Fixture draft only", "next_action": "Review", "unconfirmed_terms": ["price"], "sent": False}
        task = self.engine.submit_artifact(task["id"], "followup", data, task["revision"])
        task = self.engine.submit_artifact(task["id"], "review", self.review("commerce"), task["revision"])
        self.assertEqual(task["status"], "package_ready")
        self.assertEqual(len(task["steps"]), 7)

    def test_paths_escape_and_credentials_rejected(self):
        for path in ("../AGENTS.md", "C:/Users/secret.json", ".env", ".codex/config.toml"):
            self.assert_code("INVALID_PATH", lambda: self.engine.ws.file(path))
        self.assert_code("INVALID_PATH", lambda: Engine(self.root, self.root.parent / "outside"))

    def test_no_arbitrary_command_or_external_write_surface(self):
        self.assertEqual(self.engine.capabilities()["external_writes"], [])
        with self.assertRaises(ValueError):
            call(self.engine, "commerce_publish", {})
        self.assert_code("INVALID_REQUEST", lambda: read_platform(self.engine, "alibaba", "1;exec", "TEST001"))
        self.assert_code("UNSUPPORTED_PLATFORM", lambda: read_platform(self.engine, "other", "1"))

    def test_official_read_response_identity_and_redaction(self):
        self.write(".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py", "# fixture")
        payload = {"product": {"product_id": "1600000000001", "subject": "Fixture", "status": "approved"}, "access_token": "secret"}
        with patch("commerce.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b"")) as runner:
            result = read_platform(self.engine, "alibaba", "1600000000001", "TEST001")
        self.assertFalse(runner.call_args.kwargs["shell"])
        self.assertEqual(result["summary"]["requested_listing_id"], "1600000000001")
        self.assertIn("language=ENGLISH", runner.call_args.args[0])
        receipt = self.engine.ws.json(result["evidence"]["path"])
        self.assertEqual(receipt["response"]["access_token"], "[redacted]")
        self.assertEqual(self.engine.ws.inspect_product("TEST001")["source_state"], "HOLD_SOURCE")
        payload["product"]["product_id"] = "1600000000002"
        with patch("commerce.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b"")):
            self.assert_code("IDENTITY_UNVERIFIED", lambda: read_platform(self.engine, "alibaba", "1600000000001", "TEST001"))

    def test_encrypted_api_identity_requires_exact_formal_baseline(self):
        self.write(".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py", "# fixture")
        baseline_path = "02_Alibaba运营/receipt.json"
        self.ledger["listings"][0]["formal_fields"] = {"file": baseline_path}
        self.write_json(LEDGER, self.ledger)
        self.write_json(baseline_path, {"requested_product_id": "1600000000001", "response": {"product": {"product_id": "encrypted-fixture-id"}}})
        payload = {"product": {"product_id": "encrypted-fixture-id", "subject": "Fixture"}}
        with patch("commerce.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b"")):
            result = read_platform(self.engine, "alibaba", "1600000000001", "TEST001")
        self.assertEqual(result["summary"]["identity_verification"], "same_listing_formal_encrypted_id_match")
        self.write_json(baseline_path, {"requested_product_id": "1600000000002", "response": {"product": {"product_id": "encrypted-fixture-id"}}})
        with patch("commerce.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b"")):
            self.assert_code("IDENTITY_UNVERIFIED", lambda: read_platform(self.engine, "alibaba", "1600000000001", "TEST001"))

    def test_failed_platform_read_retains_evidence_and_does_not_retry(self):
        self.write(".agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py", "# fixture")
        payload = {"error_response": {"code": "InvalidParameter", "access_token": "secret"}}
        with patch("commerce.platforms.subprocess.run", return_value=subprocess.CompletedProcess([], 2, json.dumps(payload).encode(), b"")) as runner:
            self.assert_code("READ_FAILED", lambda: read_platform(self.engine, "alibaba", "1600000000001", "TEST001"))
        self.assertEqual(runner.call_count, 1)
        files = list((self.engine.state / "platform_reads").glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertNotIn("secret", files[0].read_text())

    def test_mcp_negotiation_tool_discovery_and_input_errors(self):
        session = Session(self.engine)
        self.assertIn("error", session.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))
        response = session.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "unknown", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
        self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
        self.assertIsNone(session.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        response = session.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        self.assertEqual(len(response["result"]["tools"]), len(tool_list()))
        self.assertIn("commerce_strategy", [t["name"] for t in response["result"]["tools"]])
        response = session.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "commerce_doctor", "arguments": {"shell": "x"}}})
        self.assertEqual(response["error"]["code"], -32602)

    def test_actual_stdio_startup_discovery_and_call(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "commerce_product", "arguments": {"sku": "TEST_ALIAS"}}},
        ]
        result = subprocess.run([sys.executable, "-X", "utf8", str(PLUGIN / "server.py"), "--workspace", str(self.root), "--stdio"],
                                input="".join(json.dumps(m) + "\n" for m in messages).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), 3)
        self.assertEqual(responses[-1]["result"]["structuredContent"]["result"]["canonical_sku"], "TEST001")

if __name__ == "__main__":
    unittest.main()
