"""Optimistic revision acceptance through real local HTTP and scoped MCP; fixtures only."""
import unittest
from urllib.parse import urlencode
import tests_desk_http as fixture
from desk_mcp import DeskTools


class CustomerRevisionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.DeskHTTPTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.request = self.fixture.request
        status, created = self.request('/api/desk/inquiries', {
            'channel': 'email', 'company': 'Synthetic revision buyer',
            'source_id': 'revision-http-fixture',
            'original_text': 'Synthetic fixture: please discuss sample requirements.'})
        self.assertEqual(status, 201)
        self.oid = created['object_id']
        self.tools = DeskTools(self.fixture.app.business, self.fixture.root,
                               self.oid, audit=self.fixture.root/'revision-audit.jsonl')

    def read(self, kind):
        status, data = self.request('/api/desk/customer-'+kind+'?'+urlencode({'object_id': self.oid}))
        self.assertEqual(status, 200)
        self.assertTrue(data['revision'])
        return data

    def body(self, kind, snapshot, value, revision=True):
        result = {'object_id': self.oid}
        if revision:
            result['revision'] = snapshot['revision']
        if kind == 'profile':
            result.update(source_hash=snapshot['source_hash'], analysis={'fit': value})
        else:
            result['next_action'] = value
        return result

    def value(self, kind, data):
        return data['analysis']['fit'] if kind == 'profile' else data['next_action']

    def test_stale_http_snapshots_cannot_overwrite_new_manual_values(self):
        for kind in ('profile', 'workflow'):
            with self.subTest(kind=kind):
                a = self.read(kind)
                b = self.read(kind)
                path = '/api/desk/customer-'+kind
                status, saved = self.request(path, self.body(kind, b, 'latest manual value'))
                self.assertEqual(status, 200)
                self.assertNotEqual(saved['revision'], a['revision'])
                status, conflict = self.request(path, self.body(kind, a, 'stale browser value'))
                self.assertEqual(status, 409, conflict)
                self.assertEqual(self.value(kind, self.read(kind)), 'latest manual value')
                status, rejected = self.request(path, self.body(kind, saved, 'missing revision value', revision=False))
                self.assertEqual(status, 400, rejected)
                self.assertEqual(self.value(kind, self.read(kind)), 'latest manual value')

    def test_scoped_mcp_write_invalidates_old_http_snapshot(self):
        for kind in ('profile', 'workflow'):
            with self.subTest(kind=kind):
                old_http = self.read(kind)
                mcp_read = self.tools.call('get_customer_'+kind, {})
                self.assertEqual(mcp_read['revision'], old_http['revision'])
                body = self.body(kind, mcp_read, 'latest MCP value')
                body.pop('object_id')
                saved = self.tools.call('save_customer_'+kind, body)
                self.assertNotEqual(saved['revision'], old_http['revision'])
                status, conflict = self.request('/api/desk/customer-'+kind,
                    self.body(kind, old_http, 'stale HTTP after MCP'))
                self.assertEqual(status, 409, conflict)
                current = self.read(kind)
                self.assertEqual(self.value(kind, current), 'latest MCP value')
                self.assertEqual(current['revision'], saved['revision'])

    def test_changed_source_is_a_conflict_and_missing_source_is_bad_request(self):
        oid = 'customer:website-BQ-REAL'
        path = '/api/desk/customer-profile'
        status, old = self.request(path+'?'+urlencode({'object_id':oid}))
        self.assertEqual(status, 200)
        self.fixture.website.fetch = lambda: {'ok':True, 'records':[
            {'reference':'BQ-REAL','company':'Fixture buyer',
             'requirements':'Updated synthetic customer requirements','internalTest':False}]}
        self.fixture.website.refresh(wait=True)
        status, _ = self.request(path, {'object_id':oid,'revision':old['revision'],
                                         'source_hash':old['source_hash'],'translation_zh':'stale'})
        self.assertEqual(status, 409)
        status, current = self.request(path+'?'+urlencode({'object_id':oid}))
        self.assertEqual(current['translation_zh'], '')
        status, _ = self.request(path, {'object_id':oid,'revision':current['revision'],
                                         'translation_zh':'missing source'})
        self.assertEqual(status, 400)


if __name__ == '__main__':
    unittest.main()
