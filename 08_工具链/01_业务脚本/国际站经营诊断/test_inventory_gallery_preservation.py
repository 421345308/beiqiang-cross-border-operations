"""Protect actual product values while tolerating observed attribute reordering."""
import copy, unittest
from repair_added_sku_marker import retained_product, inventory_rows
from repair_reviewed_gallery import protected

class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.p={'attributes':[{'attribute_id':2,'value_name':'Mesh'}, {'attribute_id':1,'value_name':'Round'}],
            'product_sku':{'skus':[{'sku_id':1,'sku_code':'REAL-35','inventory_dto_list':[{'inventory':0}]}]},
            'main_image':{'images':['original']},'struct_detail':{'detail_image':{'images':['detail']}}}

    def test_inventory_preserves_values_and_only_ignores_quantity(self):
        p=copy.deepcopy(self.p);p['attributes'].reverse();p['product_sku']['skus'][0]['inventory_dto_list'][0]['inventory']=999
        self.assertEqual(retained_product(self.p),retained_product(p))
        p['product_sku']['skus'][0]['sku_code']='WRONG'
        self.assertNotEqual(retained_product(self.p),retained_product(p))

    def test_main_edit_never_hides_inventory_or_material_change(self):
        p=copy.deepcopy(self.p);p['attributes'].reverse();p['main_image']['images']=['new']
        self.assertEqual(protected(self.p,True,False),protected(p,True,False))
        p['attributes'][0]['value_name']='Leather'
        self.assertNotEqual(protected(self.p,True,False),protected(p,True,False))
        p=copy.deepcopy(self.p);p['product_sku']['skus'][0]['inventory_dto_list'][0]['inventory']=999
        self.assertNotEqual(protected(self.p,True,False),protected(p,True,False))

    def test_duplicate_inventory_rows_fail(self):
        with self.assertRaises(AssertionError):inventory_rows({'result':{'data_list':[{'sku_id':1},{'sku_id':1}]}})

if __name__=='__main__':unittest.main()
