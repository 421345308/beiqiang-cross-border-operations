import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from douyin_agent import read_store
from miaoshou_bridge import MiaoshouBridge
from server import Handler, miaoshou_read, miaoshou_target

ORIGIN='chrome-extension://'+'a'*32
OTHER='chrome-extension://'+'b'*32


class BridgeServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        profile=self.root/'08_工具链/01_业务脚本/抖店妙手/.local/shops/brand/session.json'
        profile.parent.mkdir(parents=True);profile.write_text(json.dumps({'expectedShopId':'123','cookie':'not-for-output'}),encoding='utf8')
        self.app=SimpleNamespace(root=self.root,token='workbench-token',miaoshou_agent_token='agent-token',miaoshou_bridge=MiaoshouBridge())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.app=self.app
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()

    def request(self,path,body=None,headers=None,method='POST'):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=4)
        defaults={'Content-Type':'application/json'};defaults.update(headers or {})
        conn.request(method,path,json.dumps(body or {}),defaults);response=conn.getresponse();raw=response.read();result=(response.status,dict(response.getheaders()),json.loads(raw) if raw else None);conn.close();return result

    def post(self,suffix,body=None,headers=None):
        return self.request('/api/desk/miaoshou-bridge/'+suffix,body,headers)

    def test_origin_host_csrf_and_preflight_are_scoped(self):
        self.assertEqual(self.post('issue',headers={'Origin':self.base})[0],403)
        self.assertEqual(self.post('issue',headers={'Origin':'https://evil.example','X-Workbench-Token':'workbench-token'})[0],403)
        self.assertEqual(self.post('issue',headers={'Host':'evil.example','X-Workbench-Token':'workbench-token'})[0],403)
        self.assertEqual(self.post('read',{'shop':'brand'},{'Origin':'http://127.0.0.1:65534','X-Workbench-Token':'workbench-token'})[0],403)
        self.assertEqual(self.post('read',{'shop':'brand'},{'Origin':'http://localhost:65534','X-Workbench-Token':'workbench-token'})[0],403)
        self.assertEqual(self.post('read',{'shop':'brand'},{'X-Workbench-Token':'workbench-token'})[0],403)
        self.assertEqual(self.post('agent-read',{'shop':'brand'},{'Origin':'http://127.0.0.1:65534','X-Bridge-Agent-Token':'agent-token'})[0],403)
        self.assertEqual(self.post('status',headers={'Origin':ORIGIN,'X-Workbench-Token':'workbench-token'})[0],403)
        headers={'Origin':ORIGIN,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization, content-type','Access-Control-Request-Private-Network':'true'}
        status,returned,_=self.request('/api/desk/miaoshou-bridge/poll',headers=headers,method='OPTIONS')
        self.assertEqual(status,204);self.assertEqual(returned.get('Access-Control-Allow-Origin'),ORIGIN);self.assertEqual(returned.get('Access-Control-Allow-Private-Network'),'true')
        self.assertEqual(self.request('/api/desk/miaoshou-bridge/status',headers=headers,method='OPTIONS')[0],403)
        self.assertEqual(self.request('/api/desk/miaoshou-bridge/poll',headers={**headers,'Access-Control-Request-Headers':'x-evil'},method='OPTIONS')[0],403)

    def test_pairing_and_read_with_exact_shop_and_restricted_token(self):
        code=self.post('issue',headers={'Origin':self.base,'X-Workbench-Token':'workbench-token'})[2]['code']
        self.assertEqual(self.post('pair',{'code':code,'shop_id':'999'},{'Origin':ORIGIN})[0],403)
        _,_,paired=self.post('pair',{'code':code,'shop_id':'123'},{'Origin':ORIGIN});token=paired['token']
        self.assertEqual(self.post('poll',headers={'Origin':OTHER,'Authorization':'Bearer '+token})[0],403)
        self.assertEqual(self.post('poll',headers={'Origin':ORIGIN,'Authorization':'Bearer wrong'})[0],403)
        self.assertEqual(self.post('agent-read',{'shop':'legacy'}, {'Origin':self.base,'X-Bridge-Agent-Token':'agent-token'})[0],400)
        self.assertEqual(self.post('agent-read',{'shop':'brand','pageSize':200}, {'Origin':self.base,'X-Bridge-Agent-Token':'agent-token'})[0],400)
        self.assertEqual(self.post('status',headers={'Origin':self.base,'X-Bridge-Agent-Token':'agent-token'})[0],403)
        def worker():
            for _ in range(50):
                task=self.post('poll',headers={'Origin':ORIGIN,'Authorization':'Bearer '+token})[2]['task']
                if task:
                    self.post('complete',{'task_id':task['task_id'],'payload':{'shop_id_before':'123','shop_id_after':'123','items':[{'productId':'456','title':'shoe'}],'total':1}}, {'Origin':ORIGIN,'Authorization':'Bearer '+token});return
                time.sleep(.02)
        thread=threading.Thread(target=worker);thread.start()
        with patch.dict(os.environ,{'BEIQIANG_MIAOSHOU_BRIDGE_TOKEN':'agent-token','BEIQIANG_MIAOSHOU_BRIDGE_URL':self.base+'/api/desk/miaoshou-bridge/agent-read'}):
            result=read_store('brand','live')
        thread.join(3)
        self.assertTrue(result['ok']);self.assertEqual(result['data']['items'][0]['title'],'shoe');self.assertNotIn('shopId',result['data'])
        self.assertNotIn('not-for-output',json.dumps(result));self.assertNotIn('agent-token',json.dumps(result))

    def test_target_missing_offline_and_timeout_are_honest(self):
        self.assertEqual(miaoshou_target(self.root),'123')
        self.assertEqual(miaoshou_read(self.app.miaoshou_bridge,{'shop':'brand'})['error'],'bridge_disconnected')
        with patch.dict(os.environ,{},clear=True):self.assertEqual(read_store('brand','live')['error'],'bridge_service_unavailable')
        with patch.dict(os.environ,{'BEIQIANG_MIAOSHOU_BRIDGE_URL':'http://127.0.0.1:1/api/desk/miaoshou-bridge/agent-read','BEIQIANG_MIAOSHOU_BRIDGE_TOKEN':'private'}):
            self.assertEqual(read_store('brand','live')['error'],'bridge_service_unavailable')
        bridge=SimpleNamespace(submit=lambda *args:{'task_id':'x'},get_result=lambda task_id:{'state':'running'})
        self.assertEqual(miaoshou_read(bridge,{'shop':'brand'},timeout=.01)['error'],'bridge_timeout')


if __name__=='__main__':unittest.main()
