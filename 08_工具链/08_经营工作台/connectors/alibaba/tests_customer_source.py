import json
import tempfile
import unittest
from pathlib import Path

from customer_source import AlibabaCustomerSource,LIST,GET,CACHE


class Client:
    def __init__(self):self.calls=[];self.fail=False;self.wrong_id=False;self.same_buyer=False
    def call(self,method,params):
        self.calls.append((method,params))
        if self.fail:raise RuntimeError('access_token=PRIVATE')
        if method==LIST:
            query=json.loads(params['param_trade_ecology_order_list_query'])
            page=query['start_page'];size=query['page_size']
            return {'result':{'success':True,'value':{'total_count':3,'order_list':[{'trade_id':str(i)} for i in range(page*size+1,min((page+1)*size,3)+1)]}},'request_id':'list-id'}
        if method==GET:
            pid=params['e_trade_id']
            return {'value':{'trade_id':'wrong' if self.wrong_id else pid,'trade_status':'paid',
                'buyer':{'immutable_eid':'same' if self.same_buyer else 'buyer'+pid,'full_name':'Buyer '+pid,'country':'US'},
                'create_date':{'timestamp':123,'format_date':'Original PDT'},'shipping_address':{'mobile':'PRIVATE'},
                'order_products':[{'product_id':'123','name':'Shoes','quantity':'2','unit':'pair','private':'PRIVATE'}]},'request_id':'detail-id'}
        raise AssertionError('unexpected mutation or API')


class CustomerSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.client=Client();self.time=[1000]
        self.source=AlibabaCustomerSource(self.root,self.client,page_size=2,clock=lambda:self.time[0])
    def tearDown(self):self.temp.cleanup()

    def test_no_import_or_construction_collection_and_exact_read_methods(self):
        self.assertEqual(self.client.calls,[])
        self.assertEqual(self.source.status(start_refresh=False)['state'],'not_loaded')
        status=self.source.refresh(wait=True)
        self.assertEqual(status['state'],'ready');self.assertEqual(status['pagination']['nextPage'],2)
        self.assertEqual([m for m,p in self.client.calls],[LIST,GET,GET])
        self.assertEqual(json.loads(self.client.calls[0][1]['param_trade_ecology_order_list_query']),{'role':'seller','start_page':0,'page_size':2})
        self.assertEqual(self.client.calls[1][1],{'e_trade_id':'1','language':'en_US'})

    def test_buyer_projection_private_raw_and_single_page_coverage(self):
        status=self.source.refresh(wait=True);records=self.source.records()
        self.assertEqual(status['coverage'],'single-page-orders-not-inquiries')
        self.assertFalse(status['account_identity_verified'])
        self.assertEqual(records[0]['source_kind'],'alibaba_order_buyer')
        self.assertNotIn('PRIVATE',json.dumps(records))
        self.assertNotIn('buyer1',records[0]['id'])
        self.assertEqual(records[0]['orders'][0]['created']['format_date'],'Original PDT')
        cached=json.loads((self.root/CACHE).read_text(encoding='utf8'))
        self.assertIn('originals',cached)

    def test_buyer_dedup_uses_account_not_name(self):
        self.client.same_buyer=True
        self.source.refresh(wait=True);records=self.source.records()
        self.assertEqual(len(records),1);self.assertEqual(len(records[0]['orders']),2)

    def test_failure_preserves_prior_success_and_does_not_zero(self):
        good=self.source.refresh(wait=True);before=self.source.records()
        self.client.fail=True;self.time[0]+=121
        failed=self.source.refresh(wait=True)
        self.assertEqual(failed['state'],'error');self.assertTrue(failed['stale'])
        self.assertEqual(failed['observed_at'],good['observed_at'])
        self.assertEqual(self.source.records(),before)
        self.assertNotIn('PRIVATE',json.dumps(failed))
        calls=len(self.client.calls);self.source.status();self.assertEqual(len(self.client.calls),calls)

    def test_restart_loads_private_cache_without_io_to_platform(self):
        self.source.refresh(wait=True);other=Client()
        restarted=AlibabaCustomerSource(self.root,other,page_size=2,clock=lambda:1001)
        self.assertEqual(restarted.records(),self.source.records());self.assertEqual(other.calls,[])

    def test_next_page_and_identity_failure(self):
        result=self.source.refresh(wait=True,page=2)
        self.assertIsNone(result['pagination']['nextPage']);self.assertEqual(result['loaded_orders'],1)
        self.client.wrong_id=True;result=self.source.refresh(wait=True)
        self.assertEqual(result['error']['code'],'ORDER_IDENTITY_MISMATCH')

    def test_platform_business_failure_is_not_empty_success(self):
        class Rejected:
            def call(self,*args):return {'result':{'success':False,'error_message':'PRIVATE'}}
        source=AlibabaCustomerSource(self.root,Rejected(),clock=lambda:1000)
        status=source.refresh(wait=True)
        self.assertEqual(status['state'],'error');self.assertIsNone(status['loaded_buyers'])
        self.assertFalse((self.root/CACHE).exists())


if __name__=='__main__':unittest.main()
