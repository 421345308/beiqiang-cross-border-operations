"""Create-side omission only: no fabricated stock, defaults or deletion rules."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('create_inventory_contract',HERE/'schema_publish_contract.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class CreateInventoryTests(unittest.TestCase):
 def source_case(self,name):
  return next(r for r in json.loads((HERE/'schema_contract_fixtures/create_inventory_omission_cases.json').read_text(encoding='utf-8'))['cases'] if r['case']==name)
 def prepared(self,payload,schema):
  model_root=ET.fromstring('<field id="icbuCatProp" type="complex"><fields><field id="p-3" name="Model Number" type="input"/></fields></field>')
  schema.append(model_root)
  ET.SubElement(payload,'field',id='icbuCatProp',type='complex')
  return c.prepare_scoped_listing(schema,payload,operation='create',category_id=201153805,
      field_ids=['sku','icbuCatProp'],expected_model='OFFLINE_MODEL')
 def test_actual_5998_optional_omission_stays_omitted_even_with_schema_default(self):
  case=self.source_case('5998');schema=ET.fromstring(case['inventory_schema_xml'])
  stock=schema.find("./field[@id='sku']/fields/field[@id='skuStock']")
  self.assertIsNotNone(stock)
  values=ET.SubElement(stock,'values');ET.SubElement(values,'value',srcValue='999',warehouseCode='CN_LOCAL_01').text='999'
  result=self.prepared(ET.fromstring(case['create_sku_xml']),schema)
  self.assertIsNone(ET.fromstring(result['xml']).find(".//field[@id='skuStock']"))
  record=result['inventory_input']
  self.assertEqual(record['status'],'omitted_all');self.assertEqual(record['raw_present_fields'],[])
  self.assertEqual(len(record['omitted_sku_indexes']),record['sku_count'])
 def test_explicit_stock_is_recorded_exactly_and_not_interpreted_as_physical_count(self):
  for name in ('936','266'):
   case=self.source_case(name)
   result=self.prepared(ET.fromstring(case['create_sku_xml']),ET.fromstring(case['inventory_schema_xml']))
   record=result['inventory_input'];self.assertEqual(record['status'],'explicit_all')
   for row in record['raw_present_fields']:
    self.assertEqual(row['raw_values'][0]['text'],'999')
    self.assertEqual(row['raw_values'][0]['attributes']['srcValue'],'999')
    self.assertEqual(row['raw_values'][0]['attributes']['warehouseCode'],'CN_LOCAL_01')
   self.assertIn('do not establish physical stock',record['limits'])
 def test_required_stock_omission_stops_without_guessing_values(self):
  case=self.source_case('5998');schema=ET.fromstring(case['inventory_schema_xml'])
  stock=schema.find("./field[@id='sku']/fields/field[@id='skuStock']")
  rules=stock.find('./rules');ET.SubElement(rules,'rule',name='requiredRule',value='true')
  with self.assertRaisesRegex(ValueError,'never autofill 999'):
   self.prepared(ET.fromstring(case['create_sku_xml']),schema)
  explicit_empty=ET.fromstring(case['create_sku_xml'])
  for item in explicit_empty.findall('./field/complex-values'):
   ET.SubElement(ET.SubElement(item,'field',id='skuStock',type='multiInput'),'values')
  with self.assertRaisesRegex(ValueError,'never autofill 999'):
   self.prepared(explicit_empty,deepcopy(schema))
 def test_schema_defaults_cannot_be_copied_as_new_product_dependency_facts(self):
  schema=ET.fromstring('<itemSchema><field id="sku"><complex-values><field id="skuStock"><values><value>999</value></values></field></complex-values></field><field id="productTitle"><value>schema default</value></field></itemSchema>')
  payload=ET.fromstring('<itemSchema><field id="productTitle"><value>verified input</value></field></itemSchema>')
  with self.assertRaisesRegex(ValueError,'Schema defaults are not product facts'):
   c.prepare_scoped_listing(schema,payload,operation='create',category_id=1,field_ids=['productTitle'],dependency_ids=['sku'])
 def test_optional_create_omission_does_not_define_existing_inventory_deletion(self):
  root=ET.fromstring('<itemSchema><field id="sku"><complex-values><field id="skuStock"><values/></field></complex-values></field></itemSchema>')
  record=c.create_inventory_input_record(root)
  self.assertEqual(record['status'],'explicit_all');self.assertEqual(record['raw_present_fields'][0]['raw_values'],[])
  self.assertIn('deletion semantics',record['limits'])
  self.assertEqual(ET.tostring(c.values_only(root,operation='update',field_ids=['sku'])),ET.tostring(root))
 def test_raw_observed_score_difference_is_scoped_not_causal(self):
  a=self.source_case('5998');b=self.source_case('936');d=self.source_case('266')
  self.assertTrue(a['request_inventory_omitted']);self.assertTrue(a['formal_stock_lists_empty'])
  self.assertEqual(a['actual_score'],5.0);self.assertFalse(a['inventory_problem_flag'])
  for row in (b,d):
   self.assertFalse(row['request_inventory_omitted']);self.assertEqual(set(row['formal_inventory_values']),{0})
   self.assertEqual(row['actual_score'],3.9);self.assertTrue(row['inventory_problem_flag'])
   self.assertIn('causality',row['limits'])

 def test_actual_submitter_stops_late_stock_injection_and_receipts_preserve_omission(self):
  spec=importlib.util.spec_from_file_location('actual_create_inventory_publisher',HERE/'publish_hot_rank_hr_a_batch.py')
  pub=importlib.util.module_from_spec(spec);spec.loader.exec_module(pub)
  case=self.source_case('5998')
  listing=self.prepared(ET.fromstring(case['create_sku_xml']),ET.fromstring(case['inventory_schema_xml']))
  class MemoryClient:
   calls=0
   def top_call(self,*args):self.calls+=1;return {'biz_success':True,'product_id':123}
   def api_error(self,*args):return None
  client=MemoryClient()
  result=pub.api_submit(client,{},listing,False)
  self.assertEqual(result['inventory_input']['status'],'omitted_all');self.assertEqual(client.calls,1)
  root=ET.fromstring(listing['xml']);item=root.find("./field[@id='sku']/complex-values")
  stock=ET.SubElement(item,'field',id='skuStock',type='multiInput');values=ET.SubElement(stock,'values');ET.SubElement(values,'value',srcValue='999').text='999'
  listing['xml']=ET.tostring(root,encoding='unicode');listing['expected_fields']=pub.field_snapshot(root)
  with self.assertRaisesRegex(ValueError,'inventory changed'):
   pub.api_submit(client,{},listing,False)
  self.assertEqual(client.calls,1)

if __name__=='__main__':unittest.main()
