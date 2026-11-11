import tempfile
import unittest
from pathlib import Path

from workstreams import build_workstreams


class WorkstreamProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='beiqiang-workstreams-')
        self.root = Path(self.tmp.name).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        self.assertNotEqual(self.root, temp_root)
        self.assertTrue(self.root.is_relative_to(temp_root))
        entries = {
            '08_工具链/08_经营工作台/README.md': (
                '**总控当前工作：**合成工作目标。\n\n'
                '**总控已验证结果：**合成工具结果，测试已完成。\n\n'
                '**总控下一步：**核对合成权限。\n\n'
                '**总控阻塞：**合成连接受限，不同时启动两套。\n'),
            '02_Alibaba运营/01_店铺与全店诊断/店铺经营诊断.md': (
                '本轮研究七号仓库合成资料；11月11日授权后，合成提交被拒绝，未创建商品ID。\n\n'
                '负责人要求优先使用真实适配的现有鞋靴类目，保留实际用途。\n'),
            '03_独立站/README.md': (
                '**持续推进：国际站与独立站产品对齐（合成）。** 合成版本已验证。继续逐款核对合成来源。\n'),
        }
        for name, content in entries.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf8')

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def snapshot(state='unavailable'):
        return {'state': state, 'source': '正式工具的只读快照',
                'observed_at': '2026-11-11T09:00:00+00:00',
                'snapshot_observed_at': '2026-11-11T05:00:00+00:00',
                'workstream_links': [{'workstream':'alibaba','host_id':'durable','thread_id':'thread-one',
                    'source_note':'明确登记','linked_at':'2026-11-11T08:00:00+00:00',
                    'registration_state':'present_in_snapshot'}],
                'threads': [{'id':'thread-one','hostId':'durable','title':'正式标题',
                    'status':'active','updatedAt':'2026-11-11T04:00:00+00:00'}]}

    def test_source_excerpts_have_provenance_and_no_copied_store(self):
        rows = {row['id']: row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertEqual(set(rows), {'tools','alibaba','website'})
        for row in rows.values():
            self.assertEqual(row['source']['state'], 'ok')
            self.assertTrue(row['source']['observed_at'])
            self.assertTrue(row['source']['modified_at'])
            self.assertTrue(row['source']['result'])
            self.assertTrue(row['source']['next_action'])
        self.assertIn('合成工具结果', rows['tools']['source']['result'])
        self.assertEqual(rows['tools']['focus'], '合成工作目标。')
        self.assertIn('核对合成权限', rows['tools']['source']['next_action'])
        self.assertIn('合成提交被拒绝', rows['alibaba']['source']['blocker'])
        self.assertIn('继续逐款核对合成来源', rows['website']['source']['next_action'])
        self.assertEqual(rows['website']['source']['blocker'], '')

    def test_unavailable_source_or_changed_structure_is_not_misreported(self):
        path = self.root/'03_独立站/README.md'
        path.write_text('结构已更改，但不是此前的业务入口。', encoding='utf8')
        rows = {row['id']: row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertEqual(rows['website']['source']['state'], 'unavailable')
        self.assertIn('结构', rows['website']['source']['reason'])
        path.unlink()
        rows = {row['id']: row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertEqual(rows['website']['source']['state'], 'unavailable')
        self.assertIsNone(rows['website']['source']['modified_at'])

    def test_only_explicit_reference_is_associated_and_old_status_stays_observation(self):
        jobs = [
            {'id':'exact-session','session_id':'thread-one','title':'真实链接任务','status':'completed'},
            {'id':'exact-ref','conversations':[{'provider':'codex','conversation_id':'thread-one'}],
             'title':'明确参考任务','status':'needs_input'},
            {'id':'wrong-provider','conversations':[{'provider':'chatgpt','conversation_id':'thread-one'}]},
            {'id':'same-title','title':'正式标题','status':'running'},
        ]
        rows = {row['id']: row for row in build_workstreams(self.root, jobs, self.snapshot())}
        conversation = rows['alibaba']['conversation']
        self.assertEqual(conversation['state'], 'unavailable')
        self.assertEqual(conversation['observed_status'], 'active')
        self.assertEqual(conversation['last_observed_status'], 'active')
        self.assertEqual(conversation['observed_at'], '2026-11-11T05:00:00+00:00')
        self.assertEqual(conversation['attempted_at'], '2026-11-11T09:00:00+00:00')
        self.assertEqual(conversation['control'], 'reference_only')
        self.assertEqual({x['id'] for x in rows['alibaba']['related_jobs']},
                         {'local:exact-session','local:exact-ref'})
        self.assertIsNone(rows['tools']['conversation'])
        self.assertEqual(rows['tools']['related_jobs'], [])

    def test_individual_observation_is_not_full_snapshot_refresh(self):
        snapshot = self.snapshot()
        snapshot['threads'][0].update(status='notLoaded', individual_observation={
            'state':'ok','source':'mcp__codex_app__read_thread',
            'observed_at':'2026-11-11T10:00:00+00:00',
            'attempted_at':'2026-11-11T10:00:00+00:00','value_scope':'individual'})
        row = next(x for x in build_workstreams(self.root, [], snapshot) if x['id']=='alibaba')
        self.assertEqual(row['conversation']['state'], 'ok')
        self.assertEqual(row['conversation']['observed_status'], 'notLoaded')
        self.assertEqual(row['conversation']['observed_at'], '2026-11-11T10:00:00+00:00')
        self.assertEqual(row['conversation']['observation_scope'], 'individual')
        self.assertEqual(snapshot['state'], 'unavailable')

    def test_missing_and_ambiguous_references_never_guess_by_title(self):
        snapshot = self.snapshot('ok')
        snapshot['threads'] = [{'id':'different','hostId':'durable','title':'正式标题','status':'active'}]
        row = next(x for x in build_workstreams(self.root, [], snapshot) if x['id']=='alibaba')
        self.assertEqual(row['conversation']['state'], 'missing')
        self.assertIsNone(row['conversation']['observed_at'])
        self.assertEqual(row['conversation']['observed_status'], 'unknown')
        snapshot['workstream_links'].append(dict(snapshot['workstream_links'][0]))
        row = next(x for x in build_workstreams(self.root, [], snapshot) if x['id']=='alibaba')
        self.assertIsNone(row['conversation'])


if __name__ == '__main__':
    unittest.main()
