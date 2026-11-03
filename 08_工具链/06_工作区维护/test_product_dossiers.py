"""Ensure product dossiers do not revive superseded listing facts or images."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import product_dossiers as dossiers


class DossierReceipts(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(dossiers, 'ROOT', self.root)
        self.alias_patch = patch.object(dossiers, 'ALIASES', self.root / 'absent-alias.json')
        self.resolver_patch = patch.object(dossiers, 'resolve_legacy_asset',
                                           side_effect=lambda path, **kw: self.root / path)
        for item in (self.root_patch, self.alias_patch, self.resolver_patch):
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.tmp.cleanup)
        self.pid = '1600000000001'
        self.short_url = 'https://sc04.alicdn.com/kf/Hnew.jpg'
        self.long_url = 'https://sc04.alicdn.com/kf/Hnew/123/Hnew.jpg'
        self.old_url = 'https://sc04.alicdn.com/kf/Hold.jpg'
        self.data = {
            'sources': [],
            'products': [{'id': 'HR044', 'aliases': ['BQ1044'], 'current_model': 'BQ1044',
                          'source_state': 'ADOPTED', 'next_action': '核实', 'evidence': []}],
            'listings': [{'id': self.pid, 'product_id': 'HR044', 'model': 'BQ1044-A',
                          'formal_fields': {'file': 'receipts/new.json', 'at': '2026-11-03T05:00:00Z'}}],
        }
        self.write_json(dossiers.DETAILS / self.pid / 'formal_get.json',
                        {'observed_at_utc': '2026-09-01', 'response': {'product': {
                            'subject': 'old shoe', 'main_image': {'images': [self.old_url]}}}})
        self.write_json('receipts/new.json', {'product': {'subject': 'new shoe', 'status': 'approved',
                                                         'main_image': {'images': [self.short_url]}}})
        self.write_json(dossiers.ASSET_INDEX, {'files': [{'file': 'images/new.jpg',
            'products': ['HR044', 'BQ1044'], 'official_urls': [self.long_url]}]})
        (self.root / 'images').mkdir()
        (self.root / 'images/new.jpg').write_bytes(b'new')

    def write_json(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def render(self):
        return next(iter(dossiers.builds(self.data).values())).decode()

    def test_registered_direct_receipt_and_matching_official_image_win(self):
        result = self.render()
        self.assertIn('new shoe', result)
        self.assertIn('2026-11-03T05:00:00Z', result)
        self.assertIn('images/new.jpg', result)
        self.assertIn(self.short_url, result)
        self.assertNotIn('old shoe', result)
        self.assertNotIn(self.old_url, result)
        self.assertEqual(dossiers.sync_formal_references(self.data), 1)
        self.assertEqual(self.data['listings'][0]['formal_fields']['file'], 'receipts/new.json')

    def test_missing_registered_receipt_never_falls_back_to_old(self):
        (self.root / 'receipts/new.json').unlink()
        result = self.render()
        self.assertIn('已登记的正式回读缺失', result)
        self.assertNotIn('old shoe', result)
        self.assertNotIn(self.old_url, result)
        dossiers.sync_formal_references(self.data)
        self.assertEqual(self.data['listings'][0]['formal_fields']['file'], 'receipts/new.json')

    def test_legacy_response_receipt_still_renders(self):
        del self.data['listings'][0]['formal_fields']
        result = self.render()
        self.assertIn('old shoe', result)
        self.assertIn('2026-09-01', result)
        self.assertIn(self.old_url, result)
        self.assertIn('本地图片待补', result)

    def test_default_registered_receipt_refreshes_its_changed_fields(self):
        listing = self.data['listings'][0]
        listing['formal_fields'] = {'file': (dossiers.DETAILS / self.pid / 'formal_get.json').as_posix(),
                                    'at': '2026-08-01'}
        listing['current_platform_fields'] = {'title': 'outdated'}
        self.assertEqual(dossiers.sync_formal_references(self.data), 1)
        self.assertEqual(listing['current_platform_fields']['title'], 'old shoe')
        self.assertEqual(listing['formal_fields']['at'], '2026-09-01')

    def test_ambiguous_or_unrelated_image_is_never_guessed(self):
        self.write_json(dossiers.ASSET_INDEX, {'files': [
            {'file': 'images/new.jpg', 'products': ['HR044'], 'official_urls': [self.long_url]},
            {'file': 'images/other.jpg', 'products': ['BQ1044'], 'official_urls': [self.long_url]},
        ]})
        result = self.render()
        self.assertIn('本地图片待补', result)
        self.assertNotIn('images/new.jpg', result)
        self.assertNotIn('images/other.jpg', result)
        self.assertIsNone(dossiers.official_image_key('https://unrelated.example/kf/Hnew.jpg'))


if __name__ == '__main__':
    unittest.main()
