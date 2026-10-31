"""Local object persistence and connector boundary tests; no platform mutations."""
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from workspaces import Workspaces


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = sqlite3.connect(self.root / 'store.sqlite3')
        self.app = SimpleNamespace(root=self.root, db=self.db, lock=threading.RLock())
        self.work = Workspaces(self.app)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_canvas_reopen_retains_nodes_and_rejects_stale_edit(self):
        canvas = self.work.save('canvas', {'title': '真实本地草稿', 'nodes': [
            {'id': 'n1', 'type': 'shot', 'title': '镜头一', 'content': '实物证据', 'x': 85, 'y': 100}]})
        reopened = Workspaces(self.app).get('canvas', canvas['id'])
        self.assertEqual(reopened, canvas)
        revised = self.work.save('canvas', {**canvas, 'title': '已修订'})
        with self.assertRaisesRegex(ValueError, '其他页面'):
            self.work.save('canvas', {**canvas, 'title': '过期页面'})
        self.assertEqual(self.work.get('canvas', canvas['id']), revised)

    def test_bad_nodes_cannot_replace_saved_canvas(self):
        canvas = self.work.save('canvas', {'title': '保持原稿', 'nodes': []})
        with self.assertRaises(ValueError):
            self.work.save('canvas', {**canvas, 'nodes': [{'id':'a','type':'shot','x':float('nan'),'y':1}]})
        self.assertEqual(self.work.get('canvas',canvas['id']),canvas)

    def test_external_write_requires_post_and_specific_confirmation(self):
        calls = []
        self.work.modules['libtv'] = SimpleNamespace(execute=lambda operation, **kw: calls.append((operation, kw)) or {'ok':True,'data':{'id':'new'},'source':{'provider':'libtv-cli'}})
        args = {'name':'验收','workspace_id':'0'}
        with self.assertRaises(ValueError):
            self.work.call('libtv', 'create-project', args)
        with self.assertRaises(ValueError):
            self.work.call('libtv', 'create-project', args, write=True)
        self.assertEqual(calls, [])
        result = self.work.call('libtv', 'create-project', {**args, 'confirmed':True, 'shell':'untrusted'}, write=True)
        self.assertEqual(calls, [('create-project',args)])
        self.assertEqual(self.work.receipts()[0]['id'],result['receipt_id'])

    def test_product_draft_never_invokes_connector(self):
        def forbidden(*a, **kw): raise AssertionError('Unexpected platform call')
        self.work.modules['alibaba']=SimpleNamespace(execute=forbidden)
        draft=self.work.route_post('/api/product-drafts',{'product_id':'123','subject_before':'原名','subject_after':'候选','notes':'待确认事实'})
        self.assertEqual(draft['status'],'local_draft')
        self.assertEqual(self.work.route_get('/api/product-drafts',{})['drafts'][0],draft)

    def test_unavailable_metrics_are_not_zero_and_history_dates_survive(self):
        self.assertFalse(self.work.metrics()['ok'])
        p=self.root/'02_Alibaba运营/01_店铺与全店诊断/经营复核.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'summary':{'observed_at':'2026-10-21','period':'2026-10-11~2026-10-17','totals':{'inquiries':None,'search_clicks':4}}}),encoding='utf-8')
        result=self.work.metrics()
        self.assertIsNone(result['metrics']['inquiries'])
        self.assertEqual(result['observed_at'],'2026-10-21')
        self.assertEqual(result['metrics']['search_clicks'],4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
