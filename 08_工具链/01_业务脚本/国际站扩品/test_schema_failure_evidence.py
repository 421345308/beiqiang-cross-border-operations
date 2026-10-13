"""Failure evidence through real SDK transport/CLI with memory subprocess only."""
from pathlib import Path
import contextlib, hashlib, importlib.util, io, json, subprocess, sys, tempfile, unittest, types
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.request import Request
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
import schema_publish_contract as contract

HERE=Path(__file__).resolve().parent
SDK_PATH=HERE.parents[2]/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py'
FAKES={'accessToken':'FAKE credential /& + secret','appSecret':'FAKE signing secret','appKey':'FAKE app key'}
MARKER=b'\n__BEIQIANG_HTTP_STATUS__:'

class FailureEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(name,path):
            spec=importlib.util.spec_from_file_location(name,path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
        cls.sdk=load('failure_evidence_sdk',SDK_PATH)
        cls.pub=load('failure_evidence_publisher',HERE/'publish_hot_rank_hr_a_batch.py')

    def capture_native(self, completed=None, error=None):
        request=Request('https://open-api.alibaba.com/sync?sign=FAKE_SIGNATURE&session=FAKE_SESSION',data=b'xml=OFFLINE',headers={'Authorization':'Bearer FAKE_HEADER'})
        with patch.object(subprocess,'run',return_value=completed,side_effect=error) as runner:
            with self.assertRaises(self.sdk.ClientError) as raised:self.sdk.native_http_json(request)
            self.assertEqual(runner.call_count,1)
        return contract.safe_exception_evidence(raised.exception,FAKES)

    def assert_safe(self,result,*other):
        serialized=json.dumps(result)
        for secret in (*FAKES.values(),'FAKE_SIGNATURE','FAKE_SESSION','FAKE_HEADER',*other):
            self.assertNotIn(secret,serialized)

    def test_native_http_business_body_exit_status_refs_and_redaction(self):
        body={'error_response':{'code':'400','sub_code':'DESCRIPTION_REQUIRED','request_id':'OFFLINE_BUSINESS_REQUEST',
              'sub_msg':'bad sign=FAKE_DYNAMIC_SIGNATURE accessToken="FAKE_RESPONSE_TOKEN"',
              'access'+'_'+'token':'FAKE_RESPONSE_TOKEN','extra_private':'SHOULD_NOT_BE_SERIALIZED'}}
        result=self.capture_native(subprocess.CompletedProcess([],22,json.dumps(body).encode()+MARKER+b'400',
            b'curl failure https://open-api.alibaba.com/?sign=FAKE_SIGNATURE&session=FAKE_SESSION'))
        self.assertEqual(result['curl_exit_code'],22);self.assertEqual(result['http_status'],400)
        self.assertEqual(result['transport_phase'],'http_response');self.assertTrue(result['request_sent'])
        self.assertEqual(result['business_refs']['request_id'],'OFFLINE_BUSINESS_REQUEST')
        self.assertEqual(result['response_summary']['fields']['error_response']['sub_code'],'DESCRIPTION_REQUIRED')
        self.assert_safe(result,'FAKE_DYNAMIC_SIGNATURE','FAKE_RESPONSE_TOKEN','SHOULD_NOT_BE_SERIALIZED')

    def test_non_json_response_preserves_safe_excerpt_and_decode_phase(self):
        output=b'<html>gateway failed token=FAKE_HTML_TOKEN sign=FAKE_DYNAMIC_SIGNATURE</html>'+MARKER+b'502'
        result=self.capture_native(subprocess.CompletedProcess([],0,output,b''))
        self.assertEqual(result['http_status'],502);self.assertEqual(result['response_summary']['format'],'text')
        self.assertIn('gateway failed',result['response_summary']['excerpt']);self.assert_safe(result,'FAKE_HTML_TOKEN','FAKE_DYNAMIC_SIGNATURE')
        result=self.capture_native(subprocess.CompletedProcess([],0,b'not-json '+MARKER+b'200',b''))
        self.assertEqual(result['transport_phase'],'response_decode');self.assertEqual(result['http_status'],200)

    def test_timeout_has_partial_response_but_never_claims_not_sent(self):
        error=subprocess.TimeoutExpired(['DO_NOT_SAVE_ARGV'],65,output=b'{"error_response":{"request_id":"PARTIAL_REQUEST_ID","msg":"session=FAKE_PARTIAL_SESSION"}}',stderr=b'Authorization: Bearer FAKE_TIMEOUT_HEADER')
        result=self.capture_native(error=error)
        self.assertEqual(result['transport_phase'],'transport');self.assertIsNone(result['request_sent'])
        self.assertIsNone(result['curl_exit_code']);self.assertIsNone(result['http_status'])
        self.assertEqual(result['business_refs']['request_id'],'PARTIAL_REQUEST_ID')
        self.assert_safe(result,'FAKE_PARTIAL_SESSION','FAKE_TIMEOUT_HEADER','DO_NOT_SAVE_ARGV')

    def test_native_launch_failure_proves_only_process_not_launched(self):
        result=self.capture_native(error=FileNotFoundError('curl.exe unavailable'))
        self.assertEqual(result['transport_phase'],'subprocess_launch');self.assertFalse(result['request_sent'])
        self.assertIsNone(result['curl_exit_code']);self.assertIsNone(result['http_status'])
        self.assertEqual(result['response_summary']['format'],'not_captured')

    def test_basic_authorization_entire_value_is_removed_in_every_text_sink(self):
        encoded='ZmFrZS11c2VyOmZha2UtcGFzc3dvcmQ='
        raw='Authorization: Basic '+encoded+'\nGateway failure'
        error=self.sdk.ClientError(raw,transport_evidence={'phase':'response_decode',
            'stderr':raw,'response_body':'<html>'+raw+'</html>'})
        evidence=contract.safe_exception_evidence(error)
        self.assert_safe(evidence,encoded)
        for value in (evidence['message'],evidence['stderr_excerpt'],evidence['response_summary']['excerpt']):
            self.assertIn('[REDACTED]',value)
            self.assertNotIn('Basic'+' ',value)

    def test_plain_runtime_command_string_is_wholly_omitted_in_every_text_sink(self):
        for raw in ("command ['curl.exe','--data','FAKE_PRIVATE_PAYLOAD','--url','https://example.com']",
                    "argv: ['python', 'FAKE_PRIVATE_PAYLOAD']\nprivate second line FAKE_MULTILINE_PAYLOAD",
                    "transport failed: curl.exe --data FAKE_PRIVATE_PAYLOAD"):
            with self.subTest(raw=raw):
                error=RuntimeError(raw)
                error.transport_evidence={'stderr':raw,'response_body':'<html>'+raw+'</html>'}
                evidence=contract.safe_exception_evidence(error)
                self.assert_safe(evidence,'FAKE_PRIVATE_PAYLOAD','FAKE_MULTILINE_PAYLOAD','--data','curl.exe')
                self.assertEqual(evidence['message'],'[COMMAND_TEXT_OMITTED]')
                self.assertEqual(evidence['stderr_excerpt'],'[COMMAND_TEXT_OMITTED]')
                self.assertEqual(evidence['response_summary']['excerpt'],'[COMMAND_TEXT_OMITTED]')

    def test_legacy_unknown_and_free_text_secrets_are_bounded_not_inferred(self):
        error=self.sdk.ClientError('Native failed; curl exit 28; accessToken="quoted with spaces FAKE_Q"; '+
              'password=FAKE_PASSWORD '+FAKES['accessToken']+' Bearer FAKE_BARE '+'a'*64+'\n'+('x'*3000))
        result=contract.safe_exception_evidence(error,FAKES)
        self.assertEqual(result['curl_exit_code'],28);self.assertEqual(result['transport_phase'],'unknown')
        self.assertIsNone(result['request_sent']);self.assertIsNone(result['http_status'])
        self.assertLessEqual(len(result['message']),1200)
        self.assert_safe(result,'FAKE_Q','FAKE_PASSWORD','FAKE_BARE','a'*64)
        process_error=subprocess.CalledProcessError(28,['DO_NOT_SAVE_ARGV','PRIVATE_XML_PAYLOAD'],stderr=b'curl failed')
        result=contract.safe_exception_evidence(process_error)
        self.assert_safe(result,'DO_NOT_SAVE_ARGV','PRIVATE_XML_PAYLOAD')

    def test_actual_5998_69002_adapter_uses_sdk_evidence_transport(self):
        adapter_path=Path(r'C:\Users\spq\Documents\Codex\2026-10-02\task-8\sdk_runtime_5998.py')
        if not adapter_path.exists():self.skipTest('Owner task-scoped adapter not on this machine')
        local=types.ModuleType('inspect_local');local.P=HERE.parents[2]
        spec=importlib.util.spec_from_file_location('actual_owner_evidence_adapter',adapter_path)
        adapter=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'inspect_local':local}):spec.loader.exec_module(adapter)
        sdk=adapter.load()
        self.assertIs(sdk.http_json,sdk.native_http_json)
        result=subprocess.CompletedProcess([],22,b'{"error_response":{"request_id":"ADAPTER_REQUEST_ID"}}'+MARKER+b'503',b'gateway failed')
        with patch.object(subprocess,'run',return_value=result) as runner:
            with self.assertRaises(sdk.ClientError) as raised:
                sdk.http_json(Request('https://open-api.alibaba.com/sync',data=b'OFFLINE'))
            self.assertEqual(runner.call_count,1)
        evidence=contract.safe_exception_evidence(raised.exception)
        self.assertEqual(evidence['http_status'],503)
        self.assertEqual(evidence['business_refs']['request_id'],'ADAPTER_REQUEST_ID')

    def test_urllib_error_transport_and_response_decode_metadata(self):
        request=Request('https://open-api.alibaba.com/sync',data=b'OFFLINE')
        body=b'{"error_response":{"request_id":"URLLIB_REQUEST","code":403,"msg":"token=FAKE_TOKEN"}}'
        error=HTTPError(request.full_url,403,'forbidden',{},io.BytesIO(body))
        with patch.object(self.sdk,'urlopen',side_effect=error):
            with self.assertRaises(self.sdk.ClientError) as raised:self.sdk.http_json(request)
        result=contract.safe_exception_evidence(raised.exception)
        self.assertEqual(result['http_status'],403);self.assertEqual(result['business_refs']['request_id'],'URLLIB_REQUEST')
        self.assert_safe(result,'FAKE_TOKEN')
        with patch.object(self.sdk,'urlopen',side_effect=URLError('connection reset')):
            with self.assertRaises(self.sdk.ClientError) as raised:self.sdk.http_json(request)
        self.assertIsNone(contract.safe_exception_evidence(raised.exception)['request_sent'])
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'not JSON secret=FAKE_DECODE_SECRET'
        with patch.object(self.sdk,'urlopen',return_value=Response()):
            with self.assertRaises(self.sdk.ClientError) as raised:self.sdk.http_json(request)
        result=contract.safe_exception_evidence(raised.exception)
        self.assertEqual(result['transport_phase'],'response_decode');self.assert_safe(result,'FAKE_DECODE_SECRET')

    def test_real_publish_cli_persists_safe_diagnostics_one_write_no_retry(self):
        sdk=self.sdk
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);schema=tmp/'schema.xml';payload=tmp/'payload.xml';manifest=tmp/'manifest.json';receipt=tmp/'receipt.json'
            schema.write_text('<itemSchema><field id="icbuCatProp"><fields><field id="p-3" name="Model Number" type="input"/></fields></field><field id="productTitle"/></itemSchema>',encoding='utf-8')
            payload.write_text('<itemSchema><field id="icbuCatProp" type="complex"/><field id="productTitle"><value>OFFLINE TEST</value></field></itemSchema>',encoding='utf-8')
            manifest.write_text(json.dumps({'operation':'create','facts_reviewed':True,'source_evidence':['OFFLINE ONLY'],
                'category_id':32211,'expected_model':'OFFLINE_MODEL','current_schema':'schema.xml','payload_xml':'payload.xml',
                'current_schema_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),'schema_request_id':'OFFLINE_SCHEMA',
                'schema_acquired_at':datetime.now(timezone.utc).isoformat(),'field_ids':['icbuCatProp','productTitle']}),encoding='utf-8')
            body=json.dumps({'error_response':{'request_id':'CLI_BUSINESS_REQUEST','sub_code':'DESCRIPTION_REQUIRED',
                'msg':'Authorization=FAKE_REPLY_AUTH'}}).encode()+MARKER+b'400'
            argv=[str(HERE/'publish_hot_rank_hr_a_batch.py'),'--mode','publish','--input-manifest',str(manifest),'--receipt',str(receipt)]
            with patch.object(sdk,'http_json',sdk.native_http_json),patch.object(sys,'argv',argv),patch.object(self.pub,'load_client',return_value=sdk),patch.object(sdk,'load_config',return_value=FAKES),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],22,body,b'')) as runner,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.pub.main(),1)
                self.assertEqual(runner.call_count,1)
                with self.assertRaises(FileExistsError):self.pub.main()
                self.assertEqual(runner.call_count,1)
            result=json.loads(receipt.read_text(encoding='utf-8'))
            self.assertEqual(result['status'],'write_outcome_unknown');self.assertIsNone(result['response'])
            self.assertEqual(result['refs']['request_id'],'CLI_BUSINESS_REQUEST')
            self.assertEqual(result['failure_evidence']['http_status'],400)
            self.assertEqual(result['failure_evidence']['curl_exit_code'],22)
            self.assert_safe(result,'FAKE_REPLY_AUTH')

if __name__=='__main__':unittest.main()
