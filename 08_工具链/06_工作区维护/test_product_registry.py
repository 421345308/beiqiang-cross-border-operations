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


if __name__ == '__main__':
    unittest.main()
