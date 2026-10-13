from pathlib import Path
import json,sys
base=Path(__file__).parent
root=Path(r'C:\Users\spq\Desktop\贝强')
code=root/'08_工具链/01_业务脚本/国际站扩品'
registry=json.loads((code/'schema_capabilities.json').read_text(encoding='utf8'))
cases={}
for name in ['2627BSK','805','H219','F2888','936']:
 p=json.loads((base/'six_version_acceptance_resume'/name/'prepared_evidence.json').read_text(encoding='utf8'))
 if not p['content_ready']:continue
 row=next(x for x in registry['content_acceptance_evidence'] if x['editor_observation_id'].startswith(name+'_normal_notice_sha256:'))
 product=p['product_get']['product']
 cases[name]={'registry_row':row,'observed_at':row['observed_at'],'schema_xml':p['schema_xml'],
  'formal_get':{'request_id':p['formal_get_request'],'product':{k:product[k] for k in ['product_id','category_id','status','display','keywords','struct_detail']}},
  'public_text':p['summary'],'public_text_source':'Exact whole body verified in hash-bound visible public UIA source; not synthesized response.',
  'formal_get_observed_at':p['formal_get_at_utc'],'fresh_formal_recheck':p.get('fresh_formal_recheck')}
 cases[name]['formal_get']['product']['struct_detail']={'product_summary':p['summary']}
fixture=code/'schema_contract_fixtures/current_content_six_20261003.json'
fixture.write_text(json.dumps({'scope':'Same UTC day, exact observed products/categories only; legacy keyword evidence date explicit; no platform writes.', 'cases':cases},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
test=code/'test_six_current_content_acceptance.py'
text='''"""Actual observed content snapshots. Pure offline, no platform client."""
from pathlib import Path
from copy import deepcopy
import json, unittest
from xml.etree import ElementTree as E
import schema_publish_contract as contract

class SixCurrentContentAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=json.loads((Path(__file__).parent/'schema_contract_fixtures/current_content_six_20261003.json').read_text(encoding='utf8'))['cases']
    def evaluate(self, case, **changes):
        row=case['registry_row']
        args=dict(product_id=row['product_id'],category_id=row['category_id'],editor_observation_id=row['editor_observation_id'],observed_at=case['observed_at'])
        args.update(changes)
        return contract.evaluate_versioned_content(E.fromstring(case['schema_xml']),case['formal_get'],case['public_text'],**args)
    def test_registered_actual_current_chains_pass_without_keyword_or_retirement_claims(self):
        self.assertGreaterEqual(len(self.cases),4)
        for name, case in self.cases.items():
            with self.subTest(product=name):
                result=self.evaluate(case)
                self.assertEqual(result['status'],'product_summary_verified')
                self.assertEqual(result['summary_characters'],len(case['public_text']))
                self.assertFalse(result['keyword_write_verified'])
                self.assertFalse(result['replacement_closeout_verified'])
    def test_new_observations_still_require_exact_product_date_and_public_body(self):
        for name,case in self.cases.items():
            for change in [{'observed_at':'2026-10-04T12:00:00Z'}, {'product_id':'unverified-product'}, {'editor_observation_id':'unobserved-editor'}]:
                with self.subTest(product=name,change=change):
                    self.assertEqual(self.evaluate(case,**change)['status'],'content_version_unverified')
            missing=deepcopy(case);missing['public_text']='Public evidence not captured'
            self.assertEqual(self.evaluate(missing)['status'],'selling_point_content_pending')

if __name__=='__main__':
    unittest.main()
'''
if test.exists():assert test.read_text(encoding='utf8')==text,'Concurrent or prior test differs'
else:test.write_text(text,encoding='utf8')
print(json.dumps({'fixture_cases':list(cases),'files':[str(fixture),str(test)]},ensure_ascii=False))
