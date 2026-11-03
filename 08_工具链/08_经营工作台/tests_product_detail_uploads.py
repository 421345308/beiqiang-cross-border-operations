import copy
import unittest
from PIL import Image
from xml.etree import ElementTree as ET
from product_changes import UPDATE
from product_detail_uploads import LocalDetailPlans, ReplacementDetailChanges
from product_detail_changes import DetailChanges
from product_gallery_uploads import LocalGalleryPlans
import tests_product_changes as shared
from tests_product_detail_changes import DetailClient


class DetailUploadTests(unittest.TestCase):
    tearDown = shared.ProductChangeTests.tearDown
    write = shared.ProductChangeTests.write
    read = shared.ProductChangeTests.read

    def setUp(self):
        shared.ProductChangeTests.setUp(self)
        self.client = DetailClient()
        self.client.product['main_image']['images'] = ['https://sc04.alicdn.com/kf/Hmain.jpg']
        self.uploads = []
        self.image = self.root / 'detail.png'
        Image.new('RGB', (800, 1200), 'white').save(self.image)
        original = self.client.call
        def call(method, params):
            if method == 'alibaba.icbu.photobank.list':
                self.client.calls.append((method, copy.deepcopy(params)))
                return {'pagination_query_list': {'list': [{'id': '902', 'url': 'https://sc04.alicdn.com/kf/Hmain.jpg'}]}}
            result = original(method, params)
            if method == 'alibaba.icbu.product.schema.render':
                root = ET.fromstring(result['data'])
                captions = root.findall("./field[@id='detailImage']/complex-values/field[@id='images']/complex-values/field[@id='generalText']/value")
                for i, caption in enumerate(captions):
                    caption.text = f'text for https://sc04.alicdn.com/kf/H{i}.jpg'
                result['data'] = ET.tostring(root, encoding='unicode')
            return result
        self.client.call = call
        def upload(path):
            self.uploads.append(path)
            return {'upload_image_response': {'file_id': '901', 'photobank_url': 'https://sc04.alicdn.com/kf/Hnew.png'}}
        self.plans = LocalDetailPlans(self.app, self.client, upload)

    def plan(self, first=None, **kwargs):
        result = self.plans.prepare('123', [first or {'path': 'detail.png'}, 2, 3, 4],
            rationale='Reviewed detail replacement', evidence=['facts.md'], **kwargs)
        self.assertTrue(result['ok'], result)
        return result['change']

    def submit(self, plan):
        return self.plans.submit(plan['id'], confirmed=True, expected_version=plan['version'])

    def test_local_preview_then_mock_upload_submit_readback(self):
        before = self.path.read_bytes()
        plan = self.plan()
        self.assertEqual(plan['previews'][0]['dimensions'], [800, 1200])
        self.assertEqual(plan['previews'][0]['previewRef'], 'detail.png')
        self.assertEqual(self.uploads, [])
        plan = self.plan()
        gallery = LocalGalleryPlans(self.app, self.client, lambda path: None)
        self.assertFalse(gallery.get(plan['id'])['ok'])
        self.assertEqual(gallery.list_plans(), [])
        self.assertTrue(self.plans.get(plan['id'])['ok'])
        self.assertFalse(any(m == UPDATE for m, _ in self.client.calls))
        submitted = self.submit(plan)
        self.assertTrue(submitted['ok'], submitted)
        self.assertEqual(submitted['change']['state'], 'submitted', submitted)
        self.assertEqual(len(self.uploads), 1)
        self.assertEqual(before, self.path.read_bytes())
        self.client.product['struct_detail']['detail_image']['images'][0]['image_url'] = 'https://sc04.alicdn.com/kf/Hnew.png'
        result = self.plans.reconcile(plan['id'])
        self.assertEqual(result['change']['state'], 'local_synced', result)
        self.assertEqual(self.read()['listings'][0]['current_platform_fields']['detail_images'][0]['image_url'], 'https://sc04.alicdn.com/kf/Hnew.png')
        self.assertEqual(self.submit(result['change'])['error']['code'], 'ALREADY_ATTEMPTED_RECONCILE_ONLY')

    def test_existing_main_image_replacement_uses_bank_without_upload(self):
        plan = self.plan({'mainSlot': 1})
        result = self.submit(plan)
        self.assertEqual(result['change']['state'], 'submitted', result)
        self.assertEqual(self.uploads, [])
        self.assertTrue(any(m == 'alibaba.icbu.photobank.list' for m, _ in self.client.calls))
        change = result['change']['submissionResult']['change']
        self.assertEqual(change['diff']['after'][0]['image_set'], change['diff']['before'][0]['image_set'])
        self.assertIn('text for https://sc04.alicdn.com/kf/H0.jpg', change['xml'])

    def test_changed_image_internal_test_and_conflicts_block_upload(self):
        plan = self.plan(internal_test=True)
        self.assertEqual(self.submit(plan)['error']['code'], 'INTERNAL_TEST_NOT_SUBMITTABLE')
        plan = self.plan()
        Image.new('RGB', (800, 1200), 'black').save(self.image)
        self.assertEqual(self.submit(plan)['error']['code'], 'LOCAL_IMAGE_CHANGED')
        plan = self.plan()
        self.client.product['struct_detail']['product_summary'] = 'changed'
        self.assertEqual(self.submit(plan)['error']['code'], 'PLATFORM_VERSION_CONFLICT')
        self.assertEqual(self.uploads, [])

    def test_upload_timeout_and_unknown_outcome_never_replay(self):
        plan = self.plan()
        def timeout(path):
            self.uploads.append(path)
            raise TimeoutError('private')
        self.plans.uploader = timeout
        self.assertFalse(self.submit(plan)['ok'])
        stored = self.plans.get(plan['id'])['change']
        self.assertEqual(stored['state'], 'upload_outcome_unknown')
        self.assertEqual(self.submit(stored)['error']['code'], 'ALREADY_ATTEMPTED_RECONCILE_ONLY')
        self.assertEqual(len(self.uploads), 1)
        self.assertFalse(any(m == UPDATE for m, _ in self.client.calls))

    def test_only_urls_can_change_and_plan_tables_are_isolated(self):
        c = self.plans.changes
        baseline = c._read('123')
        target = copy.deepcopy(baseline[c.field])
        target[0]['image_set']['id'] = '150'
        result = c.prepare('123', target, rationale='x', evidence=['facts.md'])
        self.assertEqual(result['error']['code'], 'DETAIL_REPLACEMENT_URL_ONLY')
        self.assertFalse(self.plans.prepare('123', [{'path': '../detail.png'}, 2, 3, 4], rationale='x', evidence=['facts.md'])['ok'])
        self.assertFalse(self.plans.prepare('123', [1, 2, 3, 4, 1], rationale='x', evidence=['facts.md'])['ok'])
        self.assertEqual(self.uploads, [])

    def test_replacement_changes_are_not_sorting_changes_including_legacy_records(self):
        plan = self.plan()
        submitted = self.submit(plan)['change']
        change_id = submitted['changeId']
        sorting = DetailChanges(self.app, self.client)
        self.assertEqual(sorting.list_changes(), [])
        self.assertEqual(sorting.get(change_id)['error']['code'], 'CHANGE_KIND_MISMATCH')
        self.assertEqual(sorting.reconcile(change_id)['error']['code'], 'CHANGE_KIND_MISMATCH')
        correct = self.plans.changes.get(change_id)['change']
        self.assertEqual(correct['changeKind'], 'detail_replace')
        correct.pop('changeKind')
        import json
        self.app.db.execute('UPDATE product_changes SET data=? WHERE id=?', (json.dumps(correct), change_id))
        self.app.db.commit()
        self.assertEqual(sorting.list_changes(), [])
        self.assertEqual(sorting.apply(change_id, confirmed=True, expected_version=correct['version'])['error']['code'], 'CHANGE_KIND_MISMATCH')
        self.client.product['struct_detail']['detail_image']['images'][0]['image_url'] = 'https://sc04.alicdn.com/kf/Hnew.png'
        self.assertEqual(self.plans.reconcile(plan['id'])['change']['state'], 'local_synced')


if __name__ == '__main__':
    unittest.main()
