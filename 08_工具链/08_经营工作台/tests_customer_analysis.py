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
from customer_analysis import parse_result,CLEANED,ANALYSIS_TEXT,ANALYSIS_LIST
from tests_agent_jobs import Process

def response():
    return {'original_language':'en','translation_zh':'我们需要500双样品，请确认鞋款规格和样品费用。',
        'cleaned':{key:{'company':'Buyer','quantity':'500','need':'需要样品'}.get(key,'') for key in CLEANED},
        'analysis':{**{key:{'intent':'样品询问，尚未确认订单','fit':'需核逐款供货依据','next_action':'询问鞋款、尺码和交付地'}.get(key,'') for key in ANALYSIS_TEXT},
            **{key:[] for key in ANALYSIS_LIST}}}

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
        for thread in self.jobs.threads.values():thread.join(3)
        self.stop.stop();self.which.stop();self.popen.stop();self.app.db.close();self.temp.cleanup()
    def wait(self,job):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            row=self.jobs.get_job(job['id'])
            if row['status'] not in ('queued','running'):
                thread=self.jobs.threads.get(job['id'])
                if thread:thread.join(2)
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

if __name__=='__main__':unittest.main()
