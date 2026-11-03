import copy
import unittest
from PIL import Image
from product_changes import UPDATE
from product_gallery_uploads import LocalGalleryPlans
from tests_product_gallery_changes import GalleryChangeTests


class LocalGalleryTests(GalleryChangeTests):
    def setUp(self):
        super().setUp()
        self.image = self.root / 'new.png'
        Image.new('RGB', (800, 800), 'white').save(self.image)
        self.uploads = []
        original_call = self.client.call
        def call(method, params):
            if method == 'alibaba.icbu.photobank.list':
                return {'pagination_query_list': {'list': [{'url': url, 'id': file_id} for url, file_id in self.client.ids.items()]}}
            return original_call(method, params)
        self.client.call = call
        def upload(path):
            self.uploads.append(path)
            return {'upload_image_response': {'file_id': '900', 'photobank_url': 'https://sc04.alicdn.com/kf/Hnew.png'}}
        self.plans = LocalGalleryPlans(self.app, self.client, upload)

    def plan(self, **kwargs):
        result = self.plans.prepare('123', [{'path': 'new.png'}, 2, 3, 4, 5, 6], rationale='Owner selected replacement', evidence=['facts.md'], **kwargs)
        self.assertTrue(result['ok'], result)
        return result['change']

    def submit(self, plan):
        return self.plans.submit(plan['id'], confirmed=True, expected_version=plan['version'])

    def test_local_plan_is_read_only_and_previewable(self):
        before = self.path.read_bytes()
        plan = self.plan()
        self.assertEqual(plan['previews'][0]['previewRef'], 'new.png')
        self.assertEqual(plan['previews'][0]['dimensions'], [800, 800])
        self.assertEqual(self.uploads, [])
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse(any(method == UPDATE for method, _ in self.client.calls))

    def test_upload_submit_formal_sync_and_no_replay(self):
        plan = self.plan()
        result = self.submit(plan)
        self.assertTrue(result['ok'], result)
        applied = result['change']
        self.assertEqual(applied['state'], 'submitted')
        self.assertEqual(len(self.uploads), 1)
        self.assertEqual(self.submit(applied)['error']['code'], 'ALREADY_ATTEMPTED_RECONCILE_ONLY')
        self.assertEqual(self.plans.reconcile(plan['id'])['change']['state'], 'formal_pending')
        self.client.product['main_image']['images'][0] = 'https://sc04.alicdn.com/kf/Hnew.png'
        self.client.ids['https://sc04.alicdn.com/kf/Hnew.png'] = '900'
        result = self.plans.reconcile(plan['id'])
        self.assertEqual(result['change']['state'], 'local_synced', result)
        self.assertEqual(self.read()['listings'][0]['current_platform_fields']['main_images'][0], 'https://sc04.alicdn.com/kf/Hnew.png')

    def test_changed_image_test_plan_and_platform_conflict_block_upload(self):
        plan = self.plan(internal_test=True)
        self.assertEqual(self.submit(plan)['error']['code'], 'INTERNAL_TEST_NOT_SUBMITTABLE')
        plan = self.plan()
        Image.new('RGB', (800, 800), 'black').save(self.image)
        self.assertEqual(self.submit(plan)['error']['code'], 'LOCAL_IMAGE_CHANGED')
        plan = self.plan()
        self.client.product['subject'] = 'Changed externally'
        self.assertEqual(self.submit(plan)['error']['code'], 'PLATFORM_VERSION_CONFLICT')
        self.assertEqual(self.uploads, [])

    def test_upload_timeout_never_replays(self):
        plan = self.plan()
        def timeout(path):
            self.uploads.append(path)
            raise TimeoutError('private')
        self.plans.uploader = timeout
        self.assertFalse(self.submit(plan)['ok'])
        plan = self.plans.get(plan['id'])['change']
        self.assertEqual(plan['state'], 'upload_outcome_unknown')
        self.assertEqual(self.submit(plan)['error']['code'], 'ALREADY_ATTEMPTED_RECONCILE_ONLY')
        self.assertEqual(len(self.uploads), 1)
        self.assertFalse(any(method == UPDATE for method, _ in self.client.calls))

    def test_invalid_paths_and_duplicate_slots_rejected(self):
        for slots in ([{'path': '../new.png'}, 2, 3, 4, 5, 6], [{'path': 'new.png'}, 2, 2, 4, 5, 6]):
            self.assertFalse(self.plans.prepare('123', slots, rationale='reason', evidence=['facts.md'])['ok'])
        self.assertEqual(self.uploads, [])


if __name__ == '__main__':
    unittest.main()
