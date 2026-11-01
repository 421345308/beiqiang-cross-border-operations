import base64
import hashlib
import json
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
    def test_public_desktop_client_can_authorize_without_a_client_secret(self):
        url=self.auth.start({'installed':{'client_id':CLIENT}},REDIRECT)
        self.auth.finish(parse_qs(urlsplit(url).query)['state'][0],'code')
        self.assertNotIn('client_secret',self.calls[0][2]);self.assertEqual(self.saved[0][1]['client_secret'],'')


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.now=1000;self.values=[email(),email('11','outbound')];self.fail=False
        def request(url,*,token=None,form=None):
            self.calls.append((url,token,form))
            if self.fail:raise OSError('offline')
            if form is not None:return {'access_token':'temporary-token','expires_in':3600}
            if 'messages?' in url:return {'messages':[{'id':x['id']} for x in self.values]}
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
        self.assertEqual(len(self.calls),count+1)
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


if __name__=='__main__':unittest.main()
