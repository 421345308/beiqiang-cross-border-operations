import http.client
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import JOB, Store, handler_class
from crm import CRMReader
from core import Crawler, PublicTransport, analyse, bounded_read, csv_export, extract_contacts, new_candidate, normalize_url, parse_page, public_addresses
from http.server import ThreadingHTTPServer


def response(url, body, status=200, mime="text/html; charset=utf-8"):
    return {"url": url, "body": body, "status": status, "headers": {"content-type": mime}}


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.responses.get(url, response(url, "", 404, "text/plain"))


class ContactTests(unittest.TestCase):
    def test_only_visible_published_addresses(self):
        page = parse_page('''<title>Contact</title><script>private@company.example</script>
          <style>.hidden{content:'hidden@company.example'}</style><div hidden>secret@company.example</div>
          <div style="display: none">invisible@company.example</div>
          <a href="mailto:BUYERS@company.example?subject=cc@third.example">Buying team</a>
          <p>Customer service: support@company.example.</p>
          <a href="tel:+1-212-555-0100">Office</a><a href="https://wa.me/12125550100">WhatsApp</a>''', "https://company.example/contact")
        contacts = extract_contacts(page)
        emails = {c["value"]: c for c in contacts if c["kind"] == "email"}
        self.assertEqual(set(emails), {"buyers@company.example", "support@company.example"})
        self.assertEqual(emails["buyers@company.example"]["role"], "采购相关待核")
        self.assertEqual(emails["support@company.example"]["role"], "客服或订单")
        self.assertTrue(all(c["review_required"] for c in contacts))
        self.assertEqual({c["kind"] for c in contacts}, {"email", "phone", "whatsapp"})

    def test_sales_or_privacy_not_buyers(self):
        page = parse_page('<p>Procurement team contact sales@company.example and privacy@company.example</p>', "https://company.example/")
        contacts = {c["value"]: c["role"] for c in extract_contacts(page)}
        self.assertEqual(contacts["sales@company.example"], "对外销售")
        self.assertEqual(contacts["privacy@company.example"], "不用于开发")

    def test_retail_application_not_supplier_intake(self):
        page = parse_page('''<title>Become a Retailer</title><h1>Wholesale trade account</h1>
          <form><input name="email"><textarea name="message"></textarea></form>''', "https://company.example/trade")
        self.assertEqual(extract_contacts(page)[0]["role"], "对外销售")
        self.assertNotIn("supplier_intake", analyse([page])["signals"])

    def test_supplier_form_with_provenance(self):
        page = parse_page('''<title>Supplier application</title><form action="/submit" method="post">
          <label>Company email</label><input name="email"><textarea name="message"></textarea></form>''', "https://company.example/vendors")
        c = extract_contacts(page)[0]
        self.assertEqual(c["role"], "供应商申请待核")
        self.assertEqual(c["value"], "https://company.example/vendors")
        self.assertEqual(c["delivery_status"], "未验证")

    def test_newsletter_not_contact_form(self):
        page = parse_page('<form>Subscribe to our newsletter<input name="email"></form>', "https://company.example/")
        self.assertEqual(extract_contacts(page), [])

    def test_business_fit_is_not_current_demand(self):
        page = parse_page("<p>We are a wholesale footwear distributor with our own brands of casual sneakers.</p>", "https://company.example/")
        a = analyse([page])
        self.assertEqual(a["tier"], "优先人工核验")
        self.assertEqual(a["opportunity"], "未发现当前采购需求")
        self.assertEqual(a["signals"]["distribution"]["url"], page.url)
        brand_agent = parse_page('<p>Our brands include popular footwear labels.</p>', 'https://company.example/')
        self.assertNotIn("private_label", analyse([brand_agent])["signals"])

    def test_demand_requires_explicit_statement(self):
        retail = parse_page("<p>We are looking for new retailers to distribute our shoes.</p>", "https://company.example/")
        self.assertNotIn("active_demand", analyse([retail])["signals"])
        buying = parse_page("<p>We are currently seeking new footwear suppliers.</p>", "https://company.example/suppliers")
        self.assertIn("active_demand", analyse([buying])["signals"])
        self.assertIn("待核", analyse([buying])["opportunity"])

    def test_origin_bound_agency_not_prioritized_as_oem_buyer(self):
        page = parse_page('<p>We represent Spanish footwear manufacturers. Wholesale comfort shoes and private label. All our factories are in Spain.</p>', 'https://company.example/about')
        a = analyse([page])
        self.assertEqual(a["tier"], "供应链范围需核对")
        self.assertIn("origin_constraint", a["signals"])


class FetchTests(unittest.TestCase):
    def test_response_size_and_total_read_deadline(self):
        class SlowResponse:
            def read1(self, n):
                return b"12345"[:n]
        with patch("core.time.monotonic", return_value=0), self.assertRaises(ValueError):
            bounded_read(SlowResponse(), 8, 10)
        with patch("core.time.monotonic", side_effect=[0, 11]), self.assertRaisesRegex(ValueError, "超时"):
            bounded_read(SlowResponse(), 100, 10)

    def test_synthetic_vpn_dns_resolved_without_relaxing_ip_guard(self):
        synthetic = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.19.0.10", 443))]
        with patch("core.socket.getaddrinfo", return_value=synthetic), patch("core.dns_over_https", return_value=["93.184.216.34"]):
            self.assertEqual(public_addresses("company.example", 443), ["93.184.216.34"])
        with patch("core.socket.getaddrinfo", return_value=synthetic), patch("core.dns_over_https", return_value=["10.0.0.1"]):
            with self.assertRaises(ValueError):
                public_addresses("company.example", 443)

    def test_reject_nonpublic_resolved_addresses(self):
        for address in ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "::ffff:127.0.0.1"]:
            with self.subTest(address=address), patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))]):
                with self.assertRaises(ValueError):
                    public_addresses("company.example", 80)

    def test_reject_credentials_and_ports(self):
        for value in ["https://user:password@company.example/", "https://company.example:8080/", "http://company.example/\r\nx: y", "javascript:alert(1)", "ftp://company.example/"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_url(value)

    def test_public_transport_pins_ip_and_rechecks_redirect(self):
        observed = []
        class Reply:
            status = 302
            def getheaders(self):
                return [("location", "http://127.0.0.1/private")]
        class Conn:
            def __init__(self, *args, **kwargs):
                self.sock = None
            def request(self, *args, **kwargs):
                observed.append(self._create_connection(("company.example", 80), timeout=10))
            def getresponse(self):
                return Reply()
            def close(self):
                pass
        def resolve(host, port, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", port))]
        with patch("core.http.client.HTTPConnection", Conn), patch("core.socket.getaddrinfo", side_effect=resolve), patch("core.socket.create_connection", return_value="pinned") as connect:
            with self.assertRaises(ValueError):
                PublicTransport().get("http://company.example/")
            self.assertEqual(connect.call_args.args[0], ("93.184.216.34", 80))
            self.assertEqual(observed, ["pinned"])

    def test_robots_disallow_does_not_fetch_page(self):
        t = FakeTransport({"https://company.example/robots.txt": response("https://company.example/robots.txt", "User-agent: *\nDisallow: /", mime="text/plain")})
        result = Crawler(t, pause=lambda _: None).scan({"website": "https://company.example/"})
        self.assertEqual(t.calls, ["https://company.example/robots.txt"])
        self.assertEqual(result["contacts"], [])
        self.assertIn("robots", result["pages"][0]["error"])

    def test_robots_unavailable_fails_closed(self):
        t = FakeTransport({"https://company.example/robots.txt": response("https://company.example/robots.txt", "", 503)})
        result = Crawler(t, pause=lambda _: None).scan({"website": "https://company.example/"})
        self.assertEqual(t.calls, ["https://company.example/robots.txt"])
        self.assertIn("503", result["pages"][0]["error"])

    def test_rate_limited_site_stops_before_second_page(self):
        t = FakeTransport({"https://company.example/": response("https://company.example/", "", 429)})
        result = Crawler(t, pause=lambda _: None).scan({"website": "https://company.example/", "pages": ["https://company.example/contact"]})
        self.assertEqual(len(result["pages"]), 1)
        self.assertNotIn("https://company.example/contact", t.calls)

    def test_bounded_same_company_links_and_unique_contacts(self):
        homepage = '<p>We distribute casual shoes wholesale. Contact info@company.example for business enquiries.</p><a href="/contact">Contact</a><a href="https://other.example/about">About</a><a href="/account">Account</a>'
        t = FakeTransport({"https://company.example/": response("https://company.example/", homepage), "https://company.example/contact": response("https://company.example/contact", '<p>Contact our office at info@company.example for business enquiries, shoes and wholesale information.</p>')})
        result = Crawler(t, pause=lambda _: None).scan({"website": "https://company.example/"}, max_pages=2)
        self.assertEqual(len(result["pages"]), 2)
        self.assertEqual(len(result["contacts"]), 1)
        self.assertEqual(len(result["contacts"][0]["sources"]), 2)
        self.assertFalse(any("other.example" in u or "/account" in u for u in t.calls))

    def test_social_site_not_crawled(self):
        t = FakeTransport({})
        with self.assertRaises(ValueError):
            Crawler(t).scan({"website": "https://www.facebook.com/company"})
        self.assertEqual(t.calls, [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_company_dedup_and_review_preserved(self):
        self.assertEqual(self.store.add([{"website": "https://company.example/", "company": "First"}]), 1)
        row = self.store.read()[0]
        self.store.review(row["id"], "值得继续", "Existing verified note")
        self.assertEqual(self.store.add([{"website": "https://www.company.example/contact", "pages": ["https://company.example/about"]}]), 0)
        updated = self.store.read()[0]
        self.assertEqual(updated["review"]["note"], "Existing verified note")
        with patch("app.Crawler") as crawler:
            crawler.return_value.scan.return_value = {"contacts": [], "analysis": {}, "research_status": "访问受限或读取失败", "pages": []}
            self.store.scan([row["id"]])
        self.assertEqual(self.store.read()[0]["review"]["state"], "值得继续")

    def test_stop_contact_skips_fetch_and_exports_state(self):
        self.store.add([{"website": "https://company.example/", "company": "=HYPERLINK(\"bad\")"}])
        row = self.store.read()[0]
        self.store.review(row["id"], "停止联系", "Do not contact")
        with patch("app.Crawler") as crawler:
            self.store.scan([row["id"]])
            crawler.return_value.scan.assert_not_called()
        exported = csv_export(self.store.read())
        self.assertIn("停止联系", exported)
        self.assertIn("'=HYPERLINK", exported)
        self.assertIn("不是发送名单", exported)

    def test_invalid_batch_does_not_partially_write(self):
        with self.assertRaises(ValueError):
            self.store.add([{"website": "https://company.example/"}, {"website": "https://user:secret@bad.example/"}])
        self.assertEqual(self.store.read(), [])

    def test_invalid_candidate_shape(self):
        for seed in ["company.example", {"website": 123}, {"website": "https://company.example", "pages": "bad"}]:
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                self.store.add([seed])

    def test_windows_replace_lock_retries_and_preserves_original_on_failure(self):
        self.store.add([{"website": "https://company.example/"}])
        original = self.store.path.read_bytes()
        record = self.store.read()[0]
        replace = Path.replace
        attempts = []
        def transient(path, target):
            attempts.append(path)
            if len(attempts) < 3:
                raise PermissionError("synthetic Windows file lock")
            return replace(path, target)
        with patch("app.Path.replace", transient), patch("app.time.sleep"):
            self.store.review(record["id"], "暂缓", "Updated")
        self.assertEqual(len(attempts), 3)
        self.assertEqual(self.store.read()[0]["review"]["state"], "暂缓")
        committed = self.store.path.read_bytes()
        with patch("app.Path.replace", side_effect=PermissionError("synthetic persistent lock")), patch("app.time.sleep"), self.assertRaises(PermissionError):
            self.store.review(record["id"], "停止联系", "Failed write")
        self.assertEqual(self.store.path.read_bytes(), committed)
        self.assertNotEqual(original, committed)
        self.assertEqual(list(self.store.directory.glob("*.tmp")), [])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.token = "test-token"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class(self.store, self.token, CRMReader(Path(self.tmp.name) / "missing-crm.xlsx")))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, token=None, method="GET", body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        hdr = headers or {}
        if token:
            hdr["X-Workbench-Token"] = token
        if body is not None:
            hdr["Content-Type"] = "application/json"
            body = json.dumps(body)
        conn.request(method, path, body=body, headers=hdr)
        resp = conn.getresponse()
        result = (resp.status, resp.read().decode("utf-8"), dict(resp.getheaders()))
        conn.close()
        return result

    def test_api_requires_token(self):
        self.assertEqual(self.request("/api/state")[0], 403)
        self.assertEqual(self.request("/api/state", self.token)[0], 200)

    def test_host_and_origin_guard(self):
        self.assertEqual(self.request("/", headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.request("/api/state", self.token, headers={"Origin": "https://attacker.example"})[0], 403)

    def test_local_ui_and_import_review_export(self):
        status, content, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertNotIn("__TOKEN__", content)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("/api/import", self.token, "POST", {"candidates": [{"website": "https://company.example/"}]})[0], 200)
        record = self.store.read()[0]
        self.assertEqual(self.request("/api/review", self.token, "POST", {"id": record["id"], "state": "值得继续", "note": "Verified"})[0], 200)
        status, content, _ = self.request("/api/export", self.token)
        self.assertEqual(status, 200)
        self.assertIn("值得继续", content)

    def test_failed_save_has_clear_http_error_without_corrupting_data(self):
        self.store.add([{"website": "https://company.example/"}])
        original = self.store.path.read_bytes()
        record = self.store.read()[0]
        with patch("app.Path.replace", side_effect=PermissionError("synthetic persistent lock")), patch("app.time.sleep"):
            status, content, _ = self.request("/api/review", self.token, "POST", {"id": record["id"], "state": "停止联系"})
        self.assertEqual(status, 503)
        self.assertIn("原记录保留", content)
        self.assertEqual(self.store.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
