"""Consecutive actual verify CLI calls persist bindings, without platform access."""
from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as ET
import contextlib, hashlib, importlib.util, io, json, sys, tempfile, unittest
from unittest.mock import patch
import schema_publish_contract as contract

HERE=Path(__file__).resolve().parent

class VerifyPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((HERE/'schema_contract_fixtures/5998_create_sku_readback.json').read_text(encoding='utf-8'))
        spec=importlib.util.spec_from_file_location('persistent_verify_publisher',HERE/'publish_hot_rank_hr_a_batch.py')
        cls.pub=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.pub)

    def setup_files(self,tmp,operation='create'):
        request=ET.fromstring('<itemSchema>'+self.fixture['request_sku_xml']+'</itemSchema>')
        formal=ET.fromstring('<itemSchema>'+self.fixture['formal_sku_xml']+'</itemSchema>')
        receipt=tmp/'submission.json'; evidence=tmp/'readback.json'
        data={'operation':operation,'status':'submitted_needs_readback','product_id':'offline-target',
              'attempted_at':'2026-10-02T00:00:00+00:00',
              'expected_fields':contract.field_snapshot(request if operation=='create' else formal)}
        receipt.write_text(json.dumps(data),encoding='utf-8')
        return receipt,evidence,formal

    def call(self,receipt,evidence,formal,output=None):
        xml=evidence.parent/'formal.xml';xml.write_bytes(ET.tostring(formal))
        evidence.write_text(json.dumps({'product_id':'offline-target','request_id':self.fixture['formal_request_id'],
            'acquired_at':'2026-10-02T00:00:01+00:00','schema_file':'formal.xml',
            'schema_sha256':hashlib.sha256(xml.read_bytes()).hexdigest()}),encoding='utf-8')
        argv=[str(HERE/'publish_hot_rank_hr_a_batch.py'),'--mode','verify','--product-id','offline-target',
              '--receipt',str(receipt),'--formal-readback',str(evidence)]
        if output is not None:argv+=['--verification-receipt',str(output)]
        stdout=io.StringIO()
        with patch.object(sys,'argv',argv),patch.object(self.pub,'load_client') as client,contextlib.redirect_stdout(stdout):
            self.assertEqual(self.pub.main(),2) # Score/source/public not asserted by this SKU test.
            client.assert_not_called()
        return json.loads(stdout.getvalue())

    def test_consecutive_same_original_receipt_rejects_id_swap_and_retains_binding_after_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);receipt,evidence,formal=self.setup_files(tmp);original=receipt.read_bytes()
            first=self.call(receipt,evidence,formal)
            saved=tmp/'submission.json.verification.json'
            self.assertEqual(first,json.loads(saved.read_text(encoding='utf-8')))
            self.assertEqual(first['content_status'],'formal_fields_verified')
            bindings=first['established_sku_bindings'];self.assertEqual(len(bindings),22)
            changed=deepcopy(formal)
            a,b=changed.find('./field').findall('./complex-values')[:2]
            a=a.find("./field[@id='skuId']/value");b=b.find("./field[@id='skuId']/value")
            a.text,b.text=b.text,a.text
            for _ in range(2):
                second=self.call(receipt,evidence,changed) # Still use original, not first stdout.
                self.assertEqual(second['content_status'],'content_mismatch_or_noop')
                self.assertEqual(second['established_sku_bindings'],bindings)
                self.assertEqual(json.loads(saved.read_text(encoding='utf-8'))['established_sku_bindings'],bindings)
            self.assertEqual(self.call(receipt,evidence,formal)['content_status'],'formal_fields_verified')
            self.assertEqual(receipt.read_bytes(),original)
            self.assertEqual(first['submission_receipt_sha256'],hashlib.sha256(original).hexdigest())

    def test_explicit_atomic_path_replace_failure_preserves_old_ledger_and_source(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);receipt,evidence,formal=self.setup_files(tmp);output=tmp/'explicit-verification.json'
            original=receipt.read_bytes();self.call(receipt,evidence,formal,output);old=output.read_bytes()
            with patch.object(self.pub.os,'replace',side_effect=OSError('OFFLINE atomic commit failure')):
                with self.assertRaises(OSError):self.call(receipt,evidence,formal,output)
            self.assertEqual(output.read_bytes(),old);self.assertEqual(receipt.read_bytes(),original)
            self.assertEqual(list(tmp.glob('*.tmp')),[]);self.assertEqual(list(tmp.glob('*.lock')),[])
            self.assertEqual(self.call(receipt,evidence,formal,output)['content_status'],'formal_fields_verified')

    def test_reject_original_output_changed_submission_and_existing_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);receipt,evidence,formal=self.setup_files(tmp);original=receipt.read_bytes()
            with self.assertRaises(ValueError):self.call(receipt,evidence,formal,receipt)
            self.assertEqual(receipt.read_bytes(),original)
            self.call(receipt,evidence,formal)
            output=tmp/'submission.json.verification.json';state=output.read_bytes()
            lock=output.with_name(output.name+'.lock');lock.write_text('other verifier',encoding='utf-8')
            with self.assertRaises(FileExistsError):self.call(receipt,evidence,formal)
            self.assertEqual(lock.read_text(encoding='utf-8'),'other verifier');lock.unlink()
            receipt.write_bytes(original+b'\n')
            with self.assertRaises(ValueError):self.call(receipt,evidence,formal)
            self.assertEqual(output.read_bytes(),state)

    def test_update_id_comparison_stays_strict_with_persisted_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            receipt,evidence,formal=self.setup_files(Path(folder),operation='update');original=receipt.read_bytes()
            self.assertEqual(self.call(receipt,evidence,formal)['content_status'],'formal_fields_verified')
            formal.find("./field/complex-values/field[@id='skuId']/value").text='different-id'
            self.assertEqual(self.call(receipt,evidence,formal)['content_status'],'content_mismatch_or_noop')
            self.assertEqual(receipt.read_bytes(),original)

if __name__=='__main__':unittest.main()
