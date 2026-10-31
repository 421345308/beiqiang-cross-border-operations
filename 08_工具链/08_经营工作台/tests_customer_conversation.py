import unittest,json,tempfile
from pathlib import Path
from desk_mcp import DeskTools
class ConversationTests(unittest.TestCase):
    def test_complete_paginated_thread_and_scope(self):
        class Business:
            def get_object(self,oid):
                return {'kind':'customer','content':'Initial need','conversation':[{'sender':'buyer','body':'x'*25000},{'sender':'seller','body':'Already answered'}]}
        with tempfile.TemporaryDirectory() as root:
            tools=DeskTools(Business(),root,'customer:website-abc')
            source='conversation:customer:website-abc'
            self.assertIn(source,[s['path'] for s in tools.sources()])
            chunks=[];start=0
            while True:
                row=tools.read(source,start);chunks.append(row['content'])
                if row['nextStart'] is None:break
                start=row['nextStart']
            data=json.loads(''.join(chunks))
            self.assertEqual(data['messages'][-1]['body'],'Already answered')
            self.assertEqual(len(data['messages'][0]['body']),25000)
            with self.assertRaises(ValueError):tools.read('conversation:customer:website-other')
