"""Regression for observed unordered formal gallery rows, never field deletion."""
import unittest
from copy import deepcopy
import normalize_models_factory_gallery as n
class Preservation(unittest.TestCase):
 def test_partial_category_payload_rejected_before_schema_or_network(self):
  from xml.etree import ElementTree as E
  with self.assertRaisesRegex(ValueError,'category update requires'):
   n.contract.prepare_scoped_listing(E.fromstring('<itemSchema/>'),E.fromstring('<itemSchema/>'),operation='update',category_id=1,target_product_id='1',field_ids=['catId'])
 def test_sku_reordering_never_excuses_lost_rows_or_price_changes(self):
  before={'skus':[{'sku_id':1,'sku_code':'a','price':'5'},{'sku_id':2,'sku_code':'b','price':'6'}],'sku_attributes':[{'attribute_id':2,'values':[{'value_id':4},{'value_id':5}]}]}
  after=deepcopy(before);after['skus'].reverse();after['sku_attributes'][0]['values'].reverse()
  self.assertEqual(n.canonical_skus(before),n.canonical_skus(after))
  after['skus'][0]['sku_id']=20;self.assertNotEqual(n.canonical_skus(before),n.canonical_skus(after));self.assertEqual(n.canonical_skus(before,True),n.canonical_skus(after,True))
  after['skus'][0]['price']='1';self.assertNotEqual(n.canonical_skus(before,True),n.canonical_skus(after,True))
  after['skus'].pop();self.assertNotEqual(n.canonical_skus(before,True),n.canonical_skus(after,True))
 def setUp(self):
  self.p={'status':'approved','display':'Y','subject':'Exact shoe','main_image':{'images':['old']},'attributes':[{'attribute_id':3,'value_name':'HR030-A'},{'attribute_id':1,'value_name':'CN'}],'struct_detail':{'company_image':{'images':[{'image_set':{'id':700,'name':'Packing'},'image_url':'https://a/one.png'},{'image_set':{'id':400,'name':'Company'},'image_url':'https://a/two.png'}]},'product_summary':'Exact verified copy'},'product_sku':{'skus':[{'sku_id':1,'sku_code':'HR030-A-BLACK-EU39','bulk_discount_prices':[{'start_quantity':2,'price':'9.48'}]}]}}
 def test_unordered_full_rows_are_equivalent(self):
  after=deepcopy(self.p);after['struct_detail']['company_image']['images'].reverse();self.assertEqual(n.clean_product(after),n.clean_product(self.p))
 def test_lost_or_rebound_company_picture_fails(self):
  for mutate in ('lost','role','url'):
   after=deepcopy(self.p);rows=after['struct_detail']['company_image']['images']
   if mutate=='lost':rows.pop()
   elif mutate=='role':rows[0]['image_set']['id']=400
   else:rows[0]['image_url']='https://a/wrong.png'
   self.assertNotEqual(n.clean_product(after),n.clean_product(self.p))
 def test_model_scope_preserves_prices_sizes_and_copy(self):
  after=deepcopy(self.p);after['attributes'][0]['value_name']='BQ1030-A';after['product_sku']['skus'][0]['sku_code']='BQ1030-A-BLACK-EU39';self.assertEqual(n.clean_product(after,True),n.clean_product(self.p,True))
  for field in ('price','sku_id','summary'):
   broken=deepcopy(after)
   if field=='price':broken['product_sku']['skus'][0]['bulk_discount_prices'][0]['price']='1.00'
   elif field=='sku_id':broken['product_sku']['skus'][0]['sku_id']=2
   else:broken['struct_detail']['product_summary']='Other shoe'
   self.assertNotEqual(n.clean_product(broken,True),n.clean_product(self.p,True))
if __name__=='__main__':unittest.main()
