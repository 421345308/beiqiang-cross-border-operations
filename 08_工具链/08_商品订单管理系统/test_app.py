"""验证库存和订单关键约束，测试数据仅存于临时数据库。"""
import json
import re
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import Store, cents, server_for, DEMO_PASSWORD


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'test.db', demo=True)
        self.sku('A')
        self.sku('B')
        self.store.adjust(dict(code='A', delta=10, note='测试实盘'))

    def tearDown(self):
        self.tmp.cleanup()

    def sku(self, code, **changes):
        item = dict(code=code, model='DEMO-001', title='测试商品', color='黑色', size='40', price='129.99')
        self.store.save_sku({**item, **changes})

    def balance(self, code='A'):
        return next(x['stock'] for x in self.store.snapshot()['skus'] if x['code'] == code)

    def order(self, number='O1', lines=None):
        return self.store.create_order(dict(number=number, note='测试订单', lines=lines or [dict(code='A', quantity=2)]))

    def test_order_cancel_restores_once(self):
        self.order()
        self.assertEqual(self.balance(), 8)
        self.store.transition(dict(number='O1', status='已取消'))
        self.assertEqual(self.balance(), 10)
        with self.assertRaises(ValueError):
            self.store.transition(dict(number='O1', status='已取消'))
        self.assertEqual(self.balance(), 10)

    def test_shipping_does_not_double_deduct(self):
        self.order()
        self.sku('A', price='1.00')
        self.store.transition(dict(number='O1', status='已发货', tracking='TEST-TRACKING'))
        self.assertEqual(self.balance(), 8)
        self.assertEqual(self.store.snapshot()['orders'][0]['total_cents'], 25998)
        with self.assertRaises(ValueError):
            self.store.transition(dict(number='O1', status='已取消'))

    def test_insufficient_stock_rolls_back_all_lines(self):
        before = self.store.snapshot()
        with self.assertRaises(ValueError):
            self.order(lines=[dict(code='A', quantity=3), dict(code='B', quantity=1)])
        after = self.store.snapshot()
        for key in ['skus', 'orders', 'lines', 'movements', 'audit']:
            self.assertEqual(before[key], after[key])

    def test_duplicate_order_never_deducts_again(self):
        self.order()
        with self.assertRaises(ValueError):
            self.order()
        self.assertEqual(self.balance(), 8)

    def test_concurrent_orders_cannot_oversell(self):
        def worker(n):
            try:
                self.order(str(n), [dict(code='A', quantity=7)])
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, [1, 2]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.balance(), 3)

    def test_import_is_atomic_and_does_not_change_inventory(self):
        self.store.import_csv('code,model,title,color,size,price\nA,DEMO-001,新渠道名称,黑色,40,99.50\n')
        self.assertEqual(self.balance(), 10)
        before = self.store.snapshot()
        with self.assertRaises(ValueError):
            self.store.import_csv('code,model,title,color,size,price\nA,DEMO-001,名称,黑色,40,90\nB,DEMO-001,名称,白色,40,90\n')
        self.assertEqual(before['skus'], self.store.snapshot()['skus'])
        self.assertEqual(before['audit'], self.store.snapshot()['audit'])

    def test_sku_identity_cannot_be_rebound(self):
        with self.assertRaises(ValueError):
            self.sku('A', color='白色')
        with self.assertRaises(ValueError):
            self.sku('NEW', model='UNKNOWN')

    def test_invalid_money_and_quantity_are_rejected(self):
        for value in ['NaN', 'Infinity', '-1', '0.001']:
            with self.assertRaises(ValueError):
                cents(value)
        for value in [True, '1.2', 'NaN', '0', '-3']:
            with self.assertRaises(ValueError):
                self.order('BAD', [dict(code='A', quantity=value)])
        self.assertEqual(self.balance(), 10)

    def test_no_fake_initial_stock_and_no_mode_mixing(self):
        self.assertEqual(self.balance('B'), 0)
        with self.assertRaises(ValueError):
            Store(self.store.path, demo=False)

    def test_csv_formula_cells_are_escaped(self):
        self.sku('=BAD', title='@TEST')
        self.assertIn("'=BAD", self.store.export_csv().decode('utf-8-sig'))
        self.assertIn("'@TEST", self.store.export_csv().decode('utf-8-sig'))

    def test_backup_is_consistent_and_does_not_overwrite(self):
        self.order()
        target = Path(self.tmp.name) / 'backup.db'
        self.store.backup(target)
        recovered = Store(target, demo=True)
        self.assertEqual(recovered.snapshot()['orders'], self.store.snapshot()['orders'])
        self.assertEqual(recovered.snapshot()['skus'], self.store.snapshot()['skus'])
        with self.assertRaises(ValueError):
            self.store.backup(target)

    def test_initial_production_password_is_hashed_and_cannot_be_overwritten(self):
        production = Store(Path(self.tmp.name) / 'production.db')
        self.assertFalse(production.has_password())
        self.assertFalse(production.verify_password(DEMO_PASSWORD))
        with self.assertRaises(ValueError):
            production.set_password('short')
        password = 'Only-For-Test-67890'
        production.set_password(password)
        self.assertTrue(production.verify_password(password))
        self.assertFalse(production.verify_password('wrong'))
        with closing(production.connect()) as connection:
            values = [row['value'] for row in connection.execute('SELECT value FROM settings')]
        self.assertNotIn(password, values)
        with self.assertRaises(ValueError):
            production.set_password('Cannot-Replace-67890')

    def test_http_blocks_wrong_host_and_missing_csrf(self):
        server = server_for(self.store, 18766)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for request in [Request('http://127.0.0.1:18766/api/state', headers={'Host': 'evil.example'}),
                            Request('http://127.0.0.1:18766/api/stock', data=b'{}', headers={'Content-Type': 'application/json'})]:
                with self.assertRaises(HTTPError) as exc:
                    urlopen(request)
                self.assertEqual(exc.exception.code, 403)
            page = urlopen('http://127.0.0.1:18766/').read().decode()
            token = re.search(r'name="csrf" content="([^"]+)"', page)[1]
            with self.assertRaises(HTTPError) as exc:
                urlopen('http://127.0.0.1:18766/api/state')
            self.assertEqual(exc.exception.code, 401)
            headers = {'Content-Type': 'application/json', 'X-CSRF-Token': token}
            login = Request('http://127.0.0.1:18766/api/login',
                            data=json.dumps({'username':'admin','password':DEMO_PASSWORD}).encode(), headers=headers)
            response = urlopen(login)
            self.assertIn('HttpOnly', response.headers['Set-Cookie'])
            cookie = response.headers['Set-Cookie'].split(';')[0]
            headers['Cookie'] = cookie
            for asset in ('client.js', 'style.css'):
                self.assertEqual(urlopen(Request('http://127.0.0.1:18766/' + asset, headers={'Cookie':cookie})).status, 200)
            request = Request('http://127.0.0.1:18766/api/order',
                              data=json.dumps(dict(number='HTTP-1', note='HTTP测试', lines=[dict(code='A', quantity=1)])).encode(),
                              headers=headers)
            self.assertEqual(urlopen(request).status, 200)
            self.assertEqual(self.balance(), 9)
            self.assertEqual(urlopen(Request('http://127.0.0.1:18766/api/logout', data=b'{}', headers=headers)).status, 200)
            with self.assertRaises(HTTPError) as exc:
                urlopen(Request('http://127.0.0.1:18766/api/state', headers={'Cookie':cookie}))
            self.assertEqual(exc.exception.code, 401)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
