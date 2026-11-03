import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from desk_mcp import DeskTools, PRODUCTS, CHANNEL


class ContextTests(unittest.TestCase):
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
            self.assertNotIn('旧执行摘要', context['shared_sources'][1]['content'])
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
