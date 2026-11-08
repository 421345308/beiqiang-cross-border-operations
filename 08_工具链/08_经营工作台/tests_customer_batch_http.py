"""HTTP wiring for the private customer batch and safe sending services."""
import unittest
from unittest.mock import patch
import tests_desk_http as fixtures


class CustomerBatchHTTPTests(unittest.TestCase):
    setUp = fixtures.DeskHTTPTests.setUp
    tearDown = fixtures.DeskHTTPTests.tearDown
    request = fixtures.DeskHTTPTests.request
    write = fixtures.DeskHTTPTests.write

    def create_batch(self):
        status, result = self.request('/api/customer-batches', {
            'title': 'HTTP fixture', 'object_ids': ['customer:website-BQ-REAL']})
        self.assertEqual(status, 201)
        return result

    def test_list_read_research_and_local_revision(self):
        batch = self.create_batch(); bid = batch['id']; oid = batch['items'][0]['object_id']
        status, index = self.request('/api/customer-batches')
        self.assertEqual(status, 200); self.assertTrue(any(row['id'] == bid for row in index['items']))
        draft = self.app.gmail_drafts.get(oid)
        status, current = self.request('/api/customer-batches/' + bid)
        self.assertEqual(status, 200); self.assertEqual(current['items'][0]['object_id'], oid)
        research_body = {'batch_id': bid, 'revision': current['revision'], 'object_ids': [oid], 'instruction': 'Research'}
        with patch.object(self.app.batch_research, 'begin', return_value={'results':[{'status':'started'}]}) as begin:
            status, result = self.request('/api/desk/customer-batches/research', research_body)
            self.assertEqual(status, 202); self.assertEqual(result['results'][0]['status'], 'started')
            begin.assert_called_once_with(research_body)
        with patch.object(self.app.agent_jobs, 'start', return_value={'id': 'revision-job'}) as start:
            status, result = self.request('/api/desk/customer-batches/revise', {
                'batch_id': bid, 'object_id': oid, 'item_revision': current['items'][0]['item_revision'],
                'draft_version': draft['version'], 'instruction': 'Shorten this customer email'})
            self.assertEqual(status, 201); self.assertEqual(result['job']['id'], 'revision-job')
            self.assertEqual(result['batch']['items'][0]['review_state'], 'changes_requested')
            start.assert_called_once_with(oid, 'Shorten this customer email', mode='outreach_draft', batch_id=bid)
            status, _ = self.request('/api/desk/customer-batches/revise', {
                'batch_id': bid, 'object_id': oid, 'item_revision': current['items'][0]['item_revision'],
                'instruction': 'Stale change'})
            self.assertEqual(status, 409); self.assertEqual(start.call_count, 1)

    def test_research_group_routes_are_explicit_and_csrf_protected(self):
        batch = self.create_batch(); bid = batch['id']
        with patch.object(self.app.batch_research, 'list_groups', return_value={'items': []}) as listing, \
             patch.object(self.app.batch_research, 'continue_group', return_value={'results': []}) as resume:
            status, _ = self.request('/api/desk/customer-batches/research-groups?batch_id=' + bid)
            self.assertEqual(status, 200); listing.assert_called_once_with(bid)
            self.assertEqual(self.request('/api/desk/customer-batches/research-continue', {'group_id':'g'}, token=False)[0],403)
            resume.assert_not_called()
            self.assertEqual(self.request('/api/desk/customer-batches/research-continue', {'group_id':'g'})[0],202)
            resume.assert_called_once_with('g')

    def test_real_research_group_http_deduplicates_and_reads_graph(self):
        batch=self.create_batch(); oid=batch['items'][0]['object_id']
        body={'batch_id':batch['id'],'revision':batch['revision'],'object_ids':[oid],
              'instruction':'Research fixture','request_id':'e'*32}
        with patch.object(self.app.agent_jobs,'_work',lambda *_:None):
            status,first=self.request('/api/desk/customer-batches/research',body)
            self.assertEqual(status,202);self.assertEqual(first['results'][0]['status'],'started')
            status,again=self.request('/api/desk/customer-batches/research',body)
            self.assertEqual(status,202);self.assertEqual(again['results'][0]['status'],'existing')
            self.assertEqual(first['group_id'],again['group_id'])
            status,graph=self.request('/api/desk/job/graph?id='+first['group_id'])
            self.assertEqual(status,200);self.assertEqual(len(graph['jobs']),2)
            status,listed=self.request('/api/desk/customer-batches/research-groups?batch_id='+batch['id'])
            self.assertEqual(status,200);self.assertEqual(listed['items'][0]['id'],first['group_id'])
            child=first['results'][0]['job']['id']
            self.assertEqual(self.request('/api/desk/job/dispatch',{'id':child})[0],400)

    def test_sending_routes_require_token_and_use_plan_service(self):
        batch = self.create_batch(); bid = batch['id']; oid = batch['items'][0]['object_id']
        plan_id = 'a' * 32
        with patch.object(self.app.batch_sending, 'preflight', return_value={'can_confirm': False}) as preflight, \
             patch.object(self.app.batch_sending, 'send', return_value={'status': 'completed', 'items': []}) as send, \
             patch.object(self.app.batch_sending, 'get', return_value={'id': plan_id, 'batch_id': bid, 'items': []}):
            body = {'revision': batch['revision'], 'object_ids': [oid]}
            self.assertEqual(self.request('/api/customer-batches/' + bid + '/preflight', body, token=False)[0], 403)
            preflight.assert_not_called()
            self.assertEqual(self.request('/api/customer-batches/' + bid + '/preflight', body)[0], 200)
            preflight.assert_called_once_with(bid, body)
            send_body = {'plan_id': plan_id, 'confirmed': True}
            self.assertEqual(self.request('/api/customer-batches/' + bid + '/send', send_body)[0], 200)
            send.assert_called_once_with(bid, send_body)
            self.assertEqual(self.request('/api/customer-batches/' + bid + '/plans/' + plan_id)[0], 200)
            self.assertEqual(self.request('/api/customer-batches/' + 'b' * 32 + '/plans/' + plan_id)[0], 400)

    def test_event_reconciliation_routes_are_explicit(self):
        oid = 'customer:website-BQ-REAL'
        status, events = self.request('/api/desk/gmail/events?object_id=' + oid)
        self.assertEqual(status, 200); self.assertFalse(events['automatic_replay'])
        body = {'object_id': oid, 'message_id': 'm', 'job_id': 'j', 'snapshot': {},
                'confirmed': False, 'manual_note': 'review'}
        status, _ = self.request('/api/desk/gmail/events/link', body)
        self.assertEqual(status, 400)

    def test_crm_review_requires_explicit_request_and_uses_current_batch(self):
        batch = self.create_batch(); item = batch['items'][0]
        evidence = {'aliases': {'checked': True, 'terms': ['Fixture'], 'locations': ['CRM'], 'findings': 'No match'},
                    'independent_sends': {'checked': True, 'locations': ['Local log'], 'findings': 'No match'},
                    'stop_records': {'checked': True, 'locations': ['Stop list'], 'findings': 'No match'}}
        body = {'batch_id': batch['id'], 'object_id': item['object_id'], 'item_revision': item['item_revision'],
                'evidence': evidence, 'confirmed': True}
        with patch.object(self.app.outreach_checks, 'record_crm_review', return_value={'applied': True}) as record:
            self.assertEqual(self.request('/api/desk/customer-batches/crm-review', body, token=False)[0], 403)
            record.assert_not_called()
            status, result = self.request('/api/desk/customer-batches/crm-review', body)
            self.assertEqual(status, 200); self.assertEqual(result['batch']['id'], batch['id'])
            record.assert_called_once_with(batch['id'], item['object_id'], item['item_revision'], evidence, True)

    def test_remove_reference_keeps_original_customer(self):
        batch=self.create_batch();oid=batch['items'][0]['object_id']
        status,result=self.request('/api/customer-batches/'+batch['id']+'/items/remove',{
            'revision':batch['revision'],'object_ids':[oid]})
        self.assertEqual(status,200);self.assertEqual(result['counts']['total'],0)
        self.assertEqual(self.app.business.get_object(oid)['id'],oid)

    def test_legacy_job_recovery_requires_token_and_explicit_inputs(self):
        body={'id':'legacy','confirmed':True,'former_owner_pid':1234,'evidence':'PID 1234 已核对退出'}
        with patch.object(self.app.agent_jobs,'recover_legacy',return_value={'id':'legacy','status':'failed'}) as recover:
            self.assertEqual(self.request('/api/desk/job/recover-legacy',body,token=False)[0],403)
            recover.assert_not_called()
            self.assertEqual(self.request('/api/desk/job/recover-legacy',body)[0],200)
            recover.assert_called_once_with('legacy',confirmed=True,former_owner_pid=1234,evidence='PID 1234 已核对退出')


if __name__ == '__main__':
    unittest.main()
