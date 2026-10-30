"""Isolated offline source-write tests; no business documents are read."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('review_proposal',Path(__file__).with_name('review-proposal.py'))
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = '00_总控台/当前状态.md'
        self.target = self.root/self.source; self.target.parent.mkdir()
        self.raw = b'\xef\xbb\xbfAlpha\r\nBeta\nGamma\rTail\r\n'
        self.target.write_bytes(self.raw)
        self.p = dict(schema_version=1,run_id='a'*32,task_id='b'*32,status='awaiting_review',created_at='2026-10-30',source=self.source,source_hash=review.digest(review.normalize(self.raw.decode('utf-8-sig'))),source_version=1,summary='Edit',changes=[dict(path=self.source,before='Beta',after='Better',reason='clarify')],next_steps=[],note='review')
    def test_preview_apply_repeat(self):
        self.assertEqual(review.review(self.p,self.root)['status'],'preview')
        self.assertEqual(self.target.read_bytes(),self.raw)
        self.assertFalse((self.root/'08_工具链').exists())
        self.assertEqual(review.review(self.p,self.root,True)['status'],'applied')
        self.assertEqual(self.target.read_bytes(),self.raw.replace(b'Beta',b'Better'))
        self.assertEqual(review.review(self.p,self.root,True)['status'],'already_applied')
    def test_hash_conflict(self):
        self.target.write_bytes(self.raw+b'new')
        with self.assertRaisesRegex(ValueError,'hash conflict'): review.review(self.p,self.root,True)
    def test_cross_path_and_escape(self):
        for source in ('../outside.md','00_总控台/全渠道增长总控.md'):
            p=copy.deepcopy(self.p); p['changes'][0]['path']=source
            with self.assertRaises(ValueError): review.review(p,self.root,True)
        p=copy.deepcopy(self.p); p['source']='../outside.md'
        with self.assertRaises(ValueError): review.review(p,self.root,True)
    def test_duplicate_before(self):
        self.p['changes'][0]['before']='a'
        with self.assertRaisesRegex(ValueError,'exactly once'): review.review(self.p,self.root,True)
        self.assertEqual(self.target.read_bytes(),self.raw)
    def test_all_changes_validate_before_write(self):
        self.p['changes'].append(dict(path=self.source,before='missing',after='x',reason='bad'))
        with self.assertRaises(ValueError): review.review(self.p,self.root,True)
        self.assertEqual(self.target.read_bytes(),self.raw)
    def test_overlap(self):
        self.p['changes'].append(dict(path=self.source,before='Beta\nGamma',after='x',reason='overlap'))
        with self.assertRaisesRegex(ValueError,'Overlapping'): review.review(self.p,self.root,True)
    def test_newline_style_and_untouched_bytes(self):
        self.p['changes']=[dict(path=self.source,before='Alpha\nBeta',after='First\nSecond\nThird',reason='lines')]
        review.review(self.p,self.root,True)
        self.assertEqual(self.target.read_bytes(),b'\xef\xbb\xbfFirst\r\nSecond\r\nThird\nGamma\rTail\r\n')
    def test_schema_status_version(self):
        for key,value in [('schema_version',True),('source_version',True),('source_version',0),('run_id','../x'),('status','accepted')]:
            p=copy.deepcopy(self.p); p[key]=value
            with self.assertRaises(ValueError): review.review(p,self.root)
    def test_read_only(self):
        self.p.update(source=None,source_hash=None,source_version=None,changes=[])
        self.assertEqual(review.review(self.p,self.root)['status'],'preview')
        with self.assertRaises(ValueError): review.review(self.p,self.root,True)
    def test_receipt_failure_reports_written_source(self):
        real=review.atomic_write
        def fail_receipt(path,data):
            if path.suffix=='.json': raise OSError('disk error')
            real(path,data)
        with patch.object(review,'atomic_write',side_effect=fail_receipt):
            with self.assertRaisesRegex(RuntimeError,'SOURCE WAS APPLIED'): review.review(self.p,self.root,True)
        self.assertEqual(self.target.read_bytes(),self.raw.replace(b'Beta',b'Better'))
        with self.assertRaisesRegex(ValueError,'hash conflict'): review.review(self.p,self.root,True)
    def test_external_edit_before_commit(self):
        real=review.patched
        def concurrent(raw,changes):
            result=real(raw,changes); self.target.write_bytes(raw+b'changed'); return result
        with patch.object(review,'patched',side_effect=concurrent):
            with self.assertRaisesRegex(ValueError,'changed during'): review.review(self.p,self.root,True)
        self.assertEqual(self.target.read_bytes(),self.raw+b'changed')
    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            path=Path(outside)/'outside.md'; path.write_bytes(self.raw)
            self.target.unlink()
            try: self.target.symlink_to(path)
            except OSError: self.skipTest('Symlink privilege unavailable')
            with self.assertRaisesRegex(ValueError,'escapes'): review.review(self.p,self.root,True)
            self.assertEqual(path.read_bytes(),self.raw)
    def test_existing_lock(self):
        state=self.root/'08_工具链/08_经营工作台/.local/proposal-review'; state.mkdir(parents=True)
        (state/'apply.lock').touch()
        with self.assertRaisesRegex(ValueError,'apply is active'): review.review(self.p,self.root,True)
        self.assertEqual(self.target.read_bytes(),self.raw)

if __name__=='__main__': unittest.main()
