"""Supplier matching reads product-centre evidence without inventing facts."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from business import PRODUCTS, SUPPLY
from supplier_index import supplier_index
from server import Handler


class SupplierIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.supply = {
            'suppliers': [
                {'id': 's1', 'names': ['七号仓库'], 'shop_url': 'https://shop.example/', 'source_ids': ['one', 'two'],
                 'phone': '13800138000', 'matching_profile': {
                     'product_directions': [{'name': '高尔夫鞋', 'scope': '来源款', 'source_ids': ['one'], 'evidence': [
                         {'kind': 'SUPPLIER_PRODUCT_PAGE', 'url': 'https://shop.example/1', 'observed_on': '2026-11-11', 'summary': '商品款式记录'}]}],
                     'process_directions': [{'name': '鞋底开模', 'scope': '由负责人了解', 'evidence': [{'kind': 'OWNER_REPORTED'}]}],
                     'factory_identity': {'status': '供应商自述', 'summary': '尚无独立核验', 'evidence': [{'kind': 'SUPPLIER_SELF_CLAIM'}]},
                     'customization': {'status': '曾沟通', 'summary': '具体条件待确认', 'evidence': [{'kind': 'OWNER_REPORTED', 'path': '公开资料/经历.md'}]},
                     'location': {'city': '泉州', 'type': '店铺所在地', 'evidence': [{'kind': 'SUPPLIER_PRODUCT_PAGE'}]},
                     'owner_interactions': [{'summary': '曾沟通功能鞋', 'evidence': [{'kind': 'OWNER_REPORTED'}]}],
                     'open_questions': ['核实定制条件'],
                 }},
                {'id': 's2', 'names': ['工厂店'], 'shop_url': 'https://other.example/', 'source_ids': ['three']},
            ],
            'sources': [
                {'id': 'one', 'url': 'https://shop.example/1', 'supplier': '七号仓库', 'model': '8805', 'observed_at': '2026-11-11', 'price': '99.98', 'contact': '13800138000'},
                {'id': 'two', 'url': 'https://shop.example/2', 'supplier': '七号仓库', 'model': '8806'},
                {'id': 'three', 'url': 'https://other.example/3', 'supplier': '工厂店', 'model': 'T33'},
                {'id': 'orphan', 'url': 'https://www.made-in-china.com/item', 'supplier': '旧站名称', 'model': 'old1'},
            ],
        }
        self.products = {'products': [
            {'id': 'BQ-1', 'aliases': ['BQ-1', 'old alias'], 'source_state': 'ADOPTED', 'adopted_source_id': 'one', 'candidate_source_ids': ['two'], 'classification': {'local_intent_candidates': ['运动鞋']}},
            {'id': 'BQ-2', 'reference_source_id': 'three', 'source_state': 'HOLD_SOURCE'},
            {'id': 'BQ-3', 'adopted_source_id': 'orphan', 'source_state': 'HOLD_SOURCE'},
        ]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        for path, data in ((self.root / SUPPLY, self.supply), (self.root / PRODUCTS, self.products)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def test_search_profile_fields_and_exact_evidence_filters(self):
        result = supplier_index(self.root, product='高尔夫', process='开模', city='泉州', identity='供应商自述', customization_evidence='OWNER_REPORTED')
        self.assertEqual([row['id'] for row in result['suppliers']], ['s1'])
        profile = result['suppliers'][0]['profile']
        self.assertEqual(profile['factory_identity']['status'], '供应商自述')
        self.assertEqual(profile['factory_identity']['evidence'][0]['kind'], 'SUPPLIER_SELF_CLAIM')
        self.assertEqual(profile['customization']['evidence'][0]['kind'], 'OWNER_REPORTED')
        self.assertEqual(profile['location']['type'], '店铺所在地')
        self.assertFalse(supplier_index(self.root, city='泉州', customization_evidence='INDEPENDENT_PUBLIC')['suppliers'])
        self.supply['suppliers'][0]['names'] = ['7号仓库']
        self.save()
        self.assertEqual([row['id'] for row in supplier_index(self.root, q='七号')['suppliers']], ['s1'])

    def test_product_relations_and_unknown_identity_are_not_supply_claims(self):
        row = supplier_index(self.root, q='8805')['suppliers'][0]
        self.assertEqual(row['sources'][0]['model'], '8805')
        self.assertEqual(row['sources'][0]['products'][0]['role'], 'adopted')
        self.assertEqual(row['sources'][1]['products'][0]['role'], 'candidate')
        historical = supplier_index(self.root, q='T33')['suppliers'][0]
        self.assertEqual(historical['sources'][0]['products'][0]['role'], 'reference')
        self.assertEqual(historical['sources'][0]['products'][0]['source_state'], 'HOLD_SOURCE')
        self.assertEqual(historical['profile']['factory_identity']['status'], '未知')
        self.assertEqual(historical['profile']['customization']['status'], '未知')
        self.assertEqual(historical['profile']['location']['city'], '')
        self.assertFalse(historical['has_profile'])
        self.assertEqual([r['id'] for r in supplier_index(self.root, product='运动鞋')['suppliers']], ['s1'])

    def test_source_id_with_model_and_product_number_is_not_a_phone(self):
        source_id = 'src-fixture-h008-2094876'
        self.supply['suppliers'][0]['source_ids'].append(source_id)
        self.supply['suppliers'][0]['matching_profile']['product_directions'].append(
            {'name': '涉水鞋', 'scope': f'来源编号 {source_id}', 'source_ids': [source_id], 'evidence': [{'kind': 'SUPPLIER_PRODUCT_PAGE', 'url': 'https://shop.example/h008'}]})
        self.supply['sources'].append({'id': source_id, 'model': 'H008', 'url': 'https://shop.example/h008'})
        self.products['products'].append({'id': 'BQ-H008', 'candidate_source_ids': [source_id]})
        self.save()
        row = supplier_index(self.root, q='H008')['suppliers'][0]
        self.assertIn(source_id, row['profile']['product_directions'][-1]['source_ids'])
        self.assertIn(source_id, row['profile']['product_directions'][-1]['scope'])
        source = next(item for item in row['sources'] if item['id'] == source_id)
        self.assertEqual(source['products'][0]['id'], 'BQ-H008')
        self.assertEqual(source['products'][0]['role'], 'candidate')
        orphan_id = 'src-fixture-a009-2462264'
        self.supply['sources'].append({'id': orphan_id, 'model': 'A009', 'url': 'https://shop.example/a009'})
        self.save()
        self.assertEqual([item['id'] for item in supplier_index(self.root, q='A009')['unassociated_sources']], [orphan_id])

    def test_orphan_is_searchable_without_creating_a_supplier(self):
        result = supplier_index(self.root, q='old1')
        self.assertEqual(result['suppliers'], [])
        self.assertEqual([item['id'] for item in result['unassociated_sources']], ['orphan'])
        self.assertIn('made-in-china.com', result['unassociated_sources'][0]['url'])
        self.assertEqual(result['unassociated_sources'][0]['products'][0]['source_state'], 'HOLD_SOURCE')
        self.assertEqual(supplier_index(self.root, q='old1', identity='未知')['unassociated_sources'], [])

    def test_contact_cost_and_private_url_are_not_exposed(self):
        p = self.supply['suppliers'][0]['matching_profile']
        p['open_questions'].extend(['电话 13800138000', '电话 138 0013 8000', '办公电话 0595-12345678', '报价 ￥98', '采购价：人民币 85', '联系 someone@example.com', '微信：private-id'])
        p['factory_identity']['summary'] = '联系方式 13800138000'
        p['customization']['evidence'][0]['url'] = 'https://shop.example/?token=private'
        self.supply['sources'].append({'id': 'src-13800138000', 'model': 'secret-contact'})
        self.save()
        serialized = json.dumps(supplier_index(self.root), ensure_ascii=False)
        for secret in ('13800138000', '138 0013 8000', '0595-12345678', '99.98', '￥98', '人民币 85', 'someone@example.com', 'private-id', 'token=private'):
            self.assertNotIn(secret, serialized)
        self.assertNotIn('price', serialized)
        self.assertNotIn('phone', serialized)

    def test_identifiers_do_not_expose_embedded_phone_numbers(self):
        identifiers = [
            'src-shop13800138000suffix',
            'src-shop8613800138000suffix',
            'src-shop008613800138000suffix',
            'src-shop-86-138-0013-8000suffix',
            'src-shop_0086_138.0013.8000suffix',
            'src:shop:86:138:0013:8000suffix',
            'src-shop1_3_8_0_0_1_3_8_0_0_0suffix',
            'src-shop+86-138-0013-8000suffix',
            'src-shop 138 0013 8000',
            'src-shop-0595-12345678suffix',
            'src-shop-0086-0595-12345678suffix',
        ]
        supplier = self.supply['suppliers'][0]
        direction = supplier['matching_profile']['product_directions'][0]
        for n, source_id in enumerate(identifiers):
            supplier['source_ids'].append(source_id)
            direction['source_ids'].append(source_id)
            self.supply['sources'].append({'id': source_id, 'model': f'fixture-{n}'})
            self.supply['suppliers'].append({'id': source_id, 'names': [source_id], 'source_ids': []})
            self.products['products'].append({'id': source_id, 'current_model': source_id, 'aliases': [source_id], 'adopted_source_id': 'one'})
        self.save()
        serialized = json.dumps(supplier_index(self.root), ensure_ascii=False)
        for source_id in identifiers:
            with self.subTest(source_id=source_id):
                self.assertNotIn(source_id, serialized)

    def test_http_reads_current_source_and_does_not_write(self):
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        httpd.app = SimpleNamespace(root=self.root)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        try:
            def get(q):
                connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=5)
                connection.request('GET', '/api/desk/suppliers?' + urlencode({'q': q}))
                response = connection.getresponse()
                data = json.loads(response.read())
                self.assertEqual(response.status, 200)
                connection.close()
                return data
            before = (self.root / SUPPLY).read_bytes()
            self.assertEqual(get('8805')['suppliers'][0]['id'], 's1')
            self.assertEqual(before, (self.root / SUPPLY).read_bytes())
            self.supply['sources'][0]['model'] = '8805-更新'
            self.save()
            self.assertEqual(get('8805-更新')['suppliers'][0]['id'], 's1')
        finally:
            httpd.shutdown()
            httpd.server_close()
            worker.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
