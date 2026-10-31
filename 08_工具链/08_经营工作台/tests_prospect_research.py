import json
import subprocess
import unittest
from unittest.mock import patch

from prospect_research import _core,_seed,_scan,research_company


class Crawler:
    def __init__(self,failed=False):self.failed=failed;self.calls=[]
    def scan(self,seed,max_pages):
        self.calls.append((seed,max_pages))
        page={'url':seed['website'],'final_url':seed['website'],'checked_at':'2026-10-31T00:00:00Z','http_status':403 if self.failed else 200}
        if self.failed:page['error']='访问限制'
        else:page.update(text_sha256='verified-hash',title='Company')
        return {'pages':[page],'checked_at':'2026-10-31T00:00:00Z',
                'analysis':{'signals':{'footwear':{'url':seed['website'],'quote':'We supply casual shoes.'}},'risks':[]}}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.obj={'id':'prospect:existing','kind':'prospect','content':json.dumps({'website':'https://company.example/',
                  'evidence':[{'url':'https://company.example/about'},{'url':'https://another.example/'}]})}

    def test_seed_uses_real_object_urls_and_same_company_evidence_only(self):
        seed=_seed(self.obj,_core())
        self.assertEqual(seed,{'website':'https://company.example/','pages':['https://company.example/about']})
        with self.assertRaises(ValueError):_seed({'kind':'customer','website':'https://company.example/'},_core())
        with self.assertRaises(ValueError):_seed({'kind':'prospect'},_core())

    def test_three_page_cap_and_sourced_chinese_label(self):
        crawler=Crawler();result=_scan({'website':'https://company.example/'},crawler=crawler)
        self.assertEqual(crawler.calls[0][1],3)
        self.assertEqual(result['status'],'success')
        self.assertEqual(result['labels'][0]['label'],'鞋类经营')
        self.assertEqual(result['labels'][0]['excerpt'],'We supply casual shoes.')
        self.assertEqual(result['labels'][0]['url'],'https://company.example/')
        self.assertFalse(result['current_demand_confirmed'])

    def test_failed_page_has_no_success_or_unsupported_labels(self):
        result=_scan({'website':'https://company.example/'},crawler=Crawler(failed=True))
        self.assertEqual(result['status'],'failed')
        self.assertFalse(result['pages'][0]['fetch_success'])
        self.assertEqual(result['pages'][0]['excerpt'],'')
        self.assertEqual(result['labels'],[])

    def test_wall_clock_timeout_kills_actual_worker_and_returns_no_research_claim(self):
        class Process:
            def __init__(self):self.calls=0;self.killed=False
            def communicate(self,*args,**kwargs):
                self.calls+=1
                if self.calls==1:raise subprocess.TimeoutExpired('worker',1)
                return ('','')
            def kill(self):self.killed=True
        proc=Process()
        with patch('prospect_research.subprocess.Popen',return_value=proc):
            result=research_company(self.obj,timeout_seconds=1)
        self.assertTrue(proc.killed);self.assertEqual(result['status'],'timeout')
        self.assertEqual(result['pages'],[]);self.assertEqual(result['labels'],[])

    def test_worker_result_propagates_observed_date_and_object_id(self):
        class Process:
            returncode=0
            def communicate(self,*args,**kwargs):return (json.dumps({'status':'partial','fetched_at':'actual-date','pages':[]}), '')
        with patch('prospect_research.subprocess.Popen',return_value=Process()):
            result=research_company(self.obj)
        self.assertEqual(result['object_id'],'prospect:existing')
        self.assertEqual(result['fetched_at'],'actual-date')


if __name__=='__main__':unittest.main()
