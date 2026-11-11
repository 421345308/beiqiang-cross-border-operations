"""Isolated AgentJobs supervisor tests. No live service, customer or mail."""
import copy
import json
import sqlite3
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent_jobs import AgentJobs
from supervisor import Supervisor, verify_guard
import tests_agent_jobs as fixture
from workspaces import WorkspaceConflict


CASE = {'business_outcome':'让买家获得可审核答复草稿',
        'current_bottleneck':'本轮草稿还缺指定要点',
        'intended_change':'依据现有资料补全草稿',
        'stop_condition':'要点出现后转人工检查；最多自动接续一次',
        'evidence_source':'合成客户对象及本轮成果'}


class SupervisorTests(unittest.TestCase):
    setUp = fixture.AgentJobTests.setUp
    tearDown = fixture.AgentJobTests.tearDown
    wait = fixture.AgentJobTests.wait

    def first(self, mode='mail_draft'):
        job=self.wait(self.jobs.start('product:shoe', '合成工作，只准备草稿', mode=mode))
        return self.jobs.get_job(job['id'])

    def configure(self, sup, job, *, text='需要补充的要点', prerequisite='ready', value='supported', case=CASE):
        return sup.configure(job['id'], expected_version=job['version'],
            acceptance_criteria={'kind':'artifact_contains','text':text},
            continuation_instruction='依据同一合成对象资料补齐草稿要点，交人工审核，不发送。',
            authorization_ref='合成测试的明确只读草稿授权', business_case=copy.deepcopy(case),
            prerequisite_state=prerequisite, value_state=value)

    def test_missing_condition_allows_only_one_actual_read_only_followup(self):
        first = self.first()
        sup = Supervisor(self.jobs)
        configured = self.configure(sup,first)
        report = sup.scan_once()
        self.assertEqual(report['advanced'],1, report)
        completed = self.wait(configured)
        self.assertEqual(completed['attempt'],2)
        review = completed['completion_events']['1']['assessment']
        self.assertEqual((review['disposition'],review['goal_status'],review['capability_status']),
                         ('continue','unknown','unknown'))
        observation = json.loads(review['evidence']['detail'])
        self.assertEqual(observation['artifact_id'],'artifact-1')
        self.assertFalse(observation['condition_met'])
        self.assertEqual(len(observation['sha256']),64)
        self.assertEqual(completed['completion_events']['1']['dispatch']['supervision_revision'],
                         configured['supervision_revision'])
        self.assertIn('read-only',self.command)
        self.assertEqual(len(self.processes),2)
        next_report=sup.scan_once()
        self.assertEqual(next_report['blocked'],1,next_report)
        current=self.jobs.get_job(first['id'])
        self.assertEqual(current['completion_events']['2']['dispatch_blocked']['source'],'supervisor')
        sup.scan_once()
        self.assertEqual(len(self.processes),2)

    def test_marker_present_requires_human_decision_and_does_not_claim_goal_complete(self):
        first = self.first()
        sup = Supervisor(self.jobs)
        self.configure(sup,first,text='有依据的可用草稿')
        report=sup.scan_once()
        self.assertEqual(report['pending'],1,report)
        event=self.jobs.get_job(first['id'])['completion_events']['1']
        self.assertIsNone(event['dispatch'])
        self.assertEqual(event['assessment']['disposition'],'needs_decision')
        self.assertEqual(event['assessment']['goal_status'],'unknown')
        self.assertTrue(json.loads(event['assessment']['evidence']['detail'])['condition_met'])
        self.assertEqual(len(self.processes),1)

    def test_waiting_or_no_supported_value_stops_and_exposes_blocker(self):
        for prerequisite,value in [('waiting_asset','supported'),('waiting_review','supported'),
                                   ('unknown','supported'),('ready','none'),('ready','unknown')]:
            with self.subTest(prerequisite=prerequisite,value=value):
                first=self.first()
                sup=Supervisor(self.jobs)
                self.configure(sup,first,prerequisite=prerequisite,value=value)
                before=len(self.processes)
                report=sup.scan_once()
                self.assertGreaterEqual(report['blocked'],1,report)
                event=self.jobs.get_job(first['id'])['completion_events']['1']
                self.assertIsNone(event['assessment'])
                self.assertIsNone(event['dispatch'])
                self.assertIn(prerequisite,event['dispatch_blocked']['reason'])
                self.assertEqual(len(self.processes),before)

    def test_configuration_must_include_business_case_and_version(self):
        first=self.first()
        sup=Supervisor(self.jobs)
        for bad in ({}, {**CASE,'evidence_source':'   '}, {**CASE,'stop_condition':'x'*501}):
            with self.subTest(case=bad),self.assertRaises(ValueError):
                self.configure(sup,first,case=bad)
        with self.assertRaises(ValueError):
            self.configure(sup,first,prerequisite='automatic')
        configured=self.configure(sup,first,prerequisite='waiting_review')
        with self.assertRaises(WorkspaceConflict):
            self.configure(sup,first)
        saved=self.jobs.get_job(first['id'])
        self.assertEqual(saved['supervision_revision'],configured['supervision_revision'])
        self.assertEqual(saved['supervision']['prerequisite_state'],'waiting_review')
        self.assertEqual(saved['events'][-1]['type'],'supervision_configured')
        self.assertEqual(saved['events'][-1]['supervision_revision'],configured['supervision_revision'])

    def test_non_whitelisted_or_unreadable_artifact_blocks_without_dispatch(self):
        first=self.first(mode='draft')
        sup=Supervisor(self.jobs)
        self.configure(sup,first)
        result=sup.scan_once()
        self.assertEqual(result['blocked'],1,result)
        self.assertIsNone(self.jobs.get_job(first['id'])['completion_events']['1']['dispatch'])
        self.assertEqual(len(self.processes),1)

    def test_artifact_read_failure_does_not_retry_or_expose_source_content(self):
        first=self.first()
        sup=Supervisor(self.jobs)
        self.configure(sup,first)
        with patch.object(self.app.business,'list_artifacts',side_effect=RuntimeError('SECRET private detail')):
            report=sup.scan_once()
        self.assertEqual(report['blocked'],1,report)
        event=self.jobs.get_job(first['id'])['completion_events']['1']
        self.assertIsNone(event['dispatch'])
        self.assertNotIn('SECRET',json.dumps(event['dispatch_blocked']))
        self.assertEqual(len(self.processes),1)

    def test_guard_rejects_late_owner_and_disable_after_claim(self):
        first=self.first()
        sup=Supervisor(self.jobs,owner_id='owner-a')
        configured=self.configure(sup,first)
        lease=sup.claim(first['id'],1)
        with self.assertRaises(RuntimeError):
            verify_guard(self.app.db,first['id'],1,lease['guard'])
        sup.disable(first['id'],expected_version=configured['version'])
        with self.assertRaises(WorkspaceConflict):
            sup._event(first['id'],1,lease['guard'])
        self.assertIsNone(self.jobs.get_job(first['id'])['completion_events']['1']['dispatch'])
        self.assertEqual(len(self.processes),1)

    def test_conflict_latch_and_manual_review_prevent_automatic_replay(self):
        first=self.first()
        sup=Supervisor(self.jobs)
        self.configure(sup,first)
        with patch.object(self.jobs,'continue_followup',side_effect=WorkspaceConflict('synthetic conflict')):
            report=sup.scan_once()
        self.assertEqual(report['blocked'],1,report)
        current=self.jobs.get_job(first['id'])
        self.assertTrue(current['completion_events']['1']['dispatch_blocked']['requires_manual_reset'])
        sup.scan_once()
        self.assertEqual(len(self.processes),1)

    def test_concurrent_manual_intent_and_review_before_assessment_are_preserved(self):
        first=self.first()
        sup=Supervisor(self.jobs)
        self.configure(sup,first)
        assess=self.jobs.assess_completion
        def human_changes_before_assess(*args,**kwargs):
            current=self.jobs.get_job(first['id'])
            updated=self.jobs.adjust(first['id'],expected_version=current['version'],
                current_goal='人工调整的新经营目标',effective_decisions=[{'text':'先核查要点','source':'人工决定'}],
                intent_source='人工复核',intent_reason='业务信息变化',next_action='人工先检查原成果')
            assess(first['id'],1,expected_version=updated['version'],
                expected_intent_version=updated['intent']['version'],disposition='needs_decision',
                goal_status='unknown',capability_status='unknown',result_ref='artifact-1',
                gap='等待人工检查',next_action='人工先检查原成果',
                evidence={'source':'人工观察','observed_at':'2026-11-11T12:00:00Z','detail':'查看原草稿'})
            return assess(*args,**kwargs)
        with patch.object(self.jobs,'assess_completion',side_effect=human_changes_before_assess) as call:
            report=sup.scan_once()
        self.assertEqual(report['blocked'],1,report)
        current=self.jobs.get_job(first['id'])
        event=current['completion_events']['1']
        self.assertEqual(current['intent']['goal'],'人工调整的新经营目标')
        self.assertEqual(current['intent']['decisions'][0]['text'],'先核查要点')
        self.assertEqual(current['next_action'],'人工先检查原成果')
        self.assertEqual(event['assessment']['evidence']['source'],'人工观察')
        self.assertTrue(event['dispatch_blocked']['requires_manual_reset'])
        self.assertEqual(event['supervisor_conflict']['supervision_revision'],current['supervision_revision'])
        self.assertIsNone(event['dispatch'])
        self.assertEqual(len(self.app.business.artifacts),1)
        sup.scan_once();sup.scan_once()
        self.assertEqual(call.call_count,1)
        self.assertEqual(len(self.processes),1)

    def test_concurrent_manual_change_before_dispatch_preserves_assessment_and_stops(self):
        first=self.first()
        sup=Supervisor(self.jobs)
        self.configure(sup,first)
        dispatch=self.jobs.continue_followup
        def human_changes_before_dispatch(*args,**kwargs):
            current=self.jobs.get_job(first['id'])
            self.jobs.adjust(first['id'],expected_version=current['version'],next_action='人工决定先核对草稿')
            return dispatch(*args,**kwargs)
        with patch.object(self.jobs,'continue_followup',side_effect=human_changes_before_dispatch) as call:
            report=sup.scan_once()
        self.assertEqual(report['blocked'],1,report)
        current=self.jobs.get_job(first['id']);event=current['completion_events']['1']
        self.assertEqual(current['next_action'],'人工决定先核对草稿')
        self.assertEqual(event['assessment']['disposition'],'continue')
        self.assertTrue(event['dispatch_blocked']['requires_manual_reset'])
        self.assertIsNone(event['dispatch'])
        sup.scan_once();sup.scan_once()
        self.assertEqual(call.call_count,1)
        self.assertEqual(len(self.processes),1)

    def test_expired_lease_before_conflict_mark_is_recovered_as_review_not_retry(self):
        first=self.first()
        old=Supervisor(self.jobs,owner_id='old-expiring')
        self.configure(old,first)
        assess=self.jobs.assess_completion
        def human_edits_and_lease_expires(*args,**kwargs):
            current=self.jobs.get_job(first['id'])
            self.jobs.adjust(first['id'],expected_version=current['version'],next_action='已由人工修改')
            with self.jobs._write():
                self.app.db.execute('UPDATE supervisor_leases SET expires_at=? WHERE job_id=?',
                                    (time.time()-1,first['id']))
            return assess(*args,**kwargs)
        with patch.object(self.jobs,'assess_completion',side_effect=human_edits_and_lease_expires) as call:
            report=old.scan_once()
        self.assertEqual(report['blocked'],1,report)
        interim=self.jobs.get_job(first['id'])['completion_events']['1']
        self.assertIsNone(interim['assessment'])
        self.assertNotIn('supervisor_conflict',interim)  # fenced old owner could not write
        new=Supervisor(self.jobs,owner_id='new-recovery')
        recovered=new.scan_once()
        self.assertEqual(recovered['blocked'],1,recovered)
        current=self.jobs.get_job(first['id']);event=current['completion_events']['1']
        self.assertEqual(current['next_action'],'已由人工修改')
        self.assertIn('supervisor_conflict',event)
        self.assertTrue(event['dispatch_blocked']['requires_manual_reset'])
        self.assertIsNone(event['assessment']);self.assertIsNone(event['dispatch'])
        self.assertEqual(call.call_count,1)
        self.assertEqual(len(self.processes),1)

    def test_status_is_read_only_and_heartbeat_becomes_stale(self):
        first=self.first()
        sup=Supervisor(self.jobs,owner_id='status-owner',lease_seconds=5)
        self.configure(sup,first,prerequisite='waiting_review')
        sup.scan_once()
        before=self.jobs.get_job(first['id'])['version']
        status=sup.status()
        self.assertEqual(status['state'],'idle')
        self.assertEqual(status['supervised_tasks'],1)
        self.assertEqual(status['blocked'],1)
        self.assertEqual(status['planner'],'not_connected')
        self.assertEqual(self.jobs.get_job(first['id'])['version'],before)
        with self.jobs._write():
            self.app.db.execute('UPDATE supervisor_heartbeats SET heartbeat_at=? WHERE instance_id=?',
                                (time.time()-11,sup.owner_id))
        self.assertEqual(sup.status()['state'],'stale')


class SharedLeaseTests(unittest.TestCase):
    setUp = fixture.AgentJobTests.setUp
    tearDown = fixture.AgentJobTests.tearDown
    wait = fixture.AgentJobTests.wait
    configure = SupervisorTests.configure

    def test_two_connections_compete_and_fencing_rejects_late_owner(self):
        # Replace the isolated in-memory database with a fresh file, never production.
        self.app.db.close()
        path=self.root/'supervisor-test.sqlite'
        self.app.db=sqlite3.connect(path,check_same_thread=False,timeout=5)
        self.jobs=AgentJobs(self.app)
        other_app=SimpleNamespace(root=self.root,state=self.app.state,lock=threading.RLock(),
            db=sqlite3.connect(path,check_same_thread=False,timeout=5),business=self.app.business)
        other_jobs=AgentJobs(other_app)
        try:
            first=self.wait(self.jobs.start('product:shoe','合成草稿',mode='mail_draft'))
            first=self.jobs.get_job(first['id'])
            one=Supervisor(self.jobs,owner_id='lease-one')
            two=Supervisor(other_jobs,owner_id='lease-two')
            self.configure(one,first)
            gate=threading.Barrier(2)
            results=[]
            def acquire(sup):
                gate.wait()
                results.append((sup,sup.claim(first['id'],1)))
            threads=[threading.Thread(target=acquire,args=(sup,)) for sup in (one,two)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(5)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(len([v for _,v in results if v]),1,results)
            winner,old=next((s,v) for s,v in results if v)
            loser=two if winner is one else one
            with winner.jobs._write():
                winner.app.db.execute('UPDATE supervisor_leases SET expires_at=? WHERE job_id=?',
                                      (time.time()-1,first['id']))
            new=loser.claim(first['id'],1)
            self.assertGreater(new['guard']['fence'],old['guard']['fence'])
            with winner.jobs._write():
                with self.assertRaises(WorkspaceConflict):
                    verify_guard(winner.app.db,first['id'],1,old['guard'])
            with loser.jobs._write():
                self.assertTrue(verify_guard(loser.app.db,first['id'],1,new['guard']))
        finally:
            fixture.join_job_threads(other_jobs)
            other_app.db.close()

    def test_other_connection_cannot_change_supervision_during_actual_result_save(self):
        self.app.db.close()
        path=self.root/'supervisor-save-test.sqlite'
        self.app.db=sqlite3.connect(path,check_same_thread=False,timeout=5)
        self.jobs=AgentJobs(self.app)
        other_app=SimpleNamespace(root=self.root,state=self.app.state,lock=threading.RLock(),
            db=sqlite3.connect(path,check_same_thread=False,timeout=5),business=self.app.business)
        other_jobs=AgentJobs(other_app)
        entered,release=threading.Event(),threading.Event()
        try:
            first=self.wait(self.jobs.start('product:shoe','合成草稿',mode='mail_draft'))
            first=self.jobs.get_job(first['id'])
            owner=Supervisor(self.jobs,owner_id='save-owner')
            other=Supervisor(other_jobs,owner_id='save-editor')
            configured=self.configure(owner,first)
            save=self.app.business.save_artifact
            def held_save(*args,**kwargs):
                entered.set()
                if not release.wait(5):raise AssertionError('synthetic save was not released')
                return save(*args,**kwargs)
            with patch.object(self.app.business,'save_artifact',side_effect=held_save):
                self.jobs.resume(first['id'],'只读补充草稿',expected_version=configured['version'])
                self.assertTrue(entered.wait(5),'worker did not reach actual result save')
                current=other_jobs.get_job(first['id'])
                self.assertEqual(current['status'],'running')
                self.assertEqual(current['result_commit']['state'],'saving')
                with self.assertRaisesRegex(WorkspaceConflict,'正在保存'):
                    self.configure(other,current,prerequisite='waiting_review')
                with self.assertRaisesRegex(WorkspaceConflict,'正在保存'):
                    other.disable(first['id'],expected_version=current['version'])
                self.assertEqual(other_jobs.get_job(first['id'])['supervision_revision'],configured['supervision_revision'])
                release.set()
                self.wait(first)
        finally:
            release.set()
            fixture.join_job_threads(self.jobs)
            fixture.join_job_threads(other_jobs)
            other_app.db.close()


if __name__ == '__main__':
    unittest.main()
