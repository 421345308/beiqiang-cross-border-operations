"""Isolated execution tests for task intent, continuation and result fencing."""
import json
import sqlite3
import threading
import time
import unittest
from types import SimpleNamespace

import tests_agent_jobs as fixture
import tests_customer_analysis as customer_fixture
from agent_jobs import AgentJobs
from workspaces import WorkspaceConflict


class IntentJobTests(unittest.TestCase):
    # Reuse the existing synthetic business, Codex process and temporary DB;
    # no real customer or external service is involved.
    setUp = fixture.AgentJobTests.setUp
    tearDown = fixture.AgentJobTests.tearDown
    wait = fixture.AgentJobTests.wait

    def get_after_wait(self, job):
        self.wait(job)
        return self.jobs.get_job(job['id'])

    def wait_for_prompt(self, count):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if len(self.processes) >= count and self.processes[count - 1].stdin.closed:
                return self.processes[count - 1].stdin.value
            time.sleep(.01)
        self.fail('Synthetic worker did not receive its prompt')

    def test_planned_first_claim_and_both_resumes_receive_current_intent(self):
        plan = self.jobs.start('product:shoe', '原始委托', defer=True)
        first_decisions = [{'text': '保留现有产品身份', 'source': '负责人记录一'}]
        first = self.jobs.adjust(plan['id'], expected_version=plan['version'],
                                 current_goal='当前目标一', effective_decisions=first_decisions,
                                 intent_source='任务来源一', intent_reason='目标已明确',
                                 next_action='先检查原产品资料')
        done = self.get_after_wait(self.jobs.dispatch(first['id'], expected_version=first['version']))
        self.assertEqual(done['status'], 'completed')
        first_prompt = self.processes[-1].stdin.value
        for value in ('当前目标一', '保留现有产品身份', '负责人记录一', '先检查原产品资料'):
            self.assertIn(value, first_prompt)
        frozen = done['runs'][-1]['attempt_plan']
        self.assertEqual(frozen['intent']['version'], first['intent']['version'])
        self.assertEqual(frozen['intent']['decisions'], first_decisions)
        self.assertEqual(frozen['next_action'], '先检查原产品资料')

        second_decisions = [{'text': '使用现有来源，不假设库存', 'source': '负责人记录二'}]
        second = self.jobs.adjust(done['id'], expected_version=done['version'],
                                  current_goal='当前目标二', effective_decisions=second_decisions,
                                  intent_source='任务来源二', intent_reason='调整工作范围',
                                  next_action='核对第二阶段证据')
        resumed = self.get_after_wait(self.jobs.resume(second['id'], '继续同一任务', expected_version=second['version']))
        self.assertEqual(resumed['status'], 'completed')
        self.assertIn('resume', self.command)
        second_prompt = self.processes[-1].stdin.value
        for value in ('当前目标二', '使用现有来源，不假设库存', '负责人记录二', '核对第二阶段证据'):
            self.assertIn(value, second_prompt)
        self.assertEqual(resumed['runs'][-1]['attempt_plan']['intent']['version'], second['intent']['version'])

        third_decisions = [{'text': '结果仅供内部审核', 'source': '负责人记录三'}]
        third = self.jobs.adjust(resumed['id'], expected_version=resumed['version'],
                                 current_goal='当前目标三', effective_decisions=third_decisions,
                                 intent_source='任务来源三', intent_reason='结果交接',
                                 next_action='核对已有成果位置')
        fresh = self.get_after_wait(self.jobs.resume(third['id'], '新会话接续', new_session=True,
                                                     expected_version=third['version']))
        self.assertEqual(fresh['status'], 'completed')
        self.assertNotIn('resume', self.command)
        fresh_prompt = self.processes[-1].stdin.value
        for value in ('当前目标三', '结果仅供内部审核', '负责人记录三', '核对已有成果位置', 'result.md'):
            self.assertIn(value, fresh_prompt)
        self.assertEqual(fresh['runs'][-1]['attempt_plan']['intent']['version'], third['intent']['version'])
        context = self.jobs.get_task_context(fresh['id'])
        self.assertEqual(context['goal'], '当前目标三')
        self.assertEqual(context['effective_decisions'], third_decisions)
        self.assertEqual(context['next_action'], '核对已有成果位置')
        self.assertTrue(any(a.get('path') == 'result.md' for a in context['artifacts']))

    def test_intent_updates_require_version_and_keep_superseded_provenance(self):
        plan = self.jobs.start('product:shoe', '初始目标', defer=True)
        decisions = [{'text': '先核对原件', 'source': '记录 A'}]
        first = self.jobs.adjust(plan['id'], expected_version=plan['version'],
                                 current_goal='调整后的目标', effective_decisions=decisions,
                                 intent_source='明确指令 A', intent_reason='首次明确')
        self.assertEqual(first['intent']['version'], 1)
        self.assertEqual(first['intent']['history'][-1]['replacement_reason'], '首次明确')
        self.assertEqual(first['intent']['history'][-1]['superseded_by'], 1)
        with self.assertRaises(WorkspaceConflict):
            self.jobs.adjust(plan['id'], expected_version=plan['version'], current_goal='过期写入',
                             intent_source='旧来源', intent_reason='旧理由')
        same = self.jobs.adjust(plan['id'], expected_version=first['version'],
                                current_goal='调整后的目标', effective_decisions=decisions,
                                intent_source='明确指令 A', intent_reason='重复提交')
        self.assertEqual(same['version'], first['version'])
        self.assertEqual(same['intent']['version'], first['intent']['version'])
        self.assertEqual(same['adjustment_version'], first['adjustment_version'])
        second = self.jobs.adjust(plan['id'], expected_version=same['version'],
                                  current_goal='新的目标',
                                  effective_decisions=[{'text': '再核对新原件', 'source': '记录 B'}],
                                  intent_source='明确指令 B', intent_reason='新决定取代旧决定')
        self.assertEqual(second['intent']['version'], 2)
        previous = second['intent']['history'][-1]
        self.assertEqual(previous['status'], 'superseded')
        self.assertEqual(previous['superseded_by'], 2)
        self.assertEqual(previous['goal'], '调整后的目标')
        self.assertEqual(previous['decisions'], decisions)
        self.assertEqual(previous['source'], '明确指令 A')
        self.assertEqual(previous['replacement_reason'], '新决定取代旧决定')
        self.assertEqual(second['intent']['source'], '明确指令 B')

    def test_old_worker_snapshot_does_not_overwrite_new_intent(self):
        plan = self.jobs.start('product:shoe', '初始目标', defer=True)
        stale = self.jobs.get_job(plan['id'])
        changed = self.jobs.adjust(plan['id'], expected_version=stale['version'],
                                   current_goal='最新目标',
                                   effective_decisions=[{'text': '最新决定', 'source': '最新来源'}],
                                   intent_source='负责人说明', intent_reason='修正范围')
        self.jobs._save(stale)
        current = self.jobs.get_job(plan['id'])
        self.assertEqual(current['intent'], changed['intent'])
        self.assertTrue(any(event.get('type') == 'intent_changed' for event in current['events']))

    def test_explicit_goal_source_change_is_recorded_even_when_goal_is_unchanged(self):
        plan = self.jobs.start('product:shoe', '初始目标', defer=True)
        changed = self.jobs.adjust(plan['id'], expected_version=plan['version'],
                                   current_goal='初始目标', intent_source='负责人再次确认',
                                   intent_reason='补充目标依据')
        self.assertEqual(changed['intent']['version'], 1)
        self.assertEqual(changed['intent']['source'], '负责人再次确认')
        self.assertEqual(changed['intent']['history'][-1]['source'], 'initial_instruction')
        self.assertEqual(changed['intent']['history'][-1]['status'], 'superseded')

    def test_explicit_empty_decisions_are_not_the_same_as_unrecorded(self):
        plan = self.jobs.start('product:shoe', '初始目标', defer=True)
        self.assertFalse(self.jobs.get_task_context(plan['id'])['decisions_recorded'])
        with self.assertRaises(ValueError):
            self.jobs.adjust(plan['id'], expected_version=plan['version'],
                             effective_decisions=[], intent_reason='来源不可省略')
        with self.assertRaises(ValueError):
            self.jobs.adjust(plan['id'], expected_version=plan['version'],
                             effective_decisions=[{'text': '决定', 'source': ''}],
                             intent_source='测试来源', intent_reason='决定来源不可省略')
        current = self.jobs.get_job(plan['id'])
        self.assertEqual(current['version'], plan['version'])
        declared = self.jobs.adjust(plan['id'], expected_version=current['version'],
                                    effective_decisions=[], intent_source='负责人明确说明',
                                    intent_reason='本任务当前未登记额外决定')
        self.assertTrue(declared['intent']['decisions_recorded'])
        self.assertEqual(declared['intent']['decisions'], [])
        self.assertEqual(declared['intent']['version'], 1)
        done = self.get_after_wait(self.jobs.dispatch(declared['id'], expected_version=declared['version']))
        self.assertEqual(done['status'], 'completed')
        self.assertIn('"decisions_recorded": true', self.processes[-1].stdin.value)
        self.assertIn('当前业务原档', self.processes[-1].stdin.value)

    def test_changed_goal_or_decision_holds_the_running_attempt_result(self):
        for changed_field in ('goal', 'decisions'):
            with self.subTest(changed_field=changed_field):
                gate = threading.Event()
                self.options = {'gate': gate}
                plan = self.jobs.start('product:shoe', '最初委托', defer=True)
                before = self.jobs.adjust(plan['id'], expected_version=plan['version'],
                                          current_goal='领取时的目标',
                                          effective_decisions=[{'text': '领取时的决定', 'source': '原决定来源'}],
                                          intent_source='原目标来源', intent_reason='登记当前意图',
                                          next_action='领取时的下一步')
                old_artifacts = list(self.app.business.artifacts)
                expected_process_count = len(self.processes) + 1
                started = self.jobs.dispatch(before['id'], expected_version=before['version'])
                try:
                    prompt = self.wait_for_prompt(expected_process_count)
                    for expected in ('领取时的目标', '领取时的决定', '原决定来源', '领取时的下一步'):
                        self.assertIn(expected, prompt)
                    running = self.jobs.get_job(before['id'])
                    change = ({'current_goal': '运行期间的新目标'} if changed_field == 'goal' else
                              {'effective_decisions': [{'text': '运行期间的新决定', 'source': '新决定来源'}]})
                    new = self.jobs.adjust(before['id'], expected_version=running['version'],
                                           intent_source='运行期间的调整', intent_reason='新要求', **change)
                    self.assertGreater(new['intent']['version'], before['intent']['version'])
                    self.assertNotIn('运行期间的新目标' if changed_field == 'goal' else '运行期间的新决定', prompt)
                finally:
                    gate.set()
                done = self.get_after_wait(started)
                self.assertEqual(done['status'], 'needs_input')
                self.assertEqual(done['intent'], new['intent'])
                self.assertEqual(done['held_result']['reason'], 'planning_changed_during_attempt')
                self.assertEqual(done['runs'][-1]['attempt_plan']['intent']['version'], before['intent']['version'])
                self.assertEqual(self.app.business.artifacts, old_artifacts)
                self.assertIn('有依据的可用草稿', self.jobs.read_held_result(done['id'])['content'])

    def test_completed_legacy_record_uses_initial_instruction_and_can_resume(self):
        original = self.get_after_wait(self.jobs.start('product:shoe', '旧任务初始委托'))
        with self.app.lock:
            raw = json.loads(self.app.db.execute('SELECT data FROM agent_jobs WHERE id=?', (original['id'],)).fetchone()[0])
            raw.pop('intent', None)
            raw['instruction'] = '旧会话最后一次指令'
            raw.get('attempt_plan', {}).pop('intent', None)
            self.app.db.execute('UPDATE agent_jobs SET data=? WHERE id=?', (json.dumps(raw), original['id']))
            self.app.db.commit()
        current = self.jobs.get_task_context(original['id'])
        self.assertEqual(current['goal'], '旧任务初始委托')
        self.assertFalse(current['decisions_recorded'])
        self.assertEqual(current['effective_decisions'], [])
        self.assertEqual(current['intent_source'], 'initial_instruction')
        resumed = self.get_after_wait(self.jobs.resume(original['id'], '显式接续旧任务',
                                                      expected_version=current['job']['version']))
        self.assertEqual(resumed['status'], 'completed')
        prompt = self.processes[-1].stdin.value
        self.assertIn('旧任务初始委托', prompt)
        self.assertIn('尚未登记', prompt)
        self.assertEqual(resumed['runs'][-1]['attempt_plan']['intent']['version'], 0)

    def test_legacy_instruction_fallback_does_not_claim_missing_initial_source(self):
        original = self.get_after_wait(self.jobs.start('product:shoe', '旧任务内容'))
        with self.app.lock:
            raw = json.loads(self.app.db.execute('SELECT data FROM agent_jobs WHERE id=?', (original['id'],)).fetchone()[0])
            raw.pop('intent', None)
            raw.pop('initial_instruction', None)
            self.app.db.execute('UPDATE agent_jobs SET data=? WHERE id=?', (json.dumps(raw), original['id']))
            self.app.db.commit()
        context = self.jobs.get_task_context(original['id'])
        self.assertEqual(context['goal'], '旧任务内容')
        self.assertEqual(context['intent_source'], 'legacy_instruction_fallback')
        self.assertFalse(context['decisions_recorded'])

    def test_legacy_inflight_without_frozen_intent_requires_review(self):
        gate = threading.Event()
        self.options = {'gate': gate}
        started = self.jobs.start('product:shoe', '旧在途任务')
        try:
            self.wait_for_prompt(1)
            with self.jobs._write():
                running = self.jobs.get_job(started['id'])
                running['attempt_plan'].pop('intent', None)
                self.jobs._save(running)
        finally:
            gate.set()
        result = self.get_after_wait(started)
        self.assertEqual(result['status'], 'needs_input')
        self.assertEqual(result['held_result']['reason'], 'intent_snapshot_missing')
        self.assertEqual(self.app.business.artifacts, [])
        self.assertIn('有依据的可用草稿', self.jobs.read_held_result(result['id'])['content'])

    def test_final_save_claim_blocks_intent_edits_from_second_connection(self):
        dbfile = self.root / 'intent-shared.sqlite3'
        first_db = sqlite3.connect(dbfile, check_same_thread=False)
        other_db = sqlite3.connect(dbfile, check_same_thread=False)
        first_app = SimpleNamespace(root=self.root, state=self.root/'.local', lock=threading.RLock(),
                                    db=first_db, business=self.app.business)
        other_app = SimpleNamespace(root=self.root, state=self.root/'.local', lock=threading.RLock(),
                                    db=other_db, business=self.app.business)
        first, other = AgentJobs(first_app), AgentJobs(other_app)
        entered, release = threading.Event(), threading.Event()
        save = first_app.business.save_artifact
        def blocked_save(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError('test did not release final save')
            return save(*args, **kwargs)
        first_app.business.save_artifact = blocked_save
        job = None
        try:
            job = first.start('product:shoe', '隔离原子边界验收')
            self.assertTrue(entered.wait(3))
            committing = other.get_job(job['id'])
            self.assertEqual(committing['result_commit']['state'], 'saving')
            with self.assertRaises(WorkspaceConflict):
                other.adjust(job['id'], expected_version=committing['version'], current_goal='不得抢写',
                             intent_source='隔离测试', intent_reason='验证最终保存边界')
            release.set()
            fixture.join_job_threads(first, job['id'])
            complete = other.get_job(job['id'])
            self.assertEqual(complete['status'], 'completed')
            changed = other.adjust(job['id'], expected_version=complete['version'], current_goal='保存后新目标',
                                   intent_source='隔离测试', intent_reason='保存后正常修改')
            self.assertEqual(changed['intent']['goal'], '保存后新目标')
        finally:
            release.set()
            fixture.join_job_threads(first, job['id'] if job else None)
            first_app.business.save_artifact = save
            first_db.close()
            other_db.close()


class IntentCustomerAnalysisTests(unittest.TestCase):
    # The customer fixture has a separate, synthetic customer-profile store;
    # this tests the structured business write rather than Markdown alone.
    setUp = customer_fixture.CustomerAnalysisTests.setUp
    tearDown = customer_fixture.CustomerAnalysisTests.tearDown
    wait = customer_fixture.CustomerAnalysisTests.wait

    def test_changed_decision_holds_structured_result_before_profile_save(self):
        gate = threading.Event()
        self.options['gate'] = gate
        original_profile = self.app.customer_workspace.profile(self.obj['id'])
        plan = self.jobs.start(self.obj['id'], '先分析合成询盘', mode='customer_analysis', defer=True)
        before = self.jobs.adjust(plan['id'], expected_version=plan['version'],
                                  current_goal='按领取时要求分析',
                                  effective_decisions=[{'text': '按原件分析', 'source': '原说明'}],
                                  intent_source='任务登记', intent_reason='记录初始决定')
        started = self.jobs.dispatch(before['id'], expected_version=before['version'])
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.processes and self.processes[-1].stdin.closed:
                    break
                time.sleep(.01)
            self.assertTrue(self.processes and self.processes[-1].stdin.closed)
            running = self.jobs.get_job(started['id'])
            self.jobs.adjust(started['id'], expected_version=running['version'],
                             effective_decisions=[{'text': '按新说明分析', 'source': '新说明'}],
                             intent_source='新的任务登记', intent_reason='决定已调整')
        finally:
            gate.set()
        result = self.wait(started)
        self.assertEqual(result['status'], 'needs_input')
        self.assertFalse(result['profile_saved'])
        self.assertEqual(result['held_result']['reason'], 'planning_changed_during_attempt')
        self.assertEqual(result['held_result']['format'], 'json')
        after = self.app.customer_workspace.profile(self.obj['id'])
        self.assertEqual(after['revision'], original_profile['revision'])
        self.assertEqual(after['analysis'], original_profile['analysis'])
        self.assertEqual(after['translation_zh'], original_profile['translation_zh'])
        self.assertEqual(self.artifacts, [])
        held = self.jobs.read_held_result(result['id'])
        self.assertEqual(json.loads(held['content'])['translation_zh'], customer_fixture.response()['translation_zh'])

    def test_changed_intent_and_customer_validation_failures_keep_raw_result(self):
        original_content = self.obj['content']
        scenarios = {'source_changed':'customer_source_changed',
                     'source_unverified':'customer_source_unverified',
                     'invalid_result':'planning_changed_during_attempt',
                     'missing_profile_revision':'planning_changed_during_attempt'}
        for scenario, reason in scenarios.items():
            with self.subTest(scenario=scenario):
                self.obj['content'] = original_content
                gate = threading.Event()
                self.options = {'gate':gate, 'content':('# not JSON' if scenario=='invalid_result' else
                                json.dumps(customer_fixture.response(),ensure_ascii=False)),
                                'source_read':scenario!='source_unverified'}
                before_count = len(self.processes)
                started = self.jobs.start(self.obj['id'], '先分析合成询盘', mode='customer_analysis')
                try:
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        if len(self.processes)>before_count and self.processes[-1].stdin.closed:
                            break
                        time.sleep(.01)
                    self.assertTrue(len(self.processes)>before_count and self.processes[-1].stdin.closed)
                    running = self.jobs.get_job(started['id'])
                    self.jobs.adjust(started['id'], expected_version=running['version'],
                                     current_goal='新的任务目标', intent_source='负责人记录', intent_reason='目标已更新')
                    if scenario == 'source_changed':
                        changed = json.loads(original_content)
                        changed['requirements'] = 'Changed synthetic original'
                        self.obj['content'] = json.dumps(changed)
                    if scenario == 'missing_profile_revision':
                        with self.jobs._write():
                            current = self.jobs.get_job(started['id'])
                            current.pop('profile_revision', None)
                            self.jobs._save(current)
                finally:
                    gate.set()
                result = self.wait(started)
                self.assertEqual(result['status'], 'needs_input')
                self.assertFalse(result['profile_saved'])
                self.assertEqual(result['intent']['goal'], '新的任务目标')
                self.assertEqual(result['held_result']['reason'], reason)
                self.assertTrue(self.jobs.read_held_result(result['id'])['content'])
                self.assertEqual(self.artifacts, [])


if __name__ == '__main__':
    unittest.main()
