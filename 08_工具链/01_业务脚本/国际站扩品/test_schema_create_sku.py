"""Actual 5998 SKU readback regression; no client, credentials or network."""
from pathlib import Path
from xml.etree import ElementTree as ET
from copy import deepcopy
import contextlib, hashlib, importlib.util, io, json, sys, tempfile, unittest
from unittest.mock import patch
import schema_publish_contract as contract

HERE = Path(__file__).resolve().parent

class CreateSkuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((HERE/'schema_contract_fixtures/5998_create_sku_readback.json').read_text(encoding='utf-8'))
        spec=importlib.util.spec_from_file_location('sku_publisher',HERE/'publish_hot_rank_hr_a_batch.py')
        cls.pub=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.pub)

    def roots(self):
        return [ET.fromstring('<itemSchema>'+self.fixture[key]+'</itemSchema>')
                for key in ('request_sku_xml','formal_sku_xml')]

    def check(self, request, formal, **kwargs):
        return contract.verify_content_details('submitted_needs_readback',
            contract.field_snapshot(request), contract.field_snapshot(formal), operation='create', **kwargs)

    def test_actual_5998_positive_reordered_rows_generated_ids_optional_fields(self):
        request,formal=self.roots(); result=self.check(request,formal)
        self.assertEqual(result['content_status'],'formal_fields_verified')
        sku=result['sku_verification']; self.assertEqual(sku['status'],'verified')
        self.assertEqual(len(sku['bindings']),22)
        self.assertEqual(sku['bindings']['BQ-W5998-Beige-36'],'109766750118')
        observed=sku['unsubmitted_observations']['BQ-W5998-Beige-36']
        self.assertEqual(set(observed),{'price','skuStock','outerSupplyId'})
        self.assertEqual(request.findall(".//field[@id='skuStock']"),[])
        self.assertEqual(self.check(request,formal,sku_bindings=sku['bindings'])['content_status'],'formal_fields_verified')

    def test_missing_extra_duplicate_sku_rows_fail(self):
        for mode in ('missing','extra','duplicate'):
            with self.subTest(mode=mode):
                request,formal=self.roots(); sku=formal.find('./field'); row=sku.find('./complex-values')
                if mode=='missing': sku.remove(row)
                else:
                    clone=deepcopy(row)
                    if mode=='extra': clone.find("./field[@id='skuOuterId']/value").text='unexpected-code'
                    sku.append(clone)
                self.assertEqual(self.check(request,formal)['content_status'],'content_mismatch_or_noop')

    def test_missing_zero_duplicate_platform_ids_fail(self):
        for mode in ('missing','zero','duplicate'):
            with self.subTest(mode=mode):
                request,formal=self.roots(); rows=formal.find('./field').findall('./complex-values')
                field=rows[0].find("./field[@id='skuId']")
                if mode=='missing': rows[0].remove(field)
                else: field.find('./value').text='0' if mode=='zero' else rows[1].find("./field[@id='skuId']/value").text
                self.assertEqual(self.check(request,formal)['sku_verification']['status'],'mismatch')

    def test_wrong_variant_binding_and_submitted_value_changes_fail(self):
        for mode in ('props','outer','attribute','duplicate-field'):
            with self.subTest(mode=mode):
                request,formal=self.roots(); rows=formal.find('./field').findall('./complex-values')
                if mode=='props':
                    a=rows[0].find("./field[@id='props']"); b=rows[1].find("./field[@id='props']")
                    rows[0].remove(a); rows[1].remove(b);rows[0].append(b);rows[1].append(a)
                elif mode=='outer': rows[0].find("./field[@id='skuOuterId']/value").text='changed-code'
                elif mode=='attribute': rows[0].find("./field[@id='props']/values/value").set('propValueName','wrong-colour')
                else: rows[0].append(deepcopy(rows[0].find("./field[@id='props']")))
                self.assertEqual(self.check(request,formal)['content_status'],'content_mismatch_or_noop')

    def test_submitted_inventory_strict_but_unsubmitted_values_observed(self):
        request,formal=self.roots(); actual=formal.find('./field').find('./complex-values')
        code=actual.find("./field[@id='skuOuterId']/value").text
        actual.find("./field[@id='skuStock']").append(ET.fromstring('<values><value warehouseCode="CN_LOCAL_01" srcValue="0">0</value></values>'))
        self.assertEqual(self.check(request,formal)['content_status'],'formal_fields_verified')
        submitted=next(row for row in request.find('./field').findall('./complex-values')
                       if row.find("./field[@id='skuOuterId']/value").text==code)
        submitted.append(ET.fromstring('<field id="skuStock"><values><value warehouseCode="CN_LOCAL_01" srcValue="999">999</value></values></field>'))
        self.assertEqual(self.check(request,formal)['content_status'],'content_mismatch_or_noop')

    def test_established_id_swaps_fail_and_update_remains_strict(self):
        request,formal=self.roots(); bindings=self.check(request,formal)['sku_verification']['bindings']
        first,second=formal.find('./field').findall('./complex-values')[:2]
        a=first.find("./field[@id='skuId']/value"); b=second.find("./field[@id='skuId']/value")
        a.text,b.text=b.text,a.text
        self.assertEqual(self.check(request,formal,sku_bindings=bindings)['content_status'],'content_mismatch_or_noop')
        self.assertEqual(contract.verify_content('submitted_needs_readback',contract.field_snapshot(request),
            contract.field_snapshot(formal),operation='update'),'content_mismatch_or_noop')
        original=self.roots()[1]
        self.assertEqual(contract.verify_content('submitted_needs_readback',contract.field_snapshot(original),
            contract.field_snapshot(formal),operation='update'),'content_mismatch_or_noop')

    def test_real_verify_cli_positive_and_all_negative_variants_offline(self):
        request,original=self.roots()
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); receipt=tmp/'receipt.json'; formal=tmp/'formal.xml'; evidence=tmp/'evidence.json'
            base={'operation':'create','status':'submitted_needs_readback','product_id':'fixture-target',
                'attempted_at':'2026-10-02T00:00:00+00:00','expected_fields':contract.field_snapshot(request)}
            mutations=['ok','missing','duplicate','props','id','value','bound-id']
            for mutation in mutations:
                readback=deepcopy(original); rows=readback.find('./field').findall('./complex-values')
                record=deepcopy(base)
                if mutation=='missing': readback.find('./field').remove(rows[0])
                if mutation=='duplicate': readback.find('./field').append(deepcopy(rows[0]))
                if mutation=='props': rows[0].find("./field[@id='props']/values/value").text='wrong'
                if mutation=='id': rows[0].find("./field[@id='skuId']/value").text=rows[1].find("./field[@id='skuId']/value").text
                if mutation=='value': rows[0].find("./field[@id='skuOuterId']/value").text='wrong'
                if mutation=='bound-id':
                    record['sku_verification']=self.check(request,original)['sku_verification']
                    rows[0].find("./field[@id='skuId']/value").text='unexpected-new-id'
                receipt.write_text(json.dumps(record),encoding='utf-8')
                formal.write_bytes(ET.tostring(readback))
                evidence.write_text(json.dumps({'product_id':'fixture-target','request_id':self.fixture['formal_request_id'],
                    'acquired_at':'2026-10-02T00:00:01+00:00','schema_file':'formal.xml',
                    'schema_sha256':hashlib.sha256(formal.read_bytes()).hexdigest(),
                    'content_checks':{k:True for k in contract.COMPLETION_CHECKS},
                    'post_publish_score':{'actual_score':5.0,'observed_at':'2026-10-02T00:00:02+00:00',
                        'score_source':'OFFLINE_TEST_GATE_ONLY','diagnostics':{'status':'clear'}}}),encoding='utf-8')
                argv=[str(HERE/'publish_hot_rank_hr_a_batch.py'),'--mode','verify','--product-id','fixture-target',
                      '--receipt',str(receipt),'--formal-readback',str(evidence),'--verification-receipt',str(tmp/(mutation+'.verification.json'))]
                out=io.StringIO()
                with self.subTest(mutation=mutation),patch.object(sys,'argv',argv),patch.object(self.pub,'load_client') as loader,contextlib.redirect_stdout(out):
                    self.assertEqual(self.pub.main(),0 if mutation=='ok' else 2); loader.assert_not_called()
                result=json.loads(out.getvalue())
                self.assertEqual(result['content_status'],'formal_fields_verified' if mutation=='ok' else 'content_mismatch_or_noop')
                self.assertEqual(result['post_publish_acceptance']['overall_status'],'PASS' if mutation=='ok' else 'PENDING_CONTENT')
                if mutation=='ok':self.assertEqual(len(result['sku_verification']['bindings']),22)

if __name__=='__main__':unittest.main()
