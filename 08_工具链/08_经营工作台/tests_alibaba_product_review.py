import unittest
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
from alibaba_product_review import AlibabaProductReview


class ProductReviewTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.clock=1000
        self.rows=[{'id':'123','product_id':'shoe-1','url':'https://www.alibaba.com/product-detail/Test_123.html',
                    'current_platform_fields':{'title':'Old title','main_images':['https://sc04.alicdn.com/a.jpg'],
                                               'detail_images':[{'image_url':'https://sc04.alicdn.com/d.jpg'}],'at':'2026-01-01'}},
                   {'id':'456','product_id':'shoe-1','current_platform_fields':{'title':'Second'}},
                   {'id':'999','product_id':'different','current_platform_fields':{'title':'Other'}}]
        self.raw={'product':{'id':'123','subject':'Live title','status':'approved','display':'Y',
            'pc_detail_url':'https://www.alibaba.com/product-detail/Test_123.html',
            'main_image':{'images':['https://sc04.alicdn.com/a.jpg']},
            'struct_detail':{'detail_image':{'images':[{'image_url':'https://sc04.alicdn.com/d.jpg','image_set':{'name':'Detail shot'}}]},
                             'company_image':{'images':[{'image_url':'https://sc04.alicdn.com/company.jpg'}]}}}}
        business=SimpleNamespace(get_object=lambda oid:{'id':oid,'kind':'product'},_json=lambda path,key:self.rows)
        self.client=SimpleNamespace(call=self.call,safe=lambda value:value)
        self.service=AlibabaProductReview(SimpleNamespace(business=business),client=self.client,clock=lambda:self.clock)
    def call(self,method,params):
        self.calls.append((method,params));return self.raw
    def test_live_images_and_title_are_compared_per_listing(self):
        result=self.service.get('product:shoe-1');self.assertEqual([x['id'] for x in result['listings']],['123','456'])
        row=result['selected'];self.assertEqual(row['platform']['title'],'Live title')
        self.assertEqual(row['comparison'],{'title':'different','main_images':'same','detail_images':'same'})
        self.assertEqual(len(row['platform']['company_images']),1)
        self.assertEqual(self.calls[0][0],'alibaba.icbu.product.get')
    def test_unknown_local_detail_is_not_called_a_difference(self):
        self.rows[0]['current_platform_fields'].pop('detail_images')
        self.assertEqual(self.service.get('product:shoe-1')['selected']['comparison']['detail_images'],'not_recorded')
    def test_missing_platform_field_is_not_treated_as_an_empty_gallery(self):
        self.raw['product'].pop('main_image');self.raw['product']['struct_detail']={}
        row=self.service.get('product:shoe-1')['selected']
        self.assertEqual(row['comparison']['main_images'],'unavailable');self.assertEqual(row['comparison']['detail_images'],'unavailable')
    def test_no_link_and_other_products_are_never_mixed(self):
        self.assertIsNone(self.service.get('product:no-listings')['selected'])
        with self.assertRaises(ValueError):self.service.get('product:shoe-1','999')
    def test_failed_or_wrong_identity_never_claims_live_data(self):
        self.raw['product']['id']='999'
        row=self.service.get('product:shoe-1')['selected'];self.assertEqual(row['state'],'error');self.assertIsNone(row['platform'])
        self.assertEqual(row['local']['title'],'Old title')
    def test_cache_and_explicit_refresh(self):
        self.service.get('product:shoe-1');self.service.get('product:shoe-1');self.assertEqual(len(self.calls),1)
        self.service.get('product:shoe-1',refresh=True);self.assertEqual(len(self.calls),2)
    def test_html_detail_images_are_extracted_without_rendering_html(self):
        self.raw['product']['struct_detail']={};self.raw['product']['description']='<p>Hello<img src="//sc04.alicdn.com/photo.png"></p>'
        self.assertEqual(self.service.get('product:shoe-1')['selected']['platform']['detail_images'][0]['url'],'https://sc04.alicdn.com/photo.png')
    def test_title_translation_is_cached_for_the_actual_title(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        db=sqlite3.connect(':memory:',check_same_thread=False);self.addCleanup(db.close)
        event=threading.Event()
        def translate(rows):
            event.set();return [{'id':rows[0]['id'],'subject_zh':'实际平台标题的中文翻译','body_zh':''}]
        app=SimpleNamespace(business=self.service.app.business,db=db,lock=threading.RLock(),state=temp.name)
        service=AlibabaProductReview(app,client=self.client,translate=translate)
        first=service.get('product:shoe-1')['selected']['platform']['title_zh'];self.assertEqual(first['state'],'translating')
        self.assertTrue(event.wait(2))
        for thread in threading.enumerate():
            if thread.name=='product-title-translation':thread.join(2)
        self.assertEqual(service.get('product:shoe-1')['selected']['platform']['title_zh']['text'],'实际平台标题的中文翻译')


if __name__=='__main__':unittest.main()
