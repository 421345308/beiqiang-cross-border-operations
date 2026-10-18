"""Real migrated content evidence; offline tests never load a platform client."""
from pathlib import Path
from copy import deepcopy
import contextlib,hashlib,importlib.util,io,json,sys,tempfile,unittest
from unittest.mock import patch
from xml.etree import ElementTree as E
import schema_publish_contract as c

HERE=Path(__file__).parent
class VersionedContentTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.fx=json.loads((HERE/'schema_contract_fixtures/keyword_migration_20261003.json').read_text(encoding='utf-8'))
 def evaluate(self,**changes):
  x=self.fx['M001'];kwargs=dict(product_id=x['registry_row']['product_id'],category_id=x['registry_row']['category_id'],editor_observation_id=x['registry_row']['editor_observation_id'],observed_at=x['observed_at'])
  schema=changes.pop('schema',E.fromstring(x['schema_xml']));get=changes.pop('get',deepcopy(x['formal_get']));text=changes.pop('public_text',x['public_text']);kwargs.update(changes)
  return c.evaluate_versioned_content(schema,get,text,**kwargs)
 def gate(self,result):
  checks={k:True for k in c.COMPLETION_CHECKS};checks['keyword_persistence']=False
  return c.post_publish_acceptance(checks,actual_score=5.0,observed_at=self.fx['M001']['observed_at'],score_source={'kind':'offline_actual_ui_score_fixture'},diagnostics={'status':'clear'},versioned_content=result)
 def test_real_660_character_chain_passes_content_without_faking_keyword_restore(self):
  result=self.evaluate();self.assertEqual(result['status'],'product_summary_verified');self.assertEqual(result['summary_characters'],660)
  self.assertEqual(result['legacy_keywords'],['']);self.assertFalse(result['keyword_write_verified']);self.assertFalse(result['replacement_closeout_verified'])
  gate=self.gate(result);self.assertEqual(gate['overall_status'],'PASS');self.assertNotIn('keyword_persistence',gate['required_content_checks'])
 def test_single_product_observation_cannot_release_other_products_categories_dates(self):
  for change in [{'product_id':'1601969877983'},{'category_id':'201334413'},{'editor_observation_id':'unobserved_new_editor'},{'observed_at':'2026-10-04T16:40:00+00:00'}]:
   with self.subTest(change=change):
    result=self.evaluate(**change);self.assertEqual(result['status'],'content_version_unverified');self.assertEqual(self.gate(result)['overall_status'],'PENDING_CONTENT')
 def test_empty_wrong_pending_and_missing_public_summary_never_pass(self):
  for key,value in [('status','modified'),('display','N'),('product_id','WRONG_BOUND_TARGET')]:
   get=deepcopy(self.fx['M001']['formal_get']);get['product'][key]=value
   self.assertNotEqual(self.evaluate(get=get)['status'],'product_summary_verified')
  for text in ['', 'Different shoe material']:
   get=deepcopy(self.fx['M001']['formal_get']);get['product']['struct_detail']['product_summary']=text
   self.assertNotEqual(self.evaluate(get=get)['status'],'product_summary_verified')
  self.assertNotEqual(self.evaluate(public_text='No verified public body')['status'],'product_summary_verified')
 def test_changed_three_way_text_cannot_reuse_old_ui_proof_and_business_failure_cannot_pass(self):
  get=deepcopy(self.fx['M001']['formal_get']);schema=E.fromstring(self.fx['M001']['schema_xml'])
  get['product']['struct_detail']['product_summary']='A changed summary';schema.find('./field/value').text='A changed summary'
  self.assertNotEqual(self.evaluate(get=get,schema=schema,public_text='A changed summary')['status'],'product_summary_verified')
  for failure in [{'biz_success':False},{'error_response':{'code':'ApiCallLimit'}}]:
   get=deepcopy(self.fx['M001']['formal_get']);get.update(failure)
   self.assertNotEqual(self.evaluate(get=get)['status'],'product_summary_verified')
  self.assertEqual(self.evaluate(observed_at='2026-10-04T00:40:29+08:00')['status'],'product_summary_verified')
 def test_actual_ui_notice_only_2627_stays_pending(self):
  row=self.fx['2627BSK']['registry_row']
  result=self.evaluate(product_id=row['product_id'],editor_observation_id=row['editor_observation_id'])
  self.assertEqual(result['target'],'product_summary');self.assertEqual(result['status'],'selling_point_content_pending');self.assertEqual(self.gate(result)['overall_status'],'PENDING_CONTENT')
 def test_source_hash_corruption_does_not_release_content(self):
  row=deepcopy(self.fx['M001']['registry_row']);row['sources'][0]['sha256']='0'*64
  result=self.evaluate(registry={'content_acceptance_evidence':[row]});self.assertEqual(result['status'],'content_version_unverified')
 def test_current_schema_length_is_dynamic_and_unknown_unit_not_guessed(self):
  schema=E.fromstring(self.fx['M001']['schema_xml']);field=schema.find('./field')
  rules=field.find('rules')
  if rules is None:rules=E.SubElement(field,'rules')
  E.SubElement(rules,'rule',{'name':'maxLengthRule','value':'3','unit':'byte'})
  self.assertNotEqual(self.evaluate(schema=schema)['status'],'product_summary_verified')
  rules[-1].attrib.pop('unit')
  result=self.evaluate(schema=schema);self.assertEqual(result['status'],'product_summary_verified')
  self.assertTrue(any(x.get('interpretation') for x in result['constraints']))
 def test_whole_content_ignores_only_legacy_keyword_but_explicit_keyword_request_stays_strict(self):
  result=self.evaluate();expected={'productKeywords':('actual historical desired keyword',),'productTitle':('same',)};formal={'productKeywords':('empty',),'productTitle':('same',)}
  self.assertEqual(c.verify_content_details('submitted_needs_readback',expected,formal,versioned_content=result)['content_status'],'formal_fields_verified')
  formal['productTitle']=('wrong',)
  self.assertEqual(c.verify_content_details('submitted_needs_readback',expected,formal,versioned_content=result)['content_status'],'content_mismatch_or_noop')
  self.assertEqual(c.verify_content_details('submitted_needs_readback',{'productKeywords':expected['productKeywords']},formal,versioned_content=result)['content_status'],'content_mismatch_or_noop')
  self.assertEqual(c.verify_content_details('business_rejected',expected,formal,versioned_content=result)['content_status'],'unverified_content')
 def test_existing_capability_route_exposes_only_the_selected_product_version(self):
  row=self.fx['M001']['registry_row']
  result=c.capability('update','4',row['category_id'],field='productKeywords',product_id=row['product_id'])
  self.assertEqual([r['product_id'] for r in result['content_acceptance_evidence']],[row['product_id']])
  self.assertEqual(result['content_next_step'],'evaluate_versioned_content_with_current_reads')
  self.assertEqual(c.capability('update','4',row['category_id'],field='productKeywords')['content_acceptance_evidence'],[])
  self.assertEqual(c.capability('update','4','201334413',product_id=row['product_id'])['content_acceptance_evidence'],[])
 def test_existing_verify_cli_uses_hash_bound_profile_without_network(self):
  spec=importlib.util.spec_from_file_location('migration_actual_publisher',HERE/'publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(spec);spec.loader.exec_module(pub)
  x=self.fx['M001'];row=x['registry_row'];root=E.fromstring(x['schema_xml'])
  E.SubElement(E.SubElement(root,'field',{'id':'productTitle'}),'value').text='Closed-Toe EVA Mules with Ribbed Sides and Orange Sole Pods'
  keyword=E.SubElement(root,'field',{'id':'productKeywords','type':'complex'});E.SubElement(keyword,'complex-value')
  expected=deepcopy(root);E.SubElement(E.SubElement(expected.find("./field[@id='productKeywords']/complex-value"),'field',{'id':'productKeywords_0','type':'input'}),'value').text='closed toe EVA mules'
  with tempfile.TemporaryDirectory() as directory:
   d=Path(directory);(d/'formal.xml').write_text(E.tostring(root,encoding='unicode'),encoding='utf-8')
   (d/'get.json').write_text(json.dumps(x['formal_get']),encoding='utf-8')
   public_source=next(v for v in row['sources'] if v['kind']=='public_summary');raw=(HERE.resolve().parents[2]/public_source['path']).read_bytes();(d/'public.json').write_bytes(raw)
   receipt={'operation':'update','product_id':row['product_id'],'status':'submitted_needs_readback','attempted_at':'2026-10-03T13:00:00+00:00','expected_fields':c.field_snapshot(expected)};(d/'receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
   evidence={'product_id':row['product_id'],'request_id':x['formal_get']['request_id'],'acquired_at':x['observed_at'],'schema_file':'formal.xml','schema_sha256':hashlib.sha256((d/'formal.xml').read_bytes()).hexdigest(),'content_checks':{k:True for k in c.COMPLETION_CHECKS},'post_publish_score':{'actual_score':5.0,'observed_at':x['observed_at'],'score_source':{'kind':'actual_editor_score_evidence'},'diagnostics':{'status':'clear'}}}
   evidence['content_checks']['keyword_persistence']=False
   profile={'category_id':row['category_id'],'editor_observation_id':row['editor_observation_id'],'formal_get_file':'get.json','formal_get_sha256':hashlib.sha256((d/'get.json').read_bytes()).hexdigest(),'public_text_file':'public.json','public_text_sha256':hashlib.sha256(raw).hexdigest()}
   argv=[str(HERE/'publish_hot_rank_hr_a_batch.py'),'--mode','verify','--product-id',row['product_id'],'--receipt',str(d/'receipt.json'),'--formal-readback',str(d/'evidence.json')]
   for use_profile,code in [(False,2),(True,0)]:
    if use_profile:evidence['content_version']=profile
    (d/'evidence.json').write_text(json.dumps(evidence),encoding='utf-8')
    with patch.object(sys,'argv',argv),patch.object(pub,'load_client') as client,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(pub.main(),code);client.assert_not_called()
   profile['formal_get_sha256']='0'*64;(d/'evidence.json').write_text(json.dumps(evidence),encoding='utf-8')
   with patch.object(sys,'argv',argv),patch.object(pub,'load_client') as client,contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):pub.main()

if __name__=='__main__':unittest.main()
