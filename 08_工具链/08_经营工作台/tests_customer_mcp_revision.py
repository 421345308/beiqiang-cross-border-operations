"""Bound customer MCP writes use real workspace revisions and local fixtures."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from customer_workspace import CustomerWorkspace
from desk_mcp import DeskTools, dispatch, TOOLS
from workspaces import WorkspaceConflict


class CustomerMcpRevisionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        self.oid='customer:website-fixture'
        self.other='customer:website-other'
        self.objects={oid:{'id':oid,'kind':'customer','content':json.dumps({'requirements':'Synthetic request'})}
                      for oid in (self.oid,self.other)}
        self.objects['product:fixture']={'id':'product:fixture','kind':'product','content':'{}'}
        business=SimpleNamespace(get_object=lambda oid:copy.deepcopy(self.objects[oid]))
        self.app=SimpleNamespace(root=root,db=sqlite3.connect(':memory:'),lock=threading.RLock(),business=business)
        self.addCleanup(self.app.db.close)
        business.app=self.app
        self.work=self.app.customer_workspace=CustomerWorkspace(self.app)
        self.tools=DeskTools(business,root,self.oid)
        self.readonly=DeskTools(business,root,self.oid,read_only=True)

    def request(self,name,args=None,tools=None):
        return dispatch(tools or self.tools,{'id':1,'method':'tools/call',
            'params':{'name':name,'arguments':args or {}}})['result']

    def read(self,kind):return self.tools.call('get_customer_'+kind,{})

    def payload(self,kind,row,text):
        if kind=='profile':return {'revision':row['revision'],'source_hash':row['source_hash'],'analysis':{'next_action':text}}
        return {'revision':row['revision'],'next_action':text}

    def test_normal_reads_and_writes_use_actual_versions(self):
        for kind in ('profile','workflow'):
            with self.subTest(kind=kind):
                row=self.read(kind)
                result=self.request('save_customer_'+kind,self.payload(kind,row,'Internal next action'))
                self.assertFalse(result['isError'])
                saved=json.loads(result['content'][0]['text'])
                self.assertNotEqual(saved['revision'],row['revision'])
                value=saved['analysis']['next_action'] if kind=='profile' else saved['next_action']
                self.assertEqual(value,'Internal next action')
        self.assertEqual(json.loads(self.objects[self.oid]['content'])['requirements'],'Synthetic request')

    def test_manual_update_rejects_old_revision_in_dispatch(self):
        for kind in ('profile','workflow'):
            with self.subTest(kind=kind):
                old=self.read(kind)
                save=self.work.save_profile if kind=='profile' else self.work.save_workflow
                manual=save(self.oid,self.payload(kind,old,'Manual decision'))
                result=self.request('save_customer_'+kind,self.payload(kind,old,'Stale agent result'))
                self.assertTrue(result['isError'])
                self.assertEqual(json.loads(result['content'][0]['text'])['code'],'version_conflict')
                current=self.read(kind)
                self.assertEqual(current['revision'],manual['revision'])

    def test_other_object_versions_and_target_parameters_are_rejected(self):
        for kind in ('profile','workflow'):
            other=self.work.profile(self.other) if kind=='profile' else self.work.workflow(self.other)
            with self.assertRaises(WorkspaceConflict):
                self.tools.call('save_customer_'+kind,self.payload(kind,other,'Wrong target'))
            with self.assertRaises(ValueError):self.tools.call('get_customer_'+kind,{'object_id':self.other})
            args={**self.payload(kind,self.read(kind),'Wrong target'),'object_id':self.other}
            with self.assertRaises(ValueError):self.tools.call('save_customer_'+kind,args)
        self.assertEqual(self.work.profile(self.other)['analysis']['next_action'],'')
        product=DeskTools(self.app.business,self.app.root,'product:fixture')
        with self.assertRaises(ValueError):product.call('get_customer_profile',{})

    def test_read_only_reads_but_refuses_writes_and_hides_save_tools(self):
        listed=dispatch(self.readonly,{'id':1,'method':'tools/list'})['result']['tools']
        names={tool['name'] for tool in listed}
        for kind in ('profile','workflow'):
            self.assertIn('get_customer_'+kind,names);self.assertNotIn('save_customer_'+kind,names)
            row=self.readonly.call('get_customer_'+kind,{})
            with self.assertRaises(ValueError):self.readonly.call('save_customer_'+kind,self.payload(kind,row,'Forbidden'))
            self.assertTrue(self.request('save_customer_'+kind,self.payload(kind,row,'Forbidden'),self.readonly)['isError'])

    def test_missing_versions_and_source_hash_are_rejected(self):
        for kind in ('profile','workflow'):
            with self.assertRaises(ValueError):self.tools.call('save_customer_'+kind,{'next_action':'No version'})
        profile=self.read('profile')
        with self.assertRaises(ValueError):self.tools.call('save_customer_profile',{'revision':profile['revision'],'analysis':{}})

    def test_schema_round_trip_preserves_structured_derived_values(self):
        profile=self.read('profile')
        analysis={'facts':[{'claim':'Synthetic requirement','evidence':'original_text'}],
                  'inferences':['Synthetic inference'],
                  'product_fit':{'models':['fixture'],'confidence':None},'missing':None}
        cleaned={'quantity':500,'products':['fixture'],'source_notes':{'kind':'fixture'}}
        self.work.save_profile(self.oid,{'revision':profile['revision'],'source_hash':profile['source_hash'],
                                        'analysis':analysis,'cleaned':cleaned})
        read_result=self.request('get_customer_profile')
        self.assertFalse(read_result['isError'])
        current=json.loads(read_result['content'][0]['text'])
        body={'revision':current['revision'],'source_hash':current['source_hash'],
              'analysis':current['analysis'],'cleaned':current['cleaned']}
        schema=next(tool['inputSchema'] for tool in TOOLS if tool['name']=='save_customer_profile')
        for group in ('analysis','cleaned'):
            field_schema=schema['properties'][group]
            self.assertFalse(field_schema['additionalProperties'])
            for key in body[group]:
                self.assertIn(key,field_schema['properties'])
                self.assertFalse({'type','enum','const','oneOf','anyOf','allOf'} & set(field_schema['properties'][key]))
        result=self.request('save_customer_profile',body)
        self.assertFalse(result['isError'])
        saved=json.loads(result['content'][0]['text'])
        for key,value in analysis.items():self.assertEqual(saved['analysis'][key],value)
        for key,value in cleaned.items():self.assertEqual(saved['cleaned'][key],value)
        invalid={**body,'revision':saved['revision'],'analysis':{'unsupported_field':'No'}}
        self.assertNotIn('unsupported_field',schema['properties']['analysis']['properties'])
        with self.assertRaises(ValueError):self.tools.call('save_customer_profile',invalid)


if __name__=='__main__':unittest.main()
