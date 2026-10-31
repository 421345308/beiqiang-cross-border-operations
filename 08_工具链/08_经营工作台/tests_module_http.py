"""HTTP acceptance of local media and draft persistence; no platform writes."""
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from server import Handler, ThreadingHTTPServer
from media_assets import MediaAssets
from workspaces import Workspaces
from product_changes import ProductChanges, CATALOG, UPDATE
from tests_product_changes import Client


class ModuleHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.rel = '99_临时区/工作台应用验收/clip.mp4'
        clip = self.root / self.rel
        clip.parent.mkdir(parents=True)
        self.payload = b'\0\0\0\x18ftypisom0123456789'
        clip.write_bytes(self.payload)
        self.db = sqlite3.connect(self.root / 'test.sqlite3', check_same_thread=False)
        self.app = SimpleNamespace(root=self.root, state=self.root/'.local', token='local-test-token', db=self.db,
                                   lock=threading.RLock(), media=MediaAssets(self.root))
        self.app.workspaces = Workspaces(self.app)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.http.app = self.app
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.worker.join()
        self.db.close()
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port)
        supplied = {'Content-Type':'application/json', 'X-Workbench-Token':self.app.token}
        supplied.update(headers or {})
        conn.request(method, path, json.dumps(body) if body is not None else None, supplied)
        response = conn.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        conn.close()
        return result

    def test_media_resolve_stream_range_and_missing_file(self):
        code, _, raw = self.request('POST', '/api/media/resolve', {'path':self.rel})
        self.assertEqual(code, 200)
        media = json.loads(raw)['media']
        self.assertEqual(media['kind'], 'video')
        code, headers, data = self.request('GET', media['url'], headers={'Range':'bytes=2-5'})
        self.assertEqual(code, 206)
        self.assertEqual(data, self.payload[2:6])
        self.assertEqual(headers.get('Content-Range'), f'bytes 2-5/{len(self.payload)}')
        code, _, data = self.request('GET', media['url'])
        self.assertEqual((code, data), (200, self.payload))
        code, _, _ = self.request('GET', media['url'], headers={'Range':'bytes=100-200'})
        self.assertEqual(code, 416)
        code, _, _ = self.request('POST','/api/media/resolve',{'path':self.rel+'-missing.mp4'})
        self.assertEqual(code, 404)

    def test_new_routes_keep_same_local_access_boundary(self):
        code, _, _ = self.request('POST','/api/media/resolve',{'path':self.rel},
                                  {'X-Workbench-Token':'incorrect'})
        self.assertEqual(code, 403)
        code, _, _ = self.request('POST','/api/media/resolve',{'path':self.rel},
                                  {'Origin':'https://untrusted.example'})
        self.assertEqual(code, 403)
        code, _, _ = self.request('POST','/api/media/resolve',{'path':'../private.mp4'})
        self.assertIn(code, (400, 403))

    def test_media_reference_survives_api_save_and_reopen(self):
        body = {'title':'素材接口验收','nodes':[{'id':'n1','type':'asset','title':'clip',
                'content':'original reference','media_path':self.rel,'x':0,'y':0}]}
        code, _, raw = self.request('POST','/api/canvases',body)
        self.assertEqual(code, 200)
        saved = json.loads(raw)
        code, _, raw = self.request('GET','/api/canvases/'+saved['id'])
        self.assertEqual(json.loads(raw)['nodes'][0]['media_path'],self.rel)

    def test_title_workflow_through_http_uses_only_injected_platform(self):
        catalog = self.root / CATALOG
        catalog.parent.mkdir(parents=True)
        catalog.write_text(json.dumps({'listings':[
            {'id':'123','catalog_fields':{'title':'Old title'},
             'current_platform_fields':{'title':'Old title'}},
            {'id':'456','notes':'Other conversation retained'}]}),encoding='utf-8')
        (self.root/'facts.md').write_text('Fixture evidence',encoding='utf-8')
        client = Client()
        self.app.product_changes = ProductChanges(self.app,client)
        code, _, raw = self.request('POST','/api/product-changes/prepare',{
            'product_id':'123','proposed_title':'New title','rationale':'Test fixture only',
            'evidence':['facts.md']})
        prepared = json.loads(raw)
        self.assertEqual(code,200)
        self.assertTrue(prepared['ok'],prepared)
        change = prepared['change']
        url = '/api/product-changes/'+change['id']
        _, _, raw = self.request('GET',url)
        self.assertEqual(json.loads(raw)['change']['state'],'prepared')
        _, _, raw = self.request('POST',url+'/apply',{'confirmed':False,'expected_version':change['version']})
        self.assertFalse(json.loads(raw)['ok'])
        self.assertNotIn(UPDATE,[x[0] for x in client.calls])
        _, _, raw = self.request('POST',url+'/apply',{'confirmed':True,'expected_version':change['version']})
        self.assertEqual(json.loads(raw)['change']['state'],'submitted')
        client.product['subject']='New title'
        _, _, raw = self.request('POST',url+'/reconcile',{})
        reconciled = json.loads(raw)
        self.assertEqual(reconciled['change']['localSync']['state'],'synced',reconciled)
        self.assertEqual(reconciled['change']['publicVerification']['state'],'not-verified')
        rows=json.loads(catalog.read_text(encoding='utf-8'))['listings']
        self.assertEqual(rows[0]['current_platform_fields']['title'],'New title')
        self.assertEqual(rows[1]['notes'],'Other conversation retained')
        _, _, raw = self.request('GET','/api/product-changes')
        self.assertEqual(len(json.loads(raw)['changes']),1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
