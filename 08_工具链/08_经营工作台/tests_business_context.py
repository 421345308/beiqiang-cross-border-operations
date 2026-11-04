import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from desk_mcp import DeskTools, PRODUCTS, CHANNEL


class ContextTests(unittest.TestCase):
    def test_customer_commercial_product_links_keep_status_and_require_exact_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            commercial={'records':[{'id':'q1','kind':'quotation','status':'draft','products':'BQ009 / BQ001；BQ009-W1'},
                                   {'id':'q2','kind':'sample','status':'cancelled','products':'BQ009'}],
                        'next_action':'核对选款'}
            products=[{'id':'product:BQ009','title':'BQ009','source':'product-source','source_state':'OWNER_CONFIRMED'},
                      {'id':'product:BQ001','title':'BQ001','source':'product-source','source_state':'MISSING'}]
            business=SimpleNamespace(app=SimpleNamespace(customer_workspace=SimpleNamespace(profile=lambda oid:{},commercial=lambda oid:commercial)),
                get_object=lambda oid:{'id':oid,'kind':'customer','source':'object:'+oid},
                list_objects=lambda kind: products)
            refs=DeskTools(business,folder,'customer:one').call('get_business_context',{})['customer_product_references']
            self.assertEqual([r['match'] for r in refs],['exact','exact','unmatched','exact'])
            self.assertEqual(refs[0]['record_id'],'q1')
            self.assertEqual(refs[0]['status'],'draft')
            self.assertEqual(refs[1]['product']['source_state'],'MISSING')
            self.assertEqual(refs[2]['code'],'BQ009-W1')
            self.assertNotIn('product',refs[2])
            self.assertEqual(refs[3]['status'],'cancelled')

    def test_duplicate_product_ids_are_not_silently_merged(self):
        from business_context import _commercial_product_refs
        business=SimpleNamespace(list_objects=lambda kind:[{'id':'product:BQ009'},{'id':'product:BQ009'}])
        refs=_commercial_product_refs(business,{'records':[{'products':'BQ009'}]})
        self.assertEqual(refs[0]['match'],'ambiguous')
        self.assertNotIn('product',refs[0])

    def test_customer_product_refs_accept_confirmed_current_model_but_not_ambiguous_identity(self):
        from business_context import _commercial_product_refs
        products=[{'id':'product:HR049','current_model':'BQ1049','title':'BQ1049', 'aliases':['BQ1057']}]
        business=SimpleNamespace(list_objects=lambda kind:products)
        refs=_commercial_product_refs(business,{'records':[{'products':'BQ1049 / HR049 / BQ1057'}]})
        self.assertEqual([r['match'] for r in refs],['exact','exact','unmatched'])
        self.assertEqual(refs[0]['product']['id'],'product:HR049')
        products.append({'id':'product:BQ1049','current_model':'BQ1049'})
        self.assertEqual(_commercial_product_refs(business,{'records':[{'products':'BQ1049'}]})[0]['match'],'ambiguous')

    def test_current_sources_scope_and_fresh_owner_decisions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def write(path, value):
                target = root/path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value, encoding='utf8')
            write('AGENTS.md', '负责人最新决定：对外统一展示')
            write(PRODUCTS, json.dumps({'products': [{'id': 'shoe', 'current_model': 'new'}]}))
            write(CHANNEL, json.dumps({'listings': [
                {'id': 'one', 'product_id': 'shoe', 'current_platform_fields': {'status': 'approved', 'at': '2026-11-03'},
                 'pending_replacement': {'state': 'APPROVED_PUBLIC_QA_PENDING'}},
                {'id': 'other', 'product_id': 'private-other', 'current_platform_fields': {'title': 'UNRELATED'}}],
                'product_state': {'shoe': {'next_action': '公开验收'}}}))
            business = SimpleNamespace(get_object=lambda oid: {'id': oid, 'kind': 'product', 'source': PRODUCTS, 'content': '{}'})
            desk = DeskTools(business, root, 'product:shoe')
            context = desk.call('get_business_context', {})
            self.assertFalse(context['shared_sources'][1]['available'])
            channel = json.loads(next(r['content'] for r in context['current_sources'] if r['path'] == CHANNEL))
            self.assertEqual(channel['product_state']['next_action'], '公开验收')
            self.assertEqual(channel['listings'][0]['pending_replacement']['state'], 'APPROVED_PUBLIC_QA_PENDING')
            self.assertNotIn('UNRELATED', json.dumps(context))
            write('AGENTS.md', '新的负责人决定')
            self.assertEqual(desk.call('get_business_context', {})['shared_sources'][0]['content'], '新的负责人决定')
            write('00_总控台/当前状态.md', '# 当前状态\n## 长期要做成什么\n持续合作\n## 中期要形成的经营能力\n旧执行摘要')
            context = desk.call('get_business_context', {})
            self.assertIn('持续合作', context['shared_sources'][1]['content'])
            self.assertIn('旧执行摘要', context['shared_sources'][1]['content'])
            self.assertIn('可能滞后', context['shared_sources'][1]['projection'])
            self.assertIn('旧执行摘要', desk.read('00_总控台/当前状态.md')['content'])

    def test_customer_workflow_is_reused_and_creation_is_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = {'workflow': {'next_action': '回复样品方案'}, 'stale': True}
            commercial = {'records':[{'kind':'quotation','summary':'已准备报价'}], 'next_action':'回复样品方案'}
            business = SimpleNamespace(app=SimpleNamespace(customer_workspace=SimpleNamespace(profile=lambda oid: profile,commercial=lambda oid:commercial)),
                get_object=lambda oid: {'id': oid, 'kind': 'customer', 'source': 'object:'+oid})
            result = DeskTools(business, folder, 'customer:intake:one').call('get_business_context', {})
            self.assertEqual(result['customer_brief']['workflow'], profile['workflow'])
            self.assertTrue(result['customer_brief']['stale'])
            self.assertEqual(result['customer_commercial']['records'][0]['summary'],'已准备报价')
            business.get_object = lambda oid: {'kind': 'creation'}
            with self.assertRaises(ValueError):
                DeskTools(business, folder, 'creation:one').call('get_business_context', {})


if __name__ == '__main__':
    unittest.main()
