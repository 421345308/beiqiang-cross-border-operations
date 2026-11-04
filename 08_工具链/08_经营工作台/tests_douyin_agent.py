import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from desk_cli import invoke
from desk_mcp import DeskTools, dispatch
from douyin_agent import read_store


class DouyinAgentTests(unittest.TestCase):
    def test_check_only_targets_requested_shop_and_keeps_failure(self):
        calls=[]
        def runner(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0,stdout=json.dumps({'shops':[{'id':'brand','ok':False,'error':{'code':'session_expired'}}],'notice':'只读'}))
        result=read_store('brand','check',runner=runner)
        self.assertIn('--shop=brand',calls[0]);self.assertIn('--check-unbound',calls[0])
        self.assertEqual(result['result']['error']['code'],'session_expired')
        self.assertEqual(result['mode'],'check')

    def test_snapshot_never_calls_network_or_substitutes_other_shop(self):
        calls=[]
        def runner(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0,stdout=json.dumps({'available':True,'capturedAt':'2026-11-04T18:49:43+08:00','count':56,'notice':'非实时'}))
        result=read_store('brand','snapshot',runner=runner)
        self.assertIn('--snapshot-only',calls[0]);self.assertNotIn('--check-unbound',calls[0])
        self.assertEqual(result['count'],56);self.assertIn('非实时',result['notice'])
        self.assertFalse(read_store('legacy','snapshot',runner=runner)['available'])
        self.assertEqual(len(calls),1)

    def test_mismatch_invalid_and_internal_errors_are_not_leaked(self):
        for shop,mode in [('brand','write'),('else','check'),('brand','')]:
            with self.assertRaises(ValueError):read_store(shop,mode)
        for runner in (lambda *a,**k:SimpleNamespace(returncode=0,stdout='{"shops":[{"id":"legacy"}]}'),
                       lambda *a,**k:SimpleNamespace(returncode=1,stdout='private content'),
                       lambda *a,**k:(_ for _ in ()).throw(subprocess.TimeoutExpired('private',50))):
            with self.assertRaises(ValueError) as raised:read_store('brand','check',runner=runner)
            self.assertNotIn('private',str(raised.exception))

    def test_mcp_and_cli_share_the_reader_but_auto_drafts_cannot_access_it(self):
        with tempfile.TemporaryDirectory() as root:
            business=SimpleNamespace(get_object=lambda oid:{'id':oid,'kind':'channel','source':'09_国内电商/抖店/README.md'})
            normal=DeskTools(business,root,'channel:douyin')
            auto=DeskTools(business,root,'channel:douyin',read_only=True)
            with patch('douyin_agent.read_store',return_value={'available':False,'notice':'非实时'}) as reader:
                self.assertEqual(normal.call('read_douyin_store',{'shop':'brand','mode':'snapshot'})['notice'],'非实时')
                self.assertEqual(invoke(business,'douyin','snapshot',shop='brand')['notice'],'非实时')
                self.assertEqual(reader.call_count,2)
                with self.assertRaises(ValueError):auto.call('read_douyin_store',{'shop':'brand','mode':'snapshot'})
                self.assertEqual(reader.call_count,2)
            tools=dispatch(auto,{'id':1,'method':'tools/list'})['result']['tools']
            self.assertNotIn('read_douyin_store',[t['name'] for t in tools])
            paths={r['path']:r['role'] for r in normal.sources()}
            self.assertEqual(paths['09_国内电商/抖店/README.md'],'current-channel-source')
            self.assertEqual(paths['09_国内电商/抖店/AGENTS.md'],'applicable-sop')
            self.assertEqual(paths['08_工具链/01_业务脚本/抖店妙手/README.md'],'channel-tool-guide')
            self.assertFalse(any(path.startswith('04_客户开发/') for path in paths))


if __name__ == '__main__':unittest.main()
