import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from website_inquiries import WebsiteInquiries, REPLY_URL

class Response:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, *args): return json.dumps(self.data).encode()

class WebsiteReplyTests(TestCase):
    def test_sends_to_existing_inquiry_and_updates_thread(self):
        row = {'reference': 'BQ-TEST-123', 'receivedAt': '2026-10-01T00:00:00Z', 'messages': []}
        with TemporaryDirectory() as root:
            env = Path(root)/'03_独立站/03_网站源码/.env'
            env.parent.mkdir(parents=True); env.write_text('INQUIRY_ADMIN_TOKEN=test-only', encoding='utf8')
            source = WebsiteInquiries(root, fetch=lambda: {'ok': True, 'records': [row]})
            class Opener:
                def open(self, request, timeout):
                    self.request = request
                    updated = {**row, 'messages': [{'id': 'MSG-1', 'sender': 'sales', 'body': 'Hello', 'sentAt': '2026-10-31'}]}
                    return Response({'ok': True, 'record': updated, 'notificationSent': False})
            opener = Opener()
            with patch('website_inquiries.build_opener', return_value=opener):
                result = source.reply('customer:website-BQ-TEST-123', 'Hello')
            self.assertEqual(opener.request.full_url, REPLY_URL)
            self.assertEqual(json.loads(opener.request.data), {'reference': row['reference'], 'receivedAt': row['receivedAt'], 'message': 'Hello'})
            self.assertEqual(result, {'saved': True, 'notification_sent': False, 'message_id': 'MSG-1'})
            self.assertEqual(source.records()[0]['messages'][0]['body'], 'Hello')

    def test_unknown_inquiry_cannot_send(self):
        source = WebsiteInquiries('.', fetch=lambda: {'ok': True, 'records': []})
        with patch('website_inquiries.build_opener') as opener:
            with self.assertRaises(ValueError): source.reply('customer:website-missing', 'Hello')
            opener.assert_not_called()
