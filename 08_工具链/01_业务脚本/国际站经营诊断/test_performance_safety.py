"""Protect attribution and SKU/price coverage before a reversible consolidation."""
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
from copy import deepcopy
import diagnose_product_performance as d
import apply_product_performance_actions as a

class Safety(unittest.TestCase):
 def matrix(self):
  return {'product_sku':{'sku_attributes':[{'attribute_id':1,'values':[{'value_id':11,'custom_value_name':'Grey'}]},{'attribute_id':2,'values':[{'value_id':35,'custom_value_name':'EU 35'}]}],'skus':[{'attr2_value':'{"1":11,"2":35}','bulk_discount_prices':[{'start_quantity':2,'price':'9.49'},{'start_quantity':50,'price':'9.19'}]}]}}
 def test_renumbered_axes_are_compared_semantically(self):
  p=self.matrix();q=deepcopy(p);q['product_sku']['sku_attributes'][0]['values'][0]['value_id']=88;q['product_sku']['skus'][0]['attr2_value']='{"1":88,"2":35}';self.assertEqual(d.sku_matrix(p),d.sku_matrix(q))
 def test_a_colour_or_price_difference_cannot_be_deduplicated(self):
  p=self.matrix();q=deepcopy(p);q['product_sku']['sku_attributes'][0]['values'][0]['custom_value_name']='Black';self.assertNotEqual(d.sku_matrix(p),d.sku_matrix(q));q=deepcopy(p);q['product_sku']['skus'][0]['bulk_discount_prices'][0]['price']='9.45';self.assertNotEqual(d.sku_matrix(p),d.sku_matrix(q))
 def test_unresolved_binding_is_not_empty_equality_proof(self):
  p=self.matrix();p['product_sku']['skus'][0]['attr2_value']='{"1":99,"2":35}';self.assertFalse(d.sku_matrix(p))
 def test_replacement_after_window_invalidates_attribution(self):
  link={'optimization':{'source_replacement':{'at':'2026-10-12T12:00:00+00:00'}}};self.assertFalse(d.compatible(link,'2026-10-10'));self.assertTrue(d.compatible(link,'2026-10-14'))
 def test_source_binding_or_factory_change_does_not_reset_identity(self):
  link={'optimization':{'source_binding_reconciliation':{'at':'2026-10-16'},'model_factory_normalization':{'at':'2026-10-16'}}};self.assertIsNone(d.source_change(link));self.assertTrue(d.compatible(link,'2026-09-30'))
 def test_change_during_or_on_first_day_of_window_is_mixed(self):
  link={'optimization':{'source_replacement':{'at':'2026-10-06T12:00:00+00:00'}}};self.assertFalse(d.compatible(link,'2026-10-04'));self.assertFalse(d.compatible(link,'2026-10-06'));self.assertTrue(d.compatible(link,'2026-10-07'))
 def test_current_plan_never_writes_protected_source(self):
  rows=d.load(a.PLAN)['items'];self.assertFalse(d.PROTECTED&{x['id']for x in rows});self.assertEqual(len({x['id']for x in rows}),len(rows))
 def test_known_ip_rejection_blocks_before_any_api_call(self):
  row={'id':'1601943574507','kind':'repair_custom_attribute','execution_hold':'PLATFORM_IP_REJECTED_OWNER_CONFIRMED'}
  with TemporaryDirectory()as folder,patch.object(a,'BASE',Path(folder)):
   for mode in('prepare','submit'):self.assertEqual(a.operate(row,mode,None,None)['state'],'IP_REJECTION_HOLD_NO_RESUBMIT')

if __name__=='__main__':unittest.main()
