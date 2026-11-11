import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from agent_jobs import AgentJobs
from customer_workspace import CustomerWorkspace
from workspaces import WorkspaceConflict
from customer_analysis import (parse_result,prompt,SCHEMA,COMPANY_CONTEXT_SOURCES,CLEANED,ANALYSIS_TEXT,ANALYSIS_LIST,
                              LEGACY_ANALYSIS_TEXT,LEGACY_ANALYSIS_LIST)
from tests_agent_jobs import Process, join_job_threads, stop_job_threads

def response():
    return {'original_language':'en','translation_zh':'我们需要500双样品，请确认鞋款规格和样品费用。',
        'cleaned':{key:{'company':'Buyer','quantity':'500','need':'需要样品'}.get(key,'') for key in CLEANED},
        'analysis':{**{key:{'intent':'样品询问，尚未确认订单','fit':'需核逐款供货依据','next_action':'询问鞋款、尺码和交付地'}.get(key,'') for key in LEGACY_ANALYSIS_TEXT},
            **{key:[] for key in LEGACY_ANALYSIS_LIST}}}

class CustomerAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.obj={'id':'customer:website-BQ-REAL','kind':'customer','title':'Buyer','source':'网站询盘 · BQ-REAL',
            'content':json.dumps({'reference':'BQ-REAL','company':'Buyer','requirements':'We need 500 pairs of samples. Please confirm shoe specifications and sample fee.'})}
        self.artifacts=[]
        def get(oid):
            if oid!=self.obj['id']:raise ValueError('unknown')
            return copy.deepcopy(self.obj)
        def save(oid,title,content,artifact_id=None):
            item={'id':'artifact-1','object_id':oid,'title':title,'content':content};self.artifacts.append(item);return item
        business=SimpleNamespace(get_object=get,list_objects=lambda:[],save_artifact=save)
        self.app=SimpleNamespace(root=self.root,state=self.root/'runtime',db=sqlite3.connect(':memory:',check_same_thread=False),lock=threading.RLock(),business=business)
        self.app.customer_workspace=CustomerWorkspace(self.app);self.jobs=AgentJobs(self.app)
        self.options={'content':json.dumps(response(),ensure_ascii=False)};self.processes=[];self.commands=[]
        def spawn(command,**kwargs):
            self.commands.append(command);process=Process(command,**self.options);self.processes.append(process);return process
        self.popen=patch('agent_jobs.subprocess.Popen',side_effect=spawn);self.popen.start()
        self.which=patch('agent_jobs.shutil.which',return_value='/fixture/codex');self.which.start()
        self.stop=patch.object(AgentJobs,'_stop',side_effect=lambda process:process.kill());self.stop.start()
    def tearDown(self):
        for process in self.processes:process.kill()
        stop_job_threads(self.jobs)
        self.stop.stop();self.which.stop();self.popen.stop();self.app.db.close();self.temp.cleanup()
    def wait(self,job):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            row=self.jobs.get_job(job['id'])
            if row['status'] not in ('queued','running'):
                join_job_threads(self.jobs,job['id'])
                return row
            time.sleep(.01)
        self.fail('Analysis fixture did not terminate')
    def start(self):return self.jobs.start(self.obj['id'],'完整翻译并区分事实与推断',mode='customer_analysis')

    def test_analysis_schema_profile_save_and_no_duplicate_markdown_artifact(self):
        original=copy.deepcopy(self.obj);job=self.wait(self.start())
        self.assertEqual(job['status'],'completed');self.assertTrue(job['profile_saved']);self.assertIsNone(job['artifact_id'])
        self.assertEqual(self.artifacts,[]);self.assertEqual(self.obj,original)
        saved=self.app.customer_workspace.profile(self.obj['id'])
        self.assertEqual(saved['translation_zh'],response()['translation_zh']);self.assertEqual(saved['analysis']['next_action'],response()['analysis']['next_action'])
        command=self.commands[0];self.assertIn('--output-schema',command)
        schema=json.loads(Path(command[command.index('--output-schema')+1]).read_text(encoding='utf8'))
        self.assertFalse(schema['additionalProperties']);self.assertEqual(set(schema['properties']['cleaned']['required']),set(CLEANED))
        self.assertNotIn('translation_zh',self.jobs.get_job(job['id']))

    def test_new_session_keeps_full_customer_source_even_above_soft_target(self):
        original='SYNTHETIC_START_'+('x'*65000)+'_SYNTHETIC_TAIL_47_双重限制'
        self.obj['content']=json.dumps({'reference':'BQ-REAL','requirements':original},ensure_ascii=False)
        self.app.business.list_artifacts=lambda object_id:[]
        first=self.wait(self.start())
        self.assertEqual(first['status'],'completed')
        first_prompt=self.processes[-1].stdin.value
        self.assertIn(original,first_prompt)
        self.assertTrue(first['attempt_usage'][-1]['prompt_metrics']['over_target'])
        second=self.wait(self.jobs.resume(first['id'],'保留完整原文重新分析',new_session=True,
                                          expected_version=first['version']))
        prompt=self.processes[-1].stdin.value
        handoff,_=json.JSONDecoder().raw_decode(prompt.split('当前上下文（有界预览）：\n',1)[1])
        self.assertEqual(second['status'],'completed')
        self.assertIn(original,prompt)
        self.assertIn('完整逐段翻译',prompt)
        self.assertEqual(handoff['preview_budget_state'],'required_context_exceeds_budget')
        self.assertTrue(handoff['intent_summary_complete'])
        metrics=second['attempt_usage'][-1]['prompt_metrics']
        self.assertEqual(metrics['total_chars'],len(prompt))
        self.assertTrue(metrics['over_target'])

    def test_source_read_failure_is_needs_input_and_no_profile_save(self):
        self.options['source_read']=False;job=self.wait(self.start())
        self.assertEqual(job['status'],'needs_input');self.assertFalse(job['profile_saved']);self.assertIsNone(job['artifact_id'])
        self.assertEqual(self.app.customer_workspace.profile(self.obj['id'])['translation_zh'],'');self.assertFalse(self.artifacts)

    def test_changed_source_after_start_never_overwrites_derived_profile(self):
        gate=threading.Event();self.options['gate']=gate;job=self.start()
        deadline=time.monotonic()+2
        while not self.processes and time.monotonic()<deadline:time.sleep(.01)
        changed=json.loads(self.obj['content']);changed['requirements']='A new request supersedes the old one.';self.obj['content']=json.dumps(changed);gate.set()
        done=self.wait(job);self.assertEqual(done['status'],'needs_input');self.assertFalse(done['profile_saved'])
        self.assertEqual(self.app.customer_workspace.profile(self.obj['id'])['translation_zh'],'')

    def test_source_change_inside_save_window_requires_review_without_retry(self):
        workspace=self.app.customer_workspace
        saved=self.edit_analysis('Existing human decision must survive')
        row=self.app.db.execute('SELECT path FROM customer_profiles WHERE object_id=?',
                                (self.obj['id'],)).fetchone()
        derived_path=self.root/row[0]
        previous_bytes=derived_path.read_bytes()
        real_save=workspace.save_profile
        detected=[]

        def change_source_then_save(oid,body):
            # Reaching this wrapper proves the Agent's earlier source check
            # passed. Change the source only at the real service save boundary.
            current=workspace.profile(oid)
            self.assertEqual(current['source_hash'],body['source_hash'])
            self.assertEqual(current['revision'],body['revision'])
            changed=json.loads(self.obj['content'])
            changed['requirements']='New synthetic request arriving just before save.'
            self.obj['content']=json.dumps(changed)
            try:
                return real_save(oid,body)
            except WorkspaceConflict:
                detected.append('real source conflict')
                raise

        with patch.object(workspace,'save_profile',side_effect=change_source_then_save) as saving:
            done=self.wait(self.start())
            self.assertEqual(saving.call_count,1)
        self.assertEqual(detected,['real source conflict'])
        self.assertEqual(done['status'],'needs_input')
        self.assertFalse(done['profile_saved'])
        self.assertIsNone(done['artifact_id'])
        self.assertEqual(derived_path.read_bytes(),previous_bytes)
        current=workspace.profile(self.obj['id'])
        self.assertNotEqual(current['source_hash'],saved['source_hash'])
        self.assertTrue(current['stale'])
        self.assertEqual(current['analysis']['next_action'],'Existing human decision must survive')
        self.assertEqual(current['translation_zh'],saved['translation_zh'])
        self.assertEqual(len(self.processes),1)
        self.assertEqual(len(self.jobs.list_jobs()),1)
        self.assertEqual(done['attempt'],1)
        self.assertEqual(self.artifacts,[])
        self.assertFalse(self.app.db.in_transaction)

    def wait_for_process(self, count):
        deadline=time.monotonic()+2
        while (len(self.processes)<count or not self.processes[count-1].stdin.value) and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(len(self.processes),count)
        self.assertTrue(self.processes[count-1].stdin.value)

    def edit_analysis(self, text):
        profile=self.app.customer_workspace.profile(self.obj['id'])
        return self.app.customer_workspace.save_profile(self.obj['id'],{
            'source_hash':profile['source_hash'],'revision':profile['revision'],
            'analysis':{'next_action':text}})

    def test_manual_edit_during_generation_requires_review_without_overwrite(self):
        gate=threading.Event();self.options['gate']=gate;job=self.start()
        self.wait_for_process(1)
        saved=self.edit_analysis('人工决定先确认样品目的')
        gate.set();done=self.wait(job)
        self.assertEqual(done['status'],'needs_input');self.assertFalse(done['profile_saved'])
        self.assertIsNone(done['artifact_id']);self.assertEqual(len(self.processes),1)
        current=self.app.customer_workspace.profile(self.obj['id'])
        self.assertEqual(current['revision'],saved['revision'])
        self.assertEqual(current['analysis']['next_action'],'人工决定先确认样品目的')

    def test_resume_refreshes_snapshot_and_still_rejects_later_manual_edit(self):
        first=self.wait(self.start());self.assertEqual(first['status'],'completed')
        saved=self.edit_analysis('恢复前的人工说明')
        gate=threading.Event();self.options['gate']=gate
        resumed=self.jobs.resume(first['id'],'结合最新说明重新分析')
        self.assertEqual(resumed['profile_revision'],saved['revision'])
        self.assertFalse(resumed['profile_saved'])
        self.wait_for_process(2)
        self.assertIn('恢复前的人工说明',self.processes[1].stdin.value)
        latest=self.edit_analysis('恢复执行期间再次人工修改')
        gate.set();done=self.wait(resumed)
        self.assertEqual(done['status'],'needs_input');self.assertFalse(done['profile_saved'])
        self.assertEqual(self.app.customer_workspace.profile(self.obj['id'])['revision'],latest['revision'])
        self.assertEqual(len(self.processes),2)

    def test_resume_after_manual_edit_uses_new_revision_and_can_save(self):
        first=self.wait(self.start());self.assertEqual(first['status'],'completed')
        saved=self.edit_analysis('按新情况重新核对')
        resumed=self.jobs.resume(first['id'],'重新核对最新分析')
        self.assertEqual(resumed['profile_revision'],saved['revision'])
        done=self.wait(resumed)
        self.assertEqual(done['status'],'completed');self.assertTrue(done['profile_saved'])
        self.assertEqual(self.app.customer_workspace.profile(self.obj['id'])['analysis']['next_action'],
                         response()['analysis']['next_action'])

    def test_legacy_running_job_without_profile_revision_does_not_save(self):
        gate=threading.Event();self.options['gate']=gate;job=self.start()
        self.wait_for_process(1)
        with self.jobs.lock:
            legacy=self.jobs.get_job(job['id']);legacy.pop('profile_revision');self.jobs._save(legacy)
        gate.set();done=self.wait(job)
        self.assertEqual(done['status'],'needs_input');self.assertFalse(done['profile_saved'])
        self.assertEqual(self.app.customer_workspace.profile(self.obj['id'])['translation_zh'],'')

    def test_invalid_json_or_extra_claim_fields_fail_without_saving(self):
        for value in ['# Not JSON',json.dumps({**response(),'customer_value_score':99}),json.dumps({**response(),'translation_zh':''})]:
            self.options['content']=value;done=self.wait(self.start())
            self.assertEqual(done['status'],'failed');self.assertFalse(done['profile_saved']);self.assertIsNone(done['artifact_id'])
        self.assertEqual(self.app.customer_workspace.profile(self.obj['id'])['translation_zh'],'')

    def test_full_original_customer_text_is_not_18000_character_preview(self):
        original='FULL_ORIGINAL_SENTENCE. '*1000+'FINAL_REQUEST_MUST_BE_TRANSLATED'
        raw=json.loads(self.obj['content']);raw['requirements']=original;self.obj['content']=json.dumps(raw)
        self.wait(self.start());prompt=self.processes[0].stdin.value
        self.assertIn('FINAL_REQUEST_MUST_BE_TRANSLATED',prompt);self.assertIn(original,prompt)
        self.assertIn('不是摘要',prompt);self.assertIn('facts',prompt);self.assertIn('inferences',prompt)

    def test_default_draft_remains_markdown_and_requires_complete_chinese_parallel_text(self):
        self.options={'content':'# Reply\nEnglish reply.\n\n# 完整中文对照\n中文回复。'}
        done=self.wait(self.jobs.start(self.obj['id'],'准备回复草稿'))
        self.assertEqual(done['mode'],'draft');self.assertEqual(done['status'],'completed');self.assertFalse(done['profile_saved'])
        self.assertEqual(done['artifact_id'],'artifact-1');self.assertNotIn('--output-schema',self.commands[0])
        self.assertIn('完整中文对照',self.processes[0].stdin.value)

    def test_mode_validation_and_strict_cleaned_strings(self):
        with self.assertRaises(ValueError):self.jobs.start(self.obj['id'],'Do work',mode='send_email')
        malformed=response();malformed['cleaned']['quantity']=500
        with self.assertRaises(ValueError):parse_result(json.dumps(malformed))
        malformed=response();malformed['analysis']['facts']=[{'claim':'Not allowed shape'}]
        with self.assertRaises(ValueError):parse_result(json.dumps(malformed))

    def test_secretary_prompt_answers_known_factory_cooperation_before_order_checklist(self):
        text=prompt({'original_text':'Are you a factory? What is your MOQ?'},'分析核心意图')
        self.assertIn('贝强就是工厂',text)
        self.assertIn('现款可小量、混色混码',text)
        self.assertIn('Logo、鞋垫/标签、鞋盒、鞋面改色可做',text)
        self.assertIn('定制按难度商谈',text)
        self.assertIn('现在阻碍下一步',text)
        self.assertIn('报价时才需要',text)
        self.assertIn('不猜客户是否使用AI',text)
        self.assertIn('先回答核心需求',text)

    def test_operator_explanation_is_object_scoped_and_does_not_destroy_original(self):
        original='I want a factory partner and would like to know MOQ.'
        explanation='这条表单1000为必填占位，不代表1000双订单；核心为找合作工厂及了解MOQ。'
        text=prompt({'original_text':original,'cleaned':{'quantity':'1000'},'operator_context':explanation},'简报')
        self.assertIn(original,text);self.assertIn(explanation,text)
        self.assertIn('优先用其解释表单与正文冲突',text)
        self.assertIn('不能泛化到别的询盘',text)
        unrelated=prompt({'original_text':'We confirm an order of 1000 pairs.'},'分析')
        self.assertNotIn('必填占位',unrelated)

    def test_new_schema_complete_legacy_parse_compatible_and_three_questions_max(self):
        analysis=SCHEMA['properties']['analysis']
        self.assertTrue({'brief','core_need','secondary_requests','conflicts','recommended_reply','questions_now'}<=set(analysis['required']))
        self.assertEqual(analysis['properties']['questions_now']['maxItems'],3)
        self.assertEqual(parse_result(json.dumps(response()))['analysis'],response()['analysis'])
        expanded=response()
        expanded['analysis'].update(brief='寻合作，先答工厂与小量混配。',core_need='了解MOQ',recommended_reply='先介绍可承接方式，再请选款。',
                                   secondary_requests=[],conflicts=[],questions_now=['偏好的款型？'])
        self.assertEqual(parse_result(json.dumps(expanded))['analysis']['core_need'],'了解MOQ')
        expanded['analysis']['questions_now']=['a','b','c','d']
        with self.assertRaises(ValueError):parse_result(json.dumps(expanded))

    def test_context_uses_existing_sources_and_keeps_internal_details_out_of_buyer_reply(self):
        text=prompt({'original_text':'Please explain your cooperation options.'},'分析')
        for path in COMPANY_CONTEXT_SOURCES:self.assertIn(path,text)
        self.assertIn('内部成本、采购入口、供应商信息',text)
        self.assertIn('不写进建议给客户的正文',text)
        self.assertIn('英文正文，必须附完整中文译文',text)
if __name__=='__main__':unittest.main()
