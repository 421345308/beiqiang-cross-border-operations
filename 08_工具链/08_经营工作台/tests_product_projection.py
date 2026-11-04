import unittest
from unittest.mock import patch
from tests_business import BusinessTests
class ProductProjectionTests(BusinessTests):
    def test_cross_channel_projection_uses_only_explicit_product_ids(self):
        from business import DOUYIN_CHANNEL, WEBSITE_CATALOG
        self.product()
        self.write(DOUYIN_CHANNEL,{'stores':[{'key':'old','name':'旧店'},{'key':'new','name':'新店'}],'listings':[
            {'product_id':'BQ009','identity_state':'MATCHED_SOURCE_MODEL','store_key':'old','source_model':'A1','version':'加绒','observation':{'record_updated_on':'2026-10-15'}},
            {'product_id':'BQ009','identity_state':'MATCHED_EXPLICIT_PRODUCT_AND_SOURCE_EVIDENCE','store_key':'new','source_model':'A1-R','version':'常规'},
            {'product_id':None,'identity_state':'PENDING_CANONICAL_BINDING','source_model':'BQ009'},
            {'product_id':'BQ009','identity_state':'PENDING_CANONICAL_BINDING','source_model':'unconfirmed'}]})
        self.write(WEBSITE_CATALOG,[{'code':'BQ009','slug':'bq009'},{'code':'BQ-009','slug':'other'}])
        channels=self.business.get_object('product:BQ009')['other_channels']
        self.assertEqual([v['version'] for v in channels['douyin']['listings']],['加绒','常规'])
        self.assertEqual(channels['douyin']['listings'][0]['observation']['record_updated_on'],'2026-10-15')
        self.assertEqual(channels['website']['url'],'https://www.beiqiang.online/products/bq009/')
        self.write(WEBSITE_CATALOG,[{'code':'BQ009','slug':'bq009'},{'code':'BQ009','slug':'another'}])
        website=self.business.get_object('product:BQ009')['other_channels']['website']
        self.assertEqual(website['state'],'ambiguous');self.assertEqual(website['url'],'')

    def test_cross_channel_missing_source_is_not_offline_status(self):
        self.product();channels=self.business.get_object('product:BQ009')['other_channels']
        self.assertFalse(channels['douyin']['source_available'])
        self.assertEqual(channels['website']['state'],'source_unavailable')

    def test_unavailable_product_shows_replacement_status(self):
        self.product()
        import json
        from business import PRODUCTS
        rows=json.loads((self.root/PRODUCTS).read_text(encoding='utf8'))
        rows['products'][0]['publication_disposition']={'state':'OWNER_REPORTED_UNAVAILABLE_REPLACEMENT_PENDING'}
        self.write(PRODUCTS,rows)
        self.assertIn('暂停新推荐',self.business.list_objects('product')[0]['summary'])

    def test_pending_replacement_is_visible_without_overwriting_formal_fields(self):
        self.product()
        import json
        from business import CHANNEL
        data=json.loads((self.root/CHANNEL).read_text(encoding='utf8'))
        listing=data['listings'][0]
        listing['pending_replacement']={'state':'SUBMITTED_REVIEW_PENDING','source_model':'1533','observed_at':'2026-11-03'}
        self.write(CHANNEL,data)
        obj=self.business.get_object('product:BQ009')
        self.assertTrue(any(f['label'].startswith('换款审核') and '1533' in f['value'] for f in obj['facts']))
        self.assertEqual(obj['channel_listings'][0]['pending_replacement']['state'],'SUBMITTED_REVIEW_PENDING')

    def test_family_replacement_progress_warns_while_previous_source_is_retained(self):
        self.product()
        import json
        from business import CHANNEL
        data=json.loads((self.root/CHANNEL).read_text(encoding='utf8'))
        data['product_state']={'BQ009':{'replacement_progress':{'state':'IN_REVIEW','note':'新款审核中'}}}
        self.write(CHANNEL,data)
        obj=self.business.get_object('product:BQ009')
        self.assertIn('换款进行中',obj['summary'])
        self.assertTrue(any(f['label']=='换款进度' and f['value']=='新款审核中' for f in obj['facts']))

    def test_new_product_submission_is_shown_as_pending_review(self):
        self.product()
        import json
        from business import PRODUCTS
        rows=json.loads((self.root/PRODUCTS).read_text(encoding='utf8'))
        rows['products'][0]['publication_disposition']={'state':'NEW_SUBMITTED_REVIEW_PENDING'}
        self.write(PRODUCTS,rows)
        self.assertEqual(self.business.get_object('product:BQ009')['summary'],'新商品已提交 · 平台审核中')

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

    def test_historical_hr_identity_without_current_model_is_not_a_current_sku(self):
        self.product()
        import json
        from business import PRODUCTS
        rows=json.loads((self.root/PRODUCTS).read_text(encoding='utf8'))
        rows['products'][0].update({'id':'HR022','aliases':['HR022']})
        rows['products'][0].pop('current_model',None)
        self.write(PRODUCTS,rows)
        obj=self.business.get_object('product:HR022')
        self.assertEqual(obj['title'],'历史档案 · HR022')
        self.assertEqual(obj['current_model'],'')
        self.assertIn('当前型号未核',obj['summary'])
        self.assertEqual(obj['aliases'],['HR022'])

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
