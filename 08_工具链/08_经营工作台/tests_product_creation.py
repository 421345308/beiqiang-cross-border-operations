import sqlite3
import threading
import unittest
from types import SimpleNamespace

from creation_canvas import CreationCanvas
from product_creation import ProductCreation
from workspaces import WorkspaceConflict


class ProductCreationTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(db=sqlite3.connect(':memory:'), lock=threading.RLock())
        class Business:
            def get_object(self, oid):
                if oid != 'product:BQ009':
                    raise ValueError('不存在')
                return {'kind': 'product', 'assets': [{'path': '01_产品资产/BQ009/a.jpg', 'label': '主图'},
                                                        {'path': '01_产品资产/BQ009/missing.jpg', 'label': '缺失'}]}
        class Media:
            def resolve(self, path):
                if path != '01_产品资产/BQ009/a.jpg':
                    raise ValueError('找不到素材')
                return {'path': path, 'name': 'a.jpg', 'kind': 'image', 'url': '/media', 'size': 1}
        class Creation:
            def get_project(self, oid):
                if oid != 'creation:one':
                    raise ValueError('找不到项目')
                return {'title': '项目', 'summary': '', 'assets': []}
            def list_projects(self):
                return [{'id': 'creation:one', 'title': '项目', 'source': 'PROJECT.md'}]
        self.app.business = Business()
        self.app.media = Media()
        self.app.creation = Creation()
        self.app.creation_canvas = CreationCanvas(self.app)
        self.service = ProductCreation(self.app)
        self.addCleanup(self.app.db.close)

    def test_reuses_existing_asset_and_preserves_canvas(self):
        options = self.service.options('product:BQ009')
        self.assertEqual([a['name'] for a in options['assets']], ['a.jpg'])
        self.assertEqual(options['projects'][0]['id'], 'creation:one')
        result = self.service.add_to_canvas('product:BQ009', 'creation:one', '01_产品资产/BQ009/a.jpg', '')
        self.assertTrue(result['added'])
        self.assertEqual(result['canvas']['nodes'][0]['id'], 'brief')
        self.assertEqual(result['canvas']['nodes'][1]['data']['media_path'], '01_产品资产/BQ009/a.jpg')
        again = self.service.add_to_canvas('product:BQ009', 'creation:one', '01_产品资产/BQ009/a.jpg', result['canvas']['version'])
        self.assertFalse(again['added'])
        self.assertEqual(len(again['canvas']['nodes']), 2)

    def test_rejects_unrelated_missing_and_stale_data(self):
        with self.assertRaises(ValueError):
            self.service.add_to_canvas('product:BQ009', 'creation:one', '01_产品资产/other/a.jpg', '')
        with self.assertRaises(ValueError):
            self.service.add_to_canvas('product:BQ009', 'creation:one', '01_产品资产/BQ009/missing.jpg', '')
        with self.assertRaises(ValueError):
            self.service.add_to_canvas('product:BQ009', 'creation:missing', '01_产品资产/BQ009/a.jpg', '')
        self.service.add_to_canvas('product:BQ009', 'creation:one', '01_产品资产/BQ009/a.jpg', '')
        with self.assertRaises(WorkspaceConflict):
            self.service.add_to_canvas('product:BQ009', 'creation:one', '01_产品资产/BQ009/a.jpg', '')


if __name__ == '__main__':
    unittest.main()
