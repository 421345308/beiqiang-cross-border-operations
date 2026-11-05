"""Opt-in, one real model invocation against an isolated synthetic customer.

BEIQIANG_LIVE_CODEX=1 python -m unittest tests_customer_live_codex
Optional BEIQIANG_LIVE_CODEX_EVIDENCE names a directory for synthetic readbacks
and a tool-name audit. No credentials or raw CLI diagnostics are exported.
"""
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import Mock

import tests_desk_http as http_fixtures
from codex_backend import CodexBackend
from tests_agent_jobs import join_job_threads


@unittest.skipUnless(os.environ.get('BEIQIANG_LIVE_CODEX')=='1','Requires explicit BEIQIANG_LIVE_CODEX=1; consumes one model call')
class CustomerLiveCodexTests(unittest.TestCase):
    def test_real_cli_saves_profile_and_workflow_through_bound_mcp(self):
        fixture=http_fixtures.DeskHTTPTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        # Reuse only the HTTP/source fixture. Restore every model-process mock
        # before resolving or spawning the real production backend.
        fixture.stop.stop();fixture.which.stop();fixture.popen.stop()
        jobs=fixture.app.agent_jobs
        self.assertIsInstance(jobs.backend,CodexBackend)
        import agent_jobs
        import codex_backend
        self.assertNotIsInstance(agent_jobs.shutil.which,Mock)
        self.assertNotIsInstance(codex_backend.subprocess.Popen,Mock)
        self.assertNotIsInstance(type(jobs)._stop,Mock)
        exe=jobs.backend.resolve_executable()
        self.assertTrue(exe,'Actual Codex CLI is unavailable; no model invocation attempted')
        original='INTERNAL SYNTHETIC TEST ONLY. Please discuss sample options. No real buyer, email or order.'
        row=fixture.app.inquiry_intake.add({'channel':'other','original_text':original,'company':'Internal synthetic customer'})
        # Business assigns the canonical manual-import identity.
        candidates=fixture.app.business.list_objects(kind='customer')
        matching=[obj for obj in candidates if obj.get('source_type')=='manual_import']
        self.assertEqual(len(matching),1)
        oid=matching[0]['id']
        marker='LIVE_MCP_SYNTHETIC_ACCEPTANCE'
        instruction=(
            '本次仅做隔离模拟客户的工具验收，所有资料为合成数据，没有真实客户。'
            '禁止邮件、Gmail、联网检索、浏览器、外部服务、Git、子Agent、shell或直接文件修改。'
            '只调用当前beiqiang_business MCP工具并输出简短Markdown。'
            '按顺序完成：1 get_customer_profile读取实际revision和source_hash；'
            '2 save_customer_profile原样传入该revision及source_hash，analysis仅更新brief为'+marker+'；'
            '3 get_customer_workflow读取最新revision；'
            '4 save_customer_workflow原样传该revision，next_action为'+marker+'，note为内部模拟验收；'
            '5 再次get_customer_profile与get_customer_workflow核对上述两字段。'
            '保存版本冲突或工具失败时停止，不自行重试或绕过。不要执行其它经营动作。最终说明模拟客户写入是否成功。')
        code,started=fixture.request('/api/desk/jobs',{'object_id':oid,'instruction':instruction,'mode':'draft'})
        self.assertEqual(code,201)
        deadline=time.monotonic()+240
        job=started
        while job['status'] in ('queued','running') and time.monotonic()<deadline:
            time.sleep(.5)
            job=jobs.get_job(started['id'])
        if job['status'] in ('queued','running'):
            jobs.cancel(job['id'])
            self.fail('Real Codex invocation exceeded 240 seconds; cancelled, not retried')
        join_job_threads(jobs,job['id'])
        folder=Path(fixture.app.state)/'agent-jobs'/job['id']/'attempt-1'
        tool_events=[]
        diagnostics=folder/'diagnostics.log'
        for line in diagnostics.read_text(encoding='utf8').splitlines() if diagnostics.exists() else []:
            try:event=json.loads(line)
            except ValueError:continue
            item=event.get('item') or {}
            if event.get('type')=='item.completed' and item.get('type') in ('mcp_tool_call','tool_call','web_search','command_execution'):
                tool_events.append({'type':item.get('type'),'server':item.get('server'),'tool':item.get('tool'),
                                    'status':item.get('status'),'error':bool(item.get('error'))})
        profile=fixture.app.customer_workspace.profile(oid)
        workflow=fixture.app.customer_workspace.workflow(oid)
        summary={'status':job['status'],'error':job.get('error'),'attempt':job['attempt'],
                 'model':codex_backend.MODEL,'session_present':bool(job.get('session_id')),
                 'actual_executable_resolved':bool(exe),'tools':tool_events,
                 'profile_brief':profile['analysis'].get('brief'),'workflow_next_action':workflow['next_action'],
                 'source_unchanged':profile['original_text']==original}
        evidence=os.environ.get('BEIQIANG_LIVE_CODEX_EVIDENCE')
        if evidence:
            destination=Path(evidence).resolve();destination.mkdir(parents=True,exist_ok=True)
            (destination/'live-codex-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
            audit=folder/'source-reads.jsonl'
            if audit.exists():(destination/'source-reads.jsonl').write_bytes(audit.read_bytes())
        print('LIVE_CODEX_RESULT '+json.dumps(summary,ensure_ascii=True))
        self.assertEqual(job['status'],'completed',summary)
        self.assertEqual(profile['analysis'].get('brief'),marker,summary)
        self.assertEqual(workflow['next_action'],marker,summary)
        self.assertTrue(summary['source_unchanged'])
        called={event['tool'] for event in tool_events if not event['error']}
        self.assertTrue({'get_customer_profile','save_customer_profile','get_customer_workflow','save_customer_workflow'}<=called,summary)
        self.assertFalse(any(event['type'] in ('web_search','command_execution') for event in tool_events),summary)
        allowed={'get_business_context','get_customer_profile','save_customer_profile',
                 'get_customer_workflow','save_customer_workflow'}
        self.assertTrue(all(event['server']=='beiqiang_business' and event['tool'] in allowed
                            for event in tool_events),summary)


if __name__=='__main__':unittest.main()
