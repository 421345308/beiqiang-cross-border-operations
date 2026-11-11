"""Guard data preservation and separation while migrating legacy product tools."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import os

from product_registry import ProductRegistry, PRODUCTS, SUPPLY, ALIBABA, split, compose, atomic_write
from test_product_workspace import fixture


class DomainStores(unittest.TestCase):
    def test_transient_file_lock_retries_atomic_replace(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'data.json'
            path.write_bytes(b'old')
            replace = os.replace
            calls = []
            def locked_once(source, target):
                calls.append(target)
                if len(calls) == 1:
                    raise PermissionError('temporary reader lock')
                return replace(source, target)
            with patch('product_registry.os.replace', side_effect=locked_once), patch('product_registry.time.sleep'):
                atomic_write(path, b'new')
            self.assertEqual(path.read_bytes(), b'new')
            self.assertEqual(len(calls), 2)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def data(self):
        data = fixture()
        data['products'][0].update(dossier_path='local.md', classification={'local_intent_candidates':['walking'], 'platform_category_ids':['123'], 'store_groups':[]})
        return data

    def seed(self, root):
        for path, data in split(self.data()).items():
            atomic_write(root/path, (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode())

    def test_split_preserves_identity_and_per_link_evidence(self):
        data = self.data()
        parts = split(data)
        self.assertEqual(compose(parts), data)
        self.assertNotIn('listings', parts[PRODUCTS])
        self.assertNotIn('sources', parts[ALIBABA])
        self.assertNotIn('platform_category_ids', parts[PRODUCTS]['products'][0]['classification'])
        self.assertEqual(parts[ALIBABA]['listings'], data['listings'])

    def test_channel_change_does_not_rewrite_product_supply_or_douyin(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); self.seed(root)
            douyin = root/'09_国内电商/抖店/数据/渠道产品对应.json'
            atomic_write(douyin, b'{"independent":true}')
            untouched = {p: (root/p).read_bytes() for p in (PRODUCTS, SUPPLY)}
            store = ProductRegistry(root)
            data = json.loads(store.read_text())
            data['updated_on'] = '2026-10-20'
            data['listings'][0]['observation']['audit'] = 'pending'
            store.write_registry(data)
            self.assertEqual({p: (root/p).read_bytes() for p in untouched}, untouched)
            self.assertEqual(douyin.read_bytes(), b'{"independent":true}')
            self.assertEqual(json.loads(store.read_text())['listings'][0]['observation']['audit'], 'pending')

    def test_stale_writer_cannot_overwrite_newer_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); self.seed(root)
            first, second = ProductRegistry(root), ProductRegistry(root)
            a, b = (json.loads(s.read_text()) for s in (first, second))
            a['sources'][0]['price'] = '72'
            first.write_registry(a)
            with self.assertRaisesRegex(RuntimeError, 'changed concurrently'):
                second.write_registry(b)
            self.assertEqual(json.loads(first.read_text())['sources'][0]['price'], '72')


class FormalFieldResolution(unittest.TestCase):
    def setUp(self):
        from product_registry import resolve_formal_fields
        self.resolve = resolve_formal_fields
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pid = '1600000000001'
        self.listing = {'id': self.pid, 'product_id': 'LQ-1680',
                        'formal_fields': {'file': 'new.json', 'at': '2026-11-11T03:33:49Z'}}
        (self.root/'old.json').write_text(json.dumps({'requested_product_id': self.pid,
            'response': {'product': {'product_id': 'encrypted', 'subject': 'old'}}}), encoding='utf-8')
        (self.root/'new.json').write_text(json.dumps({'product': {'product_id': 'encrypted', 'subject': 'new'}}), encoding='utf-8')

    def test_registered_listing_wins_and_old_bytes_remain(self):
        old = (self.root/'old.json').read_bytes()
        result = self.resolve(self.root, 'LQ-1680', [self.listing], channel='alibaba')
        self.assertEqual((result['state'],result['file'],result['observed_at']),
                         ('recorded','new.json','2026-11-11T03:33:49Z'))
        self.assertEqual((self.root/'old.json').read_bytes(), old)

    def test_receipt_observation_time_is_not_replaced_by_registration_time(self):
        (self.root/'new.json').write_text(json.dumps({'requested_product_id':self.pid,
            'observed_at_utc':'2026-10-19T18:51:15Z','response':{'product':{'product_id':'encrypted'}}}),encoding='utf-8')
        result=self.resolve(self.root,'LQ-1680',[self.listing],channel='alibaba')
        self.assertEqual(result['observed_at'],'2026-10-19T18:51:15Z')

    def test_channel_and_listing_must_be_unambiguous(self):
        self.assertEqual(self.resolve(self.root,'LQ-1680',[self.listing])['reason'], 'channel_not_selected_or_unsupported')
        other = dict(self.listing, id='1600000000002')
        self.assertEqual(self.resolve(self.root,'LQ-1680',[self.listing,other],channel='alibaba')['reason'],'multiple_listings')
        result=self.resolve(self.root,'LQ-1680',[self.listing,other],channel='alibaba',listing_id=self.pid)
        self.assertEqual(result['file'],'new.json')
        self.assertEqual(self.resolve(self.root,'OTHER',[self.listing],channel='alibaba',listing_id=self.pid)['reason'],'listing_identity_unknown')
        duplicate=dict(self.listing,product_id='OTHER')
        self.assertEqual(self.resolve(self.root,'LQ-1680',[self.listing,duplicate],channel='alibaba')['reason'],'listing_identity_unknown')

    def test_missing_or_mismatched_receipt_never_falls_back(self):
        self.listing['formal_fields']['file']='missing.json'
        self.assertEqual(self.resolve(self.root,'LQ-1680',[self.listing],channel='alibaba')['reason'],'formal_receipt_unavailable')
        self.listing['formal_fields']['file']='new.json'
        (self.root/'new.json').write_text(json.dumps({'requested_product_id':'1600000000002',
            'response': {'product': {'product_id':'encrypted'}}}),encoding='utf-8')
        self.assertEqual(self.resolve(self.root,'LQ-1680',[self.listing],channel='alibaba')['reason'],'receipt_listing_mismatch')
        del self.listing['formal_fields']
        self.assertEqual(self.resolve(self.root,'LQ-1680',[self.listing],channel='alibaba')['reason'],'formal_receipt_not_registered')


if __name__ == '__main__':
    unittest.main()
