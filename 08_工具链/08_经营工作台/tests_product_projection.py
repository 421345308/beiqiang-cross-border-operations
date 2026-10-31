import unittest
from unittest.mock import patch
from tests_business import BusinessTests
class ProductProjectionTests(BusinessTests):
    def test_current_model_and_reference_source_are_distinct_in_list(self):
        self.product()
        import json
        from business import PRODUCTS
        rows=json.loads((self.root/PRODUCTS).read_text(encoding='utf8'))
        product=rows['products'][0]
        product['current_model']='BQ1001'
        product['reference_source_id']=product.pop('adopted_source_id')
        product['source_state']='HOLD_SOURCE'
        self.write(PRODUCTS,rows)
        obj=self.business.list_objects('product')[0]
        self.assertEqual(obj['current_model'],'BQ1001')
        self.assertEqual(obj['title'],'BQ1001')
        self.assertEqual(obj['source_role'],'reference')
        self.assertEqual(obj['source_state'],'HOLD_SOURCE')
        self.assertIn('历史参考',obj['links'][0]['label'])
        self.assertEqual(obj['publication_disposition'],{})

    def test_current_model_assets_are_joined_deduplicated_and_main_image_first(self):
        self.product()
        import json
        from business import PRODUCTS,ASSETS
        rows=json.loads((self.root/PRODUCTS).read_text(encoding='utf8'))
        rows['products'][0]['id']='HR001'
        rows['products'][0]['current_model']='BQ1001'
        self.write(PRODUCTS,rows)
        main={'file':'01_产品资产/main.jpg','products':['HR001','BQ1001'],'roles':['Alibaba main 1']}
        detail={'file':'01_产品资产/detail.jpg','products':['BQ1001'],'roles':['Website outsole']}
        self.write(ASSETS,{'files':[detail,main]})
        obj=self.business.get_object('product:HR001')
        self.assertEqual([x['path'] for x in obj['assets']],['01_产品资产/main.jpg','01_产品资产/detail.jpg'])
        self.assertEqual(self.business.list_objects('product')[0]['assets'][0]['path'],'01_产品资产/main.jpg')

    def test_identity_and_conversation(self):
        self.product()
        import json
        rows=json.loads((self.root/'00_总控台/产品中心/数据/产品.json').read_text(encoding='utf8'))
        rows['products'][0]['notes']=['HR001 historical reference']
        rows['products'].append({'id':'HR001','source_state':'HOLD_SOURCE'})
        from business import PRODUCTS
        self.write(PRODUCTS,rows)
        objects=self.business.list_objects('product')
        self.assertEqual([o['product_series'] for o in objects],['其他','HR'])
        row={'reference':'REAL','messages':[{'sender':'buyer','body':'Need black','sentAt':'2026-10-31'}]}
        original=json.dumps(row)
        with patch.object(self.website,'records',return_value=[row]):
            self.assertEqual(self.business.get_object('customer:website-REAL')['conversation'],[{'sender':'buyer','body':'Need black','sent_at':'2026-10-31'}])
        self.assertEqual(json.dumps(row),original)
        with patch.object(self.website,'records',return_value=[{'reference':'EMPTY'}]):
            self.assertEqual(self.business.get_object('customer:website-EMPTY')['conversation'],[])
if __name__=='__main__':unittest.main()
