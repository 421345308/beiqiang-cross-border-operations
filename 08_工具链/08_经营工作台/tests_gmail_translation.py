import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gmail_translation import GmailTranslator, translate_with_codex


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.app = SimpleNamespace(state=Path(self.temp.name), db=self.db, lock=threading.RLock())
        self.changed = threading.Event()

    def tearDown(self):
        worker = getattr(getattr(self, 'translator', None), 'worker', None)
        if worker: worker.join(3)
        self.db.close()
        self.temp.cleanup()

    def message(self, body='Please send 100 pairs.\n\nOn Monday someone wrote:\nold quoted text'):
        return {'id':'m1','subject':'Sample request','body':body}

    def test_batch_translation_is_cached_without_storing_original_and_deduplicated(self):
        seen = []
        def translate(rows):
            seen.extend(rows)
            return [{'id':row['id'], 'subject_zh':'样品咨询', 'body_zh':'请发送100双。'} for row in rows]
        self.translator = GmailTranslator(self.app, self.changed.set, translate)
        messages = [self.message()]
        self.translator.apply('me@example.test', messages, ['m1'])
        self.assertEqual(messages[0]['translation_state'], 'translating')
        self.assertTrue(self.changed.wait(3))
        self.assertNotIn('old quoted text', seen[0]['body'])
        messages = [self.message()]
        self.translator.apply('me@example.test', messages, ['m1'])
        self.assertEqual(messages[0]['subject_zh'], '样品咨询')
        self.assertEqual(messages[0]['translation_zh'], '请发送100双。')
        self.assertEqual(len(seen), 1)
        saved = self.db.execute('SELECT * FROM gmail_translations').fetchall()
        self.assertNotIn('Please send', str(saved))
        other = GmailTranslator(self.app, self.changed.set, translate)
        messages = [self.message()]
        other.apply('me@example.test', messages, ['m1'])
        self.assertEqual(messages[0]['translation_state'], 'ready')
        self.assertEqual(len(seen), 1)

    def test_changed_message_gets_new_translation(self):
        seen = []
        def translate(rows):
            seen.extend(rows)
            return [{'id':row['id'], 'subject_zh':'询价', 'body_zh':'中文内容'} for row in rows]
        self.translator = GmailTranslator(self.app, self.changed.set, translate)
        self.translator.apply('me@example.test', [self.message()], ['m1'])
        self.assertTrue(self.changed.wait(3)); self.changed.clear()
        self.translator.apply('me@example.test', [self.message('Please send 300 pairs.')], ['m1'])
        self.assertTrue(self.changed.wait(3))
        self.assertEqual([row['body'] for row in seen], ['Please send 100 pairs.', 'Please send 300 pairs.'])

    def test_attachment_only_message_does_not_start_translation(self):
        self.translator = GmailTranslator(self.app, self.changed.set, lambda _: self.fail('不需要翻译'))
        messages = [{'id':'m2','subject':'','body':'','attachments':[{'filename':'catalog.pdf'}]}]
        self.translator.apply('me@example.test', messages, ['m2'])
        self.assertEqual(messages[0]['translation_state'], 'ready')
        self.assertIsNone(self.translator.worker)

    def test_failed_translation_can_be_retried(self):
        def fail(_): raise RuntimeError('unavailable')
        self.translator = GmailTranslator(self.app, self.changed.set, fail)
        self.translator.apply('me@example.test', [self.message()], ['m1'])
        self.assertTrue(self.changed.wait(3)); self.changed.clear()
        messages = [self.message()]
        self.translator.apply('me@example.test', messages, ['m1'])
        self.assertEqual(messages[0]['translation_state'], 'error')
        self.translator.translate_batch = lambda rows: [{'id':'m1','subject_zh':'样品','body_zh':'请发送100双。'}]
        self.translator.apply('me@example.test', messages, ['m1'], retry=True)
        self.assertTrue(self.changed.wait(3))
        self.translator.apply('me@example.test', messages, ['m1'])
        self.assertEqual(messages[0]['translation_zh'], '请发送100双。')

    def test_codex_receives_structured_translation_and_returns_json(self):
        rows = [{'id':'m1','subject':'Price','body':'Price for BQ009?'}]
        def run(command, **kwargs):
            schema = json.loads(Path(command[command.index('--output-schema') + 1]).read_text(encoding='utf8'))
            self.assertIn('messages', schema['properties'])
            self.assertIn('Price for BQ009?', kwargs['input'])
            Path(command[command.index('-o') + 1]).write_text(json.dumps({'messages':[
                {'id':'m1','subject_zh':'价格','body_zh':'BQ009 的价格是多少？'}]},ensure_ascii=False),encoding='utf8')
            return SimpleNamespace(returncode=0)
        with patch('gmail_translation.codex_executable',return_value='codex'), patch('gmail_translation.subprocess.run',side_effect=run):
            result=translate_with_codex(self.app.state, rows)
        self.assertEqual(result[0]['body_zh'], 'BQ009 的价格是多少？')


if __name__ == '__main__':
    unittest.main()
