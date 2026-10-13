"""Offline exact-ID replacement transitions; synthetic acceptance maps, no writes."""
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib,json,tempfile,unittest
import schema_publish_contract as c
import test_schema_differentiation as d

class ReplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d.DifferentiationTests.setUpClass()
        cls.h=d.DifferentiationTests()
        cls.pub=d.DifferentiationTests.pub

    def inputs(self):
        candidate=self.h.record();old=deepcopy(candidate)
        listing=self.h.prepared(candidate,[])
        payload=ET.fromstring(listing['xml'])
        xml=ET.tostring(payload,encoding='unicode')
        ids=[f.get('id') for f in payload.findall('./field')]
        replacement={'replacement_source_product_id':old['product_id'],
          'authorization_evidence':['OFFLINE_EXPLICIT_REPLACEMENT_AUTHORIZATION'],
          'accepted_payload_xml':xml,'acceptance_record_id_bound':True,
          'acceptance_map':{'product_id':old['product_id'],
            'accepted_payload_sha256':hashlib.sha256(xml.encode()).hexdigest(),
            'accepted_field_ids':ids,'verified_field_ids':ids,
            'evidence':['OFFLINE_SYNTHETIC_COMPLETE_ACCEPTANCE_RECORD']}}
        image=b'OFFLINE_SYNTHETIC_IMAGE_BYTES'
        digest=hashlib.sha256(xml.encode()).hexdigest()
        record={'product_id':old['product_id'],'accepted_payload_sha256':digest,
          'formal_readback':{'product_id':old['product_id'],'xml':xml,'schema_sha256':digest,
            'request_id':'OFFLINE_FORMAL_GET','acquired_at':'2026-10-02T00:00:01+00:00'},
          'media_acceptance':{'product_id':old['product_id'],'accepted_payload_sha256':digest,
            'status':'verified','verified_field_ids':['scImages'],
            'checks':[{'field_id':'scImages','url':candidate['hero_url'],'content_match':True,
              'review_evidence':['OFFLINE_SYNTHETIC_VISUAL_REVIEW'],
              'source_bytes':image,'source_sha256':hashlib.sha256(image).hexdigest(),
              'actual_bytes':image,'actual_sha256':hashlib.sha256(image).hexdigest()}]}}
        replacement['acceptance_records']=[record]
        return candidate,old,listing,payload,replacement

    def reviewed(self,candidate,old,listing,payload,replacement,catalog=None):
        report=c.prepare_differentiation_review(payload,{'candidate':candidate,
          'catalog':catalog if catalog is not None else [old],'replacement':replacement},operation='create')
        listing['differentiation_review']=report
        return report

    def test_exact_old_allows_transition_preserves_model_and_old_pending(self):
        a,b,listing,payload,r=self.inputs()
        self.assertEqual(c.check_listing_differentiation(a,[b])['status'],'BLOCKED_DUPLICATE')
        report=self.reviewed(a,b,listing,payload,r)
        self.assertEqual(report['status'],'PASS')
        t=report['replacement_transition']
        self.assertEqual(t['replacement_source_product_id'],b['product_id'])
        self.assertEqual(t['old_product_disposition'],'NOT_OFFLINED_PENDING_NEW_ACCEPTANCE')
        self.assertEqual(t['finish_requirements']['target_score'],5.0)
        self.assertTrue(t['finish_requirements']['public_qa'])
        self.assertEqual(report['payload_binding']['model_number'],a['model_number'])
        c.require_differentiation_review(payload,listing,operation='create')

    def test_only_selected_old_exempt_other_duplicate_still_blocks(self):
        a,b,listing,payload,r=self.inputs()
        report=self.reviewed(a,b,listing,payload,r,[b,self.h.record(old=True)])
        self.assertEqual(report['status'],'BLOCKED_DUPLICATE')
        self.assertEqual([x['product_id'] for x in report['conflicts']],['1601969526580'])
        missing=self.reviewed(a,b,listing,payload,r,[])
        self.assertEqual(missing['status'],'UNVERIFIED')
        self.assertIsNone(missing['replacement_transition'])

    def test_complete_dynamic_sku_mapping_only_inventory_and_old_ids_removed(self):
        a,b,listing,payload,r=self.inputs()
        source=deepcopy(payload)
        sku=ET.SubElement(source,'field',id='sku',type='multiComplex')
        for i in range(14):
            row=ET.SubElement(sku,'complex-values')
            props=ET.SubElement(row,'field',id='props');values=ET.SubElement(props,'values');ET.SubElement(values,'value',propName='Size').text=str(36+i)
            for key,value in [('skuOuterId','OFFLINE-'+str(i)),('skuPrice',str(20+i)),('skuStock','999'),('skuId',str(100+i))]:
                f=ET.SubElement(row,'field',id=key);ET.SubElement(f,'value').text=value
        clean=c.values_only(source,operation='create',field_ids={f.get('id') for f in source.findall('./field')})
        for parent in list(clean.iter()):
            for child in list(parent):
                if child.tag=='field' and child.get('id')=='skuStock':parent.remove(child)
        xml=ET.tostring(source,encoding='unicode');ids=[f.get('id') for f in source.findall('./field')]
        r.update(accepted_payload_xml=xml)
        r['acceptance_map'].update(accepted_payload_sha256=hashlib.sha256(xml.encode()).hexdigest(),accepted_field_ids=ids,verified_field_ids=ids)
        rec=r['acceptance_records'][0];rec['accepted_payload_sha256']=r['acceptance_map']['accepted_payload_sha256'];rec['media_acceptance']['accepted_payload_sha256']=rec['accepted_payload_sha256'];rec['formal_readback'].update(xml=xml,schema_sha256=rec['accepted_payload_sha256'])
        self.assertEqual(c.validate_replacement_mapping(clean,r)['status'],'AUTHORIZED_TRANSITION_OLD_RETAINED')
        self.assertFalse(clean.findall(".//field[@id='skuStock']"))
        self.assertFalse(clean.findall(".//field[@id='skuId']"))
        changed=deepcopy(clean);changed.find(".//field[@id='skuPrice']/value").text='1'
        with self.assertRaisesRegex(ValueError,'differs from complete'):c.validate_replacement_mapping(changed,r)
        ET.SubElement(clean.find('./field[@id="sku"]/complex-values'),'field',id='skuStock')
        with self.assertRaisesRegex(ValueError,'omitted SKU inventory'):c.validate_replacement_mapping(clean,r)

    def test_missing_authorization_mapping_or_old_identity_never_exempts(self):
        a,b,listing,payload,r=self.inputs()
        for key in ['authorization_evidence','acceptance_records']:
            bad=deepcopy(r);bad.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):c.validate_replacement_mapping(payload,bad)
        bad=deepcopy(r);bad['acceptance_map']['verified_field_ids']=[]
        with self.assertRaisesRegex(ValueError,'every accepted payload field'):c.validate_replacement_mapping(payload,bad)
        bad=deepcopy(r);bad['replacement_source_product_id']='999';bad['acceptance_map']['product_id']='999'
        with self.assertRaisesRegex(ValueError,'complete hash-bound'):self.reviewed(a,b,listing,payload,bad)

    def test_actual_submit_receipts_keep_transition_no_retry_and_late_change_blocks(self):
        a,b,listing,payload,r=self.inputs();self.reviewed(a,b,listing,payload,r)
        class MemoryClient:
            calls=0
            fail=False
            def top_call(self,*args):
                self.calls+=1
                if self.fail:raise TimeoutError('OFFLINE timeout')
                return {'biz_success':True,'product_id':123}
            def api_error(self,*args):return None
        client=MemoryClient()
        receipt=self.pub.api_submit(client,{},listing,False)
        self.assertEqual(receipt['replacement_transition']['old_product_disposition'],'NOT_OFFLINED_PENDING_NEW_ACCEPTANCE')
        self.assertEqual(receipt['product_id'],'123')
        client.fail=True;receipt=self.pub.api_submit(client,{},listing,False)
        self.assertEqual(receipt['status'],'write_outcome_unknown');self.assertEqual(client.calls,2)
        self.assertIsNotNone(receipt['replacement_transition'])
        payload.find("./field[@id='productTitle']/value").text='changed'
        listing['xml']=ET.tostring(payload,encoding='unicode');listing['expected_fields']=c.field_snapshot(payload)
        with self.assertRaisesRegex(ValueError,'actual model/hero/title'):self.pub.api_submit(client,{},listing,False)
        self.assertEqual(client.calls,2)

    def test_actual_manifest_loader_hash_binds_files_and_explicit_old_id(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path=self.h.manifest(tmp)
            manifest=json.loads(path.read_text());context=json.loads((tmp/'review.json').read_text())
            a,b,listing,payload,r=self.inputs()
            (tmp/'accepted.xml').write_text(r.pop('accepted_payload_xml'),encoding='utf-8')
            rec=deepcopy(r['acceptance_records'][0]);formal=rec['formal_readback'];(tmp/'formal.xml').write_text(formal.pop('xml'),encoding='utf-8');formal['schema_file']='formal.xml'
            for check in rec['media_acceptance']['checks']:
                for prefix in ('source','actual'):
                    (tmp/(prefix+'.jpg')).write_bytes(check.pop(prefix+'_bytes'));check[prefix+'_file']=prefix+'.jpg'
            (tmp/'acceptance.json').write_text(json.dumps({'replacement_content_acceptance':rec}))
            r.pop('acceptance_record_id_bound');r.pop('acceptance_records');r['acceptance_map']['evidence']=['acceptance.json']
            context['replacement']=r
            for name,kind in [('accepted.xml','replacement_accepted_payload'),('acceptance.json','replacement_acceptance_record')]:
                context['evidence_files'].append({'path':name,'kind':kind,'sha256':hashlib.sha256((tmp/name).read_bytes()).hexdigest()})
            (tmp/'review.json').write_text(json.dumps(context),encoding='utf-8')
            manifest.update(replacement_source_product_id=b['product_id'],differentiation_review_sha256=hashlib.sha256((tmp/'review.json').read_bytes()).hexdigest())
            path.write_text(json.dumps(manifest))
            loaded=self.pub.load_submission_manifest(path,'create',None)
            # Existing legacy266 still blocks: this is deliberately no global bypass.
            report=loaded['differentiation_review'];self.assertEqual(report['status'],'BLOCKED_DUPLICATE')
            self.assertEqual(report['replacement_transition']['replacement_source_product_id'],b['product_id'])
            manifest.pop('replacement_source_product_id');path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'explicit matching'):self.pub.load_submission_manifest(path,'create',None)
            manifest['replacement_source_product_id']=b['product_id'];path.write_text(json.dumps(manifest))
            (tmp/'acceptance.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'evidence hash differs'):self.pub.load_submission_manifest(path,'create',None)

    def test_success_only_or_partial_acceptance_records_are_rejected(self):
        a,b,listing,payload,r=self.inputs()
        for mode in ('success_only','wrong_hash','partial_formal','partial_media','wrong_pixels','wrong_old'):
            bad=deepcopy(r);record=bad['acceptance_records'][0]
            if mode=='success_only':bad['acceptance_records']=[{'biz_success':True,'product_id':b['product_id']}]
            elif mode=='wrong_hash':record['accepted_payload_sha256']='wrong'
            elif mode=='partial_formal':
                xml='<itemSchema/>';record['formal_readback'].update(xml=xml,schema_sha256=hashlib.sha256(xml.encode()).hexdigest())
            elif mode=='partial_media':record['media_acceptance']['checks']=[]
            elif mode=='wrong_pixels':record['media_acceptance']['checks'][0]['actual_bytes']=b'CHANGED'
            elif mode=='wrong_old':record['formal_readback']['product_id']='999'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'complete hash-bound'):c.validate_replacement_mapping(payload,bad)

    def test_real_manifest_success_receipt_partial_formal_media_or_wrong_hash_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp=Path(folder);path=self.h.manifest(tmp);manifest=json.loads(path.read_text());context=json.loads((tmp/'review.json').read_text())
            a,b,listing,payload,r=self.inputs()
            (tmp/'accepted.xml').write_text(r['accepted_payload_xml'],encoding='utf-8')
            rec=deepcopy(r['acceptance_records'][0]);formal=rec['formal_readback'];(tmp/'formal.xml').write_text(formal.pop('xml'),encoding='utf-8');formal['schema_file']='formal.xml'
            for check in rec['media_acceptance']['checks']:
                for prefix in ('source','actual'):
                    (tmp/(prefix+'.jpg')).write_bytes(check.pop(prefix+'_bytes'));check[prefix+'_file']=prefix+'.jpg'
            r.pop('accepted_payload_xml');r.pop('acceptance_records');r.pop('acceptance_record_id_bound');r['acceptance_map']['evidence']=['acceptance.json'];context['replacement']=r
            for mode in ('complete','success_only','partial_formal','partial_media','wrong_hash','wrong_media_file'):
                record=deepcopy(rec)
                if mode=='partial_formal':
                    xml='<itemSchema/>';(tmp/'formal.xml').write_text(xml,encoding='utf-8');record['formal_readback']['schema_sha256']=hashlib.sha256(xml.encode()).hexdigest()
                else:(tmp/'formal.xml').write_text(listing['xml'],encoding='utf-8')
                if mode=='partial_media':record['media_acceptance']['checks']=[]
                if mode=='wrong_hash':record['accepted_payload_sha256']='wrong'
                if mode=='wrong_media_file':record['media_acceptance']['checks'][0]['actual_sha256']='wrong'
                body={'biz_success':True,'product_id':b['product_id']} if mode=='success_only' else {'replacement_content_acceptance':record}
                (tmp/'acceptance.json').write_text(json.dumps(body))
                context['evidence_files']=[x for x in context['evidence_files'] if not x.get('kind','').startswith('replacement_')]
                for name,kind in [('accepted.xml','replacement_accepted_payload'),('acceptance.json','replacement_acceptance_record')]:
                    context['evidence_files'].append({'path':name,'kind':kind,'sha256':hashlib.sha256((tmp/name).read_bytes()).hexdigest()})
                (tmp/'review.json').write_text(json.dumps(context),encoding='utf-8');manifest.update(replacement_source_product_id=b['product_id'],differentiation_review_sha256=hashlib.sha256((tmp/'review.json').read_bytes()).hexdigest());path.write_text(json.dumps(manifest))
                with self.subTest(mode=mode):
                    if mode=='complete':self.assertEqual(self.pub.load_submission_manifest(path,'create',None)['differentiation_review']['replacement_transition']['acceptance_validation']['status'],'verified')
                    else:
                        with self.assertRaises(ValueError):self.pub.load_submission_manifest(path,'create',None)

if __name__=='__main__':unittest.main()
