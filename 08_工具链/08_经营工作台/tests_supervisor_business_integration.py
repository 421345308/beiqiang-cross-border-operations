"""Business integration fixtures for durable supervision; all data is synthetic.

The real Workbench, Business, GmailService and AgentJobs use a private temporary
SQLite database and temporary source/artifact files. No real mail or model is
called: mailbox reads and the Codex process are fakes, and sockets are blocked.
"""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import server
from agent_jobs import AgentJobs
from business import ASSETS, CHANNEL, PRODUCTS, SUPPLY
from tests_agent_jobs import Process, join_job_threads, stop_job_threads
from tests_gmail_sync import ACCOUNT, BUYER, Mailbox, message
from supervisor import Supervisor
from website_inquiries import WebsiteInquiries


CUSTOMER = 'customer:website-SYNTHETIC'
PRODUCT = 'product:BQ009'
MAIL_CASE = {'business_outcome':'让合成买家获得可审核的回复',
             'current_bottleneck':'测试邮件的新需求尚未整理',
             'intended_change':'形成下一版内部回复草稿',
             'stop_condition':'需要额外资料或负责人审核时停止',
             'evidence_source':'隔离客户资料及合成邮件'}
PRODUCT_CASE = {'business_outcome':'推进合成产品资料整理',
                'current_bottleneck':'测试商品的资料尚需归纳',
                'intended_change':'保存可复核的内部商品资料',
                'stop_condition':'缺少素材或审核未完成时停止',
                'evidence_source':'隔离商品中心和合成素材'}


class ObservedGate:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def wait(self, timeout=None):
        self.entered.set()
        return self.release.wait(timeout)

    def set(self):
        self.release.set()


class SupervisorBusinessIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'runtime'
        self.app = None
        self.processes = []
        self.commands = []
        self.options = {}
        self.mailbox = Mailbox()
        self.mailbox.messages = [message('synthetic-inbound')]
        self.network = patch('socket.socket.connect', side_effect=AssertionError('network forbidden in test'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.no_connect_ex = patch('socket.socket.connect_ex', side_effect=AssertionError('network forbidden in test'))
        self.no_connect_ex.start()
        self.addCleanup(self.no_connect_ex.stop)
        self.which = patch('agent_jobs.shutil.which', return_value='/synthetic/codex')
        self.which.start()
        self.addCleanup(self.which.stop)

        def spawn(command, **kwargs):
            result = Process(command, **self.options)
            self.commands.append(command)
            self.processes.append(result)
            return result

        self.popen = patch('agent_jobs.subprocess.Popen', side_effect=spawn)
        self.popen.start()
        self.addCleanup(self.popen.stop)
        self.stop = patch.object(AgentJobs, '_stop', side_effect=lambda process: process.kill())
        self.stop.start()
        self.addCleanup(self.stop.stop)
        self._build_sources()
        self.open_workbench()

    def tearDown(self):
        self.close_workbench()

    def write_json(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')

    def _build_sources(self):
        generator = self.root / '08_工具链/06_工作区维护/build_b2b_workbench.py'
        generator.parent.mkdir(parents=True, exist_ok=True)
        generator.write_bytes((server.HERE.parent / '06_工作区维护/build_b2b_workbench.py').read_bytes())
        spec = importlib.util.spec_from_file_location('supervisor_business_fixture_parser', generator)
        parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parser)
        for path in parser.SOURCES:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('国际B2B具体要成为：**隔离测试目标**\n**当前位置：隔离测试**\n## 工作台任务\n'
                '| 任务 | 状态 | 主办 | 当前结果 | 下一步 | 依赖/需你决定 | 成果与证据 |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '| Fixture | 待开始 | Test | 未执行 | 核验 | 无 | |\n', encoding='utf8')
        self.write_json(PRODUCTS, {'products':[{'id':'BQ009', 'aliases':['BQ-009'],
            'source_state':'ADOPTED', 'adopted_source_id':'source-1',
            'raw_packages':['01_产品资产/01_原始素材/BQ009']}]})
        self.write_json(SUPPLY, {'sources':[{'id':'source-1', 'supplier':'Fixture supplier',
            'model':'MODEL-009', 'url':'https://example.invalid/source', 'observed_at':'2026-10-01'}]})
        self.write_json(ASSETS, {'files':[{'file':'01_产品资产/02_成品素材/BQ009/shoe.png',
            'products':['BQ009'], 'roles':['商品主图']}]})
        self.write_json(CHANNEL, {'listings':[{'id':'1601', 'product_id':'BQ009',
            'current_platform_fields':{'title':'Fixture title', 'status':'approved', 'at':'2026-10-31'}}]})

    def open_workbench(self):
        self.assertIsNone(self.app)
        app = server.Workbench(self.root, self.state)
        website = WebsiteInquiries(self.root, fetch=lambda:{'ok':True, 'records':[
            {'reference':'SYNTHETIC', 'company':'Fixture buyer', 'email':BUYER,
             'requirements':'Need synthetic footwear'}]}, clock=lambda:1000, ttl=120)
        website.refresh(wait=True)
        app.business.website = website
        app.gmail.translator = None
        app.gmail._account = ACCOUNT
        app.gmail._connected_at = '2026-11-01T00:00:00Z'
        app.gmail._mailbox = self.mailbox
        self.app = app
        return app

    def close_workbench(self):
        if self.app is None:
            return
        app, self.app = self.app, None
        app.supervisor = None  # Tests call scan_once directly; no loop is running.
        app.gmail.stop()
        stop_job_threads(app.agent_jobs)
        app.db.commit()
        app.db.close()

    def reopen_workbench(self):
        self.close_workbench()
        return self.open_workbench()

    def wait_finished(self, job_id, attempt=1):
        deadline = time.monotonic()+8
        while time.monotonic() < deadline:
            job = self.app.agent_jobs.get_job(job_id)
            if job.get('attempt') == attempt and job.get('worker_finished') is True:
                join_job_threads(self.app.agent_jobs, job_id)
                job = self.app.agent_jobs.get_job(job_id)
                self.assertIn(str(attempt), job.get('completion_events', {}))
                return job
            time.sleep(.01)
        self.fail('synthetic job did not finish')

    def assert_persisted_artifact(self, job):
        items = self.app.business.list_artifacts(job['object_id'])
        artifact = next(item for item in items if item['id'] == job['artifact_id'])
        path = (self.root / artifact['path']).resolve()
        self.assertTrue(path.is_relative_to(self.root))
        self.assertTrue(path.is_file())
        self.assertTrue(path.read_text(encoding='utf8').strip())
        return artifact

    def configure_supervisor(self, job, *, prerequisite='ready', value='supported',
                             criteria='NO_SYNTHETIC_MATCH', lease_seconds=30):
        supervisor = Supervisor(self.app.agent_jobs, lease_seconds=lease_seconds)
        self.app.supervisor = supervisor
        supervisor.configure(job['id'], expected_version=job['version'],
            acceptance_criteria={'kind':'artifact_contains', 'text':criteria},
            continuation_instruction='只读核对合成资料并形成内部结果',
            authorization_ref='仅供此隔离测试的明确纳管和一次接续',
            business_case=MAIL_CASE if job['object_id'] == CUSTOMER else PRODUCT_CASE,
            prerequisite_state=prerequisite, value_state=value)
        return supervisor

    def wait_prompt(self, count):
        deadline = time.monotonic()+8
        while time.monotonic() < deadline:
            if len(self.processes) >= count and self.processes[count-1].stdin.closed:
                return self.processes[count-1].stdin.value
            time.sleep(.01)
        self.fail('synthetic worker did not receive its prompt')

    def start_customer_reply(self):
        workspace = self.app.customer_workspace
        current = workspace.workflow(CUSTOMER)
        workspace.save_workflow(CUSTOMER, {'revision':current['revision'], 'state':'preparing'})
        current = workspace.workflow(CUSTOMER)
        workspace.save_workflow(CUSTOMER, {'revision':current['revision'], 'state':'waiting_customer'})
        self.mailbox.messages = [message('synthetic-inbound',
            at=(datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat())]
        result = self.app.gmail.customer(CUSTOMER)
        self.assertTrue(result['reply_pending'])
        row = self.app.db.execute('SELECT dispatch_state,job_id FROM gmail_reply_events '
                                  'WHERE object_id=? AND message_id=?',
                                  (CUSTOMER, 'synthetic-inbound')).fetchone()
        self.assertEqual(row[0], 'dispatched')
        job_id = row[1]
        job = self.wait_finished(job_id)
        return result, job

    def test_gmail_reply_existing_customer_job_and_artifact_survive_reopen(self):
        result, job = self.start_customer_reply()
        job_id = job['id']
        self.assertEqual(job['object_id'], CUSTOMER)
        self.assertEqual(job['mode'], 'mail_draft')
        self.assertEqual(job['source_event']['message_id'], 'synthetic-inbound')
        self.assertEqual(job['status'], 'completed')
        event_id = job['completion_events']['1']['event_id']
        artifact = self.assert_persisted_artifact(job)
        self.app.gmail.customer(CUSTOMER)
        self.assertEqual(len(self.processes), 1)
        with patch.object(self.mailbox, 'context', side_effect=TimeoutError('synthetic disconnected mailbox')):
            disconnected = self.app.gmail.customer(CUSTOMER, force=True)
        self.assertEqual(disconnected['status']['state'], 'error')
        self.assertIsNone(disconnected['reply_pending'])
        self.assertEqual(len(self.app.agent_jobs.list_jobs()), 1)
        self.assertEqual(len(self.processes), 1)
        self.reopen_workbench()
        reopened = self.app.agent_jobs.get_job(job_id)
        self.assertEqual(reopened['completion_events']['1']['event_id'], event_id)
        self.assertEqual(self.assert_persisted_artifact(reopened)['id'], artifact['id'])
        self.app.gmail.customer(CUSTOMER)
        self.assertEqual(len(self.app.agent_jobs.list_jobs()), 1)
        self.assertEqual(len(self.processes), 1)

    def test_product_group_dispatch_and_artifact_survive_reopen(self):
        jobs = self.app.agent_jobs
        group = jobs.create_group(PRODUCT, '合成商品研究分组')
        first = jobs.start(PRODUCT, '整理合成商品资料', parent_job_id=group['id'], defer=True)
        second = jobs.start(PRODUCT, '依据首轮结果继续', parent_job_id=group['id'],
                            depends_on=[first['id']], defer=True)
        preview = jobs.preview_priority_dispatch(group['id'])
        self.assertEqual(preview['candidate']['id'], first['id'])
        jobs.dispatch_priority_next(group['id'], first['id'], preview['candidate']['version'])
        completed = self.wait_finished(first['id'])
        self.assertEqual(completed['status'], 'completed')
        event_id = completed['completion_events']['1']['event_id']
        artifact = self.assert_persisted_artifact(completed)
        self.assertEqual(jobs.get_job(second['id'])['status'], 'planned')
        self.reopen_workbench()
        jobs = self.app.agent_jobs
        self.assertEqual(jobs.get_job(first['id'])['completion_events']['1']['event_id'], event_id)
        self.assertEqual(self.assert_persisted_artifact(jobs.get_job(first['id']))['id'], artifact['id'])
        self.assertEqual(jobs.get_job(second['id'])['status'], 'planned')
        self.assertEqual(len(self.processes), 1)

    def test_synthetic_unknown_mail_outcome_survives_database_reopen(self):
        _, job = self.start_customer_reply()
        drafts = self.app.gmail_drafts
        calls = []
        drafts.token_provider = lambda account:'synthetic-token'

        def sender(token, payload):
            calls.append('synthetic attempt')
            raise TimeoutError('synthetic unknown delivery')

        drafts.sender = sender
        draft = drafts.get(CUSTOMER)
        draft = drafts.save(CUSTOMER, draft['version'], {'to':BUYER, 'subject':'Fixture only',
                            'body_en':'Synthetic message.', 'body_zh':'合成信息。'})
        outcome = drafts.send(CUSTOMER, draft['version'])
        self.assertEqual(outcome['status'], 'unknown')
        self.assertEqual(len(calls), 1)
        supervisor = self.configure_supervisor(job)
        first = supervisor.scan_once()
        self.assertEqual(first['advanced'], 1)
        self.wait_finished(job['id'], attempt=2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(drafts.get(CUSTOMER)['status'], 'unknown')
        self.reopen_workbench()
        drafts = self.app.gmail_drafts
        drafts.token_provider = lambda account:'synthetic-token'
        drafts.sender = sender
        supervisor = Supervisor(self.app.agent_jobs)
        self.app.supervisor = supervisor
        supervisor.scan_once()
        supervisor.scan_once()
        persisted = drafts.get(CUSTOMER)
        self.assertEqual(persisted['status'], 'unknown')
        with self.assertRaises(ValueError):
            drafts.send(CUSTOMER, persisted['version'])
        self.assertEqual(len(calls), 1)

    def test_gmail_supervision_reclaims_expired_lease_after_full_reopen_once(self):
        _, job = self.start_customer_reply()
        job_id = job['id']
        supervisor = self.configure_supervisor(job, lease_seconds=30)
        lease = supervisor.claim(job_id, 1)
        self.assertIsNotNone(lease)
        old_guard = lease['guard']
        del supervisor
        self.reopen_workbench()
        supervisor = Supervisor(self.app.agent_jobs, lease_seconds=30)
        self.app.supervisor = supervisor
        pending = supervisor.scan_once()
        self.assertEqual(pending['pending'], 1)
        self.assertEqual(len(self.processes), 1)
        # Advance only the isolated supervisor clock; no wait or real process is used.
        simulated_clock = SimpleNamespace(time=lambda:time.time()+31)
        with patch('supervisor.time', simulated_clock):
            result = supervisor.scan_once()
            self.assertEqual(result['advanced'], 1)
            resumed = self.wait_finished(job_id, attempt=2)
            self.assertEqual(resumed['completion_events']['1']['dispatch']['target_attempt'], 2)
            self.assertEqual(resumed['completion_events']['1']['dispatch']['state'], 'completed')
            self.assertEqual(len(self.processes), 2)
            repeated = supervisor.scan_once()
            self.assertEqual(repeated['advanced'], 0)
            self.assertEqual(len(self.processes), 2)
            self.assertFalse(supervisor.renew(job_id, 1, old_guard))

    def test_product_draft_supervision_reports_real_blocker_after_reopen(self):
        jobs = self.app.agent_jobs
        group = jobs.create_group(PRODUCT, '合成商品研究分组')
        first = jobs.start(PRODUCT, '整理合成商品资料', parent_job_id=group['id'], defer=True)
        second = jobs.start(PRODUCT, '依据首轮结果继续', parent_job_id=group['id'],
                            depends_on=[first['id']], defer=True)
        preview = jobs.preview_priority_dispatch(group['id'])
        jobs.dispatch_priority_next(group['id'], first['id'], preview['candidate']['version'])
        job = self.wait_finished(first['id'])
        supervisor = self.configure_supervisor(job)
        del supervisor
        self.reopen_workbench()
        supervisor = Supervisor(self.app.agent_jobs)
        self.app.supervisor = supervisor
        for _ in range(2):
            result = supervisor.scan_once()
            self.assertEqual(result['blocked'], 1)
            self.assertEqual(result['advanced'], 0)
        current = self.app.agent_jobs.get_job(first['id'])
        event = current['completion_events']['1']
        self.assertIn('白名单', event['dispatch_blocked']['reason'])
        self.assertIsNone(event['dispatch'])
        self.assertEqual(self.app.agent_jobs.get_job(second['id'])['status'], 'planned')
        self.assertEqual(len(self.processes), 1)

    def test_waiting_or_no_value_is_visible_and_never_continues(self):
        _, job = self.start_customer_reply()
        supervisor = self.configure_supervisor(job, prerequisite='waiting_review')
        for prerequisite, value in (('waiting_review','supported'), ('waiting_asset','supported'),
                                    ('ready','none')):
            current = self.app.agent_jobs.get_job(job['id'])
            supervisor.configure(job['id'], expected_version=current['version'],
                acceptance_criteria={'kind':'artifact_contains','text':'NO_SYNTHETIC_MATCH'},
                continuation_instruction='只读核对合成资料并形成内部结果',
                authorization_ref='仅供此隔离测试的明确纳管和一次接续', business_case=MAIL_CASE,
                prerequisite_state=prerequisite, value_state=value)
            for _ in range(2):
                result = supervisor.scan_once()
                self.assertEqual(result['blocked'], 1)
                self.assertEqual(result['advanced'], 0)
                self.assertEqual(len(self.processes), 1)
            current = self.app.agent_jobs.get_job(job['id'])
            event = current['completion_events']['1']
            self.assertIsNone(event['dispatch'])
            self.assertTrue(event['dispatch_blocked']['reason'])
            overview = self.app.task_workspace.overview()
            self.assertTrue(any(item.get('event_id') == event['event_id']
                                and item.get('state') == 'dispatch_blocked' for item in overview['inbox']))

    def test_unknown_artifact_save_survives_reopen_and_is_not_replayed(self):
        with patch.object(self.app.business, 'save_artifact', side_effect=TimeoutError('synthetic save outcome unknown')):
            _, job = self.start_customer_reply()
        self.assertEqual(job['status'], 'needs_input')
        self.assertEqual(job['result_commit']['state'], 'outcome_unknown')
        supervisor = self.configure_supervisor(job)
        del supervisor
        self.reopen_workbench()
        supervisor = Supervisor(self.app.agent_jobs)
        self.app.supervisor = supervisor
        for _ in range(2):
            result = supervisor.scan_once()
            self.assertEqual(result['blocked'], 1)
            self.assertEqual(result['advanced'], 0)
        current = self.app.agent_jobs.get_job(job['id'])
        self.assertEqual(current['result_commit']['state'], 'outcome_unknown')
        self.assertTrue(current.get('held_result'))
        self.assertEqual(len(self.processes), 1)

    def test_running_supervised_attempt_uses_frozen_business_case_and_holds_on_change(self):
        _, job = self.start_customer_reply()
        supervisor = self.configure_supervisor(job)
        before = self.app.agent_jobs.get_job(job['id'])
        previous_artifacts = self.app.business.list_artifacts(CUSTOMER)
        gate = ObservedGate()
        self.options = {'gate':gate}
        try:
            self.assertEqual(supervisor.scan_once()['advanced'], 1)
            prompt = self.wait_prompt(2)
            self.assertTrue(gate.entered.wait(3))
            for value in MAIL_CASE.values():
                self.assertIn(value, prompt)
            self.assertIn('等待素材、审核或没有新增价值时停止', prompt)
            running = self.app.agent_jobs.get_job(job['id'])
            frozen = running['attempt_plan']
            self.assertEqual(frozen['business_case'], MAIL_CASE)
            self.assertEqual(frozen['supervision_revision'], before['supervision_revision'])
            revised = {**MAIL_CASE, 'stop_condition':'新决定：等待负责人审核',
                       'evidence_source':'更新后的合成来源'}
            supervisor.configure(job['id'], expected_version=running['version'],
                acceptance_criteria={'kind':'artifact_contains','text':'NO_SYNTHETIC_MATCH'},
                continuation_instruction='只读核对合成资料并形成内部结果',
                authorization_ref='仅供此隔离测试的明确纳管和一次接续',
                business_case=revised, prerequisite_state='waiting_review', value_state='supported')
            self.assertNotIn(revised['stop_condition'], prompt)
        finally:
            gate.set()
        done = self.wait_finished(job['id'], attempt=2)
        self.assertEqual(done['status'], 'needs_input')
        self.assertEqual(done['held_result']['reason'], 'planning_changed_during_attempt')
        self.assertEqual(done['runs'][-1]['attempt_plan']['business_case'], MAIL_CASE)
        self.assertEqual(done['supervision']['business_case'], revised)
        self.assertEqual(self.app.business.list_artifacts(CUSTOMER), previous_artifacts)
        self.assertIn('有依据的可用草稿', self.app.agent_jobs.read_held_result(job['id'])['content'])

    def test_running_supervised_attempt_holds_when_task_goal_changes(self):
        _, job = self.start_customer_reply()
        supervisor = self.configure_supervisor(job)
        previous_artifacts = self.app.business.list_artifacts(CUSTOMER)
        gate = ObservedGate()
        self.options = {'gate':gate}
        try:
            self.assertEqual(supervisor.scan_once()['advanced'], 1)
            prompt = self.wait_prompt(2)
            self.assertTrue(gate.entered.wait(3))
            running = self.app.agent_jobs.get_job(job['id'])
            changed = self.app.agent_jobs.adjust(job['id'], expected_version=running['version'],
                current_goal='运行期间重新确定的合成目标', intent_source='隔离负责人指令', intent_reason='测试目标变更')
            self.assertNotIn(changed['intent']['goal'], prompt)
        finally:
            gate.set()
        done = self.wait_finished(job['id'], attempt=2)
        self.assertEqual(done['status'], 'needs_input')
        self.assertEqual(done['intent']['goal'], changed['intent']['goal'])
        self.assertEqual(done['held_result']['reason'], 'planning_changed_during_attempt')
        self.assertEqual(self.app.business.list_artifacts(CUSTOMER), previous_artifacts)

    def test_supervised_new_session_also_receives_frozen_business_case(self):
        _, job = self.start_customer_reply()
        with self.app.agent_jobs._write():
            current = self.app.agent_jobs.get_job(job['id'])
            current['session_id'] = None  # Simulate an older attempt without a resumable session.
            self.app.agent_jobs._save(current)
        current = self.app.agent_jobs.get_job(job['id'])
        supervisor = self.configure_supervisor(current)
        self.assertEqual(supervisor.scan_once()['advanced'], 1)
        done = self.wait_finished(job['id'], attempt=2)
        self.assertEqual(done['status'], 'completed')
        self.assertNotIn('resume', self.commands[-1])
        for value in MAIL_CASE.values():
            self.assertIn(value, self.processes[-1].stdin.value)
        self.assertEqual(done['runs'][-1]['attempt_plan']['business_case'], MAIL_CASE)

    def test_manual_followup_without_supervision_snapshot_remains_compatible(self):
        _, job = self.start_customer_reply()
        supervisor = self.configure_supervisor(job)
        gate = ObservedGate()
        self.options = {'gate':gate}
        current = self.app.agent_jobs.get_job(job['id'])
        try:
            self.app.agent_jobs.assess_and_continue(job['id'], 1, expected_version=current['version'],
                expected_intent_version=current['intent']['version'], disposition='continue',
                goal_status='not_met', capability_status='unknown', result_ref=job['artifact_id'],
                gap='合成资料尚需核对', next_action='继续人工指定的只读工作',
                evidence={'source':'合成资料','observed_at':datetime.now(timezone.utc).isoformat(),'detail':'人工确认'})
            prompt = self.wait_prompt(2)
            self.assertTrue(gate.entered.wait(3))
            running = self.app.agent_jobs.get_job(job['id'])
            self.assertNotIn('supervision_revision', running['attempt_plan'])
            self.assertNotIn('business_case', running['attempt_plan'])
            self.assertNotIn(MAIL_CASE['business_outcome'], prompt)
            supervisor.configure(job['id'], expected_version=running['version'],
                acceptance_criteria={'kind':'artifact_contains','text':'NO_SYNTHETIC_MATCH'},
                continuation_instruction='只读核对合成资料并形成内部结果',
                authorization_ref='仅供此隔离测试的明确纳管和一次接续',
                business_case={**MAIL_CASE,'stop_condition':'手动接续期间的后续决定'},
                prerequisite_state='waiting_review', value_state='supported')
        finally:
            gate.set()
        done = self.wait_finished(job['id'], attempt=2)
        self.assertEqual(done['status'], 'completed')
        self.assertIsNone(done.get('held_result'))


if __name__ == '__main__':
    unittest.main()
