import base64
from email import policy
from email.parser import BytesParser
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gmail_drafts import GmailDrafts, SendRejected


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.addCleanup(self.db.close)
        self.obj = {'id':'prospect:candidate:one','kind':'prospect',
                    'content':json.dumps({'email':'buyer@example.test'}),'facts':[]}
        self.messages = [{'id':'16','thread_id':'32','direction':'inbound',
                          'sent_at':'2026-11-02T01:00:00+00:00','from':'Buyer <buyer@example.test>',
                          'reply_to':'Sales <sales@example.test>','subject':'Samples',
                          'rfc_message_id':'<buyer-1@example.test>','mail_kind':'conversation'}]
        self.calls, self.linked, self.updates, self.syncs = [], [], [], []
        self.profile = {'state':'preparing','allowed_transitions':[{'state':'waiting_customer'}]}
        self.mail = SimpleNamespace(status=lambda:{'account_email':'seller@example.test'},
            peek=lambda oid:{'messages':self.messages,'reply_pending':True},
            link_sent_address=lambda oid,address:self.linked.append((oid,address)),
            acknowledge=lambda oid:self.updates.append(('ack',oid)),
            customer=lambda oid,force:self.syncs.append((oid,force)) or {'status':{'state':'connected'}})
        workspace = SimpleNamespace(workflow=lambda oid:self.profile,
            save_workflow=lambda oid,body:self.updates.append(('workflow',body)),
            update_discovery=lambda oid,body:self.updates.append(('discovery',oid,body)))
        self.material = self.root/'catalog.pdf';self.material.write_bytes(b'%PDF test material')
        library = SimpleNamespace(list=lambda:[{'id':'resource-1','path':'catalog.pdf','title':'Product catalog'}],
                                  locate=lambda value:self.root/value)
        app = SimpleNamespace(root=self.root,state=self.root/'state',db=self.db,lock=threading.RLock(),
            business=SimpleNamespace(get_object=lambda oid:self.obj if oid==self.obj['id'] else {}),
            gmail=self.mail,customer_workspace=workspace,library=library)
        def sender(token,payload):
            self.calls.append((token,payload));return {'id':'abc123','threadId':'20'}
        self.service=GmailDrafts(app,token_provider=lambda account:'temporary-token',sender=sender,
            grant_reader=lambda account:{'refresh_token':'fixture','scopes':['https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/gmail.send']})
        self.oid=self.obj['id']

    def fill(self):
        draft=self.service.get(self.oid)
        return self.service.save(self.oid,draft['version'],{'body_en':'Hello buyer,\nHere are our shoes.',
                                                           'body_zh':'您好，这是我们的鞋子。'})

    def test_default_reply_address_thread_and_local_draft(self):
        draft=self.service.get(self.oid)
        self.assertEqual(draft['to'],'sales@example.test')
        self.assertEqual(draft['subject'],'Re: Samples')
        self.assertEqual(draft['reply_message_id'],'<buyer-1@example.test>')
        self.assertTrue(draft['can_send'])
        saved=self.fill()
        self.assertEqual(self.service.get(self.oid)['body_zh'],'您好，这是我们的鞋子。')
        self.assertEqual(saved['status'],'draft');self.assertEqual(self.calls,[])

    def test_send_grant_is_saved_only_for_the_connected_account(self):
        with patch('gmail_drafts.save_grant') as save:
            with self.assertRaisesRegex(ValueError,'当前连接'):
                self.service._save_grant('other@example.test',{},{} )
            save.assert_not_called()
            self.service._save_grant('seller@example.test',{'client_id':'fixture'},{'refresh_token':'fixture'})
            save.assert_called_once()

    def test_reviewed_send_preserves_thread_actual_attachments_and_syncs(self):
        draft=self.fill()
        draft=self.service.add_attachment(self.oid,draft['version'],filename='鞋子.jpg',data=base64.b64encode(b'photo-data').decode())
        draft=self.service.add_attachment(self.oid,draft['version'],resource_id='resource-1')
        for attachment in draft['attachments']:
            _,data=self.service.attachment(self.oid,attachment['id']);self.assertTrue(data)
        self.assertEqual(self.calls,[])
        result=self.service.send(self.oid,draft['version'])
        self.assertEqual(result['status'],'sent');self.assertEqual(len(self.calls),1)
        payload=self.calls[0][1];self.assertEqual(payload['threadId'],'20')
        raw=base64.urlsafe_b64decode(payload['raw']+'='*(-len(payload['raw'])%4))
        message=BytesParser(policy=policy.default).parsebytes(raw)
        self.assertEqual(message['To'],'sales@example.test');self.assertEqual(message['Subject'],'Re: Samples')
        self.assertEqual(message['In-Reply-To'],'<buyer-1@example.test>')
        self.assertNotIn('您好',message.get_body(preferencelist=('plain',)).get_content())
        files={p.get_filename():p.get_payload(decode=True) for p in message.iter_attachments()}
        self.assertEqual(files,{'鞋子.jpg':b'photo-data','catalog.pdf':b'%PDF test material'})
        self.assertEqual(self.linked,[(self.oid,'sales@example.test')]);self.assertEqual(self.syncs,[(self.oid,True)])
        self.assertTrue(any(row[0]=='workflow' and row[1]['state']=='waiting_customer' for row in self.updates))
        with self.assertRaises(ValueError):self.service.send(self.oid,draft['version'])
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.service.new(self.oid)['status'],'draft')

    def test_changed_attachment_must_be_selected_again_before_send(self):
        draft=self.fill();draft=self.service.add_attachment(self.oid,draft['version'],resource_id='resource-1')
        self.material.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'附件内容已改变'):self.service.send(self.oid,draft['version'])
        self.assertEqual(self.calls,[]);self.assertEqual(self.service.get(self.oid)['status'],'draft')

    def test_unknown_send_is_not_retried_and_can_be_reconciled(self):
        draft=self.fill()
        def timeout(token,payload):self.calls.append(payload);raise TimeoutError()
        self.service.sender=timeout
        unknown=self.service.send(self.oid,draft['version'])
        self.assertEqual(unknown['status'],'unknown');self.assertEqual(len(self.calls),1)
        with self.assertRaises(ValueError):self.service.send(self.oid,draft['version'])
        self.service.request=lambda url,token:{'messages':[{'id':'deadbeef','threadId':'20'}]}
        self.assertEqual(self.service.reconcile(self.oid)['status'],'sent')
        self.assertEqual(len(self.calls),1)

    def test_google_rejection_keeps_draft_for_correction(self):
        draft=self.fill()
        def rejected(token,payload):raise SendRejected('Google 未接受邮件')
        self.service.sender=rejected
        with self.assertRaisesRegex(SendRejected,'Google 未接受'):self.service.send(self.oid,draft['version'])
        self.assertEqual(self.service.get(self.oid)['status'],'draft')

    def test_stale_draft_cannot_be_sent(self):
        old=self.fill();new=self.service.save(self.oid,old['version'],{'body_en':'Revised'})
        with self.assertRaisesRegex(ValueError,'草稿已更新'):self.service.send(self.oid,old['version'])
        self.assertEqual(self.service.get(self.oid)['body_en'],'Revised');self.assertEqual(self.calls,[])

    def test_changing_subject_starts_a_new_conversation(self):
        draft=self.fill();draft=self.service.save(self.oid,draft['version'],{'subject':'Different topic'})
        self.service.send(self.oid,draft['version'])
        payload=self.calls[0][1];self.assertNotIn('threadId',payload)
        raw=base64.urlsafe_b64decode(payload['raw']+'='*(-len(payload['raw'])%4))
        self.assertNotIn('In-Reply-To',BytesParser(policy=policy.default).parsebytes(raw))

    def test_unknown_can_be_restored_only_after_explicit_confirmation(self):
        draft=self.fill();self.service.sender=lambda token,payload:(_ for _ in ()).throw(TimeoutError())
        unknown=self.service.send(self.oid,draft['version'])
        with self.assertRaises(ValueError):self.service.resume_unsent(self.oid,False)
        restored=self.service.resume_unsent(self.oid,True)
        self.assertEqual(restored['status'],'draft');self.assertNotEqual(restored['version'],unknown['version'])

    def test_process_interruption_marks_inflight_result_unknown(self):
        draft=self.fill();draft['status']='sending';self.service._put(draft)
        reopened=GmailDrafts(self.service.app,grant_reader=lambda account:{})
        self.assertEqual(reopened.get(self.oid)['status'],'unknown')


if __name__ == '__main__':unittest.main()
