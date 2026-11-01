import subprocess
import unittest
from unittest.mock import patch
from buyer_discovery import search_buyers
class Tests(unittest.TestCase):
    def test_validation(self):
        for keyword,limit in [('',1),('x',0),('x',True)]:
            with self.assertRaises(ValueError):search_buyers(keyword,limit)
    def test_timeout(self):
        with patch('buyer_discovery.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',1)):
            self.assertEqual(search_buyers()['status'],'timeout')
    def test_failure(self):
        with patch('buyer_discovery.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','private')):
            result=search_buyers();self.assertEqual(result['records'],[]);self.assertNotIn('private',str(result))
    def test_result(self):
        with patch('buyer_discovery.subprocess.run',return_value=subprocess.CompletedProcess([],0,'{"status":"success","records":[]}','')):
            self.assertEqual(search_buyers()['status'],'success')
class PublicSearchTests(unittest.TestCase):
    def test_no_key_makes_no_request(self):
        import buyer_discovery as module
        with patch.dict('os.environ', {}, clear=True), patch.object(module, '_call') as call:
            result=module._worker('footwear',10)
        self.assertEqual(result['status'],'unavailable');call.assert_not_called()

    def test_low_existing_credits_does_not_search(self):
        import buyer_discovery as module
        with patch.dict('os.environ',{'FIRECRAWL_API_KEY':'synthetic-key'}), patch.object(module,'_call',return_value={'data':{'remainingCredits':1}}) as call:
            result=module._worker('footwear',10)
        self.assertEqual(result['status'],'unavailable');self.assertEqual(call.call_count,1)

    def test_sources_identity_and_no_invented_import_statistics(self):
        import buyer_discovery as module
        rows=[{'title':'Synthetic Example Footwear','url':'https://example.test/about','description':'Distributor'},
              {'title':'duplicate','url':'https://example.test/about'},
              {'title':'unsafe','url':'javascript:alert(1)'},
              {'title':'private','url':'https://user:password@example.test/'},'bad']
        with patch.dict('os.environ',{'FIRECRAWL_API_KEY':'synthetic-key'}), patch.object(module,'_call',side_effect=[{'data':{'remainingCredits':10}},{'success':True,'data':{'web':rows},'creditsUsed':2}]) as call:
            result=module._worker('walking shoes',30)
        self.assertEqual(len(result['records']),1)
        record=result['records'][0]
        self.assertEqual(record['source_url'],'https://example.test/about')
        self.assertEqual(record['identity_status'],'unverified')
        self.assertNotIn('shipments',record);self.assertNotIn('website',record)
        self.assertEqual(call.call_args.args[2]['limit'],10)
        self.assertFalse(result['current_demand_confirmed'])

    def test_auth_failure_does_not_expose_secret(self):
        import buyer_discovery as module
        import urllib.error
        with patch.dict('os.environ',{'FIRECRAWL_API_KEY':'synthetic-secret'}), patch.object(module,'_call',side_effect=urllib.error.HTTPError('https://api.firecrawl.dev',401,'synthetic-secret',{},None)):
            result=module._worker('footwear',10)
        self.assertEqual(result['status'],'failed');self.assertNotIn('synthetic-secret',str(result))

    def test_nonobject_worker_protocol_is_failure(self):
        with patch('buyer_discovery.subprocess.run',return_value=subprocess.CompletedProcess([],0,'[]','')):
            self.assertEqual(search_buyers()['status'],'failed')

if __name__=='__main__':unittest.main()
