import json
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from pathlib import Path
from creation_canvas import CreationCanvas
from desk_cli import invoke
from desk_mcp import DeskTools

class CanvasAgentTests(unittest.TestCase):
    def setUp(self):
        self.app=SimpleNamespace(db=sqlite3.connect(':memory:'),lock=threading.RLock(),creation=SimpleNamespace(get_project=lambda oid: {'title':'项目','summary':'已知背景','assets':[]}))
        self.app.creation_canvas=CreationCanvas(self.app)
        self.business=SimpleNamespace(app=self.app,get_object=lambda oid:{'id':oid,'kind':'creation'})
    def tearDown(self):self.app.db.close()
    def test_cli_and_internal_tool_share_version_and_layout(self):
        original=invoke(self.business,'canvas','get',object_id='creation:test')
        original['nodes'][0]['position']['x']=700
        saved=invoke(self.business,'canvas','save',object_id='creation:test',content=json.dumps(original))
        tool=DeskTools(self.business,Path.cwd(),'creation:test')
        self.assertEqual(tool.call('get_creation_canvas',{}),saved)
        with self.assertRaises(ValueError):invoke(self.business,'canvas','save',object_id='creation:test',content=json.dumps(original))
    def test_missing_version_and_wrong_object_rejected(self):
        for body in ({'nodes':[],'edges':[]},{'object_id':'creation:other','version':'','nodes':[],'edges':[]}):
            with self.assertRaises(ValueError):invoke(self.business,'canvas','save',object_id='creation:test',content=json.dumps(body))
    def test_tool_rejects_customer(self):
        self.business.get_object=lambda oid:{'kind':'customer'}
        with self.assertRaises(ValueError):DeskTools(self.business,Path.cwd(),'customer:1').call('get_creation_canvas',{})

if __name__=='__main__':unittest.main()
