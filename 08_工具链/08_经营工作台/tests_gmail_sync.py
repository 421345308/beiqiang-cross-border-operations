import copy,json,sqlite3,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from gmail_sync import GmailService,customer_emails
ACCOUNT='me@example.com';BUYER='buyer@example.com';SECOND='second@example.com'
def message(mid='new',direction='inbound',at='2026-11-01T02:00:00Z',buyer=BUYER):
    return dict(id=mid,direction=direction,sent_at=at,**{'from':buyer if direction=='inbound' else ACCOUNT,'to':ACCOUNT if direction=='inbound' else buyer})
class Business:
    def __init__(self):self.objects={'customer:1':dict(id='customer:1',kind='customer',content=json.dumps({'email':BUYER}))}
    def get_object(self,oid):return copy.deepcopy(self.objects[oid])
    def list_objects(self):return list(self.objects.values())
class Mailbox:
    def __init__(self):self.messages=[];self.calls=[];self.state='ready'
    def context(self,emails,force=False):
        self.calls.append(list(emails));return dict(status=dict(state=self.state,error='Disconnected' if self.state=='error' else None,last_success_at='2026-11-01T03:00:00Z'),messages=copy.deepcopy(self.messages),reply_pending=True,next_action='')
class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=sqlite3.connect(Path(self.temp.name)/'runs.sqlite3',check_same_thread=False);self.flow=dict(state='waiting_customer',bucket='active',waiting_since='2026-11-01T01:00:00Z')
        self.app=SimpleNamespace(state=Path(self.temp.name),db=self.db,lock=threading.RLock(),business=Business(),customer_workspace=SimpleNamespace(_saved_profile=lambda oid:{'workflow':self.flow}))
        self.mail=Mailbox();self.events=[];self.saved=[];self.tested=[];self.now=1000
    def tearDown(self):self.db.close();self.temp.cleanup()
    def service(self):return GmailService(self.app,mailbox_factory=lambda _:self.mail,credential_checker=lambda _:True,credential_tester=lambda e,p:self.tested.append(e),credential_saver=lambda e,p:self.saved.append(e),on_new_reply=lambda *args:self.events.append(args),clock=lambda:self.now)
    def connect(self):s=self.service();s.connect(ACCOUNT,'secret');return s
    def test_config(self):
        s=self.connect();data=json.loads((self.app.state/'gmail.json').read_text());self.assertEqual(set(data),{'email','connected_at'});self.assertNotIn('secret',str(data));self.assertEqual(self.saved,[ACCOUNT]);self.assertEqual(s.status()['state'],'connected')
    def test_rejected_not_saved(self):
        s=self.service();s.credential_tester=lambda *args:(_ for _ in ()).throw(ValueError('bad'))
        with self.assertRaises(ValueError):s.connect(ACCOUNT,'secret')
        self.assertEqual(self.saved,[]);self.assertFalse((self.app.state/'gmail.json').exists())
    def test_no_config_no_network(self):
        s=self.service();s.scan_once();s.peek('customer:1');s.customer('customer:1');self.assertEqual(self.mail.calls,[]);self.assertEqual(s.status()['state'],'not_connected')
    def test_explicit_emails_only(self):
        obj=dict(kind='customer',content=json.dumps(dict(email=BUYER,requirements='wrong@example.com')),facts=[dict(label='原记录来源',value='wrong@example.com'),dict(label='邮箱',value=SECOND)])
        self.assertEqual(customer_emails(obj),[BUYER,SECOND])
    def test_existing_candidate_contact_is_discovered(self):
        obj=dict(kind='prospect',content=json.dumps({'source_record':{'contacts':[{'kind':'email','value':BUYER}]}}))
        self.assertEqual(customer_emails(obj),[BUYER])
    def test_strict_matching(self):
        s=self.connect();self.mail.messages=[message(buyer='otherbuyer@example.com')];r=s.customer('customer:1');self.assertEqual(r['messages'],[]);self.assertFalse(r['reply_pending']);self.assertEqual(self.events,[])
    def test_other_mailbox_rejected(self):
        s=self.connect();m=message();m['to']='other@example.com';self.mail.messages=[m];self.assertEqual(s.customer('customer:1')['messages'],[])
    def test_bcc_explicit_match(self):
        s=self.connect();m=message(direction='outbound');m['to']='undisclosed:;';m['customer_emails']=[BUYER];self.mail.messages=[m];self.assertEqual(len(s.customer('customer:1')['messages']),1)
    def test_new_once_restart(self):
        s=self.connect();self.mail.messages=[message()];s.customer('customer:1');s.customer('customer:1');self.assertEqual(len(self.events),1);self.service().customer('customer:1');self.assertEqual(len(self.events),1)
    def test_acknowledged_mail_stays_clear_until_new_reply(self):
        s=self.connect();self.mail.messages=[message()];self.assertTrue(s.customer('customer:1')['reply_pending'])
        self.assertFalse(s.acknowledge('customer:1')['reply_pending']);self.assertFalse(s.customer('customer:1',force=True)['reply_pending'])
        self.mail.messages.append(message('later',at='2026-11-01T04:00:00Z'))
        self.assertTrue(s.customer('customer:1',force=True)['reply_pending'])
    def test_history_no_trigger(self):
        s=self.connect();self.mail.messages=[message(at='2026-11-01T00:00:00Z')];self.assertEqual(len(s.customer('customer:1')['messages']),1);self.assertEqual(self.events,[])
    def test_wait_boundary_not_connect(self):
        s=self.connect();self.mail.messages=[message()];s.customer('customer:1');self.assertEqual(len(self.events),1)
    def test_active_and_prospect_replies_after_connection_are_dispatched(self):
        s=self.connect();self.flow={'state':'preparing','bucket':'active'};self.mail.messages=[message()]
        s.customer('customer:1');self.assertEqual(len(self.events),1)
        self.app.business.objects['prospect:2']=dict(id='prospect:2',kind='prospect',content=json.dumps(dict(email=SECOND)))
        self.flow={};self.mail.messages=[message('prospect-reply',buyer=SECOND)]
        s.customer('prospect:2');self.assertEqual(self.events[-1][0],'prospect:2')
    def test_old_history_without_wait_boundary_does_not_trigger(self):
        self.now=1793500000;s=self.connect();self.flow={'state':'preparing','bucket':'active'}
        self.mail.messages=[message(at='2026-10-01T00:00:00Z')]
        self.assertFalse(s.customer('customer:1')['reply_pending']);self.assertEqual(self.events,[])
    def test_reconnect_keeps_the_first_connection_boundary(self):
        s=self.connect();first=s.status()['connected_at'];self.now+=3600;s.connect(ACCOUNT,'new-secret')
        self.assertEqual(s.status()['connected_at'],first)
    def test_google_authorization_connects_and_restores_after_restart(self):
        class OAuth:
            def start(self,config,redirect,hint):return 'https://accounts.google.com/authorized'
            def finish(self,state,code):return ACCOUNT
        kwargs=dict(oauth_factory=OAuth,oauth_mailbox_factory=lambda _:self.mail,oauth_credential_checker=lambda _:True,clock=lambda:self.now)
        s=GmailService(self.app,**kwargs);s.start=lambda:None
        self.assertIn('accounts.google.com',s.start_oauth({'installed':{}},'http://127.0.0.1/callback'))
        self.assertEqual(s.finish_oauth('state','code')['auth_mode'],'oauth')
        stored=json.loads((self.app.state/'gmail.json').read_text())
        self.assertEqual(set(stored),{'email','connected_at','auth_mode','authorized_at'})
        restored=GmailService(self.app,**kwargs)
        self.assertEqual(restored.status()['state'],'connected');self.assertEqual(restored.status()['auth_mode'],'oauth')
        self.mail.messages=[message()];self.assertEqual(len(restored.customer('customer:1')['messages']),1)
    def test_testing_expiry_follows_latest_authorization_not_original_connection(self):
        class OAuth:
            def finish(self,state,code):return ACCOUNT
        config={'email':ACCOUNT,'connected_at':'2026-11-01T08:00:00+00:00','auth_mode':'oauth','publishing_status':'testing'}
        (self.app.state/'gmail.json').write_text(json.dumps(config),encoding='utf8')
        self.now=1793606400
        s=GmailService(self.app,oauth_factory=OAuth,oauth_mailbox_factory=lambda _:self.mail,oauth_credential_checker=lambda _:True,clock=lambda:self.now);s.start=lambda:None
        self.assertEqual(s.status()['authorization_expires_at'],'2026-11-08T08:00:00+00:00')
        s.finish_oauth('state','code');stored=json.loads((self.app.state/'gmail.json').read_text())
        self.assertEqual(stored['connected_at'],config['connected_at']);self.assertEqual(stored['publishing_status'],'testing')
        self.assertEqual((__import__('datetime').datetime.fromisoformat(s.status()['authorization_expires_at'])-__import__('datetime').datetime.fromisoformat(stored['authorized_at'])).days,7)
    def test_answered(self):
        s=self.connect();self.mail.messages=[message(),message('answer','outbound','2026-11-01T03:00:00Z')];self.assertFalse(s.customer('customer:1')['reply_pending']);self.assertEqual(self.events,[])
    def test_promotions_and_automatic_reply_do_not_trigger_drafts(self):
        s=self.connect();sales=message('sent','outbound','2026-11-01T02:00:00Z')
        promo=message('promotion',at='2026-11-01T03:00:00Z');promo['mail_kind']='promotion'
        automatic=message('out-of-office',at='2026-11-01T04:00:00Z');automatic['mail_kind']='automatic'
        self.mail.messages=[sales,promo,automatic];result=s.customer('customer:1')
        self.assertFalse(result['reply_pending']);self.assertEqual(self.events,[])
        self.assertEqual([m['id'] for m in result['messages']],['sent','out-of-office'])
    def test_promotions_do_not_hide_an_unanswered_buyer_reply(self):
        s=self.connect();answer=message('reply',at='2026-11-01T03:00:00Z')
        promo=message('promotion',at='2026-11-01T04:00:00Z');promo['mail_kind']='promotion'
        self.mail.messages=[answer,promo];result=s.customer('customer:1')
        self.assertTrue(result['reply_pending']);self.assertEqual(self.events[0][1]['id'],'reply')
    def test_colleague_from_matching_sent_thread_triggers_customer_reply(self):
        s=self.connect();colleague=message();colleague['from']='colleague@example.com';colleague['customer_emails']=[BUYER]
        self.mail.messages=[colleague];self.assertTrue(s.customer('customer:1')['reply_pending']);self.assertEqual(len(self.events),1)
    def test_incomplete_threads_are_not_reported_as_no_reply(self):
        s=self.connect();self.mail.messages=[message('sent','outbound','2026-11-01T03:00:00Z')]
        original=self.mail.context
        def incomplete(*args,**kwargs):
            result=original(*args,**kwargs);result['status']['thread_lookup_incomplete']=True;return result
        self.mail.context=incomplete;result=s.customer('customer:1')
        self.assertIsNone(result['reply_pending']);self.assertIn('尚未读完',result['next_action']);self.assertEqual(self.events,[])
    def test_failure_preserves(self):
        s=self.connect();self.mail.messages=[message()];s.customer('customer:1');self.mail.messages=[];self.mail.state='error';r=s.customer('customer:1');self.assertEqual(s.status()['state'],'error');self.assertIsNone(r['reply_pending']);self.assertEqual(len(r['messages']),1)
    def test_batch_one_login_per_customer_direction(self):
        s=self.connect();self.app.business.objects['prospect:2']=dict(id='prospect:2',kind='prospect',content=json.dumps(dict(email=SECOND)));self.mail.messages=[message(),message('second','outbound','2026-11-01T03:00:00Z',SECOND)];s.scan_once();self.assertEqual(len(self.mail.calls),1);self.assertTrue(s.peek('customer:1')['reply_pending']);self.assertFalse(s.peek('prospect:2')['reply_pending'])
    def test_sync_reads_customer_source_once_without_reloading_each_object(self):
        s=self.connect();obj=self.app.business.objects['customer:1'];calls=[]
        self.app.business.mail_objects=lambda:(calls.append('read') or [obj])
        self.app.business.get_object=lambda oid:(_ for _ in ()).throw(AssertionError('source read twice'))
        self.mail.messages=[message()];s.scan_once()
        self.assertEqual(calls,['read']);self.assertTrue(s.peek('customer:1')['reply_pending'])
    def test_new_buyer_candidates_update_even_without_existing_customers(self):
        s=self.connect();self.app.business.objects={}
        self.mail.buyer_candidates=lambda known,ids:{'status':{'state':'ready'},'items':[{'id':'x','summary':'鞋类采购咨询'}]}
        revision=s.revision;s.scan_once()
        self.assertEqual(s.buyer_candidates()['items'][0]['id'],'x');self.assertGreater(s.revision,revision)
        self.assertEqual(s.dismiss_candidate('x')['items'],[]);s.scan_once();self.assertEqual(s.buyer_candidates()['items'],[])
    def test_revision(self):
        s=self.connect();self.mail.messages=[message()];s.customer('customer:1');rev=s.revision;s.customer('customer:1');self.assertEqual(s.revision,rev);self.mail.state='error';s.customer('customer:1');self.assertGreater(s.revision,rev)
    def test_callback_failure_retry_and_latest_only(self):
        s=self.connect();calls=[]
        def callback(*args):calls.append(args[1]['id']);raise RuntimeError('oops')
        s.on_new_reply=callback;self.mail.messages=[message('old'),message('latest',at='2026-11-01T03:00:00Z')];s.customer('customer:1');self.assertEqual(calls,['latest']);self.assertIn('callback_error',s.peek('customer:1'));s.customer('customer:1');self.assertEqual(len(calls),1);self.now+=121;s.customer('customer:1');self.assertEqual(calls,['latest','latest'])
    def test_no_email_explicit(self):
        s=self.connect();self.app.business.objects['customer:1']['content']='{}';r=s.customer('customer:1');self.assertEqual(r['status']['state'],'no_contact_email');self.assertIn('邮箱',r['next_action'])
    def test_status_mapping(self):
        s=self.connect();self.assertEqual(s.customer('customer:1')['status']['state'],'connected');self.mail.state='not_configured';self.assertEqual(s.customer('customer:1')['status']['state'],'not_connected')
    def test_network_not_holding_status_lock(self):
        s=self.connect();entered=threading.Event();release=threading.Event();original=self.mail.context
        def slow(*args,**kwargs):entered.set();release.wait(2);return original(*args,**kwargs)
        self.mail.context=slow;t=threading.Thread(target=lambda:s.customer('customer:1'));t.start();self.assertTrue(entered.wait(1));self.assertTrue(s.lock.acquire(timeout=.2));s.lock.release();release.set();t.join(2)
    def test_start_stop(self):
        s=self.service();s.start();s.stop();self.assertFalse(s.status()['running']);self.assertEqual(self.mail.calls,[])
if __name__=='__main__':unittest.main()
