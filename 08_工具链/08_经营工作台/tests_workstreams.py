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
                '# 国际站经营诊断\n\n## 工作线当前状态\n\n'
                '**当前工作：**合成国际站工作。\n'
                '**已验证结果：**合成结果已记录。\n'
                '**下一步：**核对合成商品状态。\n'
                '**阻塞：**合成提交被拒绝。\n'),
            '03_独立站/README.md': (
                '# 独立站项目\n\n## 工作线当前状态\n\n'
                '**当前工作：**合成独立站工作。\n'
                '**已验证结果：**合成版本已验证。\n'
                '**下一步：**继续逐款核对合成来源。\n'),
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
        for key in ('alibaba', 'website'):
            row = rows[key]
            self.assertEqual(row['source']['state'], 'ok')
            self.assertTrue(row['source']['observed_at'])
            self.assertTrue(row['source']['modified_at'])
            self.assertTrue(row['source']['result'])
            self.assertTrue(row['source']['next_action'])
        self.assertEqual(rows['tools']['source']['state'], 'unknown')
        self.assertEqual(rows['tools']['source']['read_state'], 'ok')
        self.assertTrue(rows['tools']['source']['observed_at'])
        self.assertTrue(rows['tools']['source']['modified_at'])
        self.assertEqual(rows['tools']['focus'], '当前工作未登记')
        self.assertEqual(rows['tools']['source']['result'], '')
        self.assertEqual(rows['tools']['source']['next_action'], '')
        self.assertIn('合成提交被拒绝', rows['alibaba']['source']['blocker'])
        self.assertIn('继续逐款核对合成来源', rows['website']['source']['next_action'])
        self.assertEqual(rows['website']['source']['blocker'], '')

    def test_tools_current_task_comes_from_bound_job_even_when_readme_is_missing(self):
        snapshot = self.snapshot()
        snapshot['workstream_links'].append({'workstream':'tools','host_id':'durable','thread_id':'tools-thread'})
        snapshot['threads'].append({'id':'tools-thread','hostId':'durable','status':'notLoaded'})
        jobs = [{'id':'real-job','title':'实际关联工作','status':'running',
                 'summary':'AgentJobs 当前成果','next_action':'AgentJobs 当前下一步',
                 'conversations':[{'provider':'codex','conversation_id':'tools-thread',
                                   'control':'reference_only','host_id':'durable',
                                   'host_bound_at':'2026-11-11T08:30:00+00:00'}]}]
        row = next(x for x in build_workstreams(self.root, jobs, snapshot) if x['id']=='tools')
        self.assertEqual(row['source']['state'], 'unknown')
        self.assertEqual(row['source']['read_state'], 'ok')
        self.assertEqual(row['source']['result'], '')
        self.assertEqual(row['related_jobs'][0]['status'], 'running')
        self.assertEqual(row['related_jobs'][0]['result'], 'AgentJobs 当前成果')
        self.assertEqual(row['related_jobs'][0]['next_action'], 'AgentJobs 当前下一步')
        self.assertEqual(row['related_jobs'][0]['source'], 'AgentJobs')
        (self.root/'08_工具链/08_经营工作台/README.md').unlink()
        row = next(x for x in build_workstreams(self.root, jobs, snapshot) if x['id']=='tools')
        self.assertEqual(row['source']['state'], 'unavailable')
        self.assertIsNone(row['source']['modified_at'])
        self.assertEqual(row['related_jobs'][0]['id'], 'local:real-job')
        self.assertEqual(row['related_jobs'][0]['status'], 'running')

    def test_unavailable_source_or_changed_structure_is_not_misreported(self):
        path = self.root/'03_独立站/README.md'
        path.write_text('结构已更改，但不是此前的业务入口。', encoding='utf8')
        rows = {row['id']: row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertEqual(rows['website']['source']['state'], 'unknown')
        self.assertEqual(rows['website']['source']['read_state'], 'ok')
        self.assertIn('结构化', rows['website']['source']['reason'])
        path.unlink()
        rows = {row['id']: row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertEqual(rows['website']['source']['state'], 'unavailable')
        self.assertIsNone(rows['website']['source']['modified_at'])

    def test_new_source_paragraph_does_not_reuse_historical_sentence(self):
        path = self.root/'03_独立站/README.md'
        path.write_text('# 网站\n\n当前版本记录采用了全新的表述。\n\n'
                        '## 历史阶段\n\n'
                        '**持续推进：国际站与独立站产品对齐。** 旧阶段记录。继续逐款重复旧动作。\n\n'
                        '**下一步：**仅用于旧阶段。\n', encoding='utf8')
        row = next(row for row in build_workstreams(self.root, [], self.snapshot()) if row['id']=='website')
        self.assertEqual(row['source']['state'], 'unknown')
        self.assertEqual(row['source']['read_state'], 'ok')
        self.assertEqual(row['focus'], '当前工作未登记')
        self.assertEqual(row['source']['result'], '')
        self.assertEqual(row['source']['next_action'], '')

    def test_directions_come_from_global_table_and_do_not_invent_progress(self):
        path = self.root/'00_总控台/当前状态.md'
        path.parent.mkdir(parents=True)
        path.write_text('# 当前状态\n\n'
            '**海外 B2B 现行方向：**批量准备，逐封审核和局部修改；客户推进与展示并行。\n\n'
            '| 方向 | 长期结果 | 看什么判断进展 |\n'
            '| --- | --- | --- |\n'
            '| 国际 B2B | 合成国际目标 | 合成国际指标 |\n'
            '| 国内抖店 | 合成国内目标 | 合成国内指标 |\n'
            '| 内容与创作 | 合成创作目标 | 合成创作指标 |\n'
            '| 共同工作能力 | 合成协作目标 | 合成协作指标 |\n'
            '| 新业务方向 | 合成新方向目标 | 合成新方向指标 |\n', encoding='utf8')
        jobs = [{'id':'same-title-only', 'title':'新业务方向', 'status':'running'}]
        rows = {row['id']:row for row in build_workstreams(self.root, jobs, self.snapshot())}
        self.assertTrue({'tools','alibaba','website','international','domestic','creation'} <= set(rows))
        international = rows['international']
        self.assertIn('批量准备，逐封审核和局部修改', international['focus'])
        self.assertIn('客户推进与展示并行', international['focus'])
        self.assertEqual(international['source']['long_term_goal'], '合成国际目标')
        self.assertEqual(international['source']['scope'], 'direction_only')
        self.assertEqual(international['source']['result'], '')
        self.assertEqual(international['source']['next_action'], '')
        self.assertIn('长期目标（不代表当前进度）', rows['domestic']['focus'])
        self.assertIn('长期目标（不代表当前进度）', rows['creation']['focus'])
        new = next(row for row in rows.values() if row['title']=='新业务方向')
        self.assertTrue(new['id'].startswith('direction-'))
        self.assertIsNone(new['conversation'])
        self.assertEqual(new['related_jobs'], [])
        self.assertEqual(new['source']['result'], '')

    def test_missing_current_direction_does_not_resurrect_a_historical_priority(self):
        path = self.root/'00_总控台/当前状态.md'
        path.parent.mkdir(parents=True)
        path.write_text('# 当前状态\n\n**历史决定：**先展示，暂停开发。\n\n'
            '| 方向 | 长期结果 | 看什么判断进展 |\n'
            '| --- | --- | --- |\n'
            '| 国际 B2B | 合成海外目标 | 合成指标 |\n', encoding='utf8')
        row = next(row for row in build_workstreams(self.root, [], self.snapshot()) if row['id']=='international')
        self.assertIn('长期目标（不代表当前进度）', row['focus'])
        self.assertNotIn('暂停开发', row['focus'])
        self.assertEqual(row['source']['next_action'], '')

    def test_unreadable_or_ambiguous_global_directions_are_visible_as_unknown(self):
        folder = self.root/'00_总控台'
        folder.mkdir(parents=True)
        rows = {row['id']:row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertEqual(rows['direction-registry-unavailable']['source']['state'], 'unknown')
        path = folder/'当前状态.md'
        path.write_text('# 当前状态\n\n缺少方向表。\n', encoding='utf8')
        rows = {row['id']:row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertEqual(rows['direction-registry-unavailable']['source']['state'], 'unknown')
        path.write_text('# 当前状态\n\n'
            '**海外 B2B 现行方向：**旧的合成方向。\n'
            '**海外 B2B 现行方向：**新的合成方向。\n\n'
            '| 方向 | 长期结果 | 看什么判断进展 |\n'
            '| --- | --- | --- |\n'
            '| 国际 B2B | 合成海外目标 | 合成指标 |\n'
            '| 新业务方向 | 第一个目标 | 合成指标 |\n'
            '| 新业务方向 | 第二个目标 | 合成指标 |\n', encoding='utf8')
        rows = {row['id']:row for row in build_workstreams(self.root, [], self.snapshot())}
        self.assertIn('长期目标（不代表当前进度）', rows['international']['focus'])
        self.assertNotIn('旧的合成方向', rows['international']['focus'])
        duplicate = next(row for row in rows.values() if row['title']=='新业务方向')
        self.assertEqual(duplicate['source']['state'], 'unknown')
        self.assertEqual(duplicate['source']['long_term_goal'], '')
        self.assertEqual(duplicate['related_jobs'], [])

    def test_only_explicit_reference_is_associated_and_old_status_stays_observation(self):
        jobs = [
            {'id':'exact-ref','title':'明确参考任务','status':'completed',
             'conversations':[{'provider':'codex','conversation_id':'thread-one','control':'reference_only',
                               'host_id':'durable','host_bound_at':'2026-11-11T08:30:00+00:00'}],
             'summary':'已记录任务结果','next_action':'核对成果','error':'已有阻塞',
             'updated_at':'2026-11-11T05:00:00+00:00'},
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
                         {'local:exact-ref'})
        self.assertEqual(rows['alibaba']['related_jobs_observation']['state'], 'ok')
        linked = rows['alibaba']['related_jobs'][0]
        self.assertEqual(linked['result'], '已记录任务结果')
        self.assertEqual(linked['next_action'], '核对成果')
        self.assertEqual(linked['blocker'], '已有阻塞')
        self.assertEqual(linked['source'], 'AgentJobs')
        self.assertEqual(linked['host_id'], 'durable')
        self.assertEqual(linked['relation'], 'conversation_ref')
        self.assertTrue(linked['observed_at'])
        self.assertIsNone(rows['tools']['conversation'])
        self.assertEqual(rows['tools']['related_jobs'], [])

    def test_same_thread_id_on_different_hosts_only_matches_its_bound_job(self):
        def bound(host):
            return {'provider':'codex', 'conversation_id':'thread-one', 'control':'reference_only',
                    'host_id':host, 'host_bound_at':'2026-11-11T08:30:00+00:00'}
        snapshot = self.snapshot('ok')
        snapshot['threads'].append({'id':'thread-one', 'hostId':'second-host', 'title':'another', 'status':'idle'})
        snapshot['workstream_links'].append({'workstream':'website','host_id':'second-host','thread_id':'thread-one'})
        jobs = [{'id':'first','conversations':[bound('durable')]},
                {'id':'second','conversations':[bound('second-host')]}]
        rows = {row['id']:row for row in build_workstreams(self.root, jobs, snapshot)}
        self.assertEqual([job['id'] for job in rows['alibaba']['related_jobs']], ['local:first'])
        self.assertEqual([job['id'] for job in rows['website']['related_jobs']], ['local:second'])
        self.assertEqual(rows['alibaba']['related_jobs'][0]['host_id'], 'durable')
        self.assertEqual(rows['website']['related_jobs'][0]['host_id'], 'second-host')

    def test_unbound_or_competing_reference_never_claims_a_job(self):
        valid = {'provider':'codex', 'conversation_id':'thread-one', 'control':'reference_only',
                 'host_id':'durable', 'host_bound_at':'2026-11-11T08:30:00+00:00'}
        valid_job = {'id':'bound','conversations':[valid]}
        conflicts = [
            {'id':'session-only','session_id':'thread-one'},
            {'id':'unbound','conversations':[{'provider':'codex','conversation_id':'thread-one',
                                               'control':'reference_only'}]},
            {'id':'missing-bound-time','conversations':[{**valid,'host_id':'another','host_bound_at':None}]},
            {'id':'invalid-bound-time','conversations':[{**valid,'host_bound_at':'not-a-time'}]},
            {'id':'duplicate-job','conversations':[dict(valid)]},
            {'id':'duplicate-refs','conversations':[dict(valid),dict(valid)]},
            {'id':'unreadable','conversations':'not-a-list'},
        ]
        for conflict in conflicts:
            with self.subTest(conflict=conflict['id']):
                row = next(row for row in build_workstreams(self.root, [valid_job, conflict], self.snapshot())
                           if row['id']=='alibaba')
                self.assertEqual(row['related_jobs'], [])
                self.assertEqual(row['related_jobs_observation']['state'], 'ambiguous')
        row = next(row for row in build_workstreams(self.root, [{'id':'session-only','session_id':'thread-one'}],
                                                       self.snapshot()) if row['id']=='alibaba')
        self.assertEqual(row['related_jobs'], [])
        self.assertEqual(row['related_jobs_observation']['state'], 'ambiguous')

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
