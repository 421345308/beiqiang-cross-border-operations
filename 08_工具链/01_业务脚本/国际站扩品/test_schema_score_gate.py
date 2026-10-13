"""Score is a post-publish completion gate, separate from content/source truth."""
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import unittest
import contextlib
import io
import sys
import tempfile
import hashlib
from unittest.mock import patch
from xml.etree import ElementTree as ET

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('score_contract',HERE/'schema_publish_contract.py')
contract=importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

class ScoreGateTests(unittest.TestCase):
    def gate(self, score, checks=None, diagnostics=None):
        return contract.post_publish_acceptance(
            {k:True for k in contract.COMPLETION_CHECKS} if checks is None else checks,
            actual_score=score, observed_at='2026-10-02T10:00:00+00:00' if score is not None else None,
            score_source={'method':'alibaba.icbu.product.score.get','request_id':'OFFLINE_TEST'} if score is not None else None,
            diagnostics={'status':'clear','details':{}} if diagnostics is None else diagnostics)
    def test_missing_score_is_pending(self):
        result=self.gate(None)
        self.assertEqual(result['target_score'],5.0)
        self.assertIsNone(result['actual_score'])
        self.assertEqual(result['overall_status'],'PENDING_SCORE')
    def test_4_9_requires_diagnostic_optimization(self):
        result=self.gate(4.9,diagnostics={'status':'available','details':{'inventory':True}})
        self.assertEqual(result['overall_status'],'PENDING_OPTIMIZATION')
        self.assertTrue(result['diagnostics']['details']['inventory'])
    def test_5_0_requires_all_other_evidence(self):
        self.assertEqual(self.gate(5.0)['overall_status'],'PASS')
        for field in contract.COMPLETION_CHECKS:
            checks={k:True for k in contract.COMPLETION_CHECKS}
            checks[field]=None
            self.assertEqual(self.gate(5.0,checks)['overall_status'],'PENDING_CONTENT')
    def test_5_0_without_metadata_or_diagnostics_cannot_pass(self):
        checks={k:True for k in contract.COMPLETION_CHECKS}
        self.assertEqual(contract.post_publish_acceptance(checks,actual_score=5.0)['overall_status'],'PENDING_SCORE_EVIDENCE')
        self.assertEqual(self.gate(5.0,diagnostics={'status':'not_read'})['overall_status'],'PENDING_DIAGNOSTICS')
    def test_266_has_no_guessed_score(self):
        registry=json.loads((HERE/'schema_capabilities.json').read_text(encoding='utf-8'))
        row=next(r for r in registry['evidence'] if r['product_id']=='1601969707634')
        score=row['post_publish_acceptance']
        self.assertEqual(score['target_score'],5.0)
        for key in ('actual_score','observed_at','score_source'):
            self.assertIsNone(score[key])
        self.assertEqual(score['overall_status'],'PENDING_SCORE')
    def test_first_publish_does_not_require_a_score(self):
        spec=importlib.util.spec_from_file_location('actual_publisher_score_test',HERE/'publish_hot_rank_hr_a_batch.py')
        publisher=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publisher)
        listing=publisher.prepare_scoped_listing(ET.fromstring('<itemSchema><field id="productTitle"><value>old</value></field><field id="icbuCatProp" type="complex"><fields><field id="p-3" name="Model Number" type="input"/></fields></field></itemSchema>'),ET.fromstring('<itemSchema><field id="productTitle"><value>new</value></field><field id="icbuCatProp" type="complex"/></itemSchema>'),operation='create',category_id=32211,field_ids=['productTitle','icbuCatProp'],expected_model='OFFLINE_MODEL')
        class MemoryClient:
            calls=0
            def top_call(self,config,method,params):
                self.calls+=1
                return {'biz_success':True,'product_id':123}
            def api_error(self,response):
                return None
        client=MemoryClient()
        result=publisher.api_submit(client,{},listing,False)
        self.assertEqual(client.calls,1)
        self.assertEqual(result['status'],'submitted_needs_readback')
        self.assertEqual(result['post_publish_acceptance']['overall_status'],'PENDING_SCORE')

    def test_real_verify_cli_does_not_pass_low_score_or_unverified_public_content(self):
        spec=importlib.util.spec_from_file_location('actual_scored_verify_cli',HERE/'publish_hot_rank_hr_a_batch.py')
        publisher=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publisher)
        xml='<itemSchema><field id="productTitle"><value>verified</value></field></itemSchema>'
        attempted=datetime.now(timezone.utc)
        acquired=(attempted+timedelta(seconds=1)).isoformat()
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            (directory/'formal.xml').write_text(xml,encoding='utf-8')
            receipt={'operation':'update','product_id':'123','status':'submitted_needs_readback','attempted_at':attempted.isoformat(),
                     'expected_fields':publisher.field_snapshot(ET.fromstring(xml))}
            (directory/'receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
            for score,public,expected_code in ((4.9,True,2),(5.0,None,2),(5.0,True,0)):
                evidence={'product_id':'123','request_id':'OFFLINE_FORMAL','acquired_at':acquired,
                    'schema_file':'formal.xml','schema_sha256':hashlib.sha256((directory/'formal.xml').read_bytes()).hexdigest(),
                    'content_checks':{k:True for k in contract.COMPLETION_CHECKS if k!='formal_fields'},
                    'post_publish_score':{'actual_score':score,'observed_at':acquired,
                        'score_source':{'method':'alibaba.icbu.product.score.get','request_id':'OFFLINE_SCORE'},
                        'diagnostics':{'status':'clear'}}}
                evidence['content_checks']['public_page']=public
                (directory/'evidence.json').write_text(json.dumps(evidence),encoding='utf-8')
                argv=[str(HERE/'publish_hot_rank_hr_a_batch.py'),'--mode','verify','--product-id','123',
                      '--receipt',str(directory/'receipt.json'),'--formal-readback',str(directory/'evidence.json')]
                with patch.object(sys,'argv',argv),patch.object(publisher,'load_client') as loader,contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(publisher.main(),expected_code)
                    loader.assert_not_called()

if __name__=='__main__':
    unittest.main()
