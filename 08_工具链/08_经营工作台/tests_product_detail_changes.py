import copy
import unittest
from xml.etree import ElementTree as ET

import tests_product_changes as shared
from product_changes import GET, RENDER, UPDATE
from product_detail_changes import DetailChanges


class DetailClient(shared.Client):
    def __init__(self):
        super().__init__()
        self.product['struct_detail_product'] = True
        self.product['struct_detail'] = {'product_summary': 'Keep summary', 'company_image': {'images': ['keep']},
            'detail_image': {'images': [{'image_set': {'id': '300', 'name': 'Detail shot'},
                'image_url': f'https://sc04.alicdn.com/kf/H{i}.jpg'} for i in range(4)]}}

    def call(self, method, params):
        if method != RENDER:
            return super().call(method, params)
        self.calls.append((method, copy.deepcopy(params)))
        root = ET.Element('itemSchema')
        kind = ET.SubElement(root, 'field', id='productDescType', type='singleCheck')
        ET.SubElement(kind, 'value').text = '4'
        group = ET.SubElement(root, 'field', id='detailImage', type='multiComplex')
        rules = ET.SubElement(group, 'rules')
        ET.SubElement(rules, 'rule', name='supportCustomOrder', value='true')
        block = ET.SubElement(group, 'complex-values')
        role = ET.SubElement(block, 'field', id='gallery', type='singleCheck')
        ET.SubElement(role, 'value').text = '300'
        images = ET.SubElement(block, 'field', id='images', type='multiComplex')
        for row in self.product['struct_detail']['detail_image']['images']:
            entry = ET.SubElement(images, 'complex-values')
            url = ET.SubElement(entry, 'field', id='imageURL', type='input')
            ET.SubElement(url, 'value').text = row['image_url'].removeprefix('https:')
            text = ET.SubElement(entry, 'field', id='generalText', type='input')
            ET.SubElement(text, 'value').text = 'text for ' + row['image_url']
        return {'data': ET.tostring(root, encoding='unicode')}


class DetailTests(unittest.TestCase):
    tearDown = shared.ProductChangeTests.tearDown
    write = shared.ProductChangeTests.write
    read = shared.ProductChangeTests.read
    apply = shared.ProductChangeTests.apply

    def setUp(self):
        shared.ProductChangeTests.setUp(self)
        self.client = DetailClient()
        self.changes = DetailChanges(self.app, self.client)

    def prepare(self, internal_test=False):
        result = self.changes.prepare_reorder('123', [2, 1, 3, 4], rationale='Prioritize detail',
            evidence=['facts.md'], internal_test=internal_test)
        self.assertTrue(result['ok'], result)
        return result['change']

    def test_minimal_schema_and_full_lifecycle(self):
        change = self.prepare()
        xml = ET.fromstring(change['xml'])
        self.assertEqual({f.get('id') for f in xml}, {'detailImage', 'productDescType'})
        self.assertIn('text for //sc04', change['xml'].replace('https:', ''))
        self.assertEqual(self.apply(change)['change']['state'], 'submitted')
        self.client.product['struct_detail']['detail_image']['images'] = change['diff']['after']
        result = self.changes.reconcile(change['id'])
        self.assertEqual(result['change']['state'], 'local_synced', result)
        self.assertEqual(self.read()['listings'][0]['current_platform_fields']['detail_images'], change['diff']['after'])
        self.assertEqual(sum(m == UPDATE for m, _ in self.client.calls), 1)

    def test_non_target_summary_change_blocks_write(self):
        change = self.prepare()
        self.client.product['struct_detail']['product_summary'] = 'Unexpected'
        self.assertEqual(self.apply(change)['error']['code'], 'PLATFORM_VERSION_CONFLICT')
        self.assertFalse(any(m == UPDATE for m, _ in self.client.calls))

    def test_sorting_kind_and_legacy_records_cannot_use_replacement_routes(self):
        from product_detail_uploads import ReplacementDetailChanges
        import json
        change = self.prepare()
        self.assertEqual(change['changeKind'], 'detail_reorder')
        replacements = ReplacementDetailChanges(self.app, self.client)
        self.assertEqual(replacements.list_changes(), [])
        self.assertEqual(replacements.get(change['id'])['error']['code'], 'CHANGE_KIND_MISMATCH')
        change.pop('changeKind')
        self.app.db.execute('UPDATE product_changes SET data=? WHERE id=?', (json.dumps(change), change['id']))
        self.app.db.commit()
        self.assertTrue(self.changes.get(change['id'])['ok'])
        self.assertEqual(replacements.reconcile(change['id'])['error']['code'], 'CHANGE_KIND_MISMATCH')

    def test_formal_array_uses_explicit_group_order(self):
        rows = self.client.product['struct_detail']['detail_image']['images']
        for i, row in enumerate(rows):
            row['image_set']['order'] = str(i // 2)
        unordered = [rows[2], rows[3], rows[0], rows[1]]
        product = copy.deepcopy(self.client.product)
        product['struct_detail']['detail_image']['images'] = unordered
        normalized = self.changes._target(product)
        self.assertEqual([r['image_url'] for r in normalized], [r['image_url'] for r in rows])
        self.assertTrue(all('order' not in r['image_set'] for r in normalized))
        self.assertEqual(unordered[0]['image_set']['order'], '1')

    def test_schema_aligns_unordered_formal_array_without_order_metadata(self):
        original = self.client.call
        def unordered(method, params):
            result = original(method, params)
            if method == GET:
                rows = result['product']['struct_detail']['detail_image']['images']
                rows.reverse()
            return result
        self.client.call = unordered
        result = self.changes.diagnose('123')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['change']['platform']['detail_images'][0]['image_url'],
                         self.client.product['struct_detail']['detail_image']['images'][0]['image_url'])
        self.assertFalse(any(m == UPDATE for m, _ in self.client.calls))

    def test_test_draft_and_invalid_input_never_write(self):
        change = self.prepare(internal_test=True)
        self.assertEqual(self.apply(change)['error']['code'], 'INTERNAL_TEST_NOT_SUBMITTABLE')
        for order in ([1, 1, 2, 3], [True, 2, 3, 4], [2, 1]):
            self.assertFalse(self.changes.prepare_reorder('123', order, rationale='x', evidence=['facts.md'])['ok'])
        self.assertFalse(any(m == UPDATE for m, _ in self.client.calls))

    def test_non_target_company_change_blocks_sync(self):
        change = self.prepare()
        self.apply(change)
        self.client.product['struct_detail']['detail_image']['images'] = change['diff']['after']
        self.client.product['struct_detail']['company_image'] = {'images': ['changed']}
        before = self.path.read_bytes()
        self.assertEqual(self.changes.reconcile(change['id'])['change']['state'], 'formal_pending')
        self.assertEqual(before, self.path.read_bytes())

    def test_complete_groups_move_with_text_and_roles(self):
        original = self.client.call
        def grouped(method, params):
            result = original(method, params)
            if method == RENDER:
                root = ET.fromstring(result['data'])
                group = root.find("./field[@id='detailImage']")
                block = group.find('./complex-values')
                images = block.find("./field[@id='images']")
                entries = images.findall('./complex-values')
                second = copy.deepcopy(block)
                second_images = second.find("./field[@id='images']")
                for item in second_images.findall('./complex-values'):
                    second_images.remove(item)
                for item in entries[2:]:
                    images.remove(item)
                    second_images.append(item)
                group.append(second)
                result['data'] = ET.tostring(root, encoding='unicode')
            return result
        self.client.call = grouped
        diagnosis = self.changes.diagnose('123')['change']
        self.assertEqual([g['slots'] for g in diagnosis['detailGroups']], [[1, 2], [3, 4]])
        self.assertEqual(len({g['groupId'] for g in diagnosis['detailGroups']}), 2)
        result = self.changes.prepare_reorder('123', [3, 4, 2, 1], rationale='Group priority', evidence=['facts.md'])
        self.assertTrue(result['ok'], result)
        change = result['change']
        root = ET.fromstring(change['xml'])
        urls = [v.text for v in root.findall("./field[@id='detailImage']/complex-values/field[@id='images']/complex-values/field[@id='imageURL']/value")]
        self.assertEqual(urls, ['//sc04.alicdn.com/kf/H2.jpg', '//sc04.alicdn.com/kf/H3.jpg', '//sc04.alicdn.com/kf/H1.jpg', '//sc04.alicdn.com/kf/H0.jpg'])
        bad = self.changes.prepare_reorder('123', [1, 3, 2, 4], rationale='Split', evidence=['facts.md'])
        self.assertEqual(bad['error']['code'], 'DETAIL_GROUP_MUST_REMAIN_CONTIGUOUS')
        self.assertFalse(any(m == UPDATE for m, _ in self.client.calls))
        self.assertEqual(self.apply(change)['change']['state'], 'submitted')
        self.client.product['struct_detail']['detail_image']['images'] = change['diff']['after']
        self.assertEqual(self.changes.reconcile(change['id'])['change']['state'], 'local_synced')


if __name__ == '__main__':
    unittest.main()
