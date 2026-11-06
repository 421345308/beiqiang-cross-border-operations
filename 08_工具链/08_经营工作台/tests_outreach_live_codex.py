"""Opt-in real Codex execution on an isolated, synthetic email draft only."""
import json
import os
from pathlib import Path
import time
import unittest

import tests_desk_http as http_fixtures
from tests_agent_jobs import join_job_threads


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
        events = []
        for line in diagnostics.read_text(encoding='utf8').splitlines() if diagnostics.exists() else []:
            try: event = json.loads(line)
            except ValueError: continue
            item = event.get('item') or {}
            if event.get('type') == 'item.completed' and item.get('type') in ('mcp_tool_call', 'tool_call', 'web_search', 'command_execution'):
                events.append({'type': item.get('type'), 'server': item.get('server'),
                               'tool': item.get('tool'), 'error': bool(item.get('error'))})
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
        fixture.stop.stop(); fixture.which.stop(); fixture.popen.stop()
        for name in ('Synthetic Research Alpha', 'Synthetic Research Beta'):
            fixture.app.inquiry_intake.add({'channel': 'other', 'original_text': 'Synthetic research only: '+name, 'company': name})
        customers = {o['title']: o['id'] for o in fixture.app.business.list_objects(kind='customer')
                     if o.get('source_type') == 'manual_import'}
        self.assertEqual(set(customers), {'Synthetic Research Alpha', 'Synthetic Research Beta'})
        jobs = fixture.app.agent_jobs; started = {}
        for index, (name, oid) in enumerate(sorted(customers.items())):
            marker = 'SYNTHETIC_RESEARCH_' + ('A' if index == 0 else 'B')
            instruction = ('这是隔离合成验收，禁止联网、发信、shell和访问其他客户。'
                '只使用当前客户MCP：先get_customer_profile读取实际revision和source_hash，'
                '再save_customer_profile原样传入revision及source_hash，把analysis.brief设置为'+marker+'。'
                '然后prepare_customer_email_draft，使用返回version通过save_customer_email_draft保存：'
                'to为buyer'+str(index)+'@example.invalid，subject为'+marker+'，body_en为Synthetic research draft，'
                'body_zh为模拟研究草稿。无需附件，不要声称发信。保存后各读取一次确认。')
            started[oid] = (jobs.start(oid, instruction, mode='outreach_research', batch_id='b'*32), marker, index)
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
            events = []
            for line in diagnostics.read_text(encoding='utf8').splitlines() if diagnostics.exists() else []:
                try: event = json.loads(line)
                except ValueError: continue
                item = event.get('item') or {}
                if event.get('type') == 'item.completed' and item.get('type') in ('mcp_tool_call','tool_call','web_search','command_execution'):
                    events.append({'type':item.get('type'),'tool':item.get('tool'),'error':bool(item.get('error'))})
            results[oid] = {'status':job['status'],'error':job.get('error'),
                'profile_saved':profile['analysis'].get('brief') == marker,
                'draft_saved':draft.get('subject') == marker and draft.get('to') == 'buyer'+str(index)+'@example.invalid'
                    and draft.get('body_zh') == '模拟研究草稿' and draft.get('status') == 'draft',
                'batch_saved':job.get('batch_id') == 'b'*32,'events':events}
        print('OUTREACH_PARALLEL_LIVE_RESULT ' + json.dumps(list(results.values()), ensure_ascii=True))
        for result in results.values():
            self.assertEqual(result['status'], 'completed', result)
            self.assertTrue(result['profile_saved'] and result['draft_saved'] and result['batch_saved'], result)
            names = {e['tool'] for e in result['events'] if not e['error']}
            self.assertTrue({'get_customer_profile','save_customer_profile','prepare_customer_email_draft',
                             'save_customer_email_draft'} <= names, result)
            self.assertFalse(any(e['type'] in ('web_search','command_execution') for e in result['events']), result)


if __name__ == '__main__': unittest.main()
