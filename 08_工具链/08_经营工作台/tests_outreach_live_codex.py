"""Opt-in real Codex execution on an isolated, synthetic email draft only."""
import json
import os
from pathlib import Path
import time
import unittest
import shutil
import uuid

import tests_desk_http as http_fixtures
from tests_agent_jobs import join_job_threads


def retain_failed_synthetic_logs(test, fixture):
    """Keep only opt-in synthetic diagnostics privately when acceptance fails."""
    result=getattr(getattr(test,'_outcome',None),'result',None)
    failed=bool(result and any(case is test for case,_ in list(result.failures)+list(result.errors)))
    if not failed:return
    destination=Path(__file__).resolve().parent/'.local'/'live-acceptance-failures'/uuid.uuid4().hex
    source=Path(fixture.app.state)/'agent-jobs'
    for name in ('diagnostics.log','source-reads.jsonl'):
        for path in source.glob('*/attempt-*/'+name):
            target=destination/path.relative_to(source)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
    print('SYNTHETIC_FAILURE_LOGS '+str(destination))


def tool_failed(item):
    result=item.get('result')
    return bool(item.get('error') or (isinstance(result,dict) and result.get('isError'))
                or item.get('status') in ('failed','error','cancelled'))


class DiagnosticEnvelopeTests(unittest.TestCase):
    def test_oversized_completed_tool_keeps_valid_metadata_and_next_event(self):
        import tempfile
        from types import SimpleNamespace
        from agent_jobs import AgentJobs
        jobs=object.__new__(AgentJobs);jobs.app=SimpleNamespace()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            large={'type':'item.completed','item':{'id':'call-large','type':'mcp_tool_call',
                'server':'beiqiang_business','tool':'save_customer_profile','status':'completed',
                'arguments':{'private':'DO_NOT_RETAIN_ARGUMENT'},'result':{'content':'x'*40000},'error':None}}
            original=json.dumps(large)+'\n'
            next_event=json.dumps({'type':'item.completed','item':{'id':'call-next','type':'mcp_tool_call','tool':'get_customer_profile'}})+'\n'
            old_output=original[:32000]+next_event[:32000]
            self.assertEqual(len(old_output.splitlines()),1)
            with self.assertRaises(ValueError):json.loads(old_output)
            jobs._diagnostic(path,original)
            jobs._diagnostic(path,json.dumps({'type':'item.completed','item':{'id':'call-next','type':'mcp_tool_call','tool':'get_customer_profile'}})+'\n')
            lines=(path/'diagnostics.log').read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines),2)
            first,second=map(json.loads,lines)
            self.assertEqual(first['type'],'item.completed')
            self.assertEqual(first['item'],{'id':'call-large','type':'mcp_tool_call','server':'beiqiang_business',
                                           'tool':'save_customer_profile','status':'completed','error':False})
            self.assertTrue(first['diagnostic_projection']['truncated'])
            self.assertNotIn('DO_NOT_RETAIN_ARGUMENT',lines[0])
            self.assertNotIn('result',first['item'])
            self.assertEqual(second['item']['id'],'call-next')
            self.assertLess(len(lines[0]),1000)
    def test_held_stderr_reader_cannot_block_job_completion(self):
        import threading
        from unittest.mock import patch
        from tests_agent_jobs import AgentJobTests
        fixture=AgentJobTests(methodName='runTest');fixture.setUp()
        release=threading.Event();closed=threading.Event()
        class HeldStderr:
            def __iter__(self):
                release.wait(20)
                return iter(())
            def close(self):closed.set()
        original_spawn=fixture.jobs.backend.spawn
        def spawn(*args,**kwargs):
            process=original_spawn(*args,**kwargs);process.stderr=HeldStderr();return process
        original_join=threading.Thread.join
        def short_join(thread,timeout=None):
            return original_join(thread,.01 if thread.name.startswith('agent-stderr-') else timeout)
        try:
            with patch.object(fixture.jobs.backend,'spawn',side_effect=spawn),patch.object(threading.Thread,'join',short_join):
                started=time.monotonic()
                job=fixture.wait(fixture.jobs.start('product:shoe','synthetic only'))
                self.assertLess(time.monotonic()-started,2)
                self.assertEqual(job['status'],'completed')
                self.assertFalse(closed.is_set(),'Main worker must not synchronously close an active reader')
                log=Path(fixture.app.state)/'agent-jobs'/job['id']/'attempt-1'/'diagnostics.log'
                self.assertIn('"diagnostic_trace_incomplete": true',log.read_text(encoding='utf-8'))
            release.set()
            self.assertTrue(closed.wait(2),'Reader owns and eventually closes stderr')
        finally:
            release.set();fixture.tearDown()

    def test_backend_separates_stderr_telemetry_from_json_events(self):
        import sys
        import threading
        from codex_backend import CodexBackend
        code="import sys; sys.stdout.write('{\"type\":\"item.completed\",\"item\":{\"type\":\"mcp_tool_call\",\"tool\":\"save_customer_profile\"}}');sys.stdout.flush();sys.stderr.write('TELEMETRY\\n');sys.stderr.flush();sys.stdout.write('\\n');sys.stdout.flush()"
        process=CodexBackend.spawn([sys.executable,'-c',code],env=os.environ.copy(),flags={})
        captured=[]
        reader=threading.Thread(target=lambda:captured.extend(process.stderr.readlines()))
        reader.start()
        stdout=process.stdout.read();process.wait(timeout=10);reader.join(timeout=10)
        for stream in (process.stdin,process.stdout,process.stderr):stream.close()
        self.assertEqual(json.loads(stdout)['item']['tool'],'save_customer_profile')
        self.assertEqual(captured,['TELEMETRY\n'])
        # The old STDERR=STDOUT route produces a single invalid JSON line.
        with self.assertRaises(ValueError):json.loads(stdout.rstrip('\n')+captured[0]+'\n')

    def test_oversized_error_and_size_cap_are_not_successful_complete_trace(self):
        import tempfile
        from types import SimpleNamespace
        from agent_jobs import AgentJobs
        jobs=object.__new__(AgentJobs);jobs.app=SimpleNamespace()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            event={'type':'item.completed','item':{'type':'mcp_tool_call','tool':'save_customer_profile',
                'status':'completed','error':None,'result':{'isError':True,'content':'x'*40000}}}
            jobs._diagnostic(path,json.dumps(event))
            projected=json.loads((path/'diagnostics.log').read_text())
            self.assertTrue(tool_failed(projected['item']))
            jobs._diagnostic(path,'non JSON diagnostic without newline')
            jobs._diagnostic(path,json.dumps({'type':'turn.completed'}))
            lines=(path/'diagnostics.log').read_text().splitlines()
            self.assertEqual(json.loads(lines[-1])['type'],'turn.completed')
            (path/'diagnostics.log').write_text('x'*2_000_000)
            jobs._diagnostic(path,json.dumps(event))
            size=(path/'diagnostics.log').stat().st_size
            jobs._diagnostic(path,json.dumps(event))
            self.assertEqual((path/'diagnostics.log').stat().st_size,size)
            self.assertTrue(json.loads((path/'diagnostics.log').read_text().splitlines()[-1])['diagnostic_trace_incomplete'])


@unittest.skipUnless(os.environ.get('BEIQIANG_LIVE_CODEX') == '1', 'Consumes one real model invocation')
class OutreachLiveCodexTests(unittest.TestCase):
    def test_agent_revises_only_bound_synthetic_draft(self):
        fixture = http_fixtures.DeskHTTPTests()
        fixture.setUp(); self.addCleanup(fixture.tearDown)
        fixture.stop.stop(); fixture.which.stop(); fixture.popen.stop()
        fixture.app.inquiry_intake.add({'channel': 'other', 'original_text': 'Synthetic only',
                                       'company': 'Internal synthetic fixture'})
        matches = [o for o in fixture.app.business.list_objects(kind='customer') if o.get('source_type') == 'manual_import']
        self.assertEqual(len(matches), 1); oid = matches[0]['id']
        drafts = fixture.app.gmail_drafts
        draft = drafts.get(oid)
        original = drafts.save(oid, draft['version'], {'to': 'fixture@example.invalid',
            'subject': 'Synthetic fixture subject', 'body_en': 'Original synthetic English.', 'body_zh': '原始模拟中文。'})
        marker = 'SYNTHETIC_REVISED_ONLY'
        instruction = ('这是隔离模拟数据。不要联网、发信、使用 shell 或操作其他对象。'
                       '先读取当前客户草稿，再通过草稿工具将英文正文改为 "' + marker +
                       '"，中文对照改为“模拟内容已修改”；保持收件人和主题不变。保存后再次读取草稿核对。')
        jobs = fixture.app.agent_jobs
        job = jobs.start(oid, instruction, mode='outreach_draft', batch_id='a' * 32)
        deadline = time.monotonic() + 240
        while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
            time.sleep(.5); job = jobs.get_job(job['id'])
        if job['status'] in ('queued', 'running'):
            jobs.cancel(job['id']); self.fail('Real Codex exceeded 240 seconds; cancelled without retry')
        join_job_threads(jobs, job['id'])
        final = drafts._saved(oid)
        diagnostics = Path(fixture.app.state) / 'agent-jobs' / job['id'] / 'attempt-1' / 'diagnostics.log'
        self.assertNotIn('\"diagnostic_trace_incomplete\": true',diagnostics.read_text(encoding='utf8'))
        events = []
        for line in diagnostics.read_text(encoding='utf8').splitlines() if diagnostics.exists() else []:
            try: event = json.loads(line)
            except ValueError: continue
            item = event.get('item') or {}
            if event.get('type') == 'item.completed' and item.get('type') in ('mcp_tool_call', 'tool_call', 'web_search', 'command_execution'):
                events.append({'type': item.get('type'), 'server': item.get('server'),
                               'tool': item.get('tool'), 'error': tool_failed(item)})
        result = {'status': job['status'], 'error': job.get('error'), 'batch_id_saved': job.get('batch_id') == 'a' * 32,
                  'english_updated': final.get('body_en') == marker, 'chinese_updated': final.get('body_zh') == '模拟内容已修改',
                  'recipient_unchanged': final.get('to') == original['to'],
                  'subject_unchanged': final.get('subject') == original['subject'], 'tools': events}
        print('OUTREACH_LIVE_CODEX_RESULT ' + json.dumps(result, ensure_ascii=True))
        self.assertEqual(job['status'], 'completed', result)
        self.assertTrue(all(result[k] for k in ('batch_id_saved', 'english_updated', 'chinese_updated',
                                                  'recipient_unchanged', 'subject_unchanged')), result)
        names = {e['tool'] for e in events if not e['error']}
        self.assertTrue({'get_customer_email_draft', 'save_customer_email_draft'} <= names, result)
        self.assertFalse(any(e['type'] in ('web_search', 'command_execution') for e in events), result)

    def test_two_research_agents_prepare_separate_synthetic_customers(self):
        fixture = http_fixtures.DeskHTTPTests()
        fixture.setUp(); self.addCleanup(fixture.tearDown)
        self.addCleanup(retain_failed_synthetic_logs,self,fixture)
        fixture.stop.stop(); fixture.which.stop(); fixture.popen.stop()
        for name in ('Synthetic Research Alpha', 'Synthetic Research Beta'):
            fixture.app.inquiry_intake.add({'channel': 'other', 'original_text': 'Synthetic research only: '+name, 'company': name})
        customers = {o['title']: o['id'] for o in fixture.app.business.list_objects(kind='customer')
                     if o.get('source_type') == 'manual_import'}
        self.assertEqual(set(customers), {'Synthetic Research Alpha', 'Synthetic Research Beta'})
        jobs = fixture.app.agent_jobs; started = {}
        batch=fixture.app.customer_batches.create({'title':'Synthetic parallel research','object_ids':list(customers.values())})
        instruction=('这是隔离合成验收，禁止联网、发信、shell和访问其他客户。'
            '当前客户名称含 Alpha 时，标记用 SYNTHETIC_RESEARCH_A、收件人 buyer0@example.invalid；'
            '名称含 Beta 时，标记用 SYNTHETIC_RESEARCH_B、收件人 buyer1@example.invalid。'
            '只使用当前客户MCP：先get_customer_profile读取实际revision和source_hash，'
            '再save_customer_profile原样传入revision及source_hash，把analysis.brief设置为当前客户标记。'
            '然后prepare_customer_email_draft，使用返回version通过save_customer_email_draft保存：'
            'to用当前客户收件人，subject用当前客户标记，body_en为Synthetic research draft，'
            'body_zh为模拟研究草稿。无需附件，不要声称发信。保存后各读取一次确认。')
        created=fixture.app.batch_research.begin({'batch_id':batch['id'],'revision':batch['revision'],
            'object_ids':list(customers.values()),'instruction':instruction,'request_id':'c'*32})
        self.assertTrue(all(row['status']=='started' for row in created['results']),created)
        by_id={row['object_id']:row['job'] for row in created['results']}
        for index, (name, oid) in enumerate(sorted(customers.items())):
            marker = 'SYNTHETIC_RESEARCH_' + ('A' if index == 0 else 'B')
            started[oid] = (by_id[oid], marker, index)
        self.assertEqual(len(jobs.threads), 2, 'Both independent research jobs should be active together')
        results = {}
        deadline = time.monotonic() + 240
        for oid, (job, marker, index) in started.items():
            while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
                time.sleep(.5); job = jobs.get_job(job['id'])
            if job['status'] in ('queued', 'running'):
                jobs.cancel(job['id']); self.fail('Real research exceeded 240 seconds; cancelled without retry')
            join_job_threads(jobs, job['id'])
            profile = fixture.app.customer_workspace.profile(oid); draft = fixture.app.gmail_drafts._saved(oid) or {}
            diagnostics = Path(fixture.app.state) / 'agent-jobs' / job['id'] / 'attempt-1' / 'diagnostics.log'
            self.assertNotIn('\"diagnostic_trace_incomplete\": true',diagnostics.read_text(encoding='utf8'))
            events = []
            for line in diagnostics.read_text(encoding='utf8').splitlines() if diagnostics.exists() else []:
                try: event = json.loads(line)
                except ValueError: continue
                item = event.get('item') or {}
                if event.get('type') == 'item.completed' and item.get('type') in ('mcp_tool_call','tool_call','web_search','command_execution'):
                    events.append({'type':item.get('type'),'tool':item.get('tool'),'error':tool_failed(item)})
            results[oid] = {'status':job['status'],'error':job.get('error'),
                'profile_saved':profile['analysis'].get('brief') == marker,
                'draft_saved':draft.get('subject') == marker and draft.get('to') == 'buyer'+str(index)+'@example.invalid'
                    and draft.get('body_zh') == '模拟研究草稿' and draft.get('status') == 'draft',
                'batch_saved':job.get('batch_id') == batch['id'],'events':events}
        print('OUTREACH_PARALLEL_LIVE_RESULT ' + json.dumps(list(results.values()), ensure_ascii=True))
        for result in results.values():
            self.assertEqual(result['status'], 'completed', result)
            self.assertTrue(result['profile_saved'] and result['draft_saved'] and result['batch_saved'], result)
            names = {e['tool'] for e in result['events'] if not e['error']}
            self.assertTrue({'get_customer_profile','save_customer_profile','prepare_customer_email_draft',
                             'save_customer_email_draft'} <= names, result)
            self.assertFalse(any(e['type'] in ('web_search','command_execution') for e in result['events']), result)
        graph=jobs.get_graph(created['group_id'])
        self.assertEqual(graph['aggregate']['status'],'completed')
        self.assertEqual(graph['aggregate']['counts'].get('completed'),2)
        self.assertEqual(len([job for job in graph['jobs'] if job.get('parent_job_id')==created['group_id']]),2)


if __name__ == '__main__': unittest.main()
