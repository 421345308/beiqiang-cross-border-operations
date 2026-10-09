"""Regression fixtures for source identity, per-listing evidence and generated views."""
import copy
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_product_workspace import build, validate, view_matches, TOTAL, CSV, QUERY
from check_workspace import WorkspaceCheck, literal_paths

def fixture():
    return {'schema_version':1,'updated_on':'2026-10-09',
        'sources':[{'id':'s1','url':'https://example.com/shoe/059','model':'059','supplier':'供应商','price':'68','currency':'CNY','observed_at':'2026-09-28','evidence':[]}],
        'products':[{'id':'HR001','aliases':['HR001'],'source_state':'CANDIDATE','adopted_source_id':None,'candidate_source_ids':['s1'],'next_action':'复核候选','notes':[],'evidence':[]}],
        'listings':[{'id':'1600000000001','product_id':'HR001','model':'HR001-A','url':'https://www.alibaba.com/product-detail/a_1600000000001.html','bound_source_id':None,'observation':{'audit':'approved','display':'Y','at':'2026-09-28'},'evidence':[]}],
        'workstreams':[]}

class SourceIdentity(unittest.TestCase):
    def test_candidate_never_exports_as_formally_adopted(self):
        data=fixture()
        self.assertEqual(validate(data),[])
        rendered=build(data)
        rows=list(csv.DictReader(io.StringIO(rendered[CSV].decode('utf-8-sig'))))
        self.assertEqual(rows[0]['供应鞋款直达链接'],'')
        self.assertIn('候选 059',rendered[TOTAL].decode())
        self.assertIn('2026-09-28',rendered[QUERY].decode())

    def test_family_source_does_not_promote_sibling_binding(self):
        data=fixture()
        data['products'][0].update(source_state='ADOPTED',adopted_source_id='s1',candidate_source_ids=[])
        data['listings'][0]['bound_source_id']='s1'
        sibling=copy.deepcopy(data['listings'][0])
        sibling.update(id='1600000000002',model='HR001-B',bound_source_id=None)
        data['listings'].append(sibling)
        rows=list(csv.DictReader(io.StringIO(build(data)[CSV].decode('utf-8-sig'))))
        self.assertTrue(rows[0]['供应鞋款直达链接'])
        self.assertEqual(rows[1]['供应鞋款直达链接'],'')

    def test_original_product_source_does_not_claim_link_adoption(self):
        data=fixture()
        data['products'][0].update(source_state='MAPPED',reference_source_id='s1',candidate_source_ids=[])
        self.assertEqual(validate(data),[])
        rendered=build(data)
        self.assertIn('原款来源已关联；链接绑定待核',rendered[TOTAL].decode())
        rows=list(csv.DictReader(io.StringIO(rendered[CSV].decode('utf-8-sig'))))
        self.assertEqual(rows[0]['供应鞋款直达链接'],'')

    def test_split_abc_family_and_duplicate_ids_fail(self):
        data=fixture()
        other=copy.deepcopy(data['products'][0])
        other.update(id='incorrect',aliases=['wrong'])
        data['products'].append(other)
        sibling=copy.deepcopy(data['listings'][0])
        sibling.update(model='HR001-B',product_id='incorrect')
        data['listings'].append(sibling)
        errors=validate(data)
        self.assertTrue(any('duplicate ID' in e for e in errors))
        self.assertTrue(any('split' in e for e in errors))

    def test_source_conflict_cannot_remain_adopted(self):
        data=fixture()
        data['products'][0].update(source_state='CONFLICT',adopted_source_id='s1')
        self.assertTrue(any('must not be adopted' in e for e in validate(data)))

    def test_different_original_models_can_share_one_offer_url(self):
        data=fixture()
        second=copy.deepcopy(data['sources'][0])
        second.update(id='s2',model='060')
        data['sources'].append(second)
        self.assertEqual(validate(data),[])
        second['model']='059'
        self.assertTrue(any('maintained once' in e for e in validate(data)))

    def test_missing_evidence_and_unsafe_url_fail(self):
        data=fixture()
        data['sources'][0].update(url='javascript:alert(1)',evidence=['missing-source.json'])
        with TemporaryDirectory() as tmp:
            errors=validate(data,Path(tmp))
        self.assertTrue(any('unsafe URL' in e for e in errors))
        self.assertTrue(any('missing evidence' in e for e in errors))

    def test_historical_id_is_not_dropped_or_marked_online(self):
        data=fixture()
        data['listings'][0].update(url='',observation={'audit':'当前未核','display':'','at':'2026-09-05'})
        result=build(data)
        self.assertIn('1600000000001',result[TOTAL].decode())
        self.assertEqual(build(data),result)
        self.assertIn('当前未核',result[QUERY].decode())

    def test_checker_rejects_new_dated_cleanup_report(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            control=root/'00_总控台'
            control.mkdir()
            (root/'07_知识库与Skills').mkdir()
            (control/'当前状态.md').write_text('# 当前状态\n',encoding='utf-8')
            (control/'项目整理_2026-10-10').mkdir()
            checker=WorkspaceCheck(root)
            checker.governance()
            self.assertTrue(any('dated maintenance report' in x['message'] for x in checker.errors))

    def test_command_argument_is_not_a_filename(self):
        self.assertEqual(literal_paths('Read `08_工具链/02_视频工具/seedance_video/seedance_generate.py --help`.'),['08_工具链/02_视频工具/seedance_video/seedance_generate.py'])

    def test_windows_checkout_line_endings_do_not_make_views_stale(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'view.md'
            path.write_bytes(b'first\r\nsecond\r\n')
            self.assertTrue(view_matches(path,b'first\nsecond\n'))
            self.assertFalse(view_matches(path,b'first\nchanged\n'))

    def test_public_checkout_does_not_require_private_customer_records(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'04_客户开发/README.md'
            target=root/'04_客户开发/07_RFQ专岗/README.md'
            checker=WorkspaceCheck(root)
            checker.missing_reference('active_links',source,target,'missing private record')
            self.assertEqual(checker.errors,[])
            self.assertEqual(len(checker.warnings),1)

    def test_missing_private_record_still_fails_when_local_folder_is_present(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'04_客户开发/README.md'
            target=root/'04_客户开发/07_RFQ专岗/README.md'
            target.parent.mkdir(parents=True)
            checker=WorkspaceCheck(root)
            checker.missing_reference('active_links',source,target,'missing private record')
            self.assertEqual(len(checker.errors),1)

if __name__=='__main__':
    unittest.main()
