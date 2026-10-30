import json
import unittest

from adapter import ExistingClient, execute, sanitize


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class AdapterTests(unittest.TestCase):
    def test_capabilities_has_no_io(self):
        client = FakeClient(RuntimeError())
        self.assertTrue(execute("capabilities", client=client)["ok"])
        self.assertEqual(client.calls, [])

    def test_explicit_check(self):
        client = FakeClient({"products": [], "total_item": 0})
        value = execute("connection-check", client=client)
        self.assertTrue(value["ok"])
        self.assertEqual(client.calls, [("alibaba.icbu.product.list", {"language": "ENGLISH", "current_page": 1, "page_size": 1})])
        self.assertFalse(value["source"]["account"]["identityVerified"])

    def test_pagination_uses_returned_size(self):
        client = FakeClient({"products": [{"id": "7"}], "total_item": 3, "page_size": 1})
        result = execute("products", client=client, page=2, page_size=50)
        self.assertEqual(client.calls[0][1]["current_page"], 2)
        self.assertEqual(result["pagination"]["nextPage"], 3)
        client.response = {"products": [{"id": "8"}], "total_item": 3, "page_size": 1}
        self.assertIsNone(execute("products", client=client, page=3)["pagination"]["nextPage"])

    def test_detail_params(self):
        client = FakeClient({"product": {"id": "123", "subject": "Shoe"}})
        self.assertTrue(execute("product", client=client, product_id="123")["ok"])
        self.assertEqual(client.calls, [("alibaba.icbu.product.get", {"language": "ENGLISH", "product_id": "123"})])

    def test_detail_identity_encrypted_id_and_projection(self):
        raw = {"product_id": "encrypted-id", "pc_detail_url": "https://www.alibaba.com/product-detail/Shoe_123.html",
               "subject": "Shoe", "mobile": "private", "address": "private", "unknown": {"phone": "private"},
               "main_image": {"images": ["https://example.invalid/shoe.jpg"], "mobile": "private"}}
        value = execute("product", client=FakeClient({"product": raw}), product_id="123")
        self.assertTrue(value["ok"])
        self.assertNotIn("private", json.dumps(value))
        for changed in ({**raw, "id": "999"}, {**raw, "pc_detail_url": "https://www.alibaba.com/product-detail/Shoe_999.html"}):
            self.assertFalse(execute("product", client=FakeClient({"product": changed}), product_id="123")["ok"])

    def test_short_and_duplicate_pages_fail(self):
        for raw in ({"products": [{"id": "1"}], "total_item": 4, "page_size": 2},
                    {"products": [{"id": "1"}, {"id": "1"}], "total_item": 2, "page_size": 2}):
            value = execute("products", client=FakeClient(raw))
            self.assertFalse(value["ok"])
            self.assertIsNone(value["data"])
            self.assertIsNone(value["pagination"])

    def test_failures_never_become_empty_success(self):
        for raw in ({}, {"code": "InsufficientPermission"}, {"error_response": {"msg": "secret"}},
                    {"products": []}, {"products": [], "total_item": -1}, RuntimeError("access_token=secret")):
            with self.subTest(raw=type(raw).__name__):
                result = execute("products", client=FakeClient(raw))
                self.assertFalse(result["ok"])
                self.assertIsNone(result["data"])
                self.assertIsNone(result["pagination"])
                self.assertIsNone(result["source"]["collectedAt"])
                self.assertNotIn("secret", json.dumps(result))

    def test_no_unrestricted_method_or_invalid_input(self):
        client = FakeClient({})
        for args in (("alibaba.icbu.product.update", {}), ("products", {"page": 0}),
                     ("product", {"product_id": "x?token=bad"})):
            self.assertFalse(execute(args[0], client=client, **args[1])["ok"])
        self.assertEqual(client.calls, [])

    def test_redaction_in_nested_fields_and_embedded_secrets(self):
        client = ExistingClient()
        client.config = {"appKey": "fake-key", "appSecret": "fake-secret", "accessToken": "fake-token"}
        data = {"appSecret": "fake-secret", "nested": [{"text": "oops fake-token", "access_token": "value"}],
                "url": "https://example.invalid/?sign=value"}
        output = json.dumps(client.safe(data))
        for forbidden in ("fake-secret", "fake-token", "access_token", "sign=value"):
            self.assertNotIn(forbidden, output)


if __name__ == "__main__":
    unittest.main()
