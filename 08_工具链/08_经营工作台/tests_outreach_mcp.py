"""Object-scoped email preparation tools never send and honor versions."""
import unittest
from pathlib import Path

from codex_backend import CodexBackend
from desk_mcp import DeskTools, dispatch
from tests_gmail_drafts import DraftTests


class OutreachMcpTests(unittest.TestCase):
    def setUp(self):
        self.fixture=DraftTests('test_default_reply_address_thread_and_local_draft')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        app=self.fixture.service.app
        app.business.app=app
        app.gmail_drafts=self.fixture.service
        self.tools=DeskTools(app.business,app.root,self.fixture.oid,draft_only=True)
        self.readonly=DeskTools(app.business,app.root,self.fixture.oid,read_only=True)

    def test_draft_only_tools_save_actual_draft_and_never_send(self):
        names={x['name'] for x in dispatch(self.tools,{'id':1,'method':'tools/list'})['result']['tools']}
        self.assertTrue({'get_customer_email_draft','prepare_customer_email_draft',
                         'save_customer_email_draft','add_customer_email_attachment'}<=names)
        self.assertNotIn('save_customer_profile',names)
        self.assertFalse(any('send' in name for name in names))
        self.assertIsNone(self.tools.call('get_customer_email_draft',{})['draft'])
        draft=self.tools.call('prepare_customer_email_draft',{})
        saved=self.tools.call('save_customer_email_draft',{'version':draft['version'],
            'fields':{'subject':'Personalized fixture','body_en':'Fixture English','body_zh':'测试中文'}})
        with self.assertRaises(ValueError):
            self.tools.call('save_customer_email_draft',{'version':draft['version'],'fields':{'body_en':'stale'}})
        attached=self.tools.call('add_customer_email_attachment',{'version':saved['version'],'resource_id':'resource-1'})
        self.assertEqual(self.tools.call('get_customer_email_draft',{})['draft']['version'],attached['version'])
        self.assertEqual(attached['body_en'],'Fixture English')
        self.assertEqual(len(attached['attachments']),1)
        self.assertEqual(self.fixture.calls,[])
        with self.assertRaises(ValueError):self.tools.call('save_customer_profile',{})
        with self.assertRaises(ValueError):self.tools.call('prepare_customer_email_draft',{'object_id':'other'})

    def test_readonly_cannot_create_or_edit_draft(self):
        names={x['name'] for x in dispatch(self.readonly,{'id':1,'method':'tools/list'})['result']['tools']}
        self.assertIn('get_customer_email_draft',names)
        self.assertNotIn('prepare_customer_email_draft',names)
        with self.assertRaises(ValueError):self.readonly.call('prepare_customer_email_draft',{})
        with self.assertRaises(ValueError):self.readonly.call('save_customer_email_draft',{'version':'v','fields':{}})
        self.assertIsNone(self.fixture.service._saved(self.fixture.oid))

    def test_revise_backend_uses_scoped_tools_and_read_only_sandbox(self):
        command=CodexBackend.command('codex',Path('run'),Path('result'),root=Path('.'),state=Path('state'),
                                     object_id=self.fixture.oid,mode='outreach_draft')
        self.assertEqual(command[command.index('-s')+1],'read-only')
        self.assertNotIn('--search',command)
        mcp=next(value for value in command if value.startswith('mcp_servers.beiqiang_business.args='))
        self.assertIn('--draft-only',mcp)
        self.assertNotIn('--read-only',mcp)

    def test_research_scope_allows_profile_and_draft_but_not_send_or_other_writes(self):
        app=self.fixture.service.app
        tools=DeskTools(app.business,app.root,self.fixture.oid,research_only=True)
        names={x['name'] for x in dispatch(tools,{'id':1,'method':'tools/list'})['result']['tools']}
        self.assertTrue({'research_company','save_customer_profile','save_customer_email_draft','list_objects'}<=names)
        self.assertNotIn('save_customer_commercial',names)
        self.assertFalse(any('send' in name for name in names))
        with self.assertRaises(ValueError):tools.call('save_customer_commercial',{})
        with self.assertRaises(ValueError):tools.call('list_objects',{'kind':'customer'})
        command=CodexBackend.command('codex',Path('run'),Path('result'),root=Path('.'),state=Path('state'),
                                     object_id=self.fixture.oid,mode='outreach_research')
        self.assertEqual(command[command.index('-s')+1],'read-only')
        self.assertIn('--search',command)
        self.assertIn('--research-only',next(x for x in command if x.startswith('mcp_servers.beiqiang_business.args=')))


if __name__=='__main__':unittest.main()
