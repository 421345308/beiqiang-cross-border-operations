import unittest,tempfile
from pathlib import Path
from creation import Creation
class CreationTests(unittest.TestCase):
    def test_original_project_and_assets(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'05_内容与视频'/'example';p.mkdir(parents=True)
            (p.parent/'README.md').write_text('[project](example/PROJECT.md)',encoding='utf8')
            (p/'PROJECT.md').write_text('# 真项目\n尚未验收\n[成片](movie.mp4)\nhttps://libtv.ai/project/test',encoding='utf8')
            (p/'movie.mp4').write_bytes(b'example')
            c=Creation(root);rows=c.list_projects('真项目');self.assertEqual(len(rows),1)
            detail=c.get_project(rows[0]['id']);self.assertEqual(detail['assets'][0]['name'],'movie.mp4')
            self.assertEqual(detail['links'],['https://libtv.ai/project/test'])
            with self.assertRaises(ValueError):c.get_project('../secrets')
    def test_cli_is_read_only(self):
        class Adapter:
            def execute(self,operation,**kwargs):return operation,kwargs
        result=Creation('.',Adapter()).libtv_projects('12',2)
        self.assertEqual(result,('projects',{'workspace_id':'12','page':2,'page_size':20}))
    def test_business_agent_sources_and_project_private_artifact(self):
        import sqlite3,threading
        from types import SimpleNamespace
        from business import Business
        from desk_mcp import DeskTools
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)/'05_内容与视频';p=base/'one';p.mkdir(parents=True)
            (base/'README.md').write_text('[one](one/PROJECT.md)',encoding='utf8')
            original='# Project\nOriginal facts';(p/'PROJECT.md').write_text(original,encoding='utf8')
            db=sqlite3.connect(':memory:')
            try:
                business=Business(SimpleNamespace(root=Path(root),db=db,lock=threading.RLock()))
                oid=business.list_objects(kind='creation')[0]['id']
                tool=DeskTools(business,root,oid)
                self.assertEqual(tool.read('object:'+oid)['content'],original)
                self.assertFalse(any(s['role']=='company-capabilities' for s in tool.sources()))
                artifact=business.save_artifact(oid,'Draft','Creative draft')
                self.assertIn('/one/.local/成果/',artifact['path'])
                self.assertEqual(business.list_artifacts(oid)[0]['content'],'Creative draft')
                self.assertEqual((p/'PROJECT.md').read_text(encoding='utf8'),original)
            finally:db.close()
