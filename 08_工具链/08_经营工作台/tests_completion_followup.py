"""Synthetic SQLite checks for same-job completion review records."""
from pathlib import Path
import copy
from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_jobs import AgentJobs
from completion_followup import CompletionFollowup, EVIDENCE_CLOCK_SKEW, _evidence
from tests_agent_jobs import Business
from workspaces import WorkspaceConflict


if issubclass(AgentJobs, CompletionFollowup):
    ReviewJobs = AgentJobs
else:
    class ReviewJobs(CompletionFollowup, AgentJobs):
        pass


class CompletionFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.app = SimpleNamespace(root=root, state=root/'.local', lock=threading.RLock(),
                                   db=self.db, business=Business())
        self.jobs = ReviewJobs(self.app)
        self.job_id = 'a'*32
        self.evidence = {'source':'合成成果与原档', 'observed_at':'2020-11-11T12:00:00+00:00',
                         'detail':'已核对合成成果与能力要求。'}

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def seed(self, *, status='completed', attempt=1, intent_version=1, frozen_version=1):
        frozen = {'version':frozen_version,'goal':'旧轮目标','decisions':[],
                  'decisions_recorded':False,'source':'synthetic','updated_at':None}
        plan = {'attempt':attempt,'adjustment_version':0,'intent':frozen,'next_action':''}
        job = {'id':self.job_id, 'object_id':'product:shoe', 'title':'合成任务',
               'instruction':'合成初始要求', 'initial_instruction':'合成初始要求',
               'status':status, 'attempt':attempt, 'worker_finished':True, 'version':0,
               'created_at':'2026-11-11T11:00:00+00:00', 'events':[], 'artifact_id':'synthetic-artifact',
               'attempt_plan':plan, 'intent':{'version':intent_version,'goal':'当前目标',
                   'decisions':[], 'decisions_recorded':False, 'source':'synthetic',
                   'updated_at':None, 'history':[]},
               'runs':[{'attempt':attempt,'status':status,'artifact_ids':['synthetic-artifact'],
                        'attempt_plan':copy.deepcopy(plan),'summary':'本轮合成结果'}]}
        with self.jobs._write():
            self.jobs._save(job)
        return self.jobs.get_job(self.job_id)

    def register(self, job=None):
        with self.jobs._write():
            job = job or self.jobs.get_job(self.job_id)
            event = self.jobs._record_finished_attempt(job)
            self.jobs._save(job)
        return event

    def assess(self, job, **overrides):
        fields = {'expected_version':job['version'], 'expected_intent_version':job['intent']['version'],
                  'disposition':'continue', 'goal_status':'not_met', 'capability_status':'unknown',
                  'result_ref':'artifact:synthetic-artifact', 'gap':'仍需验证下一阶段',
                  'next_action':'继续核对合成结果', 'evidence':self.evidence}
        fields.update(overrides)
        return self.jobs.assess_completion(self.job_id, 1, **fields)

    def test_register_finished_run_once_without_claiming_goal_complete(self):
        self.seed()
        with self.jobs._write():
            job = self.jobs.get_job(self.job_id)
            first = copy.deepcopy(self.jobs._record_finished_attempt(job))
            revision = job['completion_revision']
            second = self.jobs._record_finished_attempt(job)
            self.assertEqual(first, second)
            self.assertEqual(job['completion_revision'], revision)
            self.jobs._save(job)
        current = self.jobs.get_job(self.job_id)
        event = self.jobs.completion_view(current)[0]
        self.assertEqual(event['event_id'],f'agent-job:{self.job_id}:attempt:1')
        self.assertEqual(event['source'],'agent_jobs')
        self.assertEqual(event['run_status'],'completed')
        self.assertEqual(event['intent_version'],1)
        self.assertEqual(event['artifact_ids'],['synthetic-artifact'])
        self.assertEqual(event['state'],'awaiting_review')
        self.assertEqual(event['effective_state'],'awaiting_review')
        self.assertEqual(event['notification'],'not_connected')
        self.assertIsNone(event['assessment'])

    def test_record_requires_transaction_confirmed_finish_and_terminal_status(self):
        job = self.seed()
        with self.assertRaises(RuntimeError):
            self.jobs._record_finished_attempt(job)
        for changes in ({'worker_finished':False}, {'status':'running'}, {'attempt':0}, {'attempt':True}):
            with self.subTest(changes=changes), self.jobs._write():
                invalid = {**job,**changes}
                with self.assertRaises(ValueError):self.jobs._record_finished_attempt(invalid)
        self.assertNotIn('completion_events',self.jobs.get_job(self.job_id))

    def test_evidence_backed_assessment_and_duplicate_are_idempotent(self):
        job = self.seed();self.register(job);job = self.jobs.get_job(self.job_id)
        result = self.assess(job)
        self.assertEqual(result['assessment']['disposition'],'continue')
        self.assertEqual(result['assessment']['intent_version'],1)
        self.assertEqual(result['assessment']['evidence'],self.evidence)
        current = self.jobs.get_job(self.job_id)
        view = self.jobs.completion_view(current)[0]
        self.assertEqual(view['state'],'ready_to_continue')
        again = self.assess(current)
        latest = self.jobs.get_job(self.job_id)
        self.assertEqual(again['assessment'],result['assessment'])
        self.assertEqual(latest['version'],current['version'])
        self.assertEqual(latest['completion_revision'],current['completion_revision'])

    def test_identical_replay_returns_existing_unknown_receipt_without_new_dispatch(self):
        job=self.seed();self.register(job);original=self.jobs.get_job(self.job_id)
        self.assess(original)
        stale_version=original['version']
        with self.jobs._write():
            current=self.jobs.get_job(self.job_id)
            current['completion_events']['1']['dispatch']={'state':'unknown','request_id':'one-request'}
            current['completion_revision']+=1
            self.jobs._save(current)
        before=self.jobs.get_job(self.job_id)
        replay=self.assess(before,expected_version=stale_version)
        self.assertEqual(replay['dispatch']['state'],'unknown')
        self.assertEqual(replay['dispatch']['request_id'],'one-request')
        self.assertEqual(self.jobs.get_job(self.job_id)['version'],before['version'])

    def test_stale_identical_assessment_without_receipt_does_not_dispatch(self):
        job=self.seed();self.register(job);original=self.jobs.get_job(self.job_id)
        self.assess(original)
        changed=self.jobs.get_job(self.job_id)
        with self.assertRaises(WorkspaceConflict):self.assess(changed,expected_version=original['version'])
        self.assertIsNone(self.jobs.get_job(self.job_id)['completion_events']['1']['dispatch'])

    def test_verified_complete_needs_successful_run_met_status_and_no_gap(self):
        for status in ('completed','failed','needs_input'):
            with self.subTest(status=status):
                self.db.execute('DELETE FROM agent_jobs');self.db.commit()
                job = self.seed(status=status);self.register(job);job = self.jobs.get_job(self.job_id)
                if status != 'completed':
                    with self.assertRaises(ValueError):
                        self.assess(job, disposition='verified_complete',goal_status='met',capability_status='met',gap='',next_action='')
                else:
                    for invalid in ({'goal_status':'unknown'}, {'capability_status':'not_met'}, {'gap':'欠交付'}, {'result_ref':''}):
                        with self.assertRaises(ValueError):
                            self.assess(job, **{'disposition':'verified_complete','goal_status':'met','capability_status':'met','gap':'','next_action':'',**invalid})
                    self.assess(job, disposition='verified_complete',goal_status='met',capability_status='met',gap='',next_action='')
                    self.assertEqual(self.jobs.completion_view(self.jobs.get_job(self.job_id))[0]['state'],'verified_complete')

    def test_unfinished_assessment_needs_next_action_and_valid_timestamped_evidence(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id)
        for invalid in ({'next_action':'  '}, {'evidence':{'source':'x','observed_at':'2026-11-11','detail':'x'}},
                        {'evidence':{'source':'','observed_at':'2026-11-11T12:00:00Z','detail':'x'}},
                        {'evidence':{'source':'x','observed_at':'2026-11-11T12:00:00Z','detail':''}},
                        {'goal_status':'assumed'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):self.assess(job,**invalid)
        self.assertIsNone(self.jobs.completion_view(self.jobs.get_job(self.job_id))[0]['assessment'])

    def test_evidence_time_uses_utc_and_allows_only_bounded_clock_skew(self):
        fixed = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed.astimezone(tz) if tz is not None else fixed.replace(tzinfo=None)
        def evidence_at(value):
            return {'source':'synthetic evidence', 'observed_at':value, 'detail':'测试记录，不代表已自动核实。'}
        boundary = fixed + EVIDENCE_CLOCK_SKEW
        too_late = boundary + timedelta(microseconds=1)
        with patch('completion_followup.datetime', FixedDateTime):
            for value in (fixed.isoformat(), boundary.isoformat(),
                          boundary.astimezone(timezone(timedelta(hours=8))).isoformat(),
                          (fixed-timedelta(days=365)).isoformat(),
                          (fixed-timedelta(minutes=1)).astimezone(timezone(timedelta(hours=8))).isoformat()):
                with self.subTest(valid=value):
                    self.assertEqual(_evidence(evidence_at(value))['observed_at'],value)
            for value in (too_late.isoformat(),
                          too_late.astimezone(timezone(timedelta(hours=-5))).isoformat(),
                          (fixed+timedelta(days=1)).astimezone(timezone(timedelta(hours=8))).isoformat()):
                with self.subTest(invalid=value), self.assertRaisesRegex(ValueError,'不能超出当前时间'):
                    _evidence(evidence_at(value))
            with self.assertRaisesRegex(ValueError,'必须包含时区'):
                _evidence(evidence_at('2026-11-11T12:00:00'))

    def test_future_evidence_does_not_mutate_the_job(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id)
        future=(datetime.now(timezone.utc)+EVIDENCE_CLOCK_SKEW+timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(ValueError,'不能超出当前时间'):
            self.assess(job,evidence={'source':'未发生的事件','observed_at':future,'detail':'synthetic'})
        latest=self.jobs.get_job(self.job_id)
        self.assertEqual(latest['version'],job['version'])
        self.assertIsNone(latest['completion_events']['1']['assessment'])

    def test_assessment_records_task_next_action_at_review_without_overwriting_it(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id)
        planned=self.jobs.adjust(self.job_id,expected_version=job['version'],next_action='人工先核对样品')
        event=self.assess(planned,next_action='验收建议下一轮核对资料')
        self.assertEqual(event['assessment']['task_next_action_at_review'],'人工先核对样品')
        self.assertEqual(event['assessment']['next_action'],'验收建议下一轮核对资料')
        current=self.jobs.get_job(self.job_id)
        self.assertEqual(current['next_action'],'人工先核对样品')
        changed=self.jobs.adjust(self.job_id,expected_version=current['version'],next_action='人工改为先核对库存')
        self.assertEqual(changed['completion_events']['1']['assessment']['task_next_action_at_review'],'人工先核对样品')

    def test_legacy_assessment_without_action_baseline_remains_unknown_not_inferred(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id);self.assess(job)
        with self.jobs._write():
            job=self.jobs.get_job(self.job_id)
            job['completion_events']['1']['assessment'].pop('task_next_action_at_review')
            job['completion_revision']+=1
            self.jobs._save(job)
        view=self.jobs.completion_view(self.jobs.get_job(self.job_id))[0]
        self.assertNotIn('task_next_action_at_review',view['assessment'])

    def test_continue_cannot_hide_a_completed_goal_without_a_remaining_gap(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id)
        with self.assertRaises(ValueError):
            self.assess(job,disposition='continue',goal_status='met',capability_status='met',gap='')

    def test_changed_intent_marks_old_review_and_rejects_stale_version(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id);self.assess(job)
        job=self.jobs.get_job(self.job_id)
        changed=self.jobs.adjust(self.job_id,expected_version=job['version'],current_goal='新目标',
                                 intent_source='负责人新决定',intent_reason='目标已变更')
        view=self.jobs.completion_view(changed)[0]
        self.assertEqual(view['state'],'review_required')
        self.assertTrue(view['intent_changed'])
        with self.assertRaises(WorkspaceConflict):
            self.assess(changed,expected_intent_version=1)
        with self.assertRaises(WorkspaceConflict):
            self.assess(changed,expected_version=job['version'])
        self.assess(changed, evidence={'source':'新版本核验','observed_at':'2020-11-11T13:00:00Z','detail':'按新目标重新评估。'})
        latest=self.jobs.get_job(self.job_id)
        event=latest['completion_events']['1']
        self.assertEqual(event['assessment']['intent_version'],2)
        self.assertEqual(event['assessment_history'][-1]['status'],'superseded')
        self.assertEqual(self.jobs.completion_view(latest)[0]['state'],'ready_to_continue')

    def test_unknown_dispatch_survives_changed_intent_and_forbids_review_overwrite(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id);self.assess(job)
        with self.jobs._write():
            job=self.jobs.get_job(self.job_id)
            job['completion_events']['1']['dispatch']={'state':'unknown','request_id':'synthetic-request'}
            job['completion_revision']+=1
            self.jobs._save(job)
        job=self.jobs.get_job(self.job_id)
        changed=self.jobs.adjust(self.job_id,expected_version=job['version'],current_goal='新目标',
                                 intent_source='新来源',intent_reason='调整')
        view=self.jobs.completion_view(changed)[0]
        self.assertEqual(view['state'],'dispatch_unknown')
        self.assertTrue(view['intent_changed'])
        self.assertEqual(view['dispatch']['request_id'],'synthetic-request')
        with self.assertRaises(WorkspaceConflict):self.assess(changed)
        self.assertEqual(self.jobs.get_job(self.job_id)['completion_events']['1']['dispatch']['state'],'unknown')

    def test_failed_review_and_unrecognized_dispatch_stay_actionable_without_assuming_delivery(self):
        job=self.seed(status='failed');self.register(job);job=self.jobs.get_job(self.job_id)
        for disposition in ('needs_decision','blocked','unknown'):
            self.assess(job,disposition=disposition)
            job=self.jobs.get_job(self.job_id)
            view=self.jobs.completion_view(job)[0]
            self.assertEqual(view['state'],disposition)
            self.assertEqual(view['run_status'],'failed')
        for raw_dispatch in ({}, {'state':'unrecognized','request_id':'r'}, 'corrupt'):
            with self.subTest(dispatch=raw_dispatch):
                with self.jobs._write():
                    job=self.jobs.get_job(self.job_id)
                    job['completion_events']['1']['dispatch']=raw_dispatch
                    job['completion_revision']+=1
                    self.jobs._save(job)
                job=self.jobs.get_job(self.job_id)
                self.assertEqual(self.jobs.completion_view(job)[0]['state'],'dispatch_unknown')
                with self.assertRaises(WorkspaceConflict):self.assess(job,disposition='blocked')

    def test_legacy_missing_frozen_intent_is_unknown_not_invented(self):
        job=self.seed()
        with self.jobs._write():
            job=self.jobs.get_job(self.job_id)
            job['runs'][0]['attempt_plan'].pop('intent')
            job['attempt_plan'].pop('intent')
            self.jobs._save(job)
        job=self.jobs.get_job(self.job_id);event=self.register(job)
        self.assertIsNone(event['intent_version'])
        view=self.jobs.completion_view(self.jobs.get_job(self.job_id))[0]
        self.assertFalse(view['intent_version_known'])
        self.assertEqual(view['state'],'review_required')

    def test_unknown_current_intent_cannot_hide_previously_verified_review(self):
        job=self.seed();self.register(job);job=self.jobs.get_job(self.job_id)
        self.assess(job,disposition='verified_complete',goal_status='met',capability_status='met',gap='',next_action='')
        current=self.jobs.get_job(self.job_id)
        current['intent']['version']='invalid'
        view=self.jobs.completion_view(current)[0]
        self.assertFalse(view['intent_version_known'])
        self.assertEqual(view['state'],'review_required')
        current['completion_events']['1']['dispatch']={'state':'unknown','request_id':'synthetic-request'}
        view=self.jobs.completion_view(current)[0]
        self.assertFalse(view['intent_version_known'])
        self.assertEqual(view['state'],'dispatch_unknown')

    def test_corrupt_completion_event_is_unavailable_not_silently_empty(self):
        job=self.seed()
        for broken in (None, [], {'1':{'attempt':1,'event_id':'wrong'}}):
            with self.subTest(broken=broken),self.assertRaises(ValueError):
                self.jobs.completion_view({**job,'completion_events':broken})


if __name__ == '__main__':
    unittest.main()
