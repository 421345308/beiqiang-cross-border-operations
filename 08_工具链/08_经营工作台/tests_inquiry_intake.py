import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

from inquiry_intake import DIRECTORY, InquiryConflict, InquiryIntake


class InquiryIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = SimpleNamespace(root=self.root, lock=threading.RLock())
        self.intake = InquiryIntake(self.app)
        self.body = {'channel': 'alibaba', 'company': 'Buyer Company', 'contact_name': 'Buyer',
                     'country': 'US', 'quantity': '20 pairs requested', 'original_text': 'Hello,\r\nNeed 20 pairs.  \n',
                     'source_url': 'https://message.alibaba.com/message/default.htm', 'source_id': 'message-123',
                     'received_at': '2026-10-31T10:00:00+08:00'}

    def tearDown(self):
        self.temp.cleanup()

    def test_preserves_exact_original_and_no_automatic_identity_claim(self):
        row = self.intake.add(self.body)
        self.assertEqual(row['original_text'], self.body['original_text'])
        self.assertEqual(row['original_sha256'], hashlib.sha256(self.body['original_text'].encode('utf8')).hexdigest())
        self.assertEqual(row['source_type'], 'manual_import')
        self.assertFalse(row['buyer_identity_verified'])
        self.assertFalse(row['natural_acquisition_verified'])
        path = self.root / DIRECTORY / (row['id'] + '.json')
        self.assertEqual(json.loads(path.read_text(encoding='utf8')), row)
        self.assertEqual(self.intake.get_record(row['id']), row)

    def test_duplicate_same_source_and_text_returns_original_without_mutation(self):
        row = self.intake.add(self.body)
        path = self.root / DIRECTORY / (row['id'] + '.json'); original = path.read_bytes()
        duplicate = self.intake.add({**self.body, 'company': 'Changed metadata'})
        self.assertEqual(duplicate, row)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(self.intake.list_records()), 1)

    def test_changed_text_same_source_explicit_conflict_keeps_original(self):
        row = self.intake.add(self.body)
        path = self.root / DIRECTORY / (row['id'] + '.json'); original = path.read_bytes()
        with self.assertRaises(InquiryConflict):
            self.intake.add({**self.body, 'original_text': 'Different request'})
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(self.intake.list_records()), 1)

    def test_text_dedup_without_source_id_and_across_different_source_ids(self):
        first = self.intake.add({**self.body, 'source_id': ''})
        second = self.intake.add({**self.body, 'source_id': 'another-id'})
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.intake.list_records()), 1)
        with self.assertRaises(InquiryConflict):
            self.intake.add({**self.body, 'source_id': 'another-id', 'original_text': 'Changed under the deduplicated source ID'})
        self.assertEqual(len(self.intake.list_records()), 1)

    def test_different_channels_never_merge_same_text_or_source_id(self):
        first = self.intake.add(self.body)
        second = self.intake.add({**self.body, 'channel': 'email'})
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(len(self.intake.list_records()), 2)

    def test_new_instance_reopens_same_files_without_sqlite(self):
        row = self.intake.add(self.body)
        other = InquiryIntake(self.app)
        self.assertEqual(other.get_record(row['id']), row)
        self.assertEqual(other.list_records(), [row])

    def test_rejects_invalid_inputs_without_storing_record(self):
        for changes in ({'channel': 'website'}, {'original_text': ' '}, {'original_text': 'x'*100001},
                        {'source_url': 'javascript:bad'}, {'source_url': 'https://user:password@example.com'},
                        {'received_at': 'not a date'}):
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError): self.intake.add({**self.body, **changes})
        self.assertEqual(self.intake.list_records(), [])

    def test_detects_tampered_original_instead_of_returning_false_evidence(self):
        row = self.intake.add(self.body)
        path = self.root / DIRECTORY / (row['id'] + '.json')
        row['original_text'] = 'tampered'; path.write_text(json.dumps(row), encoding='utf8')
        with self.assertRaises(ValueError): self.intake.get_record(row['id'])


if __name__ == '__main__': unittest.main()
