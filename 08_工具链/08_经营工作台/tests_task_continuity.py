import unittest
from pathlib import Path
from unittest.mock import patch
from tests_agent_jobs import AgentJobTests, join_job_threads

class TaskContinuityTests(AgentJobTests):
    def test_multiple_links_version_and_validation(self):
        job=self.wait(self.jobs.start('product:shoe','原始目标'))
        job=self.jobs.get_job(job['id'])
        linked=self.jobs.link_conversation(job['id'],provider='chatgpt',conversation_id='abc-123',provenance='explicit_manual',url='https://chatgpt.com/c/abc-123',expected_version=job['version'])
        self.assertEqual(linked['conversations'][-1]['control'],'reference_only')
        self.assertGreater(linked['version'],job['version'])
        with self.assertRaises(ValueError):self.jobs.link_conversation(job['id'],provider='chatgpt',conversation_id='next',provenance='manual',expected_version=job['version'])
        for url in ['https://chatgpt.com.evil/c/next','https://user@chatgpt.com/c/next','https://chatgpt.com/c/other','https://chatgpt.com/c/next?token=secret','javascript:alert(1)']:
            with self.assertRaises(ValueError):self.jobs.link_conversation(job['id'],provider='chatgpt',conversation_id='next',provenance='manual',url=url,expected_version=linked['version'])

    def test_stale_worker_save_preserves_new_link_and_version(self):
        job=self.wait(self.jobs.start('product:shoe','目标'))
        stale=self.jobs.get_job(job['id'])
        linked=self.jobs.link_conversation(job['id'],provider='chatgpt',conversation_id='manual-link',provenance='explicit_manual',expected_version=stale['version'])
        self.jobs._save(stale)
        saved=self.jobs.get_job(job['id'])
        self.assertGreater(saved['version'],linked['version'])
        self.assertTrue(any(c['conversation_id']=='manual-link' for c in saved['conversations']))

    def test_fresh_session_retains_identity_history_and_context(self):
        job=self.wait(self.jobs.start('product:shoe','原始目标'))
        original=self.jobs.get_job(job['id'])
        old_run=dict(original['runs'][0])
        self.app.business.obj['content']='UPDATED CURRENT FACT'
        with self.assertRaises(ValueError):self.jobs.resume(job['id'],'继续',new_session=True)
        next_job=self.jobs.resume(job['id'],'只做下一步',new_session=True,expected_version=original['version'])
        self.wait(next_job)
        current=self.jobs.get_job(job['id'])
        self.assertEqual(current['initial_instruction'],'原始目标')
        self.assertEqual(current['runs'][0],old_run)
        self.assertEqual(len(current['runs']),2)
        self.assertNotIn('resume',self.command)
        prompt=self.processes[-1].stdin.value
        self.assertIn('UPDATED CURRENT FACT',prompt)
        self.assertIn('原始目标',prompt)
        self.assertIn('有依据的可用草稿',prompt)
        self.assertFalse(self.jobs.get_task_context(job['id'])['capabilities']['external_conversation_control'])

    def test_handoff_bounds_and_excludes_conversation_and_event_history(self):
        job=self.wait(self.jobs.start('product:shoe','目标'))
        with self.jobs._write():
            row=self.jobs.get_job(job['id'])
            row['events'].append({'at':'now','type':'message','text':'PRIVATE_EVENT_HISTORY'})
            row['conversations'].append({'provider':'chatgpt','conversation_id':'PRIVATE_CHAT_ID','provenance':'manual'})
            self.jobs._save(row)
        self.app.business.artifacts[0]['content']='A'*200000
        self.app.business.artifacts.append({'id':'unrelated-artifact','object_id':'product:shoe','content':'OTHER_TASK_OUTPUT'})
        prompt=self.jobs._continuity_prompt(job['id'])
        self.assertLess(len(prompt),60000)
        self.assertNotIn('PRIVATE_EVENT_HISTORY',prompt)
        self.assertNotIn('PRIVATE_CHAT_ID',prompt)
        self.assertNotIn('OTHER_TASK_OUTPUT',prompt)
        self.assertIn('"truncated": true',prompt)
        artifacts=self.jobs.get_task_context(job['id'])['artifacts']
        self.assertTrue(artifacts[0]['task_output'])
        self.assertFalse(artifacts[1]['task_output'])

    def test_new_session_cannot_bypass_uncertain_owner(self):
        job=self.wait(self.jobs.start('product:shoe','目标'))
        with self.jobs._write():
            current=self.jobs.get_job(job['id']);current.update(worker_finished=False,owner_pid=123456)
            self.jobs._save(current)
        current=self.jobs.get_job(job['id'])
        with patch.object(self.jobs,'_owner_alive',return_value=None):
            with self.assertRaises(ValueError):self.jobs.resume(job['id'],'继续',new_session=True,expected_version=current['version'])

    def test_current_customer_decisions_workflow_and_commercial_are_read_live(self):
        from types import SimpleNamespace
        self.app.business.obj.update(id='customer:buyer',kind='customer')
        state={'operator_context':'current owner decision','analysis':{'brief':'known buyer'},'workflow':{'next_action':'old next step'},'revision':'v1'}
        self.app.customer_workspace=SimpleNamespace(profile=lambda oid:dict(state),commercial=lambda oid:{'next_action':'current quote'})
        job=self.wait(self.jobs.start('customer:buyer','目标'))
        state['workflow']={'next_action':'latest next step'}
        state['operator_context']='latest owner decision'
        context=self.jobs.get_task_context(job['id'])
        self.assertEqual(context['customer_context']['workflow']['next_action'],'latest next step')
        self.assertEqual(context['customer_context']['operator_context'],'latest owner decision')
        self.assertEqual(context['customer_context']['commercial']['next_action'],'current quote')
        self.assertIn('latest owner decision',self.jobs._continuity_prompt(job['id']))

    def test_legacy_record_defaults_and_live_context(self):
        job=self.wait(self.jobs.start('product:shoe','目标'))
        with self.app.lock:
            import json
            row=self.jobs.get_job(job['id'])
            for key in ('version','conversations','runs','artifact_ids'):row.pop(key,None)
            self.app.db.execute('UPDATE agent_jobs SET data=? WHERE id=?',(json.dumps(row),job['id']));self.app.db.commit()
        current=self.jobs.get_task_context(job['id'])['job']
        self.assertEqual(current['version'],0)
        self.assertEqual(current['conversations'][0]['provenance'],'backend_session_event')
        self.app.business.obj['summary']='current original source'
        self.assertEqual(self.jobs.get_task_context(job['id'])['object']['summary'],'current original source')

# Opt-in isolated real CLI acceptance, never touches production or user chats.
import os
import time

@unittest.skipUnless(os.environ.get('BEIQIANG_LIVE_CODEX')=='1','Consumes two real model invocations')
class FreshSessionLiveTests(unittest.TestCase):
    def test_fresh_session_on_same_synthetic_task(self):
        import tests_desk_http as fixtures
        fixture=fixtures.DeskHTTPTests()
        fixture.setUp();self.addCleanup(fixture.tearDown)
        fixture.stop.stop();fixture.which.stop();fixture.popen.stop()
        fixture.app.inquiry_intake.add({'channel':'other','company':'Synthetic Task Continuity',
                                       'original_text':'Isolated synthetic task continuity, no email sending.'})
        obj=next(o for o in fixture.app.business.list_objects(kind='customer') if o.get('source_type')=='manual_import')
        jobs=fixture.app.agent_jobs
        def wait(job):
            deadline=time.monotonic()+240
            while job['status'] in ('queued','running') and time.monotonic()<deadline:
                time.sleep(.5);job=jobs.get_job(job['id'])
            if job['status'] in ('queued','running'):
                jobs.cancel(job['id']);self.fail('Real fresh-session acceptance timed out; no retry')
            join_job_threads(jobs,job['id'])
            self.assertEqual(job['status'],'completed',job.get('error'))
            return jobs.get_job(job['id'])
        first=wait(jobs.start(obj['id'],'隔离合成验收。禁止联网、shell、发信及写业务字段。最终仅输出 SYNTHETIC_PRIOR_OUTPUT。',mode='outreach_research'))
        first_session=first['session_id']
        second=wait(jobs.resume(first['id'],'隔离合成验收。禁止联网、shell、发信及写业务字段。仅当交接上下文包含之前成果 SYNTHETIC_PRIOR_OUTPUT 时，最终输出 SYNTHETIC_FRESH_CONTEXT_OK。',new_session=True,expected_version=first['version']))
        self.assertEqual(second['id'],first['id'])
        self.assertNotEqual(second['session_id'],first_session)
        self.assertEqual(len(second['runs']),2)
        self.assertEqual(len(second['artifact_ids']),2)
        artifact=next(a for a in jobs.get_task_context(first['id'])['artifacts'] if a['id']==second['artifact_id'])
        self.assertIn('SYNTHETIC_FRESH_CONTEXT_OK',artifact['content'])
        import json
        for attempt in (1,2):
            diagnostic=Path(fixture.app.state)/'agent-jobs'/first['id']/('attempt-'+str(attempt))/'diagnostics.log'
            for line in diagnostic.read_text(encoding='utf-8').splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                item=event.get('item') or {}
                self.assertNotIn(item.get('type'),('web_search','command_execution'))
                self.assertNotIn(item.get('tool'),('send_customer_email','save_customer_email_draft','save_customer_profile'))

if __name__=='__main__':unittest.main()
