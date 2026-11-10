import unittest
from types import SimpleNamespace

from product_gaps import ProductGaps
from today import Today


def product(pid, *, assets=(), supply='own', source_url='', role='missing', links=(), facts=()):
    return {'id': 'product:' + pid, 'title': pid, 'assets': list(assets),
            'supply': {'kind': supply, 'url': source_url}, 'source_role': role,
            'links': [{'label': label} for label in links], 'channel_listings':[{'id':label.split()[-1]} for label in links], 'category': '系带',
            'facts': [{'label': label, 'value': value} for label, value in facts]}


class FakeBusiness:
    def __init__(self, products): self.products = products; self.calls = 0
    def list_objects(self, kind='', q=''): self.calls += 1; return list(self.products)
    def get_object(self, oid):
        for item in self.products:
            if item['id'] == oid: return item
        raise ValueError('找不到商品')


class GapTests(unittest.TestCase):
    def test_own_factory_does_not_need_a_supplier_link(self):
        business = FakeBusiness([product('BQ001', assets=[{}], links=['Alibaba 1601825021825'])])
        summary = ProductGaps(SimpleNamespace(business=business)).summary()
        self.assertEqual(summary['with_gaps'], 0)
        self.assertEqual(business.calls, 1)

    def test_platform_association_does_not_depend_on_link_label(self):
        row=product('BQ001',assets=[{}],links=['Alibaba 1601825021825'])
        row['links'][0]['label']='国际站商品'
        detail=ProductGaps(SimpleNamespace(business=FakeBusiness([row]))).for_product('BQ001')
        self.assertNotIn('no_platform_id',detail['gap_keys'])
        self.assertEqual(detail['platform_ids'],['1601825021825'])

    def test_only_external_source_without_link_is_reported(self):
        business = FakeBusiness([product('BQ002', assets=[], supply='external', links=[])])
        row = ProductGaps(SimpleNamespace(business=business)).summary()['items'][0]
        self.assertEqual(set(row['gap_keys']), {'no_asset', 'no_platform_id', 'no_source'})

    def test_old_supply_projection_does_not_create_a_false_todo(self):
        business = FakeBusiness([product('BQ035', supply='unconfirmed', assets=[{}],
                                         links=['Alibaba 10000046705043'])])
        self.assertEqual(ProductGaps(SimpleNamespace(business=business)).summary()['with_gaps'], 0)

    def test_hidden_hr_records_do_not_inflate_counts(self):
        business = FakeBusiness([product('HR022', supply='unconfirmed'),
                                 product('BQ003', assets=[{}], links=['Alibaba 1601825021825'])])
        summary = ProductGaps(SimpleNamespace(business=business)).summary()
        self.assertEqual(summary['total'], 1)
        self.assertEqual(summary['with_gaps'], 0)

    def test_missing_projection_does_not_prove_price_or_sizes_missing(self):
        business = FakeBusiness([product('BQ005', assets=[{}], links=['Alibaba 1601825021825'])])
        detail = ProductGaps(SimpleNamespace(business=business)).for_product('BQ005')
        self.assertNotIn('no_spec', detail['gap_keys'])
        self.assertNotIn('no_price', detail['gap_keys'])
        self.assertNotIn('blocking', detail)


class TodayTests(unittest.TestCase):
    def app(self, queue=None, candidates=(), messages=(), jobs=(), changes=(), inbox=()):
        queue = queue or (lambda **_: {'items': [], 'counts': {}})
        workspace = SimpleNamespace(queue=queue, discovery=lambda: {'candidates': list(candidates)},
                                    _saved_profile=lambda _: {})
        gmail = SimpleNamespace(status=lambda: {'state': 'connected'},
                                peek=lambda _: {'messages': list(messages)},
                                buyer_candidates=lambda: {'status': {'state': 'ready'}, 'items': list(inbox)})
        return SimpleNamespace(customer_workspace=workspace, gmail=gmail,
            product_changes=SimpleNamespace(list_changes=lambda: list(changes)),
            business=SimpleNamespace(alibaba=SimpleNamespace(status=lambda: {'stale': False}),
                                     website_status=lambda: {'stale': False}),
            agent_jobs=SimpleNamespace(list_jobs=lambda: list(jobs)))

    def test_known_prospect_reply_is_actionable_and_shows_real_sender(self):
        oid = 'prospect:candidate:1'
        app = self.app(candidates=[{'title': '买家', 'object_id': oid, 'gmail_reply_pending': True}],
            messages=[{'direction': 'inbound', 'from': 'person@gmail.com', 'sent_at': '2026-11-01T12:00:00Z'}],
            jobs=[{'object_id': oid, 'status': 'failed', 'title': '买家', 'updated_at': '2026-11-01T12:01:00Z'}])
        rows = Today(app).snapshot()['groups']['act']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kind'], 'customer_reply')
        self.assertIn('person@gmail.com', rows[0]['judgment'])
        self.assertIn('自动整理未完成', rows[0]['judgment'])
        self.assertEqual(rows[0]['action']['object_id'], oid)

    def test_new_mail_is_shown_and_historical_or_answered_is_not(self):
        app = self.app(inbox=[{'title': '新买家', 'is_new': True, 'answered': False},
                              {'title': '旧来信', 'is_new': False}, {'title': '已回复', 'is_new': True, 'answered': True}])
        rows = Today(app).snapshot()['groups']['act']
        self.assertEqual([row['title'] for row in rows], ['新买家来信：新买家'])

    def test_waiting_and_reply_are_separate(self):
        def queue(**_):
            return {'counts': {}, 'items': [
                {'object_id': 'customer:1', 'title': 'A', 'workflow': {'pending_party': 'customer'}},
                {'object_id': 'customer:2', 'title': 'B', 'workflow': {'gmail_reply_pending': True}}]}
        snap = Today(self.app(queue=queue)).snapshot()
        self.assertEqual(snap['groups']['act'][0]['kind'], 'customer_reply')
        self.assertEqual(snap['groups']['watch'][0]['kind'], 'customer_waiting')

    def test_history_only_returns_to_todos_when_there_is_a_new_reply(self):
        def queue(bucket, **_):
            return {'counts': {}, 'items': [] if bucket == 'active' else [
                {'object_id': 'customer:old', 'title': '旧客户', 'workflow': {}},
                {'object_id': 'customer:reply', 'title': '有来信的客户', 'workflow': {'gmail_reply_pending': True}}]}
        rows = Today(self.app(queue=queue)).snapshot()['groups']['act']
        self.assertEqual([row['object_id'] for row in rows], ['customer:reply'])

    def test_old_failed_job_is_not_shown_after_later_success(self):
        app = self.app(jobs=[{'id': '1', 'object_id': 'product:1', 'status': 'failed', 'updated_at': '2026-11-01T01:00:00Z'},
                             {'id': '2', 'object_id': 'product:1', 'status': 'completed', 'updated_at': '2026-11-01T02:00:00Z'}])
        self.assertFalse(any(row['kind'] == 'agent_job' for row in Today(app).snapshot()['groups']['act']))

    def test_new_plans_or_groups_do_not_hide_real_failed_work(self):
        app = self.app(jobs=[
            {'id':'failed','object_id':'product:1','status':'failed','updated_at':'2026-11-01T01:00:00Z'},
            {'id':'planned','object_id':'product:1','status':'planned','updated_at':'2026-11-01T02:00:00Z'},
            {'id':'group','object_id':'product:1','task_kind':'group','status':'planned','updated_at':'2026-11-01T03:00:00Z'}])
        self.assertTrue(any(row['kind']=='agent_job' and row['object_id']=='product:1'
                            for row in Today(app).snapshot()['groups']['act']))

    def test_customer_progress_supersedes_older_unfinished_work(self):
        def queue(**_):
            return {'counts': {}, 'items': [{'object_id': 'customer:1', 'title': '买家',
                    'workflow': {'pending_party': 'customer', 'updated_at': '2026-11-01T03:00:00Z'}}]}
        app = self.app(queue=queue, jobs=[{'object_id': 'customer:1', 'status': 'needs_input',
                                           'updated_at': '2026-11-01T02:00:00Z'}])
        snap = Today(app).snapshot()
        self.assertEqual(snap['groups']['act'], [])
        self.assertEqual(snap['groups']['watch'][0]['kind'], 'customer_waiting')

    def test_test_draft_does_not_become_a_todo(self):
        app = self.app(changes=[{'id': 'c1', 'state': 'prepared', 'internalTest': True}])
        snap = Today(app).snapshot()
        self.assertFalse(any(snap['groups'].values()))

    def test_connection_error_is_reported(self):
        app = self.app()
        def fail(): raise RuntimeError('网站不可读')
        app.business.website_status = fail
        snap = Today(app).snapshot()
        self.assertEqual(snap['sources']['website']['state'], 'unavailable')

    def test_disconnected_gmail_is_surfaced(self):
        app = self.app()
        app.gmail.status = lambda: {'state': 'not_connected'}
        self.assertTrue(any(row['kind'] == 'gmail_link' for row in Today(app).snapshot()['groups']['act']))

    def test_customer_mail_error_does_not_hide_a_successful_buyer_scan(self):
        app = self.app(inbox=[{'id':'synthetic-mail', 'title':'新买家', 'is_new':True, 'answered':False}])
        app.gmail.status = lambda: {'state':'error', 'error':'客户邮件读取失败'}
        snapshot = Today(app).snapshot()
        self.assertEqual(snapshot['sources']['gmail']['state'], 'error')
        self.assertEqual(snapshot['sources']['buyer_mail']['state'], 'ready')
        self.assertEqual({row['kind'] for row in snapshot['groups']['act']}, {'gmail_link', 'buyer_mail'})
        app.gmail.buyer_candidates = lambda: {'status': {'state':'error'}, 'items': [
            {'id':'stale', 'title':'旧扫描', 'is_new':True, 'answered':False}]}
        snapshot = Today(app).snapshot()
        self.assertFalse(any(row['kind'] == 'buyer_mail' for row in snapshot['groups']['act']))

    def test_catalog_failure_and_actual_differences_are_actionable(self):
        app=self.app()
        app.catalog_monitor=SimpleNamespace(status=lambda:{'state':'error','stale':True,'last_attempt_at':'2026-11-10T00:00:00Z'})
        failed=Today(app).snapshot()
        self.assertEqual(failed['sources']['alibaba_catalog']['state'],'error')
        self.assertTrue(any(item['kind']=='catalog_status' and item['severity']=='high' for item in failed['groups']['act']))
        app.catalog_monitor.status=lambda:{'state':'ready','stale':False,'review_required':1,
                                           'comparison':{'different':[{'id':'101'}]},'changes':None}
        item=next(item for item in Today(app).snapshot()['groups']['act'] if item['kind']=='catalog_status')
        self.assertIn('1 条审核状态需核对',item['judgment'])
        self.assertIn('1 条与本地记录不同',item['judgment'])


if __name__ == '__main__': unittest.main()
