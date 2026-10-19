"""Offline checks for intentional source-range removal versus accidental SKU loss."""
import unittest
from copy import deepcopy
from xml.etree import ElementTree as E
from schema_publish_contract import prepare_scoped_listing,values_only

class RemovalTests(unittest.TestCase):
    def setUp(self):
        self.current=E.fromstring('<itemSchema><field id="sku" type="multiComplex"/></itemSchema>')
        for i in ('101','102','103'):
            row=E.SubElement(self.current[0],'complex-values')
            E.SubElement(E.SubElement(row,'field',{'id':'skuId'}),'value').text=i
            E.SubElement(E.SubElement(row,'field',{'id':'props'}),'values').append(E.fromstring('<value propId="1" propValueId="'+i+'">1:'+i+'</value>'))
        self.patch=values_only(self.current,operation='update',field_ids=['sku']);self.patch[0].remove(self.patch[0][1])
        self.review={'ids':['102'],'reason':'Exact source excludes this size','source_evidence':['exact-source.json']}
    def prepare(self,review=None):
        return prepare_scoped_listing(self.current,self.patch,operation='update',category_id=1,target_product_id='123',field_ids=['sku'],reviewed_sku_removals=review)
    def test_default_still_rejects_silent_removal(self):
        with self.assertRaises(ValueError):self.prepare()
    def test_explicit_subset_is_accepted(self):
        result=self.prepare(self.review)
        self.assertEqual([x.text for x in E.fromstring(result['xml']).findall('.//field[@id="skuId"]/value')],['101','103'])
    def test_unknown_id_and_missing_evidence_rejected(self):
        for review in ({**self.review,'ids':['999']},{**self.review,'source_evidence':[]},{**self.review,'ids':['101','102','103']}):
            with self.assertRaises(ValueError):self.prepare(review)
    def test_rebinding_or_unbound_addition_rejected(self):
        original=deepcopy(self.patch)
        self.patch[0][0].find('./field[@id="props"]/values/value').text='1:999'
        with self.assertRaises(ValueError):self.prepare(self.review)
        self.patch=original;self.patch[0].append(E.fromstring('<complex-values><field id="skuId"/><field id="props"><values/></field></complex-values>'))
        with self.assertRaises(ValueError):self.prepare(self.review)

if __name__=='__main__':unittest.main()
