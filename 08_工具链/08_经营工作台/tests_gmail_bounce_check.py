"""Stubbed official Gmail reads; never uses real mailbox credentials or sends."""
import base64
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from urllib.parse import parse_qs, urlsplit

from gmail_bounce_check import check_bounces, MAX_PAGES, MAX_RAW_BYTES, _batch_request, _oauth_request, BATCH_URL, _candidate_cache

ADDRESS = 'buyer@example.test'


def message(body, sender='mailer-daemon@example.test'):
    raw = ('From: ' + sender + '\r\nTo: sender@example.test\r\nSubject: Delivery failed\r\n'
           'Content-Type: text/plain; charset=utf-8\r\n\r\n' + body).encode()
    return {'id': 'a1', 'internalDate':'1794000000000', 'raw':base64.urlsafe_b64encode(raw).decode()}


def dsn(blocks, body='Delivery status report'):
    raw = ('From: postmaster@example.test\r\nTo: sender@example.test\r\nSubject: Delivery status\r\n'
           'MIME-Version: 1.0\r\nContent-Type: multipart/report; boundary="test"; report-type=delivery-status\r\n\r\n'
           '--test\r\nContent-Type: text/plain\r\n\r\n' + body + '\r\n'
           '--test\r\nContent-Type: message/delivery-status\r\n\r\nReporting-MTA: dns; example.test\r\n\r\n' +
           '\r\n\r\n'.join('Final-Recipient: rfc822; ' + address + '\r\nAction: ' + action + '\r\nStatus: ' + status
                              for address, action, status in blocks) + '\r\n\r\n--test--\r\n').encode()
    return {'id':'a1', 'raw':base64.urlsafe_b64encode(raw).decode()}


def batch_response(parts):
    chunks=[]
    for mid,status,value in parts:
        body=json.dumps(value).encode()
        chunks.append(b'--batch_test\r\nContent-Type: application/http\r\nContent-ID: <response-bounce-'+mid.encode()+
                      b'>\r\n\r\nHTTP/1.1 '+str(status).encode()+b' Result\r\nContent-Type: application/json\r\nContent-Length: '+
                      str(len(body)).encode()+b'\r\n\r\n'+body+b'\r\n')
    return {'content_type':'multipart/mixed; boundary=batch_test','body':b''.join(chunks)+b'--batch_test--\r\n'}


class BounceTests(unittest.TestCase):
    def setUp(self):
        _candidate_cache.clear()
    def mailbox(self, pages=None, messages=None, failure=None):
        self.calls = []
        pages = pages or {'': {'messages': []}}
        messages = messages or {}
        def request(url, **kwargs):
            self.calls.append((url, kwargs))
            if failure:
                raise failure
            parts = urlsplit(url)
            query = parse_qs(parts.query)
            if parts.path.endswith('/messages'):
                return pages[query.get('pageToken', [''])[0]]
            return messages[parts.path.rsplit('/',1)[-1]]
        return SimpleNamespace(_access_token=lambda:'synthetic-token', request=request)

    def check(self, raw):
        return check_bounces(self.mailbox({'':{'messages':[{'id':'a1'}]}}, {'a1':raw}), ADDRESS)

    def test_empty_complete_query_is_only_scoped_clear(self):
        result = check_bounces(self.mailbox(), ADDRESS)
        self.assertEqual(result['status'], 'clear')
        self.assertTrue(result['coverage']['complete'])
        self.assertFalse(result['coverage']['deliverability_verified'])
        self.assertFalse(result['coverage']['other_accounts_checked'])
        self.assertIn('in:anywhere', parse_qs(urlsplit(self.calls[0][0]).query)['q'][0])
        self.assertNotIn(ADDRESS, parse_qs(urlsplit(self.calls[0][0]).query)['q'][0])

    def test_exact_daemon_failure_blocks_without_retaining_body(self):
        result = self.check(message('Delivery failed for <buyer@example.test>: user unknown'))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['events'][0]['id'], 'a1')
        self.assertTrue(result['events'][0]['at'])
        self.assertNotIn('user unknown', str(result))
        self.assertNotIn('synthetic-token', str(result))

    def test_dsn_failed_recipient_not_original_to_or_another_recipient(self):
        self.assertEqual(self.check(dsn([(ADDRESS,'failed','5.1.1')]))['status'], 'blocked')
        self.assertEqual(self.check(dsn([('other@example.test','failed','5.1.1'),(ADDRESS,'delivered','2.0.0')]))['status'], 'clear')

    def test_4xx_delay_not_permanent_failure(self):
        result = self.check(dsn([(ADDRESS,'delayed','4.2.0')], 'Delivery failed temporarily for buyer@example.test, retrying'))
        self.assertEqual(result['status'], 'clear')

    def test_similar_addresses_do_not_match(self):
        for other in ('otherbuyer@example.test', 'buyer@example.test.evil', 'buyer+tag@example.test'):
            with self.subTest(other=other):
                self.assertEqual(self.check(message('Delivery failed for ' + other))['status'], 'clear')

    def test_chinese_adjacent_to_address_does_not_hide_failure(self):
        self.assertEqual(self.check(message('投递失败buyer@example.test地址不存在'))['status'], 'blocked')

    def test_address_and_failure_on_separate_lines_is_unknown(self):
        result = self.check(message('Delivery failed\r\nRecipient: buyer@example.test'))
        self.assertEqual(result['status'], 'unknown')

    def test_untrusted_or_negated_text_never_blocks(self):
        self.assertEqual(self.check(message('Delivery failed for buyer@example.test', sender='sales@example.test'))['status'], 'unknown')
        self.assertNotEqual(self.check(message('No delivery failure for buyer@example.test; address not found was unrelated'))['status'], 'blocked')
        self.assertNotEqual(self.check(message('> Delivery failed for buyer@example.test'))['status'], 'blocked')

    def test_full_pagination_finds_second_page_failure(self):
        box = self.mailbox({'':{'messages':[], 'nextPageToken':'page2'}, 'page2':{'messages':[{'id':'a1'}]}},
                           {'a1':message('Delivery failed for buyer@example.test')})
        result = check_bounces(box, ADDRESS)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['coverage']['pages'], 2)

    def test_pagination_limit_or_repeated_token_is_unknown(self):
        pages = {'':{'messages':[], 'nextPageToken':'p1'}, 'p1':{'messages':[], 'nextPageToken':'p2'},
                 'p2':{'messages':[], 'nextPageToken':'p3'}}
        result = check_bounces(self.mailbox(pages), ADDRESS)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['coverage']['pages'], MAX_PAGES)
        result = check_bounces(self.mailbox({'':{'nextPageToken':'p'}, 'p':{'nextPageToken':'p'}}), ADDRESS)
        self.assertEqual(result['status'], 'unknown')

    def test_missing_body_bad_base64_and_wrong_id_are_unknown(self):
        for raw in ({'id':'a1','snippet':'Delivery failed for '+ADDRESS}, {'id':'a1','raw':'!!!'},
                    {'id':'a2','raw':message('Complete body')['raw']}):
            with self.subTest(raw=raw):
                self.assertEqual(self.check(raw)['status'], 'unknown')

    def test_omitted_listing_and_invalid_ids_are_not_false_clear(self):
        for page in ({'messages':[], 'resultSizeEstimate':1}, {'messages':[{'id':'not-a-gmail-id'}]}, {'messages':None}, {'error':{'code':403}}):
            with self.subTest(page=page):
                self.assertEqual(check_bounces(self.mailbox({'':page}),ADDRESS)['status'], 'unknown')

    def test_permission_failures_and_imap_not_supported_are_unknown(self):
        result = check_bounces(self.mailbox(failure=PermissionError('secret detail')), ADDRESS)
        self.assertEqual(result['status'], 'unknown')
        self.assertNotIn('secret detail', str(result))
        self.assertEqual(check_bounces(SimpleNamespace(), ADDRESS)['status'], 'unknown')
        box = SimpleNamespace(_access_token=lambda:(_ for _ in ()).throw(ValueError('private')), request=lambda *a,**kw:{})
        self.assertEqual(check_bounces(box,ADDRESS)['status'], 'unknown')

    def test_invalid_address_does_not_query_mailbox(self):
        box = self.mailbox()
        self.assertEqual(check_bounces(box, 'buyer@example.test\nOR anything')['status'], 'unknown')
        self.assertEqual(self.calls, [])

    def test_temporary_plaintext_failure_is_ambiguous(self):
        self.assertEqual(self.check(message('Delivery failed temporarily for buyer@example.test; retrying'))['status'], 'unknown')

    def test_original_message_attachment_does_not_supply_failed_recipient(self):
        raw = ('From: mailer-daemon@example.test\r\nSubject: Delivery failed\r\n'
               'MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=t\r\n\r\n'
               '--t\r\nContent-Type: text/plain\r\n\r\nDelivery failed for other@example.test\r\n'
               '--t\r\nContent-Type: message/rfc822\r\n\r\n'
               'From: sender@example.test\r\nTo: buyer@example.test\r\nSubject: Original\r\n\r\n'
               'Delivery failed for buyer@example.test\r\n--t--\r\n').encode()
        result = self.check({'id':'a1','raw':base64.urlsafe_b64encode(raw).decode()})
        self.assertEqual(result['status'], 'clear')
        result = self.check(message('Original message follows:\r\nDelivery failed for buyer@example.test'))
        self.assertNotEqual(result['status'], 'blocked')

    def test_result_cap_cannot_report_clear(self):
        ids = [format(i+1,'x') for i in range(80)]
        rows = [{'id':mid} for mid in ids]
        messages = {mid:{**message('Delivery failed for other@example.test'),'id':mid} for mid in ids}
        result = check_bounces(self.mailbox({'':{'messages':rows}}, messages), ADDRESS)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['coverage']['messages_checked'], 75)

    def test_positive_evidence_still_blocks_when_later_page_fails(self):
        box = self.mailbox({'':{'messages':[{'id':'a1'}], 'nextPageToken':'missing-page'}},
                           {'a1':message('Delivery failed for buyer@example.test')})
        result = check_bounces(box, ADDRESS)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['coverage']['complete'])

    def test_batch_reordered_parts_match_content_id_without_individual_gets(self):
        box=self.mailbox({'':{'messages':[{'id':'a1'},{'id':'b2'}]}})
        def batch(ids,*,token):
            self.assertEqual(ids,['a1','b2'])
            self.assertEqual(token,'synthetic-token')
            return batch_response([('b2',200,{**message('Delivery failed for buyer@example.test'),'id':'b2'}),
                                   ('a1',200,message('Delivery failed for other@example.test'))])
        result=check_bounces(box,ADDRESS,batch_request=batch)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['events'][0]['id'],'b2')
        self.assertTrue(result['coverage']['complete'])
        self.assertEqual(result['coverage']['batch_requests'],1)
        self.assertEqual(len(self.calls),1)

    def test_batch_missing_duplicate_error_and_wrong_identity_are_unknown(self):
        good=message('Delivery failed for other@example.test')
        cases=[[], [('a1',200,good),('a1',200,good)], [('a1',403,{'error':{'code':403}})],
               [('b2',200,{**good,'id':'b2'})], [('a1',200,{**good,'id':'b2'})]]
        for parts in cases:
            with self.subTest(parts=parts):
                result=check_bounces(self.mailbox({'':{'messages':[{'id':'a1'}]}}),ADDRESS,
                                      batch_request=lambda ids,token:batch_response(parts))
                self.assertEqual(result['status'],'unknown')
                self.assertFalse(result['coverage']['complete'])

    def test_batch_duplicate_positive_is_not_trusted(self):
        good=message('Delivery failed for buyer@example.test')
        response=batch_response([('a1',200,good),('a1',200,good)])
        result=check_bounces(self.mailbox({'':{'messages':[{'id':'a1'}]}}),ADDRESS,
                              batch_request=lambda ids,token:response)
        self.assertEqual(result['status'],'unknown')
        self.assertEqual(result['events'],[])

    def test_batch_partial_error_preserves_positive_with_incomplete_coverage(self):
        response=batch_response([('a1',200,message('Delivery failed for buyer@example.test')),
                                 ('b2',429,{'error':{'code':429}})])
        result=check_bounces(self.mailbox({'':{'messages':[{'id':'a1'},{'id':'b2'}]}}),ADDRESS,
                              batch_request=lambda ids,token:response)
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(result['coverage']['complete'])

    def test_batch_malformed_mime_json_length_and_truncation_are_unknown(self):
        good=batch_response([('a1',200,message('Delivery failed for other@example.test'))])
        variants=[{'content_type':'application/json','body':b'{}'},
                  {**good,'body':good['body'].replace(b'--batch_test--\r\n',b'')},
                  {**good,'body':good['body'].replace(b'Content-Length: ',b'Content-Length: 999')},
                  {**good,'body':good['body'].replace(b'HTTP/1.1 200',b'HTTP/1.1 500')},
                  {**good,'body':good['body'].replace(b'application/json',b'text/html')},
                  {**good,'body':good['body']+b'unexpected suffix'}]
        for response in variants:
            with self.subTest(response=response):
                result=check_bounces(self.mailbox({'':{'messages':[{'id':'a1'}]}}),ADDRESS,
                                      batch_request=lambda ids,token:response)
                self.assertEqual(result['status'],'unknown')

    def test_batch_transport_failure_has_no_slow_individual_fallback(self):
        def batch(ids,*,token):raise TimeoutError('private token and body detail')
        result=check_bounces(self.mailbox({'':{'messages':[{'id':'a1'}]}}),ADDRESS,batch_request=batch)
        self.assertEqual(result['status'],'unknown')
        self.assertEqual(len(self.calls),1)
        self.assertNotIn('private token',str(result))

    def test_batch_75_messages_use_three_lists_and_three_batches(self):
        ids=[format(i+1,'x') for i in range(75)]
        pages={'':{'messages':[{'id':mid} for mid in ids[:25]],'nextPageToken':'p2'},
               'p2':{'messages':[{'id':mid} for mid in ids[25:50]],'nextPageToken':'p3'},
               'p3':{'messages':[{'id':mid} for mid in ids[50:]]}}
        batches=[]
        def batch(ids,*,token):
            batches.append(ids)
            return batch_response([(mid,200,{**message('Delivery failed for other@example.test'),'id':mid}) for mid in ids])
        result=check_bounces(self.mailbox(pages),ADDRESS,batch_request=batch)
        self.assertEqual(result['status'],'clear')
        self.assertEqual(result['coverage']['messages_checked'],75)
        self.assertEqual(result['coverage']['batch_requests'],3)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(len(batches),3)

    def test_production_request_selects_official_batch_transport(self):
        box=SimpleNamespace(account_email='sender@example.test',_access_token=lambda:'synthetic-token',request=_oauth_request)
        with patch('gmail_oauth.urlopen') as listing,patch('gmail_bounce_check._batch_request') as batch:
            profile=json.dumps({'emailAddress':'sender@example.test','historyId':'10'}).encode()
            listing.return_value.__enter__.return_value.read.side_effect=[profile,json.dumps({'messages':[{'id':'a1'}]}).encode(),profile]
            batch.return_value=batch_response([('a1',200,message('Delivery failed for other@example.test'))])
            result=check_bounces(box,ADDRESS)
            self.assertEqual(result['status'],'clear')
            batch.assert_called_once_with(['a1'],token='synthetic-token')

    def test_official_wire_transport_uses_only_read_gets_and_blocks_redirects(self):
        response=batch_response([('a1',200,message('Delivery failed for other@example.test'))])
        with patch('gmail_bounce_check.build_opener') as build:
            reader=build.return_value.open.return_value.__enter__.return_value
            reader.read.return_value=response['body']
            reader.headers={'Content-Type':response['content_type']}
            result=_batch_request(['a1'],token='synthetic-token')
            request=build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,BATCH_URL)
            self.assertEqual(request.get_method(),'POST')
            self.assertIn(b'GET /gmail/v1/users/me/messages/a1?format=raw HTTP/1.1',request.data)
            self.assertNotIn(b'synthetic-token',request.data)
            self.assertNotIn(b'/send',request.data)
            handler=build.call_args.args[0]()
            self.assertIsNone(handler.redirect_request(None,None,302,'',{},'https://elsewhere.test'))
            self.assertEqual(result,response)

    def native_fixture(self):
        state={'history':'10','profiles':0,'lists':0,'batches':0,'profile_failure':False,'batch_failure':False,'during':None}
        def request(url,**kwargs):
            if url.endswith('/profile'):
                state['profiles']+=1
                if state['profile_failure']:raise PermissionError('Synthetic permission failure')
                return {'emailAddress':'sender@example.test','historyId':state['history']}
            if urlsplit(url).path.endswith('/messages'):
                state['lists']+=1
                return {'messages':[{'id':'a1'}]}
            self.fail('Individual GET bypassed native batch')
        def batch(ids,*,token):
            state['batches']+=1
            if state['during']:state['during']()
            if state['batch_failure']:raise TimeoutError('Synthetic timeout')
            return batch_response([('a1',200,message('Delivery failed for buyer@example.test'))])
        box=SimpleNamespace(account_email='sender@example.test',_access_token=lambda:'synthetic-token',request=request)
        return state,request,batch,box

    def test_native_cache_hit_reparses_for_each_exact_customer(self):
        state,request,batch,box=self.native_fixture()
        with patch('gmail_bounce_check._oauth_request',request):
            first=check_bounces(box,'other@example.test',batch_request=batch)
            second=check_bounces(box,ADDRESS,batch_request=batch)
        self.assertEqual(first['status'],'clear')
        self.assertEqual(second['status'],'blocked')
        self.assertEqual(second['events'][0]['id'],'a1')
        self.assertEqual(second['coverage']['candidate_cache'],'hit')
        self.assertEqual(state['lists'],1)
        self.assertEqual(state['batches'],1)
        self.assertEqual(state['profiles'],4)
        self.assertNotIn('synthetic-token',str(_candidate_cache))

    def test_native_watermark_change_forces_full_refresh(self):
        state,request,batch,box=self.native_fixture()
        with patch('gmail_bounce_check._oauth_request',request):
            check_bounces(box,'other@example.test',batch_request=batch)
            state['history']='11'
            result=check_bounces(box,'other@example.test',batch_request=batch)
        self.assertEqual(result['status'],'clear')
        self.assertEqual(result['coverage']['candidate_cache'],'refresh')
        self.assertEqual(state['batches'],2)
        self.assertEqual(_candidate_cache['sender@example.test']['history'],'11')

    def test_native_changed_or_failed_observation_never_returns_cached_clear(self):
        state,request,batch,box=self.native_fixture()
        with patch('gmail_bounce_check._oauth_request',request):
            check_bounces(box,'other@example.test',batch_request=batch)
            state['profile_failure']=True
            result=check_bounces(box,'other@example.test',batch_request=batch)
            self.assertEqual(result['status'],'unknown')
            self.assertEqual(len(_candidate_cache),0)
            state['profile_failure']=False
            state['during']=lambda:state.update(history='12')
            result=check_bounces(box,'other@example.test',batch_request=batch)
            self.assertEqual(result['status'],'unknown')
            self.assertFalse(result['coverage']['complete'])
            self.assertEqual(len(_candidate_cache),0)

    def test_native_missing_watermark_incomplete_batch_and_memory_limit_not_cached(self):
        state,request,batch,box=self.native_fixture()
        with patch('gmail_bounce_check._oauth_request',request):
            state['history']=''
            self.assertEqual(check_bounces(box,'other@example.test',batch_request=batch)['status'],'unknown')
            self.assertEqual(state['batches'],0)
            state['history']='10';state['batch_failure']=True
            self.assertEqual(check_bounces(box,'other@example.test',batch_request=batch)['status'],'unknown')
            self.assertEqual(len(_candidate_cache),0)
            state['batch_failure']=False
            with patch('gmail_bounce_check.MAX_CACHE_BYTES',1):
                result=check_bounces(box,'other@example.test',batch_request=batch)
                self.assertEqual(result['status'],'clear')
                self.assertFalse(result['coverage']['cache_stored'])
                self.assertEqual(len(_candidate_cache),0)

    def test_native_concurrent_old_refresh_cannot_overwrite_new_watermark(self):
        state,request,batch,box=self.native_fixture()
        started,finish=threading.Event(),threading.Event()
        def during():
            if state['batches']==1:
                started.set()
                if not finish.wait(5):raise TimeoutError()
        state['during']=during
        results=[]
        def run():results.append(check_bounces(box,'other@example.test',batch_request=batch))
        with patch('gmail_bounce_check._oauth_request',request):
            old=threading.Thread(target=run);old.start()
            self.assertTrue(started.wait(5))
            state['history']='11'
            new=threading.Thread(target=run);new.start()
            finish.set()
            old.join(10);new.join(10)
        self.assertFalse(old.is_alive() or new.is_alive())
        self.assertEqual(sorted(r['status'] for r in results),['clear','unknown'])
        self.assertEqual(_candidate_cache['sender@example.test']['history'],'11')
        self.assertEqual(state['batches'],2)

    def test_address_semantic_unknown_does_not_force_candidate_redownload(self):
        state,request,batch,box=self.native_fixture()
        def ambiguous(ids,*,token):
            state['batches']+=1
            return batch_response([('a1',200,message('Delivery failed\r\nRecipient: buyer@example.test'))])
        with patch('gmail_bounce_check._oauth_request',request):
            first=check_bounces(box,ADDRESS,batch_request=ambiguous)
            second=check_bounces(box,'other@example.test',batch_request=ambiguous)
            third=check_bounces(box,ADDRESS,batch_request=ambiguous)
        self.assertEqual(first['status'],'unknown')
        self.assertFalse(first['coverage']['complete'])
        self.assertTrue(first['coverage']['candidate_transport_complete'])
        self.assertTrue(first['coverage']['cache_stored'])
        self.assertEqual(second['status'],'clear')
        self.assertTrue(second['coverage']['complete'])
        self.assertEqual(second['coverage']['candidate_cache'],'hit')
        self.assertEqual(third['status'],'unknown')
        self.assertFalse(third['coverage']['complete'])
        self.assertEqual(third['coverage']['candidate_cache'],'hit')
        self.assertEqual(state['batches'],1)
        self.assertEqual(state['lists'],1)

    def test_missing_raw_response_is_not_cached_as_complete_transport(self):
        state,request,batch,box=self.native_fixture()
        def missing_raw(ids,*,token):
            state['batches']+=1
            return batch_response([('a1',200,{'id':'a1','snippet':'Incomplete response'})])
        with patch('gmail_bounce_check._oauth_request',request):
            first=check_bounces(box,ADDRESS,batch_request=missing_raw)
            second=check_bounces(box,'other@example.test',batch_request=missing_raw)
        self.assertEqual(first['status'],'unknown')
        self.assertEqual(second['status'],'unknown')
        self.assertFalse(first['coverage']['candidate_transport_complete'])
        self.assertEqual(len(_candidate_cache),0)
        self.assertEqual(state['batches'],2)

    def test_large_dsn_with_original_pdf_preserves_exact_recipient_checks(self):
        # A returned original message may carry its catalogue PDF. This is a
        # synthetic payload, not customer content, and never leaves the process.
        original=EmailMessage()
        original['From']='sender@example.test'
        original['To']=ADDRESS
        original['Subject']='Synthetic catalogue'
        original.set_content('Synthetic original proposal')
        original.add_attachment(b'%PDF-synthetic\n'+b'X'*(2400*1024),maintype='application',subtype='pdf',filename='synthetic.pdf')
        report=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(dsn([(ADDRESS,'failed','5.1.1')])['raw']))
        returned=EmailMessage()
        returned.set_type('message/rfc822')
        returned.set_payload([original])
        report.attach(returned)
        raw=report.as_bytes(policy=policy.SMTP)
        self.assertGreater(len(raw),3*1024*1024)
        self.assertLess(len(raw),4*1024*1024)
        value={'id':'a1','raw':base64.urlsafe_b64encode(raw).decode()}
        self.assertEqual(self.check(value)['status'],'blocked')
        box=self.mailbox({'':{'messages':[{'id':'a1'}]}},{'a1':value})
        self.assertEqual(check_bounces(box,'different@example.test')['status'],'clear')

    def test_raw_above_new_limit_stays_unknown(self):
        self.assertEqual(MAX_RAW_BYTES,12*1024*1024)
        raw=b'X'*(MAX_RAW_BYTES+1)
        value={'id':'a1','raw':base64.urlsafe_b64encode(raw).decode()}
        self.assertEqual(self.check(value)['status'],'unknown')


if __name__ == '__main__':
    unittest.main()
