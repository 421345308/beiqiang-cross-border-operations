import json
import copy
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from outreach_checks import OutreachChecks
from customer_batches import CustomerBatches
from workspaces import WorkspaceConflict
from unittest.mock import patch

class CRM:
    def __init__(self):
        self.result = dict(status='已读取', sha256='fixture-hash', coverage='fixture only', match_status='已匹配', stop_state='未发现明确停止', matches=[])
    def check(self, candidate):
        self.candidate=candidate
        return self.result
class Box:
    def __init__(self):
        self.calls=[]
        self.value=dict(status=dict(state='ready',account_email='sales@factory.test',last_success_at='2026-11-06',history_limited=False,shared_observation={'state':'complete'}),messages=[])
    def context(self, addresses, *, force=False):
        self.calls.append((addresses,force))
        return self.value
class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.objects={'a':dict(id='a',kind='customer',title='Buyer',content=json.dumps(dict(email='buyer@buyer.test',website='https://buyer.test',website_verification='verified')))}
        self.box=Box();self.crm=CRM()
        self.app=NS(business=NS(get_object=lambda oid:self.objects[oid]),gmail=NS(_mailbox=self.box,peek=lambda oid:self.box.value))
        self.service=OutreachChecks(self.app,crm_reader=self.crm)
        self.draft=dict(status='draft',to='buyer@buyer.test',version=4)
    def inspect(self,**kw):
        return self.service.inspect('a',self.draft,**dict(dict(refresh=True),**kw))
    def inbound(self,body,**kw):
        self.box.value['messages']=[dict(dict(id='m1',direction='inbound',sent_at='2026-11-06',**{'from':'buyer@buyer.test','to':'sales@factory.test','body':body}),**kw)]
    def codes(self,result):return {r['code'] for r in result['reasons']}
    def test_direct_read_only_refresh(self):
        self.app.gmail.customer=lambda *a,**k:self.fail('dispatch forbidden')
        result=self.inspect()
        self.assertEqual(result['status'],'unknown');self.assertIn('bounce_coverage_unknown',self.codes(result));self.assertFalse(result['can_auto_send'])
        self.assertEqual(self.box.calls,[(['buyer@buyer.test'],True)])
        self.assertEqual(result['crm']['sha256'],'fixture-hash')
    def test_default_cache_never_fetches(self):
        result=self.service.inspect('a',self.draft)
        self.assertEqual(result['status'],'unknown');self.assertEqual(self.box.calls,[])
    def test_optout_rejection_bounce(self):
        for body in ('Please unsubscribe us.','We are not interested.','Delivery failed: user unknown'):
            self.inbound(body);result=self.inspect()
            self.assertEqual(result['status'],'blocked');self.assertNotIn(body,json.dumps(result))
    def test_quotes_and_our_signature(self):
        self.inbound('Thanks.\n> Please unsubscribe us.\nOn Monday Buyer wrote:\nNot interested')
        self.box.value['messages'].append(dict(direction='outbound',**{'from':'sales@factory.test','to':'buyer@buyer.test','body':'Reply unsubscribe to opt out'}))
        result=self.inspect();self.assertNotIn('mail_stop',self.codes(result));self.assertIn('previously_contacted',self.codes(result))
    def test_cross_customer_does_not_suppress(self):
        self.inbound('unsubscribe',**{'from':'other@else.test'})
        result=self.inspect();self.assertNotIn('mail_stop',self.codes(result));self.assertEqual(result['status'],'unknown')
    def test_truncated_history_body_and_failed_connection(self):
        self.inbound('hello',body_truncated=True)
        self.assertIn('mail_body_incomplete',self.codes(self.inspect()))
        for key in ('history_limited','thread_lookup_incomplete'):
            self.box.value['status'][key]=True;self.assertIn('mail_history_incomplete',self.codes(self.inspect()))
        self.box.value['status']['state']='error';self.assertIn('mail_unavailable',self.codes(self.inspect()))
    def test_local_and_crm_stop(self):
        for state in ('停止联系','EMAIL_INVALID','do_not_contact'):
            self.objects['a']['content']=json.dumps(dict(email='buyer@buyer.test',review=dict(state=state)))
            self.assertEqual(self.inspect()['status'],'blocked')
        self.crm.result['stop_state']='明确停止';self.assertIn('crm_suppressed',self.codes(self.inspect()))
    def test_negative_crm_stop_mark_is_not_a_stop(self):
        self.crm.result['matches']=[dict(stop_raw='未退订',stop_state='未发现明确停止',history=[])]
        self.assertNotIn('crm_history_suppressed',self.codes(self.inspect()))
    def test_negative_crm_history_checks_do_not_become_stop_records(self):
        for field in ('status','outcome','notes'):
            for text in ('未退订','未停止联系','未拒绝联系','无退信','未发现退信',
                         'not unsubscribed','no opt-out','no opt out'):
                with self.subTest(field=field,text=text):
                    self.crm.result['matches']=[dict(history=[{field:text}],latest_touch={'date':'2026-11-06'})]
                    result=self.inspect()
                    self.assertNotIn('crm_history_suppressed',self.codes(result))
                    # Correcting a false stop must not grant first-contact permission.
                    self.assertIn('previously_contacted',self.codes(result))
                    self.assertFalse(result['can_auto_send'])
    def test_negative_crm_checks_preserve_real_stops_in_other_fields_and_rows(self):
        for history in ([{'status':'未发现退信','notes':'Please unsubscribe us'}],
                        [{'notes':'未退订；之后收到退信'}],
                        [{'outcome':'not unsubscribed'}, {'notes':'not interested'}],
                        [{'status':'无退信','outcome':'EMAIL_INVALID'}]):
            with self.subTest(history=history):
                self.crm.result['matches']=[dict(history=history)]
                result=self.inspect()
                self.assertIn('crm_history_suppressed',self.codes(result))
                self.assertEqual(result['status'],'blocked')
    def test_negative_crm_check_does_not_hide_buyer_optout(self):
        self.crm.result['matches']=[dict(history=[{'notes':'未退订；未发现退信'}])]
        self.inbound('Please unsubscribe us.')
        result=self.inspect()
        self.assertNotIn('crm_history_suppressed',self.codes(result))
        self.assertIn('mail_stop',self.codes(result))
        self.assertEqual(result['status'],'blocked')
    def test_crm_unknown(self):
        self.crm.result=dict(status='读取失败',matches=[])
        result=self.inspect();self.assertEqual(result['status'],'unknown');self.assertIsNone(result['crm']['sha256'])
    def test_exact_duplicates_only(self):
        self.objects['b']=dict(id='b',kind='customer',title='Other',content=json.dumps(dict(email='buyer@buyer.test')))
        self.objects['c']=dict(id='c',kind='customer',title='Buyer',content=json.dumps(dict(email='different@other.test')))
        self.assertEqual(self.inspect(batch_ids=['a','b','c'])['duplicates'],[dict(object_id='b',methods=['email_exact'])])
        self.objects['b']['content']=json.dumps(dict(email='colleague@buyer.test',website='https://buyer.test',website_verification='verified'))
        result=self.inspect(batch_ids=['b']);self.assertEqual(result['duplicates'][0]['methods'],['verified_domain_exact']);self.assertNotIn('colleague@buyer.test',json.dumps(result))
    def test_canonical_crm_exact_match_hash_and_stop(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from zipfile import ZipFile
        from xml.sax.saxutils import escape
        from outreach_checks import _crm_module
        def sheet(rows):
            cells=[]
            for n,row in enumerate(rows,1):
                cells.append('<row r="%s">'%n+''.join('<c r="%s%s" t="inlineStr"><is><t>%s</t></is></c>'%(chr(65+i),n,escape(str(v))) for i,v in enumerate(row))+'</row>')
            return '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(cells)+'</sheetData></worksheet>'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.xlsx'
            with ZipFile(path,'w') as z:
                z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Account Pool" r:id="a"/><sheet name="Outreach Log" r:id="b"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="a" Target="worksheets/a.xml"/><Relationship Id="b" Target="worksheets/b.xml"/></Relationships>')
                z.writestr('xl/worksheets/a.xml',sheet([['Lead ID','Website / identity source','Business email/form','CRM stage','Last touch','Stop / opt-out'],['L1','https://buyer.test','buyer@buyer.test','EMAIL_INVALID','','yes']]))
                z.writestr('xl/worksheets/b.xml',sheet([['Lead ID','Actual date','Status','Outcome']]))
            self.service._reader=_crm_module().CRMReader(path)
            result=self.inspect()
            self.assertEqual(result['status'],'blocked')
            self.assertEqual(result['crm']['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(result['crm']['match_count'],1)
            self.assertIn('crm_suppressed',self.codes(result))

    def test_unknown_recipient_and_draft(self):
        self.draft.update(status='unknown',to='other@else.test')
        self.assertIn('recipient_identity_unknown',self.codes(self.inspect()))

    def profile_contact(self, address, *, text=None, url='https://source.test/contact', observed='2026-11-06'):
        return {'cleaned':{'email':address},'provenance':{'evidence':[
            {'text':address if text is None else text,'url':url,'observed_at':observed}]}}

    def test_shared_source_backed_profile_address_blocks_both_directions(self):
        # Neither source object originally had an email. Both were researched
        # later; adding a second customer must not bypass exact-address dedupe.
        for oid in ('a','b'):
            self.objects[oid]=dict(id=oid,kind='customer',content=json.dumps({'website':'https://'+oid+'.test'}))
        profiles={oid:self.profile_contact('shared@buyer.test') for oid in ('a','b')}
        self.app.customer_workspace=NS(profile=lambda oid:profiles[oid])
        draft={**self.draft,'to':'shared@buyer.test','account':'sales@factory.test'}
        for oid,other in [('a','b'),('b','a')]:
            with self.subTest(oid=oid):
                result=self.service.inspect(oid,draft,batch_ids=['a','b'],refresh=True)
                self.assertEqual(result['status'],'blocked')
                self.assertFalse(result['can_auto_send'])
                self.assertIn('batch_duplicate',self.codes(result))
                self.assertEqual(result['duplicates'],[{'object_id':other,'methods':['email_exact']}])
                self.assertNotIn('recipient_identity_unknown',self.codes(result))

    def test_original_contact_matches_other_objects_researched_profile_contact(self):
        self.objects['b']=dict(id='b',kind='customer',content='{}')
        profiles={'a':{},'b':self.profile_contact('BUYER@BUYER.TEST')}
        self.app.customer_workspace=NS(profile=lambda oid:profiles[oid])
        result=self.inspect(batch_ids=['a','b'])
        self.assertEqual(result['duplicates'],[{'object_id':'b','methods':['email_exact']}])
        self.assertFalse(result['can_auto_send'])

    def test_profile_address_requires_exact_dated_public_evidence(self):
        self.objects['b']=dict(id='b',kind='customer',content='{}')
        for options in ({'observed':''},{'url':''},{'text':'buyer@buyer.test.other.test'},
                        {'text':'differentbuyer@buyer.test'}):
            with self.subTest(options=options):
                profiles={'a':{},'b':self.profile_contact('buyer@buyer.test',**options)}
                self.app.customer_workspace=NS(profile=lambda oid:profiles[oid])
                self.assertEqual(self.inspect(batch_ids=['a','b'])['duplicates'],[])

    def test_profile_contact_with_adjacent_chinese_punctuation_is_exact(self):
        self.objects['a']['content']='{}'
        self.app.customer_workspace=NS(profile=lambda oid:self.profile_contact('buyer@example.test',text='官网公开buyer@example.test；供客户联系使用。'))
        self.assertEqual(self.service.identity_emails(self.objects['a']),{'buyer@example.test'})
class ManualCRMReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.raw=b'Synthetic catalogue'
        self.objects={'customer:a':{'id':'customer:a','kind':'customer','title':'Synthetic buyer','content':json.dumps({
            'email':'buyer@example.test','website':'https://buyer.example.test'})}}
        self.profile={'revision':'p1','source_hash':'source1','provenance':{'evidence':[{
            'url':'https://buyer.example.test/contact','observed_at':'2026-11-06','text':'buyer@example.test'}]}}
        self.draft={'object_id':'customer:a','version':'d1','status':'draft','account':'sender@example.test',
                    'to':'buyer@example.test','subject':'Synthetic','body_en':'English','body_zh':'Chinese',
                    'attachments':[{'id':'attachment','sha256':hashlib.sha256(self.raw).hexdigest()}]}
        self.crm=CRM()
        self.crm.result.update(match_status='未匹配',stop_state='未知')
        self.box=Box()
        self.box.value['status'].update(account_email='sender@example.test',thread_lookup_incomplete=False,
                                       shared_observation={'state':'complete'})
        self.evidence={
            'aliases':{'checked':True,'terms':['Synthetic Brand','Synthetic Trading Ltd'],
                'locations':['CRM Account Pool company and identity columns'],
                'findings':'Searched both registered names; no matching company or brand found.'},
            'independent_sends':{'checked':True,'locations':['Independent sent-mail archive and manual outreach log'],
                'findings':'Exact buyer@example.test address and both company names had no independent sends.'},
            'stop_records':{'checked':True,'locations':['CRM stop list and historical refusal register'],
                'findings':'Checked the precise email and company aliases; no refusal or stop entry found.'}}
        self.app=self.make_app()
        self.batch=self.app.customer_batches.create({'title':'Synthetic batch','object_ids':['customer:a']})

    def make_app(self):
        directory=self.root/'.local';directory.mkdir(exist_ok=True)
        db=sqlite3.connect(directory/'test.sqlite3',check_same_thread=False,timeout=5)
        self.addCleanup(db.close)
        app=NS(db=db,lock=threading.RLock(),root=self.root,
            business=NS(get_object=lambda oid:copy.deepcopy(self.objects[oid])),
            customer_workspace=NS(profile=lambda oid:copy.deepcopy(self.profile)),
            gmail_drafts=NS(_saved=lambda oid:copy.deepcopy(self.draft),_attachment_bytes=lambda a:self.raw),
            gmail=NS(_mailbox=self.box,peek=lambda oid:copy.deepcopy(self.box.value)))
        app.outreach_checks=OutreachChecks(app,crm_reader=self.crm)
        app.outreach_checks._module=NS(domains=lambda website:set())
        app.customer_batches=CustomerBatches(app)
        return app

    def live(self,app=None):
        return (app or self.app).customer_batches.get(self.batch['id'])['items'][0]

    def record(self,app=None,item_revision=None,evidence=None,confirmed=True):
        app=app or self.app
        revision=item_revision or self.live(app)['item_revision']
        return app.outreach_checks.record_crm_review(self.batch['id'],'customer:a',revision,
            evidence or self.evidence,confirmed)

    def inspect(self,app=None,refresh=True):
        with patch('gmail_bounce_check.check_bounces',return_value={'status':'clear','coverage':{'complete':True}}):
            return (app or self.app).outreach_checks.inspect('customer:a',self.draft,refresh=refresh)

    def test_scoped_review_removes_only_crm_gate_and_keeps_original_unknown(self):
        self.assertIn('crm_scope_unknown',{r['code'] for r in self.inspect()['reasons']})
        saved=self.record()
        self.assertTrue(saved['applied'])
        result=self.inspect()
        self.assertEqual(result['status'],'clear')
        self.assertEqual(result['crm']['stop_state'],'未知')
        self.assertTrue(result['crm_manual_review']['applied'])
        self.assertEqual(self.inspect(refresh=False)['status'],'unknown')
        self.assertTrue(self.inspect(self.make_app())['crm_manual_review']['applied'])

    def test_source_profile_crm_sha_account_and_recipient_changes_invalidate(self):
        self.record()
        mutations=[lambda:self.profile.update(source_hash='source2'),
                   lambda:self.profile.update(cleaned={'company':'Different legal entity'}),
                   lambda:self.profile['provenance']['evidence'][0].update(url='https://different.example.test/contact'),
                   lambda:self.crm.result.update(sha256='new-sha'),
                   lambda:self.draft.update(account='other@example.test'),lambda:self.draft.update(to='other@example.test'),
                   lambda:self.objects['customer:a'].update(title='Other legal entity')]
        for mutation in mutations:
            before=(copy.deepcopy(self.profile),copy.deepcopy(self.crm.result),copy.deepcopy(self.draft),copy.deepcopy(self.objects))
            mutation()
            with self.subTest(mutation=mutation):
                result=self.inspect()
                self.assertFalse(result['crm_manual_review']['applied'])
                self.assertIn('crm_scope_unknown',{r['code'] for r in result['reasons']})
            self.profile,self.crm.result,self.draft,self.objects=before

    def test_mailbox_only_profile_revision_change_preserves_manual_crm_review(self):
        saved=self.record()
        self.profile['revision']='new-mailbox-watermark-with-same-customer-source'
        result=self.inspect()
        self.assertTrue(result['crm_manual_review']['applied'])
        self.assertEqual(result['crm_manual_review']['review_id'],saved['review_id'])
        self.assertNotIn('crm_scope_unknown',{r['code'] for r in result['reasons']})
        self.assertEqual(result['crm']['stop_state'],'未知')

    def test_stale_item_revision_cannot_record_after_crm_or_draft_change(self):
        old=self.live()['item_revision']
        self.crm.result['sha256']='new-crm'
        with self.assertRaises(WorkspaceConflict):self.record(item_revision=old)
        old=self.live()['item_revision']
        self.draft.update(to='other@example.test')
        with self.assertRaises(WorkspaceConflict):self.record(item_revision=old)

    def test_generic_evidence_and_missing_confirmation_rejected(self):
        for key in self.evidence:
            evidence=copy.deepcopy(self.evidence)
            evidence[key]['findings']='已核对，无问题'
            with self.subTest(key=key),self.assertRaises(ValueError):self.record(evidence=evidence)
        for value in (False,1,'true',None):
            with self.subTest(confirmed=value),self.assertRaises(ValueError):self.record(confirmed=value)
        evidence=copy.deepcopy(self.evidence);evidence['aliases']['terms']=[]
        with self.assertRaises(ValueError):self.record(evidence=evidence)

    def test_crm_failure_conflict_suppression_and_missing_coverage_not_eligible(self):
        for patchvalue in ({'status':'读取失败'},{'match_status':'冲突待核'},{'stop_state':'明确停止'},
                           {'local_stop':True},{'sha256':''},{'coverage':''},{'matches':[{'stop_raw':'退订'}]}):
            before=copy.deepcopy(self.crm.result);self.crm.result.update(patchvalue)
            with self.subTest(patchvalue=patchvalue),self.assertRaises(ValueError):self.record()
            self.crm.result=before

    def test_manual_review_does_not_waive_mail_bounce_unknown_history_or_sent_state(self):
        self.record()
        for key,value in (('history_limited',True),('thread_lookup_incomplete',True),
                          ('state','error'),('shared_observation',{'state':'unknown'})):
            before=copy.deepcopy(self.box.value['status']);self.box.value['status'][key]=value
            with self.subTest(key=key):self.assertNotEqual(self.inspect()['status'],'clear')
            self.box.value['status']=before
        self.draft['status']='unknown'
        self.assertIn('draft_state_unknown',{r['code'] for r in self.inspect()['reasons']})
        self.draft['status']='draft'
        self.box.value['messages']=[{'direction':'outbound','from':'sender@example.test','to':'buyer@example.test','body':'Prior mail'}]
        self.assertIn('previously_contacted',{r['code'] for r in self.inspect()['reasons']})
        self.box.value['messages']=[]
        for status in ('unknown','blocked'):
            with patch('gmail_bounce_check.check_bounces',return_value={'status':status}):
                result=self.app.outreach_checks.inspect('customer:a',self.draft,refresh=True)
                self.assertNotEqual(result['status'],'clear')

    def test_two_connections_cannot_overwrite_same_snapshot_or_existing_binding(self):
        other=self.make_app();revision=self.live()['item_revision']
        self.record(item_revision=revision)
        with self.assertRaises(WorkspaceConflict):self.record(other,item_revision=revision)
        with self.assertRaises(WorkspaceConflict):self.record(other)
        stored=json.loads(self.app.db.execute('SELECT data FROM outreach_crm_reviews').fetchone()[0])
        self.assertEqual(stored['evidence'],self.evidence)
        self.assertNotIn('English',json.dumps(stored))

    def test_complete_shared_observation_is_required_and_cannot_be_waived(self):
        self.record()
        self.box.value['status'].pop('shared_observation')
        result=self.inspect()
        self.assertTrue(result['crm_manual_review']['applied'])
        self.assertIn('mail_shared_observation_unknown',{r['code'] for r in result['reasons']})
        self.assertFalse(result['can_auto_send'])

    def test_simultaneous_connections_only_one_can_record_same_review(self):
        other=self.make_app()
        revision=self.live()['item_revision']
        barrier=threading.Barrier(2)
        results=[]
        def record(app):
            barrier.wait(timeout=5)
            try:
                self.record(app,item_revision=revision)
                results.append('saved')
            except WorkspaceConflict:
                results.append('conflict')
        threads=[threading.Thread(target=record,args=(app,)) for app in (self.app,other)]
        for t in threads:t.start()
        for t in threads:t.join(10)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(sorted(results),['conflict','saved'])

    def test_workbook_change_during_confirmation_does_not_acknowledge_new_sha(self):
        revision=self.live()['item_revision']
        check=self.crm.check
        calls=[]
        def changing(candidate):
            calls.append(candidate)
            if len(calls)==2:self.crm.result['sha256']='changed-during-confirmation'
            return check(candidate)
        with patch.object(self.crm,'check',side_effect=changing):
            with self.assertRaises(WorkspaceConflict):self.record(item_revision=revision)
        self.assertEqual(self.app.db.execute('SELECT COUNT(*) FROM outreach_crm_reviews').fetchone()[0],0)


if __name__=='__main__':unittest.main()
