import json
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from pathlib import Path
from creation_canvas import CreationCanvas
from desk_cli import invoke
from desk_mcp import DeskTools, dispatch
from product_creation import ProductCreation

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

    def test_agent_save_is_shared_with_cli_and_stale_save_reports_conflict(self):
        tool=DeskTools(self.business,Path.cwd(),'creation:test')
        original=tool.call('get_creation_canvas',{})
        updated={**original,'nodes':[ *original['nodes'], {'id':'shot-1','type':'text',
                    'position':{'x':200,'y':100},'data':{'title':'镜头一','content':'实物细节'}} ]}
        saved=tool.call('save_creation_canvas',updated)
        self.assertEqual(invoke(self.business,'canvas','get',object_id='creation:test'),saved)
        result=dispatch(tool,{'id':1,'method':'tools/call','params':{'name':'save_creation_canvas','arguments':updated}})['result']
        self.assertTrue(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['code'],'version_conflict')
        self.assertEqual(tool.call('get_creation_canvas',{}),saved)

    def test_save_rejects_read_only_bad_scope_and_missing_version(self):
        canvas={'nodes':[],'edges':[],'version':''}
        reader=DeskTools(self.business,Path.cwd(),'creation:test',read_only=True)
        self.assertNotIn('save_creation_canvas',[x['name'] for x in dispatch(reader,{'id':1,'method':'tools/list'})['result']['tools']])
        with self.assertRaises(ValueError):reader.call('save_creation_canvas',canvas)
        tool=DeskTools(self.business,Path.cwd(),'creation:test')
        with self.assertRaises(ValueError):tool.call('save_creation_canvas',{'nodes':[],'edges':[]})
        self.business.get_object=lambda oid:{'kind':'customer'}
        with self.assertRaises(ValueError):tool.call('save_creation_canvas',canvas)

    def test_product_asset_add_uses_current_project_and_shared_service(self):
        path='01_产品资产/BQ009/a.jpg'
        self.business.get_object=lambda oid: ({'id':oid,'kind':'product','assets':[{'path':path}]} if oid=='product:BQ009' else {'id':oid,'kind':'creation'})
        self.app.business=self.business
        self.app.media=SimpleNamespace(resolve=lambda p:{'path':p,'name':'a.jpg','kind':'image'} if p==path else (_ for _ in ()).throw(ValueError('missing')))
        self.app.creation.list_projects=lambda:[{'id':'creation:test','title':'项目','source':'PROJECT.md'}]
        self.app.product_creation=ProductCreation(self.app)
        tool=DeskTools(self.business,Path.cwd(),'creation:test')
        self.assertEqual(tool.call('product_creation_options',{'product_id':'product:BQ009'})['assets'][0]['path'],path)
        self.assertEqual(invoke(self.business,'product-creation','options',object_id='product:BQ009')['assets'][0]['path'],path)
        args={'product_id':'product:BQ009','path':path,'version':''}
        added=tool.call('add_product_asset_to_canvas',args)
        self.assertTrue(added['added'])
        self.assertEqual(invoke(self.business,'canvas','get',object_id='creation:test'),added['canvas'])
        duplicate=invoke(self.business,'product-creation','add',object_id='product:BQ009',project_id='creation:test',media_path=path,version=added['canvas']['version'])
        self.assertFalse(duplicate['added'])
        result=dispatch(tool,{'id':2,'method':'tools/call','params':{'name':'add_product_asset_to_canvas','arguments':args}})['result']
        self.assertTrue(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['code'],'version_conflict')
        with self.assertRaises(ValueError):DeskTools(self.business,Path.cwd(),'creation:test',read_only=True).call('add_product_asset_to_canvas',args)
        with self.assertRaises(ValueError):DeskTools(self.business,Path.cwd(),'product:BQ009').call('add_product_asset_to_canvas',args)

    def test_capability_discovery_uses_mcp_definitions(self):
        result=invoke(self.business,'capabilities','list',query='save_creation_canvas')
        self.assertEqual([item['name'] for item in result['capabilities']],['save_creation_canvas'])
        self.assertEqual(result['availability'],'unknown')
        self.assertFalse(result['capabilities'][0]['annotations']['readOnlyHint'])

if __name__=='__main__':unittest.main()
