import unittest

from miaoshou_bridge import BridgeError, MiaoshouBridge

ORIGIN = 'chrome-extension://' + 'a' * 32
OTHER = 'chrome-extension://' + 'b' * 32


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.b = MiaoshouBridge(clock=lambda: self.now)
        self.code = self.b.issue_pairing('123')['code']

    def pair(self):
        return self.b.pair(self.code, ORIGIN, '123')['token']

    def test_pair_restrictions_and_expiry(self):
        for origin, shop in [(OTHER, '999'), ('https://example.com', '123')]:
            with self.assertRaises(BridgeError): self.b.pair(self.code, origin, shop)
        self.now += 301
        with self.assertRaises(BridgeError): self.pair()

    def test_single_use_origin_and_write_denial(self):
        token = self.pair()
        with self.assertRaises(BridgeError): self.pair()
        with self.assertRaises(BridgeError): self.b.poll(OTHER, token)
        with self.assertRaises(BridgeError): self.b.poll(ORIGIN, 'invalid')
        for operation, params in [('delete', {}), ('products', {'url': 'https://example.com'}), ('products', {'page': True})]:
            with self.assertRaises(BridgeError): self.b.submit(operation, params)
        self.now += 31
        with self.assertRaises(BridgeError): self.b.submit('connection-check')

    def test_product_projection_and_identity(self):
        token = self.pair()
        tid = self.b.submit('products', {'page': 1, 'pageSize': 20})['task_id']
        job = self.b.poll(ORIGIN, token)
        self.assertEqual(job['expected_shop_id'], '123')
        payload = {'shop_id_before': '123', 'shop_id_after': '123', 'total': 1,
                   'items': [{'productId': '123456789012345678', 'name': 'shoe', 'shopToken': 'SECRET'}], 'cookie': 'SECRET'}
        self.b.complete(ORIGIN, token, tid, payload)
        result = self.b.get_result(tid)['result']
        self.assertTrue(result['ok'])
        self.assertNotIn('SECRET', repr(result))
        self.assertEqual(result['data']['items'], [{'productId': '123456789012345678', 'name': 'shoe'}])
        with self.assertRaises(BridgeError): self.b.complete(ORIGIN, token, tid, payload)

    def test_different_shop_and_invalid_schema(self):
        token = self.pair()
        tid = self.b.submit('products', {'pageSize': 20})['task_id']
        self.b.poll(ORIGIN, token)
        self.b.complete(ORIGIN, token, tid, {'shop_id_before': '123', 'shop_id_after': '456', 'items': [], 'total': 0})
        self.assertEqual(self.b.get_result(tid)['result']['error'], 'shop_mismatch')
        tid = self.b.submit('products', {'pageSize': 20})['task_id']
        self.b.poll(ORIGIN, token)
        self.b.complete(ORIGIN, token, tid, {'shop_id_before': '123', 'shop_id_after': '123', 'items': [{'productId': '1'}, {'productId': '1'}], 'total': 2})
        self.assertEqual(self.b.get_result(tid)['result']['error'], 'schema_changed')

    def test_timed_out_tasks_do_not_wait_forever(self):
        token = self.pair()
        tid = self.b.submit('connection-check')['task_id']
        self.b.poll(ORIGIN, token)
        self.now += 60
        self.assertEqual(self.b.get_result(tid)['result']['error'], 'bridge_disconnected')
        with self.assertRaises(BridgeError): self.b.complete(ORIGIN, token, tid, {})

    def test_last_page_rejects_more_items_than_remain(self):
        token=self.pair()
        tid=self.b.submit('products', {'page': 2, 'pageSize': 20})['task_id']
        self.b.poll(ORIGIN,token)
        rows=[{'productId':str(i)} for i in range(2)]
        self.b.complete(ORIGIN,token,tid,{'shop_id_before':'123','shop_id_after':'123','items':rows,'total':21})
        self.assertEqual(self.b.get_result(tid)['result']['error'],'schema_changed')

    def test_consumed_results_and_old_orphans_are_removed(self):
        token=self.pair()
        tid=self.b.submit('connection-check')['task_id']
        self.b.poll(ORIGIN,token)
        self.b.complete(ORIGIN,token,tid,{'shop_id_before':'123','shop_id_after':'123'})
        self.assertTrue(self.b.get_result(tid)['result']['ok'])
        with self.assertRaises(BridgeError):self.b.get_result(tid)
        orphan=self.b.submit('connection-check')['task_id']
        self.now+=120
        self.b.poll(ORIGIN,token)
        with self.assertRaises(BridgeError):self.b.get_result(orphan)

    def test_cancel_running_task_rejects_late_completion(self):
        token=self.pair()
        tid=self.b.submit('connection-check')['task_id']
        self.b.poll(ORIGIN,token)
        self.b.cancel(tid)
        with self.assertRaises(BridgeError):self.b.complete(ORIGIN,token,tid,{'shop_id_before':'123','shop_id_after':'123'})


if __name__ == '__main__':
    unittest.main()
