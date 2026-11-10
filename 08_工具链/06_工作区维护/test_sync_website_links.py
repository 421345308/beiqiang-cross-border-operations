import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync_website_links', Path(__file__).with_name('sync_website_links.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class WebsiteLinkSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        target = self.root / sync.OVERRIDES
        target.parent.mkdir(parents=True)
        target.write_text('{}\n', encoding='utf-8')
        (self.root / 'source.json').write_text('{"revision": 1}', encoding='utf-8')
        product = {'id': 'P1', 'aliases': ['BQ001'], 'adopted_source_id': 'src1', 'raw_packages': []}
        self.inputs = {
            'root': self.root, 'snapshot_path': Path('snapshot.json'),
            'fingerprints': {str(sync.OVERRIDES): sync.digest(target.read_bytes()),
                             'source.json': sync.digest((self.root / 'source.json').read_bytes())},
            'products': {'P1': product}, 'sources': {'src1': {'id': 'src1', 'url': 'https://example.test/product'}},
            'index': sync.identity_index([product]),
            'website': {'BQ001': {'code': 'BQ001', 'alibabaProductId': 'old', 'colors': ['Grey'], 'images': ['a', 'b', 'c', 'd']}},
            'listings': {'1234567890': {'id': '1234567890', 'product_id': 'P1', 'bound_source_id': 'src1'}},
            'official': {'1234567890': {'id': '1234567890', 'status': 'approved', 'display': 'Y', 'red_model': 'BQ001'}},
            'snapshot': {'observed_at_utc': '2026-11-04T05:48:18+00:00'},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_product_identity_and_source_must_match(self):
        self.inputs['listings']['1234567890']['product_id'] = 'P2'
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            sync.plan(self.inputs, [('BQ001', '1234567890')])
        self.inputs['listings']['1234567890']['product_id'] = 'P1'
        self.inputs['listings']['1234567890']['bound_source_id'] = 'old-source'
        with self.assertRaisesRegex(ValueError, 'different adopted source'):
            sync.plan(self.inputs, [('BQ001', '1234567890')])

    def test_newer_formal_offline_or_changed_model_blocks_stale_snapshot(self):
        listing = self.inputs['listings']['1234567890']
        listing['current_platform_fields'] = {'at': '2026-11-05T00:00:00+00:00', 'status': 'approved', 'display': 'N', 'model': 'BQ001'}
        with self.assertRaisesRegex(ValueError, 'newer local formal readback'):
            sync.plan(self.inputs, [('BQ001', '1234567890')])
        listing['current_platform_fields'].update(display='Y', model='BQ-OTHER')
        with self.assertRaisesRegex(ValueError, 'changed the model'):
            sync.plan(self.inputs, [('BQ001', '1234567890')])

    def test_owner_confirmed_factory_requires_explicit_current_mode_date_and_local_evidence(self):
        product = self.inputs['products']['P1']
        product.update(source_state='OWNER_CONFIRMED', adopted_source_id=None,
                       supply_mode={'current': 'OWN_FACTORY', 'state': 'OWNER_CONFIRMED_2026_11_02',
                                    'at': '2026-11-02', 'evidence': ['source.json']})
        self.inputs['listings']['1234567890']['bound_source_id'] = None
        self.assertEqual(sync.plan(self.inputs, [('BQ001', '1234567890')])['changes'][0]['to'], '1234567890')
        for field, value in [('current', 'UNKNOWN'), ('state', 'INFERRED'), ('at', 'not-a-date'), ('evidence', ['missing.json'])]:
            old = product['supply_mode'][field]
            product['supply_mode'][field] = value
            with self.assertRaisesRegex(ValueError, 'no recorded adopted source'):
                sync.plan(self.inputs, [('BQ001', '1234567890')])
            product['supply_mode'][field] = old
        product['source_state'] = 'MAPPED'
        with self.assertRaisesRegex(ValueError, 'no recorded adopted source'):
            sync.plan(self.inputs, [('BQ001', '1234567890')])

    def test_plan_rejects_concurrent_source_change_and_fresh_reapply_is_noop(self):
        proposal = sync.plan(self.inputs, [('BQ001', '1234567890')])
        (self.root / 'source.json').write_text('{"revision": 2}', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'changed before write'):
            sync.apply_plan(self.inputs, proposal)
        self.assertEqual(json.loads((self.root / sync.OVERRIDES).read_text()), {})
        (self.root / 'source.json').write_text('{"revision": 1}', encoding='utf-8')
        self.assertTrue(sync.apply_plan(self.inputs, proposal))
        self.assertEqual(json.loads((self.root / sync.OVERRIDES).read_text()), {'BQ001': '1234567890'})
        self.inputs['fingerprints'][str(sync.OVERRIDES)] = sync.digest((self.root / sync.OVERRIDES).read_bytes())
        self.inputs['website']['BQ001']['alibabaProductId'] = '1234567890'
        with self.assertRaisesRegex(RuntimeError, 'fresh plan'):
            sync.apply_plan(self.inputs, proposal)
        fresh = sync.plan(self.inputs, [('BQ001', '1234567890')])
        self.assertFalse(sync.apply_plan(self.inputs, fresh))

    def test_snapshot_requires_complete_unique_ids(self):
        snapshot = {'host': 'open-api.alibaba.com', 'method': 'alibaba.icbu.product.list', 'observed_at_utc': '2026-11-04T00:00:00+00:00',
                    'complete': True, 'total_item': 2, 'saved_rows': 2, 'products': [{'id': 1}, {'id': 1}]}
        with self.assertRaisesRegex(ValueError, 'unique IDs'):
            sync.checked_snapshot(snapshot)


if __name__ == '__main__':
    unittest.main()
