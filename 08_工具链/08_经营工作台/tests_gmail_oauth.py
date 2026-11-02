import base64
import hashlib
import json
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

from gmail_oauth import GmailOAuth, GmailOAuthMailbox, SCOPE, parse_api_message

ACCOUNT='me@example.com'; BUYER='buyer@example.com'; CLIENT='sample.apps.googleusercontent.com'
CONFIG={'installed':{'client_id':CLIENT,'client_secret':'sample-client-secret'}}
REDIRECT='http://127.0.0.1:8766/api/desk/gmail/oauth/callback'


def encoded(value):return base64.urlsafe_b64encode(value.encode()).decode().rstrip('=')


def email(mid='10',direction='inbound',body='Please share samples'):
    sender,recipient=(BUYER,ACCOUNT) if direction=='inbound' else (ACCOUNT,BUYER)
    return {'id':mid,'threadId':'20','internalDate':'1793500000000','snippet':'Sample request',
            'payload':{'mimeType':'multipart/mixed','headers':[{'name':'From','value':sender},{'name':'To','value':recipient},
                {'name':'Subject','value':'Samples'}], 'parts':[{'mimeType':'text/plain','body':{'data':encoded(body)}},
                {'mimeType':'application/pdf','filename':'catalog.pdf','body':{'attachmentId':'ignored'}}]}}


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.saved=[];self.now=1000
        def request(url,*,token=None,form=None):
            self.calls.append((url,token,form))
            if form is not None:return {'access_token':'access-token','refresh_token':'refresh-token','scope':SCOPE}
            return {'emailAddress':ACCOUNT}
        self.auth=GmailOAuth(request=request,reader=lambda account:None,saver=lambda account,value:self.saved.append((account,value)),clock=lambda:self.now)
    def test_authorization_uses_readonly_pkce_and_saves_only_after_consent(self):
        url=self.auth.start(CONFIG,REDIRECT,ACCOUNT);query=parse_qs(urlsplit(url).query)
        self.assertEqual(query['scope'],[SCOPE]);self.assertEqual(query['redirect_uri'],[REDIRECT]);self.assertEqual(query['code_challenge_method'],['S256'])
        self.assertNotIn('sample-client-secret',url);self.assertEqual(self.saved,[])
        verifier=self.auth.pending['verifier'];challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'],[challenge]);self.assertEqual(self.auth.finish(query['state'][0],'temporary-code'),ACCOUNT)
        self.assertEqual(self.saved[0][0],ACCOUNT);self.assertEqual(self.saved[0][1]['refresh_token'],'refresh-token')
        self.assertEqual(self.calls[0][2]['code_verifier'],verifier)
    def test_invalid_state_or_expiry_cannot_store_credentials(self):
        self.auth.start(CONFIG,REDIRECT)
        with self.assertRaises(ValueError):self.auth.finish('wrong','code')
        self.assertEqual(self.saved,[]);state=self.auth.pending['state'];self.now+=901
        with self.assertRaises(ValueError):self.auth.finish(state,'code')
        self.assertEqual(self.saved,[])
    def test_requires_desktop_client_and_refresh_token(self):
        with self.assertRaises(ValueError):self.auth.start({'web':CONFIG['installed']},REDIRECT)
        self.auth.start(CONFIG,REDIRECT);state=self.auth.pending['state'];self.auth.request=lambda *args,**kwargs:{'access_token':'a'}
        with self.assertRaises(ValueError):self.auth.finish(state,'code')
        self.assertEqual(self.saved,[])
    def test_reauthorization_can_reuse_saved_client(self):
        self.auth.reader=lambda account:{'client_id':CLIENT,'client_secret':'saved','refresh_token':'old'}
        query=parse_qs(urlsplit(self.auth.start(None,REDIRECT,ACCOUNT)).query)
        self.assertEqual(query['client_id'],[CLIENT])
    def test_send_scope_authorization_delivers_grant_to_separate_handler(self):
        scope=SCOPE+' https://www.googleapis.com/auth/gmail.send';grants=[]
        def request(url,*,token=None,form=None):
            return {'access_token':'a','refresh_token':'r','scope':scope} if form else {'emailAddress':ACCOUNT}
        oauth=GmailOAuth(request=request,reader=lambda account:{'client_id':CLIENT,'refresh_token':'old'},
                         scope=scope,grant_handler=lambda account,client,tokens:grants.append((account,client,tokens)))
        query=parse_qs(urlsplit(oauth.start(None,REDIRECT,ACCOUNT)).query)
        self.assertEqual(set(query['scope'][0].split()),set(scope.split()))
        self.assertEqual(oauth.finish(query['state'][0],'one-time-code'),ACCOUNT)
        self.assertEqual(grants[0][0],ACCOUNT);self.assertEqual(grants[0][2]['refresh_token'],'r')
    def test_public_desktop_client_can_authorize_without_a_client_secret(self):
        url=self.auth.start({'installed':{'client_id':CLIENT}},REDIRECT)
        self.auth.finish(parse_qs(urlsplit(url).query)['state'][0],'code')
        self.assertNotIn('client_secret',self.calls[0][2]);self.assertEqual(self.saved[0][1]['client_secret'],'')


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.now=1000;self.values=[email(),email('11','outbound')];self.thread_values=None;self.fail=False
        def request(url,*,token=None,form=None):
            self.calls.append((url,token,form))
            if self.fail:raise OSError('offline')
            if form is not None:return {'access_token':'temporary-token','expires_in':3600}
            if 'messages?' in url:return {'messages':[{'id':x['id']} for x in self.values]}
            if '/threads/' in url:return {'messages':self.values if self.thread_values is None else self.thread_values}
            mid=url.split('/messages/')[1].split('?')[0]
            return next(x for x in self.values if x['id']==mid)
        self.box=GmailOAuthMailbox(ACCOUNT,request=request,reader=lambda account:{'client_id':CLIENT,'client_secret':'secret','refresh_token':'refresh'},clock=lambda:self.now)
    def test_reads_matching_messages_and_does_not_download_attachments(self):
        result=self.box.context([BUYER]);self.assertEqual(result['status']['state'],'ready')
        self.assertEqual(len(result['messages']),2);self.assertEqual(result['messages'][0]['body'],'Please share samples')
        self.assertEqual(result['messages'][0]['attachments'][0]['filename'],'catalog.pdf')
        self.assertEqual(result['messages'][0]['id'],'16')
        self.assertFalse(any('attachments/' in call[0] for call in self.calls))
    def test_poll_caches_unchanged_message_content(self):
        self.box.context([BUYER]);count=len(self.calls);self.now+=121;self.box.context([BUYER])
        self.assertEqual(len(self.calls),count+2)
    def test_slow_background_sync_does_not_block_another_customer(self):
        entered,release=threading.Event(),threading.Event();results={}
        self.box._token='token';self.box._token_expires=self.now+3600
        def request(url,*,token=None,form=None):
            query=parse_qs(urlsplit(url).query).get('q',[''])[0]
            if BUYER in query:entered.set();release.wait(3)
            return {'messages':[]}
        self.box.request=request
        first=threading.Thread(target=lambda:results.update(first=self.box.context([BUYER])))
        second=threading.Thread(target=lambda:results.update(second=self.box.context(['other@example.com'])))
        first.start();self.assertTrue(entered.wait(1));second.start();second.join(1)
        try:self.assertFalse(second.is_alive());self.assertEqual(results['second']['status']['state'],'ready')
        finally:release.set();first.join(3);second.join(3)
    def test_public_desktop_client_refresh_does_not_require_a_secret(self):
        self.box.reader=lambda account:{'client_id':CLIENT,'refresh_token':'refresh'}
        self.assertEqual(self.box.context([BUYER])['status']['state'],'ready')
        self.assertNotIn('client_secret',self.calls[0][2])
    def test_failed_refresh_preserves_history_without_claiming_no_reply(self):
        self.box.context([BUYER]);self.fail=True;result=self.box.context([BUYER],force=True)
        self.assertEqual(result['status']['state'],'error');self.assertIsNone(result['reply_pending']);self.assertEqual(len(result['messages']),2)
    def test_only_exact_customer_and_account_addresses_match(self):
        self.assertIsNone(parse_api_message(email(),ACCOUNT,{'another@example.com'}))
        self.assertIsNone(parse_api_message(email(), 'another@example.com',{BUYER}))
    def test_html_and_truncated_text(self):
        value=email();value['payload']['parts']=[{'mimeType':'text/html','body':{'data':encoded('<p>Hello <b>buyer</b></p>')}},
                                                {'mimeType':'text/plain','body':{'attachmentId':'body-is-separate'}}]
        result=parse_api_message(value,ACCOUNT,{BUYER});self.assertIn('Hello',result['body']);self.assertTrue(result['body_truncated'])
    def test_reply_address_and_rfc_message_id_are_available_for_threaded_reply(self):
        value=email();value['payload']['headers'].extend([{'name':'Reply-To','value':'Sales <sales@example.com>'},{'name':'Message-ID','value':'<buyer-1@example.com>'}])
        result=parse_api_message(value,ACCOUNT,{BUYER})
        self.assertEqual(result['reply_to'],'Sales <sales@example.com>');self.assertEqual(result['rfc_message_id'],'<buyer-1@example.com>')
    def test_colleague_in_same_thread_associates_with_customer(self):
        sent=email('11','outbound');colleague=email('12');colleague['payload']['headers'][0]['value']='colleague@example.com'
        self.values=[sent];self.thread_values=[sent,colleague]
        messages=self.box.context([BUYER])['messages']
        self.assertEqual(len(messages),2);self.assertEqual(messages[-1]['customer_emails'],[BUYER])
        self.assertEqual(messages[-1]['from'],'colleague@example.com')
    def test_same_subject_thread_does_not_merge_other_companies(self):
        sent=email('11','outbound');sent['payload']['headers'].append({'name':'Message-ID','value':'<sent-to-buyer>'})
        unrelated=email('12');unrelated['payload']['headers'][0]['value']='other@different-company.test'
        unrelated['payload']['headers'].append({'name':'In-Reply-To','value':'<sent-to-someone-else>'})
        self.values=[sent];self.thread_values=[sent,unrelated]
        self.assertEqual([m['id'] for m in self.box.context([BUYER])['messages']],['17'])
    def test_cross_domain_reply_requires_a_reference_to_the_customer_mail(self):
        sent=email('11','outbound');sent['payload']['headers'].append({'name':'Message-ID','value':'<sent-to-buyer>'})
        colleague=email('12');colleague['payload']['headers'][0]['value']='agent@buyer-representative.test'
        colleague['payload']['headers'].append({'name':'In-Reply-To','value':'<sent-to-buyer>'})
        self.values=[sent];self.thread_values=[sent,colleague]
        self.assertEqual(len(self.box.context([BUYER])['messages']),2)
    def test_public_email_domain_alone_does_not_merge_buyers(self):
        buyer='buyer@gmail.com';sent=email('11','outbound');sent['payload']['headers'][1]['value']=buyer
        unrelated=email('12');unrelated['payload']['headers'][0]['value']='stranger@gmail.com'
        self.values=[sent];self.thread_values=[sent,unrelated]
        self.assertEqual(len(self.box.context([buyer])['messages']),1)
    def test_thread_excludes_spam_and_drafts(self):
        sent=email('11','outbound');spam=email('12');spam['labelIds']=['SPAM']
        self.values=[sent];self.thread_values=[sent,spam]
        self.assertEqual(len(self.box.context([BUYER])['messages']),1)
    def test_thread_error_preserves_direct_correspondence_and_reports_incomplete(self):
        original=self.box.request
        def broken(url,**kwargs):
            if '/threads/' in url:raise OSError('offline')
            return original(url,**kwargs)
        self.box.request=broken;result=self.box.context([BUYER])
        self.assertEqual(result['status']['state'],'ready');self.assertTrue(result['status']['thread_lookup_incomplete'])
        self.assertEqual(len(result['messages']),2)
    def test_inbox_finds_undiscovered_buyer_and_filters_marketing(self):
        buyer=email('30',body='We are looking for a supplier of knitted shoes. Could you provide a quotation?')
        buyer['payload']['headers'][0]['value']='New Buyer <newbuyer@example.com>'
        promo=email('31',body='Discover the latest shoes in our newsletter!')
        promo['payload']['headers'][0]['value']='store@example.com';promo['payload']['headers'].append({'name':'List-Unsubscribe','value':'<https://example.com>'})
        known=email('32',body='We are looking for a supplier of knitted shoes.')
        self.values=[buyer,promo,known]
        result=self.box.buyer_candidates({BUYER})
        self.assertEqual(result['status']['state'],'ready');self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['email'],'newbuyer@example.com');self.assertIn('鞋类',result['items'][0]['summary'])
        self.assertNotIn('body',result['items'][0])
    def test_inbox_does_not_duplicate_a_reply_already_linked_by_thread(self):
        buyer=email('30',body='We are looking for a supplier of shoes.')
        buyer['payload']['headers'][0]['value']='colleague@example.com';self.values=[buyer]
        self.assertEqual(self.box.buyer_candidates({BUYER},linked_ids={'48'})['items'],[])
    def test_candidate_marks_reply_sent_in_same_thread(self):
        buyer=email('30',body='We are looking for a supplier of knitted shoes.')
        buyer['payload']['headers'][0]['value']='newbuyer@example.com'
        answer=email('31','outbound');answer['internalDate']='1793501000000'
        answer['payload']['headers'][1]['value']='newbuyer@example.com'
        self.values=[buyer];self.thread_values=[buyer,answer]
        result=self.box.buyer_candidates({BUYER})
        self.assertTrue(result['items'][0]['answered'])


if __name__=='__main__':unittest.main()
