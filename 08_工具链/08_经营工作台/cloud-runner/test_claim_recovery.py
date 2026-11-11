"""Offline claim readback recovery tests. No network or model calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
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
                return {'claim_protocol':1,'request_id':fields['request_id'],
                        'state':'unknown' if delayed and len(reads)==1 else state}
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
                q.call.assert_not_called()

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

if __name__=='__main__':unittest.main()
