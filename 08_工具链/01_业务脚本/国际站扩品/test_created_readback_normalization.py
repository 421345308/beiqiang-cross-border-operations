from pathlib import Path
from copy import deepcopy
import json, unittest
import schema_publish_contract as c
class CreatedReadbackNormalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=json.loads((Path(c.__file__).parent/'schema_contract_fixtures/create_readback_normalization_20261004.json').read_text(encoding='utf-8'))['cases']
    def field(self,node,fid):
        if node[0]=='field' and dict(node[1]).get('id')==fid:return node
        for child in node[3]:
            value=self.field(child,fid)
            if value is not None:return value
        return None
    def value(self,node):
        if node[0]=='value':return node
        for child in node[3]:
            value=self.value(child)
            if value is not None:return value
        return None
    def test_two_real_creates_verify_normalized_fields_and_sku_bindings(self):
        for case in self.cases:
            with self.subTest(case=case['name']):
                result=c.verify_content_details('submitted_needs_readback',case['expected_fields'],case['formal_fields'],operation='create',versioned_content={'status':'product_summary_verified'})
                bad=[k for k,v in case['expected_fields'].items() if k not in ['sku','productKeywords'] and not c.created_field_equivalent(k,v,case['formal_fields'][k])]
                self.assertEqual(result['content_status'],'formal_fields_verified',bad)
                self.assertEqual(result['sku_verification']['status'],'verified')
    def test_real_changed_values_and_hero_slot_swaps_still_fail(self):
        case=self.cases[0];expected=case['expected_fields'];formal=case['formal_fields']
        for fid,nested,text in [('minOrderQuantity',None,'3.0'),('ladderPrice','price','19.04'),('pkgMeasure','length','35')]:
            with self.subTest(field=fid):
                actual=deepcopy(formal[fid]);target=self.field(actual,nested) if nested else actual;self.value(target)[2]=text
                self.assertFalse(c.created_field_equivalent(fid,expected[fid],actual))
        actual=deepcopy(formal['scImages']);first=self.value(self.field(actual,'scImages_0'));second=self.value(self.field(actual,'scImages_1'));first[2],second[2]=second[2],first[2]
        self.assertFalse(c.created_field_equivalent('scImages',expected['scImages'],actual))
        actual=deepcopy(formal['icbuCatProp']);value=self.value(self.field(actual,'p-191290428'));attrs=dict(value[1]);attrs['inputValue']='Rubber';value[1]=list(attrs.items())
        self.assertFalse(c.created_field_equivalent('icbuCatProp',expected['icbuCatProp'],actual))
    def test_gallery_duplicates_different_assets_and_wrong_hosts_fail(self):
        case=self.cases[0];expected=case['expected_fields'];formal=case['formal_fields']
        for kind in ['duplicate','asset','host']:
            actual=deepcopy(formal['detailImage']);images=self.field(actual,'images')
            if kind=='duplicate':images[3].append(deepcopy(images[3][0]))
            else:
                value=self.value(images)
                if kind=='asset':value[2]=value[2].replace('/kf/H','/kf/HOTHER')
                else:value[2]=value[2].replace('sc04.alicdn.com','example.com')
            with self.subTest(change=kind):self.assertFalse(c.created_field_equivalent('detailImage',expected['detailImage'],actual))
    def test_update_comparison_stays_strict_and_keyword_only_noop_stays_failed(self):
        case=self.cases[0]
        result=c.verify_content_details('submitted_needs_readback',{'minOrderQuantity':case['expected_fields']['minOrderQuantity']},{'minOrderQuantity':case['formal_fields']['minOrderQuantity']},operation='update')
        self.assertEqual(result['content_status'],'content_mismatch_or_noop')
        result=c.verify_content_details('submitted_needs_readback',{'productKeywords':case['expected_fields']['productKeywords']},{'productKeywords':case['formal_fields']['productKeywords']},operation='create',versioned_content={'status':'product_summary_verified'})
        self.assertEqual(result['content_status'],'content_mismatch_or_noop')
if __name__=='__main__':unittest.main()
