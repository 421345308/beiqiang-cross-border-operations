"""An uncertain customer write must be actionable across all callers."""
import http.client
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import server
from customer_workspace import CustomerWriteOutcomeUnknown
from desk_mcp import dispatch
import tests_customer_analysis as analysis_fixtures


def uncertain(*args, **kwargs):
    raise CustomerWriteOutcomeUnknown('private fixture error must not be exposed')


class CustomerOutcomeUnknownTests(unittest.TestCase):
    def test_http_returns_explicit_safe_outcome_unknown(self):
        app=SimpleNamespace(token='test-token', customer_workspace=SimpleNamespace(save_commercial=uncertain))
        httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);httpd.app=app
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
            try:
                conn.request('POST','/api/desk/customer-commercial',
                             body=json.dumps({'object_id':'customer:fixture','revision':'v'}),
                             headers={'X-Workbench-Token':'test-token','Content-Type':'application/json'})
                response=conn.getresponse();payload=json.loads(response.read())
            finally:conn.close()
            self.assertEqual(response.status,500)
            self.assertEqual(payload['code'],'outcome_unknown')
            self.assertIn('先核对',payload['error'])
            self.assertNotIn('private',json.dumps(payload))
        finally:
            httpd.shutdown();thread.join(5);httpd.server_close()

    def test_mcp_returns_structured_safe_outcome_unknown(self):
        tools=SimpleNamespace(call=uncertain,read_only=False)
        reply=dispatch(tools,{'id':42,'method':'tools/call',
                              'params':{'name':'save_customer_commercial','arguments':{}}})
        result=reply['result'];payload=json.loads(result['content'][0]['text'])
        self.assertTrue(result['isError']);self.assertEqual(payload['code'],'outcome_unknown')
        self.assertIn('先核对',payload['message']);self.assertNotIn('private',json.dumps(reply))

    def test_customer_analysis_job_requires_review_and_does_not_retry(self):
        fixture=analysis_fixtures.CustomerAnalysisTests('test_analysis_schema_profile_save_and_no_duplicate_markdown_artifact')
        fixture.setUp()
        try:
            with patch.object(fixture.app.customer_workspace,'save_profile',side_effect=uncertain):
                job=fixture.wait(fixture.start())
            self.assertEqual(job['status'],'needs_input');self.assertFalse(job['profile_saved'])
            self.assertIn('保存结果不明',job['error']);self.assertIn('未自动重试',job['error'])
            self.assertNotIn('private',job['error']);self.assertEqual(len(fixture.processes),1)
            self.assertFalse(fixture.artifacts)
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
