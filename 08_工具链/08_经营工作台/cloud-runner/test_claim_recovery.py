"""Offline claim readback recovery tests. No network or model calls."""
import json
import io
import queue
import threading
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
import runner


class ClaimRecoveryTests(unittest.TestCase):
    def invoke(self, directory, queue, execute=None):
        env = {'WORKBENCH_RUNNER_URL':'https://www.beiqiang.online/api/workbench-runner',
               'WORKBENCH_RUNNER_SECRET':'synthetic-test-secret-only',
               'WORKBENCH_RUNNER_STATE':directory}
        with patch.dict(runner.os.environ,env,clear=True), patch('sys.argv',['runner.py','--run-id','a'*32]), \
                patch.object(runner.shutil,'which',return_value='/fixture/codex'), \
                patch.object(runner,'Queue',return_value=queue), patch.object(runner.time,'sleep'), \
                patch.object(runner,'execute',execute or Mock()):
            runner.main()

    def queue(self, state, *, delayed=False):
        queue=Mock(); request={}; reads=[]
        def call(action, **fields):
            if action=='heartbeat': return {'claim_protocol':1}
            if action=='claim':
                request.update(fields)
                raise TimeoutError('lost response')
            if action=='claim_status':
                reads.append(fields)
                result={'claim_protocol':1,'request_id':fields['request_id'],
                        'state':'unknown' if delayed and len(reads)==1 else state}
                if result['state']=='claimed':result['run_id']=fields.get('run_id','a'*32)
                return result
            raise AssertionError(action)
        queue.call.side_effect=call
        return queue,request,reads

    def test_empty_response_loss_is_read_back_without_reclaim(self):
        q,request,reads=self.queue('empty')
        with tempfile.TemporaryDirectory() as directory:
            self.invoke(directory,q)
            self.assertFalse((Path(directory)/'claiming.json').exists())
        self.assertEqual([c.args[0] for c in q.call.call_args_list],['heartbeat','claim','claim_status'])
        self.assertEqual(reads[0]['request_id'],request['request_id'])
        self.assertEqual(reads[0]['run_id'],'a'*32)

    def test_delayed_empty_commit_can_be_observed_without_reclaim(self):
        q,_,reads=self.queue('empty',delayed=True)
        with tempfile.TemporaryDirectory() as directory:self.invoke(directory,q)
        self.assertEqual(len(reads),2)
        self.assertEqual(sum(c.args[0]=='claim' for c in q.call.call_args_list),1)

    def test_claimed_or_unknown_result_preserves_marker_and_stops(self):
        for state,expected in [('claimed',1),('unknown',3)]:
            with self.subTest(state=state),tempfile.TemporaryDirectory() as directory:
                q,request,reads=self.queue(state)
                with self.assertRaises(TimeoutError):self.invoke(directory,q)
                marker=json.loads((Path(directory)/'claiming.json').read_text())
                self.assertEqual(marker['request_id'],request['request_id'])
                self.assertEqual(marker['claim_options'],{'run_id':'a'*32})
                self.assertEqual(len(reads),expected)
                q.reset_mock()
                with self.assertRaisesRegex(RuntimeError,'reconciliation'):self.invoke(directory,q)
                self.assertEqual([c.args[0] for c in q.call.call_args_list],['claim_status'])
                self.assertEqual(q.call.call_args.kwargs,{'request_id':marker['request_id'],'run_id':'a'*32})
                self.assertEqual(json.loads((Path(directory)/'claiming.json').read_text()),marker)

    def test_mismatched_receipt_and_auth_error_never_clear_marker(self):
        for response in ({'claim_protocol':1,'request_id':'b'*32,'state':'empty'},
                         HTTPError('https://fixture',401,'denied',{},None)):
            q=Mock()
            q.call.side_effect=response if isinstance(response,Exception) else lambda *a,**k:response
            with patch.object(runner.time,'sleep') as sleep:
                self.assertFalse(runner.confirmed_empty_claim(q,'a'*32,{}))
                sleep.assert_not_called()

    def test_old_server_never_claims_protocol_support(self):
        q=Mock()
        def call(action,**fields):
            if action=='heartbeat':return {}
            if action=='claim':
                self.assertNotIn('request_id',fields)
                raise TimeoutError('legacy unknown')
            raise AssertionError(action)
        q.call.side_effect=call
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TimeoutError):self.invoke(directory,q)
            self.assertTrue((Path(directory)/'claiming.json').exists())
        self.assertEqual([c.args[0] for c in q.call.call_args_list],['heartbeat','claim'])

    def test_matching_ack_executes_once_and_wrong_ack_never_executes(self):
        for matches in (True,False):
            with self.subTest(matches=matches),tempfile.TemporaryDirectory() as directory:
                q=Mock(); execute=Mock()
                def call(action,**fields):
                    if action=='heartbeat':return {'claim_protocol':1}
                    if action=='claim':return {'claim_protocol':1,'request_id':fields['request_id'] if matches else 'b'*32,
                                              'job':{'id':'a'*32}}
                    raise AssertionError(action)
                q.call.side_effect=call
                if matches:
                    self.invoke(directory,q,execute)
                    execute.assert_called_once()
                else:
                    with self.assertRaisesRegex(RuntimeError,'acknowledgement'):self.invoke(directory,q,execute)
                    execute.assert_not_called()
                    self.assertTrue((Path(directory)/'claiming.json').exists())

    def saved_marker(self, directory, *, options=None, run_id=None):
        options = {} if options is None else options
        marker={'at':123456.0,'requested_run_id':run_id,'request_id':'c'*32,
                'claim_protocol':1,'claim_options':options}
        path=Path(directory)/'claiming.json'
        path.write_text(json.dumps(marker),encoding='utf-8')
        return path,marker

    def test_restart_confirmed_empty_uses_persisted_scope_then_can_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path,old=self.saved_marker(directory,options={'run_id':'a'*32,'public_web_research':True},run_id='a'*32)
            q=Mock(); execute=Mock()
            def call(action,**fields):
                if action=='claim_status':
                    self.assertEqual(fields,{'request_id':old['request_id'],**old['claim_options']})
                    return {'claim_protocol':1,'request_id':old['request_id'],'state':'empty'}
                if action=='heartbeat':return {'claim_protocol':1}
                if action=='claim':
                    self.assertNotEqual(fields['request_id'],old['request_id'])
                    return {'claim_protocol':1,'request_id':fields['request_id'],'job':None}
                raise AssertionError(action)
            q.call.side_effect=call
            with patch('sys.stdout',new_callable=io.StringIO) as output:
                self.invoke(directory,q,execute)
            event=json.loads(output.getvalue().splitlines()[0])
            self.assertEqual(event,{'event':'startup_claim_status','request_id':old['request_id'],
                                    'scope':old['claim_options'],'state':'empty'})
            self.assertNotIn('synthetic-test-secret-only',output.getvalue())
            self.assertEqual([c.args[0] for c in q.call.call_args_list],['claim_status','heartbeat','claim'])
            self.assertFalse(path.exists());execute.assert_not_called()

    def test_automatic_start_rechecks_all_preflight_after_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path,old=self.saved_marker(directory);q=Mock();order=[]
            def call(action,**fields):
                order.append(action)
                if action=='claim_status':return {'claim_protocol':1,'request_id':old['request_id'],'state':'empty'}
                if action=='heartbeat':return {'claim_protocol':1}
                if action=='claim':return {'claim_protocol':1,'request_id':fields['request_id'],'job':None}
                raise AssertionError(action)
            q.call.side_effect=call
            def check():
                order.append('preflight')
                return ({'ok':False,'checks':[{'name':'execution_recovery','ok':False,
                    'code':'EXECUTION_OUTCOME_REQUIRES_REVIEW'}]} if order.count('preflight')==1 else {'ok':True})
            env={'WORKBENCH_RUNNER_URL':'https://www.beiqiang.online/api/workbench-runner',
                 'WORKBENCH_RUNNER_SECRET':'synthetic-test-secret-only','WORKBENCH_RUNNER_STATE':directory}
            with patch.dict(runner.os.environ,env,clear=True),patch('sys.argv',['runner.py','--once']), \
                    patch.object(runner.shutil,'which',return_value='/fixture/codex'), \
                    patch('preflight.preflight',side_effect=check),patch.object(runner,'Queue',return_value=q):
                runner.main()
            self.assertEqual(order,['preflight','claim_status','preflight','heartbeat','claim'])
            self.assertFalse(path.exists())

    def test_automatic_start_unknown_stops_before_ready_or_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path,old=self.saved_marker(directory,options={'public_web_research':True});before=path.read_bytes()
            q=Mock();q.call.return_value={'claim_protocol':1,'request_id':old['request_id'],'state':'unknown'}
            pending={'ok':False,'checks':[{'name':'execution_recovery','ok':False,
                                          'code':'EXECUTION_OUTCOME_REQUIRES_REVIEW'}]}
            env={'WORKBENCH_RUNNER_URL':'https://www.beiqiang.online/api/workbench-runner',
                 'WORKBENCH_RUNNER_SECRET':'synthetic-test-secret-only','WORKBENCH_RUNNER_STATE':directory}
            with patch.dict(runner.os.environ,env,clear=True),patch('sys.argv',['runner.py','--once']), \
                    patch.object(runner.shutil,'which',return_value='/fixture/codex'), \
                    patch('preflight.preflight',return_value=pending) as check,patch.object(runner,'Queue',return_value=q):
                with self.assertRaisesRegex(RuntimeError,'unknown'):runner.main()
            self.assertEqual(path.read_bytes(),before);check.assert_called_once()
            self.assertEqual([c.args[0] for c in q.call.call_args_list],['claim_status'])
            self.assertEqual(q.call.call_args.kwargs,{'request_id':old['request_id'],'public_web_research':True})

    def test_preflight_failure_after_confirmed_empty_does_not_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path,old=self.saved_marker(directory);q=Mock()
            q.call.return_value={'claim_protocol':1,'request_id':old['request_id'],'state':'empty'}
            pending={'ok':False,'checks':[{'name':'execution_recovery','ok':False,
                                          'code':'EXECUTION_OUTCOME_REQUIRES_REVIEW'}]}
            env={'WORKBENCH_RUNNER_URL':'https://www.beiqiang.online/api/workbench-runner',
                 'WORKBENCH_RUNNER_SECRET':'synthetic-test-secret-only','WORKBENCH_RUNNER_STATE':directory}
            with patch.dict(runner.os.environ,env,clear=True),patch('sys.argv',['runner.py','--once']), \
                    patch.object(runner.shutil,'which',return_value='/fixture/codex'), \
                    patch('preflight.preflight',side_effect=[pending,{'ok':False}]),patch.object(runner,'Queue',return_value=q):
                with self.assertRaises(SystemExit):runner.main()
            self.assertFalse(path.exists())
            self.assertEqual([c.args[0] for c in q.call.call_args_list],['claim_status'])

    def test_other_preflight_failure_never_queries_or_clears(self):
        with tempfile.TemporaryDirectory() as directory:
            path,_=self.saved_marker(directory);before=path.read_bytes();q=Mock()
            failed={'ok':False,'checks':[{'name':'execution_recovery','ok':False,'code':'EXECUTION_OUTCOME_REQUIRES_REVIEW'},
                                         {'name':'queue_endpoint','ok':False,'code':'UNEXPECTED_QUEUE_ENDPOINT'}]}
            env={'WORKBENCH_RUNNER_URL':'https://www.beiqiang.online/api/workbench-runner',
                 'WORKBENCH_RUNNER_SECRET':'synthetic-test-secret-only','WORKBENCH_RUNNER_STATE':directory}
            with patch.dict(runner.os.environ,env,clear=True),patch('sys.argv',['runner.py','--once']), \
                    patch.object(runner.shutil,'which',return_value='/fixture/codex'), \
                    patch('preflight.preflight',return_value=failed),patch.object(runner,'Queue',return_value=q):
                with self.assertRaises(SystemExit):runner.main()
            self.assertEqual(path.read_bytes(),before);q.call.assert_not_called()

    def test_restart_nonempty_or_unavailable_receipts_never_reclaim(self):
        options={'run_id':'a'*32}
        responses=[('unknown',{'claim_protocol':1,'request_id':'c'*32,'state':'unknown'}),
                   ('claimed',{'claim_protocol':1,'request_id':'c'*32,'state':'claimed','run_id':'a'*32}),
                   ('receipt_mismatch',{'claim_protocol':1,'request_id':'b'*32,'state':'empty'}),
                   ('receipt_mismatch',{'claim_protocol':1,'request_id':'c'*32,'state':'empty','run_id':'a'*32}),
                   ('receipt_mismatch',{'claim_protocol':1,'request_id':'c'*32,'state':'claimed','run_id':'b'*32}),
                   ('scope_conflict',HTTPError('https://fixture',409,'conflict',{},None)),
                   ('network_error',TimeoutError('offline')),
                   ('network_error',URLError(ConnectionResetError('synthetic reset')))]
        for label,response in responses:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as directory:
                path,old=self.saved_marker(directory,options=options,run_id='a'*32);before=path.read_bytes()
                q=Mock();execute=Mock()
                q.call.side_effect=response if isinstance(response,Exception) else lambda *args,**kwargs:response
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError,label):self.invoke(directory,q,execute)
                    self.assertEqual(path.read_bytes(),before)
                self.assertEqual([c.args[0] for c in q.call.call_args_list],['claim_status','claim_status'])
                for c in q.call.call_args_list:self.assertEqual(c.kwargs,{'request_id':old['request_id'],**options})
                execute.assert_not_called()

    def test_untrusted_marker_or_other_active_state_is_not_queried(self):
        for fault in ('legacy','bad_scope','active','blocked'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                path,marker=self.saved_marker(directory)
                if fault=='legacy':marker.pop('request_id')
                if fault=='bad_scope':marker['claim_options']={'unrecognized':True}
                path.write_text(json.dumps(marker),encoding='utf-8');before=path.read_bytes()
                if fault in ('active','blocked'):(Path(directory)/(fault+'.json')).write_text('{}')
                q=Mock()
                with self.assertRaisesRegex(RuntimeError,'reconciliation'):self.invoke(directory,q)
                self.assertEqual(path.read_bytes(),before);q.call.assert_not_called()

    def test_marker_changed_during_readback_is_never_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path,old=self.saved_marker(directory);q=Mock()
            def call(action,**fields):
                self.assertEqual(action,'claim_status')
                path.write_text(json.dumps({**old,'request_id':'d'*32}),encoding='utf-8')
                return {'claim_protocol':1,'request_id':old['request_id'],'state':'empty'}
            q.call.side_effect=call
            with self.assertRaisesRegex(RuntimeError,'marker changed'):self.invoke(directory,q)
            self.assertEqual(json.loads(path.read_text())['request_id'],'d'*32)
            self.assertEqual([c.args[0] for c in q.call.call_args_list],['claim_status'])

    def test_local_runner_lock_serializes_and_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)
            child_code="import sys;from pathlib import Path;import runner;\nwith runner.runner_process_lock(Path(sys.argv[1])): print('acquired')"
            def child():
                return subprocess.run([sys.executable,'-B','-X','utf8','-c',child_code,directory],
                                      cwd=Path(__file__).parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      text=True,encoding='utf-8',errors='replace',timeout=10)
            with runner.runner_process_lock(state):
                with self.assertRaisesRegex(RuntimeError,'local state lock'):
                    with runner.runner_process_lock(state):pass
                blocked=child()
                self.assertNotEqual(blocked.returncode,0)
                self.assertIn('local state lock',blocked.stderr)
            released=child()
            self.assertEqual(released.returncode,0,released.stderr)
            self.assertIn('acquired',released.stdout)


    def test_crashed_process_releases_local_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            code="import sys,time;from pathlib import Path;import runner;\nwith runner.runner_process_lock(Path(sys.argv[1])):\n print('ready',flush=True);time.sleep(30)"
            proc=subprocess.Popen([sys.executable,'-B','-X','utf8','-c',code,directory],cwd=Path(__file__).parent,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
            output=queue.Queue()
            reader=threading.Thread(target=lambda:output.put(proc.stdout.readline()),daemon=True);reader.start()
            try:
                self.assertEqual(output.get(timeout=10).strip(),'ready')
                with self.assertRaisesRegex(RuntimeError,'local state lock'):
                    with runner.runner_process_lock(Path(directory)):pass
                proc.terminate();proc.wait(timeout=10)
                with runner.runner_process_lock(Path(directory)):pass
            finally:
                if proc.poll() is None:
                    proc.kill();proc.wait(timeout=10)
                proc.stdout.close();proc.stderr.close()


if __name__=='__main__':unittest.main()
