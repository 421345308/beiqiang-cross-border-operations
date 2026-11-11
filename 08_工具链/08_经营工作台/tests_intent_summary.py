"""Isolated task-intent handoff tests; no service or customer data required."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from task_continuity import TaskContinuity


class _Business:
    def __init__(self):
        self.artifacts = []

    def get_object(self, object_id):
        return {'id': object_id, 'kind': 'product', 'title': 'synthetic object'}

    def list_artifacts(self, object_id):
        return copy.deepcopy(self.artifacts)


class _Harness(TaskContinuity):
    def __init__(self, root):
        self.business = _Business()
        self.app = SimpleNamespace(root=root, business=self.business)
        self.job = {'id': 'synthetic-job', 'object_id': 'product:synthetic',
                    'instruction': '本轮工作', 'initial_instruction': '最初目标',
                    'status': 'completed', 'attempt': 0, 'created_at': '2026-11-01T00:00:00Z',
                    'version': 7, 'events': [], 'artifact_ids': [], 'next_action': '当前下一步'}

    def get_job(self, job_id):
        if job_id != self.job['id']:
            raise ValueError('unknown job')
        return copy.deepcopy(self.job)


class IntentSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'AGENTS.md').write_text('适用约束原文', encoding='utf8')
        status = self.root / '00_总控台/当前状态.md'
        status.parent.mkdir(parents=True)
        status.write_text('当前目标原档', encoding='utf8')
        self.service = _Harness(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, **kwargs):
        prompt = self.service._continuity_prompt('synthetic-job', **kwargs)
        return prompt, json.loads(prompt.split('当前上下文（有界预览）：\n', 1)[1])

    def test_legacy_goal_fallback_does_not_invent_decisions(self):
        context = self.service.get_task_context('synthetic-job')
        self.assertEqual(context['goal'], '最初目标')
        self.assertEqual(context['intent_version'], 0)
        self.assertEqual(context['source_version']['intent_version'], 0)
        self.assertEqual(context['intent_source'], 'initial_instruction')
        self.assertEqual(context['intent_updated_at'], '2026-11-01T00:00:00Z')
        self.assertEqual(context['effective_decisions'], [])
        self.assertFalse(context['decisions_recorded'])
        prompt, handoff = self.payload()
        self.assertFalse(handoff['decisions_recorded'])
        self.assertIn('不能据此认定不存在约束', handoff['decision_status'])
        self.assertIn('读取当前原档', handoff['decision_status'])
        del self.service.job['initial_instruction']
        self.assertEqual(self.service.get_task_context('synthetic-job')['goal'], '本轮工作')

    def test_only_current_intent_and_decisions_enter_handoff(self):
        self.service.job['intent'] = {
            'version': 3, 'goal': '当前目标', 'decisions': [{'text': '当前有效决定', 'source': '负责人记录'}],
            'decisions_recorded': True, 'source': '负责人调整', 'updated_at': '2026-11-11T00:00:00Z',
            'history': [{'state': 'superseded', 'goal': 'HISTORIC_GOAL_ONLY',
                         'decisions': [{'text': 'HISTORIC_DECISION_ONLY', 'source': '旧记录'}]}],
        }
        context = self.service.get_task_context('synthetic-job')
        self.assertEqual(context['goal'], '当前目标')
        self.assertEqual(context['effective_decisions'], [{'text': '当前有效决定', 'source': '负责人记录'}])
        self.assertEqual(context['source_version']['intent_version'], 3)
        prompt, handoff = self.payload()
        self.assertEqual(handoff['goal'], '当前目标')
        self.assertEqual(handoff['effective_decisions'], context['effective_decisions'])
        self.assertTrue(handoff['decisions_recorded'])
        self.assertEqual(handoff['intent_source'], '负责人调整')
        self.assertEqual(handoff['intent_basis'], 'current_task_record')
        self.assertNotIn('HISTORIC_GOAL_ONLY', prompt)
        self.assertNotIn('HISTORIC_DECISION_ONLY', prompt)
        self.assertNotIn('最初目标', prompt)

    def test_attempt_uses_frozen_intent_and_even_an_empty_frozen_action(self):
        self.service.job['intent'] = {
            'version': 2, 'goal': '更新后的目标', 'decisions': [{'text': '更新后的决定', 'source': '更新记录'}],
            'decisions_recorded': True, 'source': '更新来源', 'updated_at': '2026-11-11T00:00:00Z', 'history': [],
        }
        frozen = {'version': 1, 'goal': '领取时目标', 'decisions': [{'text': '领取时决定', 'source': '领取时来源'}],
                  'decisions_recorded': True, 'source': '首次记录', 'updated_at': '2026-11-10T00:00:00Z'}
        prompt, handoff = self.payload(frozen_intent=frozen, frozen_next_action='')
        self.assertEqual(handoff['goal'], '领取时目标')
        self.assertEqual(handoff['effective_decisions'], frozen['decisions'])
        self.assertEqual(handoff['intent_version'], 1)
        self.assertEqual(handoff['source_version']['intent_version'], 1)
        self.assertEqual(handoff['intent_basis'], 'frozen_at_claim')
        self.assertEqual(handoff['next_action'], '')
        self.assertNotIn('更新后的目标', prompt)
        self.assertNotIn('更新后的决定', prompt)
        self.assertNotIn('当前下一步', prompt)

    def test_handoff_gives_task_output_location_and_constraint_sources(self):
        self.service.job['artifact_ids'] = ['task-output']
        self.service.business.artifacts = [
            {'id': 'task-output', 'title': '已有成果', 'path': 'work/result.md', 'content': '依据与成果'},
            {'id': 'other-output', 'title': '无关成果', 'path': 'other.md', 'content': 'UNRELATED'},
        ]
        prompt, handoff = self.payload()
        self.assertEqual(handoff['next_action'], '当前下一步')
        self.assertEqual(len(handoff['prior_task_outputs']), 1)
        output = handoff['prior_task_outputs'][0]
        self.assertEqual(output['id'], 'task-output')
        self.assertEqual(output['path'], 'work/result.md')
        self.assertTrue(output['task_output'])
        self.assertNotIn('UNRELATED', prompt)
        self.assertEqual([x['path'] for x in handoff['shared_sources']], ['AGENTS.md', '00_总控台/当前状态.md'])
        self.assertTrue(all(x['available'] for x in handoff['shared_sources']))
        self.assertNotIn('适用约束原文', prompt)
        self.assertIn('get_business_context', handoff['retrieval'])

    def test_task_context_projects_current_status_but_hashes_original(self):
        status = self.root / '00_总控台/当前状态.md'
        status.write_text('现行目标\n历史不再有效的规则', encoding='utf-8-sig')
        expected = hashlib.sha256(status.read_bytes()).hexdigest()
        original = status.read_bytes().decode('utf-8-sig')
        with patch('business_context.current_goals_projection', create=True,
                   return_value=('现行目标', True)) as projection:
            shared = self.service.get_task_context('synthetic-job')['shared_sources'][1]
        projection.assert_called_once_with(original)
        self.assertEqual(shared['source_sha256'], expected)
        self.assertEqual(shared['content'], '现行目标')
        self.assertTrue(shared['projection_complete'])
        self.assertIn('历史内容按原路径查看', shared['projection'])
        with patch('business_context.current_goals_projection', create=True,
                   return_value=('可识别部分', False)):
            shared = self.service.get_task_context('synthetic-job')['shared_sources'][1]
        self.assertEqual(shared['content'], '可识别部分')
        self.assertFalse(shared['projection_complete'])
        self.assertIn('结构不完整', shared['projection'])

    def test_supported_maximum_intent_is_not_silently_truncated(self):
        decisions = [{'text': f'决定{i:02}' + 'd'*290, 'source': '来源记录'} for i in range(20)]
        self.assertLessEqual(sum(len(d['text']) + len(d['source']) for d in decisions), 6000)
        goal = '目标' * 6000
        self.service.job['intent'] = {'version': 4, 'goal': goal, 'decisions': decisions,
            'decisions_recorded': True, 'source': '负责人调整', 'updated_at': None, 'history': []}
        prompt, handoff = self.payload()
        self.assertEqual(handoff['goal'], goal)
        self.assertEqual(handoff['effective_decisions'], decisions)
        self.assertTrue(handoff['intent_summary_complete'])
        self.assertLess(len(prompt), 60000)

    def test_oversized_legacy_intent_is_explicitly_incomplete(self):
        decisions = [{'text': '决定' + str(i), 'source': '历史来源'} for i in range(21)]
        self.service.job['intent'] = {'version': 1, 'goal': 'g'*12001, 'decisions': decisions,
            'decisions_recorded': True, 'source': '历史导入', 'updated_at': None, 'history': []}
        _, handoff = self.payload()
        self.assertTrue(handoff['goal_truncated'])
        self.assertTrue(handoff['decisions_truncated'])
        self.assertFalse(handoff['intent_summary_complete'])
        self.assertIn('先读取原任务上下文', handoff['retrieval'])


if __name__ == '__main__':
    unittest.main()
