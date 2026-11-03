import copy
import unittest
from xml.etree import ElementTree as ET
from product_changes import GET, RENDER, UPDATE, ProductChanges
from product_gallery_changes import GalleryChanges
import tests_product_changes as title_tests
Client = title_tests.Client

class GalleryClient(Client):
    def __init__(self):
        super().__init__()
        self.product['main_image']={'images':[f'https://sc04.alicdn.com/kf/shoe{i}.jpg' for i in range(6)]}
        self.ids={url:str(i+100) for i,url in enumerate(self.product['main_image']['images'])}
        self.bad_schema=False
    def call(self,method,params):
        if method != RENDER:
            return super().call(method,params)
        self.calls.append((method,copy.deepcopy(params)))
        root=ET.Element('itemSchema');group=ET.SubElement(root,'field',id='scImages',type='complex')
        ET.SubElement(group,'rules');values=ET.SubElement(group,'complex-value')
        for i,url in enumerate(self.product['main_image']['images']):
            field=ET.SubElement(values,'field',id=f'scImages_{i}',type='input')
            value=ET.SubElement(field,'value',fileId=self.ids[url]);value.text=url.removeprefix('https:')
            if self.bad_schema and i==0: value.attrib.clear()
        ET.SubElement(root,'field',id='productTitle',type='input')
        return {'data':ET.tostring(root,encoding='unicode')}

class GalleryChangeTests(unittest.TestCase):
    tearDown=title_tests.ProductChangeTests.tearDown
    write=title_tests.ProductChangeTests.write
    read=title_tests.ProductChangeTests.read
    apply=title_tests.ProductChangeTests.apply
    def setUp(self):
        title_tests.ProductChangeTests.setUp(self)
        self.client=GalleryClient();data=self.read()
        for key in ('current_platform_fields','catalog_fields'):
            data['listings'][0][key]['main_images']=copy.deepcopy(self.client.product['main_image']['images'])
        self.write(data);self.changes=GalleryChanges(self.app,self.client)
    def prepare(self,internal_test=False):
        result=self.changes.prepare_reorder('123',[2,1,3,4,5,6],rationale='Show side view first',evidence=['facts.md'],internal_test=internal_test)
        self.assertTrue(result['ok'],result);return result['change']
    def test_gallery_reorder_review_submit_readback_and_local_sync(self):
        before=self.path.read_bytes();change=self.prepare()
        self.assertEqual(change['diff']['field'],'main_images')
        self.assertEqual(change['diff']['after'][0],self.client.product['main_image']['images'][1])
        root=ET.fromstring(change['xml'])
        self.assertEqual([f.get('id') for f in root.findall('./field')],['scImages'])
        self.assertNotIn('rules',change['xml'])
        self.assertEqual(root.find('./field/complex-value/field/value').get('fileId'),'101')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.apply(change)['change']['state'],'submitted')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.changes.reconcile(change['id'])['change']['state'],'formal_pending')
        self.client.product['main_image']['images']=change['diff']['after']
        result=self.changes.reconcile(change['id']);self.assertTrue(result['ok'],result)
        self.assertEqual(result['change']['state'],'local_synced')
        row=self.read()['listings'][0]
        for key in ('catalog_fields','current_platform_fields'):
            self.assertEqual(row[key]['main_images'],change['diff']['after'])
        self.assertEqual(row['current_platform_fields']['title'],'Old title')
        self.assertEqual(row['formal_fields']['main_images']['change_id'],change['id'])
        self.assertEqual(result['change']['publicVerification']['state'],'not-verified')
        self.assertEqual(sum(method==UPDATE for method,_ in self.client.calls),1)
        self.assertTrue(self.changes.reconcile(change['id'])['ok'])
    def test_gallery_conflicts_and_invalid_order(self):
        for order in ([1,1,3,4,5,6],[0,1,2,3,4,5],[True,2,3,4,5,6]):
            self.assertFalse(self.changes.prepare_reorder('123',order,rationale='reason',evidence=['facts.md'])['ok'])
        change=self.prepare();self.client.product['subject']='auto optimized title'
        self.assertEqual(self.apply(change)['error']['code'],'PLATFORM_VERSION_CONFLICT')
        self.assertFalse(any(method==UPDATE for method,_ in self.client.calls))
    def test_gallery_test_draft_not_submittable_and_field_separation(self):
        change=self.prepare(internal_test=True)
        self.assertEqual(self.apply(change)['error']['code'],'INTERNAL_TEST_NOT_SUBMITTABLE')
        titles=ProductChanges(self.app,self.client)
        self.assertEqual(titles.get(change['id'])['error']['code'],'CHANGE_FIELD_MISMATCH')
        self.assertEqual(titles.list_changes(),[])
    def test_gallery_schema_file_id_required(self):
        self.client.bad_schema=True
        result=self.changes.prepare_reorder('123',[2,1,3,4,5,6],rationale='reason',evidence=['facts.md'])
        self.assertEqual(result['error']['code'],'GALLERY_SCHEMA_UNVERIFIED')
        self.assertEqual(self.changes.list_changes(),[])
    def test_gallery_non_target_side_effect_blocks_sync(self):
        change=self.prepare();self.apply(change)
        self.client.product['main_image']['images']=change['diff']['after'];self.client.product['keywords']=['unexpected']
        before=self.path.read_bytes();result=self.changes.reconcile(change['id'])
        self.assertEqual(result['change']['state'],'formal_pending');self.assertEqual(self.path.read_bytes(),before)

    def test_gallery_timeout_not_replayed_and_shared_product_claim(self):
        change=self.prepare();self.client.receipt=TimeoutError('private')
        result=self.apply(change)
        self.assertEqual(result['change']['state'],'outcome_unknown')
        restarted=GalleryChanges(self.app,self.client)
        self.assertEqual(restarted.apply(change['id'],confirmed=True,expected_version=result['change']['version'])['error']['code'],'ALREADY_ATTEMPTED_RECONCILE_ONLY')
        second=self.prepare()
        self.assertEqual(self.apply(second)['error']['code'],'PRODUCT_CHANGE_IN_PROGRESS')
        self.assertEqual(sum(method==UPDATE for method,_ in self.client.calls),1)

    def test_gallery_unrecorded_local_images_are_recorded_after_formal_read(self):
        data=self.read()
        for key in ('catalog_fields','current_platform_fields'):
            data['listings'][0][key].pop('main_images')
        self.write(data);change=self.prepare()
        self.assertIsNone(change['diff']['localBefore'])
        self.apply(change);self.client.product['main_image']['images']=change['diff']['after']
        self.assertEqual(self.changes.reconcile(change['id'])['change']['state'],'local_synced')
        self.assertEqual(self.read()['listings'][0]['current_platform_fields']['main_images'],change['diff']['after'])
    def test_gallery_real_schema_zero_ids_thumbnail_urls_and_scrambled_slots(self):
        real_call=self.client.call
        def call(method,params):
            if method == 'alibaba.icbu.photobank.list':
                self.client.calls.append((method,copy.deepcopy(params)))
                return {'pagination_query_list':{'list':[{'id':file_id,'url':url} for url,file_id in self.client.ids.items()]}}
            result=real_call(method,params)
            if method==RENDER:
                root=ET.fromstring(result['data']);group=root.find('./field/complex-value')
                fields=list(group)
                for field in fields:
                    value=field.find('./value');value.set('fileId','0');value.set('fileFlag','no')
                    value.text=value.text.replace('.jpg','.jpg_350x350.jpg')
                group[:]=[fields[i] for i in [1,2,0,5,3,4]]
                result['data']=ET.tostring(root,encoding='unicode')
            return result
        # Use real KF asset names so only the observed thumbnail rule applies.
        urls=[f'https://sc04.alicdn.com/kf/Hasset{i}.jpg' for i in range(6)]
        self.client.product['main_image']['images']=urls
        self.client.ids={url:str(i+100) for i,url in enumerate(urls)}
        self.client.call=call
        change=self.prepare()
        values=ET.fromstring(change['xml']).findall('./field/complex-value/field/value')
        self.assertEqual(values[0].get('fileId'),'101')
        self.assertEqual(values[0].text,'//sc04.alicdn.com/kf/Hasset1.jpg')
        self.apply(change);self.client.product['main_image']['images']=change['diff']['after']
        self.assertEqual(self.changes.reconcile(change['id'])['change']['state'],'local_synced')
        self.assertEqual(self.read()['listings'][0]['current_platform_fields']['main_images'],change['diff']['after'])
        self.assertEqual(sum(method=='alibaba.icbu.photobank.list' for method,_ in self.client.calls),1)

    def test_gallery_missing_bank_asset_does_not_prepare_or_submit(self):
        real_call=self.client.call
        def call(method,params):
            if method=='alibaba.icbu.photobank.list':
                return {'pagination_query_list':{'list':[]}}
            result=real_call(method,params)
            if method==RENDER:
                root=ET.fromstring(result['data'])
                for value in root.findall('./field/complex-value/field/value'):
                    value.set('fileId','0')
                result['data']=ET.tostring(root,encoding='unicode')
            return result
        self.client.call=call
        result=self.changes.prepare_reorder('123',[2,1,3,4,5,6],rationale='reason',evidence=['facts.md'])
        self.assertEqual(result['error']['code'],'IMAGE_BANK_ASSET_NOT_FOUND')
        self.assertEqual(self.changes.list_changes(),[])
        self.assertFalse(any(method==UPDATE for method,_ in self.client.calls))

if __name__=='__main__': unittest.main()
