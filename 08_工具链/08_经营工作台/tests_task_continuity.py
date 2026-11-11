import unittest
import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests_agent_jobs import AgentJobTests, join_job_threads
from agent_jobs import AgentJobs
from workspaces import WorkspaceConflict

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

    def test_claim_freezes_owner_action_and_later_change_holds_result(self):
        first=self.wait(self.jobs.start('product:shoe','原始目标'))
        planned=self.jobs.adjust(first['id'],expected_version=first['version'],next_action='本轮先核对样品')
        with self.assertRaises(ValueError):
            self.jobs.resume(first['id'],'继续原任务')
        class ObservedGate:
            def __init__(self):self.entered=threading.Event();self.release=threading.Event()
            def wait(self,timeout=None):self.entered.set();return self.release.wait(timeout)
            def set(self):self.release.set()
        gate=ObservedGate();self.options={'gate':gate}
        second=self.jobs.resume(first['id'],'继续原任务',expected_version=planned['version'])
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                if len(self.processes)>=2 and self.processes[-1].stdin.closed:break
                time.sleep(.01)
            self.assertGreaterEqual(len(self.processes),2)
            self.assertTrue(gate.entered.wait(3))
            prompt=self.processes[-1].stdin.value
            self.assertIn('本轮先核对样品',prompt)
            running=self.jobs.get_job(first['id'])
            self.assertEqual(running['attempt_plan']['next_action'],'本轮先核对样品')
            updated=self.jobs.adjust(first['id'],expected_version=running['version'],next_action='下一轮先核对包装')
            self.assertEqual(updated['next_action'],'下一轮先核对包装')
            self.assertNotIn('下一轮先核对包装',prompt)
        finally:gate.set()
        done=self.wait(second)
        self.assertEqual(done['status'],'needs_input')
        self.assertEqual(done['next_action'],'下一轮先核对包装')
        self.assertEqual(done['runs'][-1]['attempt_plan']['next_action'],'本轮先核对样品')
        self.assertEqual(done['runs'][-1]['attempt_plan']['adjustment_version'],planned['adjustment_version'])
        self.assertEqual(done['held_result']['reason'],'planning_changed_during_attempt')
        self.assertEqual(len(self.app.business.artifacts),1)
        held=self.jobs.read_held_result(first['id'])
        self.assertEqual(held['attempt'],2)
        self.assertIn('有依据的可用草稿',held['content'])
        self.assertIn('其他工具',held['warning'])
        self.assertEqual(self.jobs.get_task_context(first['id'])['next_action'],'下一轮先核对包装')
        self.assertTrue(any(x['type']=='planning_adjusted' for x in done['events']))

    def test_stale_worker_save_preserves_planning_event_and_explicit_clear(self):
        job=self.wait(self.jobs.start('product:shoe','目标'))
        stale=self.jobs.get_job(job['id'])
        changed=self.jobs.adjust(job['id'],expected_version=stale['version'],next_action='先核对')
        cleared=self.jobs.adjust(job['id'],expected_version=changed['version'],next_action='')
        self.jobs._save(stale)
        result=self.jobs.get_job(job['id'])
        self.assertEqual(result['next_action'],'')
        self.assertEqual(result['adjustment_version'],cleared['adjustment_version'])
        self.assertEqual(sum(x['type']=='planning_adjusted' for x in result['events']),2)
        self.assertEqual(self.jobs.get_task_context(job['id'])['next_action'],'')

    def test_planned_dispatch_uses_action_frozen_at_claim(self):
        plan=self.jobs.start('product:shoe','准备资料',defer=True)
        planned=self.jobs.adjust(plan['id'],expected_version=plan['version'],next_action='先读取当前商品资料')
        started=self.jobs.dispatch(plan['id'],expected_version=planned['version'])
        done=self.wait(started)
        self.assertEqual(done['status'],'completed')
        self.assertIn('先读取当前商品资料',self.processes[-1].stdin.value)
        self.assertEqual(done['runs'][-1]['attempt_plan']['next_action'],'先读取当前商品资料')
        self.assertEqual(done['runs'][-1]['attempt_plan']['adjustment_version'],planned['adjustment_version'])

    def test_new_session_receives_frozen_owner_action(self):
        first=self.wait(self.jobs.start('product:shoe','原始目标'))
        planned=self.jobs.adjust(first['id'],expected_version=first['version'],next_action='先检查供应依据')
        second=self.jobs.resume(first['id'],'接续工作',new_session=True,expected_version=planned['version'])
        done=self.wait(second)
        self.assertEqual(done['status'],'completed')
        self.assertIn('先检查供应依据',self.processes[-1].stdin.value)
        self.assertEqual(done['runs'][-1]['attempt_plan']['next_action'],'先检查供应依据')
        self.assertNotIn('resume',self.command)

    def test_result_commit_fences_another_database_connection(self):
        dbfile=self.root/'shared.sqlite3'
        first_db=sqlite3.connect(dbfile,check_same_thread=False)
        second_db=sqlite3.connect(dbfile,check_same_thread=False)
        first_app=SimpleNamespace(root=self.root,state=self.root/'.local',lock=threading.RLock(),db=first_db,business=self.app.business)
        second_app=SimpleNamespace(root=self.root,state=self.root/'.local',lock=threading.RLock(),db=second_db,business=self.app.business)
        first=AgentJobs(first_app);other=AgentJobs(second_app)
        entered=threading.Event();release=threading.Event();save=first_app.business.save_artifact
        def blocked(*args,**kwargs):
            entered.set()
            if not release.wait(5):raise AssertionError('test failed to release final save')
            return save(*args,**kwargs)
        first_app.business.save_artifact=blocked
        try:
            job=first.start('product:shoe','隔离并发验证')
            self.assertTrue(entered.wait(3))
            committing=other.get_job(job['id'])
            self.assertEqual(committing['result_commit']['state'],'saving')
            self.assertEqual(committing['result_commit']['attempt'],1)
            self.assertEqual(committing['result_commit']['owner_id'],first.owner_id)
            self.assertTrue(committing['result_commit']['started_at'])
            with self.assertRaises(WorkspaceConflict):
                other.adjust(job['id'],expected_version=committing['version'],next_action='不要覆盖当前结果')
            release.set();join_job_threads(first,job['id'])
            complete=other.get_job(job['id'])
            self.assertEqual(complete['status'],'completed')
            self.assertNotIn('result_commit',complete)
            adjusted=other.adjust(job['id'],expected_version=complete['version'],next_action='下一次再核对')
            self.assertEqual(adjusted['next_action'],'下一次再核对')
        finally:
            release.set();join_job_threads(first)
            first_app.business.save_artifact=save
            first_db.close();second_db.close()

    def test_unknown_result_requires_explicit_reconciliation_before_resume(self):
        self.app.business.fail_save=True
        job=self.wait(self.jobs.start('product:shoe','目标'))
        self.assertEqual(job['status'],'needs_input')
        self.assertEqual(job['result_commit']['state'],'outcome_unknown')
        self.assertIn('有依据的可用草稿',self.jobs.read_held_result(job['id'])['content'])
        with self.assertRaises(ValueError):
            self.jobs.resume(job['id'],'继续',new_session=True,expected_version=job['version'])
        with self.assertRaises(ValueError):
            self.jobs.reconcile_result_commit(job['id'],expected_version=job['version'],evidence='  ',outcome='failed')
        with self.assertRaises(WorkspaceConflict):
            self.jobs.reconcile_result_commit(job['id'],expected_version=job['version']-1,evidence='已核对业务资料',outcome='failed')
        count=len(self.processes)
        reviewed=self.jobs.reconcile_result_commit(job['id'],expected_version=job['version'],evidence='已核对业务资料和回执',outcome='failed')
        self.assertNotIn('result_commit',reviewed)
        self.assertEqual(reviewed['status'],'needs_input')
        self.assertEqual(reviewed['result_reconciliations'][-1]['evidence'],'已核对业务资料和回执')
        self.assertEqual(len(self.processes),count)

    def test_restart_during_result_commit_preserves_uncertain_outcome(self):
        job=self.wait(self.jobs.start('product:shoe','目标'))
        with self.jobs._write():
            row=self.jobs.get_job(job['id'])
            row.update(status='running',owner_pid=999999998,process_id=999999999,worker_finished=False,
                       result_commit={'state':'saving','attempt':row['attempt'],'owner_id':'old',
                                      'owner_pid':999999998,'started_at':'2026-11-11T00:00:00Z'})
            self.jobs._save(row)
        with patch.object(AgentJobs,'_pid_alive',return_value=False):
            other=AgentJobs(self.app)
            recovered=other.get_job(job['id'])
            self.assertEqual(recovered['status'],'needs_input')
            self.assertEqual(recovered['result_commit']['state'],'outcome_unknown')
            self.assertEqual(recovered['held_result']['reason'],'result_outcome_unknown')
            with self.assertRaises(ValueError):
                other.resume(job['id'],'继续',new_session=True,expected_version=recovered['version'])
        self.assertEqual(len(self.processes),1)

    def test_held_result_cannot_read_unrecorded_or_oversized_attempt(self):
        job=self.wait(self.jobs.start('product:shoe','目标'))
        with self.assertRaises(ValueError):self.jobs.read_held_result(job['id'])
        with self.jobs._write():
            row=self.jobs.get_job(job['id'])
            row['held_result']={'attempt':1,'format':'markdown','reason':'result_outcome_unknown','recorded_at':'now'}
            self.jobs._save(row)
        path=self.app.state/'agent-jobs'/job['id']/'attempt-1'/'final.md'
        path.write_bytes(b'a'*2_000_001)
        with self.assertRaises(ValueError):self.jobs.read_held_result(job['id'])
        with self.assertRaises(ValueError):self.jobs.read_held_result('../other')

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
