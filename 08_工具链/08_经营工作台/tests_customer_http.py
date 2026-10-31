"""Local HTTP + scoped MCP acceptance; all sources/processes are fixtures."""
import json
from pathlib import Path
import unittest
from urllib.parse import urlencode
import tests_desk_http as fixture
from tests_customer_analysis import response as analysis_response
from connectors.alibaba.customer_source import AlibabaCustomerSource,LIST,GET
from desk_mcp import DeskTools

class OrderClient:
    def __init__(self):self.calls=[]
    def call(self,method,params):
        self.calls.append((method,params))
        if method==LIST:return {'result':{'success':True,'value':{'total_count':1,'order_list':[{'trade_id':'71'}]}},'request_id':'fixture-list'}
        if method==GET:return {'value':{'trade_id':'71','trade_status':'paid','buyer':{'immutable_eid':'fixture-buyer','full_name':'Order Buyer','country':'US'},
            'order_products':[{'product_id':'123','name':'Fixture shoe','quantity':'12','unit':'pair'}]},'request_id':'fixture-detail'}
        raise AssertionError('Only the two read APIs are allowed')

class CustomerHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.DeskHTTPTests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.app=self.fixture.app;self.root=self.fixture.root;self.request=self.fixture.request
    def intake(self,text='ORIGINAL_MESSAGE_UNIQUE_5912 We need 800 pairs of walking shoes.'):
        status,result=self.request('/api/desk/inquiries',{'channel':'email','company':'Fixture Actual Buyer',
            'contact_name':'Buyer','country':'US','quantity':'800','source_id':'fixture-message-5912',
            'received_at':'2026-10-31T10:00:00Z','original_text':text})
        self.assertEqual(status,201);return result
    def tools(self,oid):return DeskTools(self.app.business,self.root,oid,audit=self.root/'read-audit.jsonl')

    def test_inquiry_queue_workflow_and_operator_context_share_current_brief(self):
        created=self.intake();oid=created['object_id']
        status,queue=self.request('/api/desk/inquiry-queue?bucket=active')
        self.assertEqual(status,200);self.assertIn(oid,[r['object_id'] for r in queue['items']])
        status,flow=self.request('/api/desk/customer-workflow',{'object_id':oid,'state':'preparing','priority':'high','next_action':'先准备合作回复'})
        self.assertEqual(status,200);self.assertEqual(flow['state'],'preparing')
        status,profile=self.request('/api/desk/customer-profile?'+urlencode({'object_id':oid}))
        self.assertEqual(status,200);self.assertFalse(profile['stale'])
        status,saved=self.request('/api/desk/customer-profile',{'object_id':oid,'source_hash':profile['source_hash'],'operator_context':'此数量是估计值，先讨论合作方式'})
        self.assertEqual(status,200);self.assertEqual(saved['workflow']['priority'],'high')
        brief=self.tools(oid).call('get_object',{})['customer_brief']
        self.assertEqual(brief['operator_context'],'此数量是估计值，先讨论合作方式')
        self.assertEqual(brief['workflow']['next_action'],'先准备合作回复')
        status,closed=self.request('/api/desk/customer-workflow',{'object_id':oid,'state':'archived'})
        self.assertEqual(status,200)
        status,active=self.request('/api/desk/inquiry-queue?bucket=active')
        self.assertNotIn(oid,[r['object_id'] for r in active['items']])
        status,ended=self.request('/api/desk/inquiry-queue?bucket=archive')
        self.assertIn(oid,[r['object_id'] for r in ended['items']])

    def test_manual_inquiry_http_object_profile_and_chinese_save_reopen(self):
        original='We need 800 pairs. Please confirm available sizes, sample fee and lead time.'
        created=self.intake(original);oid=created['object_id']
        status,obj=self.request('/api/desk/object?'+urlencode({'id':oid}))
        self.assertEqual(status,200);self.assertEqual(obj['source_type'],'manual_import');self.assertEqual(obj['original_text'],original)
        status,profile=self.request('/api/desk/customer-profile?'+urlencode({'object_id':oid}))
        self.assertEqual(status,200);self.assertEqual(profile['original_text'],original)
        status,saved=self.request('/api/desk/customer-profile',{'object_id':oid,'source_hash':profile['source_hash'],
            'original_language':'en','translation_zh':'我们需要800双。请确认可供尺码、样品费用和交期。',
            'analysis':{'intent':'采购条件询问，尚未成交','fit':'待逐款核实','next_action':'确认鞋款及所需尺码',
                'facts':['原文询问800双'],'inferences':['可能在比较供应商，需核实'],'basis':['已录入原邮件正文'],'missing':['具体鞋款']}})
        self.assertEqual(status,200);self.assertEqual(saved['translation_zh'],'我们需要800双。请确认可供尺码、样品费用和交期。')
        status,reopened=self.request('/api/desk/customer-profile?'+urlencode({'object_id':oid}))
        self.assertEqual(status,200);self.assertEqual(reopened['translation_zh'],saved['translation_zh']);self.assertFalse(reopened['stale'])
        self.assertEqual(self.app.inquiry_intake.get_record(created['record']['id'])['original_text'],original)
        current=self.tools(oid);source=next(row for row in current.call('list_sources',{}) if row['role']=='current-object-source')
        self.assertIn(original,current.call('read_source',{'path':source['path']})['content'])

    def test_discovery_origin_object_id_makes_actual_inquiry_source_readable_to_mcp(self):
        created=self.intake();origin=created['object_id']
        status,task=self.request('/api/desk/discovery',{'kind':'research_task','title':'核实原询盘采购角色',
            'target':'围绕已收到的需求准备核验','origin_object_id':origin,'next_action':'查原询盘后准备问题，不外发'})
        self.assertEqual(status,201);self.assertEqual(task['origin_object_id'],origin)
        oid=task['object_id'];status,obj=self.request('/api/desk/object?'+urlencode({'id':oid}))
        self.assertEqual(status,200);self.assertEqual(obj['kind'],'prospect')
        tools=self.tools(oid);tools.call('get_object',{})
        sources=tools.call('list_sources',{})
        linked=next((source for source in sources if source['role']=='linked-business-source'),None)
        self.assertIsNotNone(linked,'Research task must expose the actual linked original, not merely save origin_object_id')
        original=tools.call('read_source',{'path':linked['path']})
        self.assertIn('ORIGINAL_MESSAGE_UNIQUE_5912',original['content'])

    def test_order_buyer_http_and_mcp_read_preserve_order_not_inquiry_semantics(self):
        client=OrderClient();source=AlibabaCustomerSource(self.root,client=client,clock=lambda:1000,page_size=5)
        source.refresh(wait=True);self.app.business.alibaba=source
        status,index=self.request('/api/desk/objects?kind=customer')
        self.assertEqual(status,200)
        rows=[row for row in index['objects'] if row.get('source_type')=='alibaba_order_buyer'];self.assertEqual(len(rows),1)
        oid=rows[0]['id'];status,obj=self.request('/api/desk/object?'+urlencode({'id':oid}))
        self.assertEqual(status,200);self.assertIn('不代表新询盘',obj['summary'])
        tools=self.tools(oid);tools.call('get_object',{})
        origin=next(row for row in tools.call('list_sources',{}) if row['role']=='current-object-source')
        raw=json.loads(tools.call('read_source',{'path':origin['path']})['content'])
        self.assertEqual(raw['source_kind'],'alibaba_order_buyer');self.assertEqual(raw['orders'][0]['id'],'71')
        self.assertEqual(raw['orders'][0]['products'][0]['quantity'],'12')
        self.assertEqual([method for method,params in client.calls],[LIST,GET])
        status,profile=self.request('/api/desk/customer-profile?'+urlencode({'object_id':oid}))
        self.assertEqual(status,200);self.assertEqual(profile['source_type'],'alibaba_order_buyer')
        self.assertEqual(profile['provenance']['acquisition'],'unknown')

    def test_customer_analysis_mode_http_passes_through_and_saves_only_profile(self):
        created=self.intake('We need 500 pairs of samples. Please confirm shoe specifications and sample fee.');oid=created['object_id']
        self.fixture.options={'content':json.dumps(analysis_response(),ensure_ascii=False)}
        status,job=self.request('/api/desk/jobs',{'object_id':oid,'instruction':'完整翻译和清洗分析，不外发','mode':'customer_analysis'})
        self.assertEqual(status,201);self.assertEqual(job['mode'],'customer_analysis')
        done=self.fixture.wait_job(job['id']);self.assertEqual(done['status'],'completed');self.assertTrue(done['profile_saved'])
        self.assertIsNone(done['artifact_id'])
        status,profile=self.request('/api/desk/customer-profile?'+urlencode({'object_id':oid}))
        self.assertEqual(status,200);self.assertEqual(profile['translation_zh'],analysis_response()['translation_zh'])
        self.assertEqual(self.request('/api/desk/artifacts?'+urlencode({'object_id':oid}))[1]['artifacts'],[])
        self.assertEqual(self.app.inquiry_intake.get_record(created['record']['id'])['original_text'],created['record']['original_text'])
        self.assertEqual(self.request('/api/desk/jobs',{'object_id':oid,'instruction':'Not supported','mode':'send_email'})[0],400)

    def test_customer_scoped_mcp_can_find_and_read_products_without_other_customer_exposure(self):
        oid=self.intake()['object_id'];tools=self.tools(oid)
        products=tools.call('list_objects',{'kind':'product','q':'Fixture supplier'})
        self.assertEqual([item['id'] for item in products],['product:BQ009']);self.assertLessEqual(len(products),20)
        selected=tools.call('read_product',{'product_id':'BQ009'})
        self.assertEqual(selected['object']['id'],'product:BQ009')
        source=next(row for row in selected['sources'] if row['role']=='current-object-source')
        raw=tools.call('read_product',{'product_id':'BQ009','source_path':source['path']})
        self.assertIn('BQ009',raw['content']);self.assertIn('ADOPTED',raw['content'])
        self.assertEqual([item['id'] for item in tools.call('list_objects',{'kind':'customer'})],[oid])

if __name__=='__main__':unittest.main()
