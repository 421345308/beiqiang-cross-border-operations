import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from competitor_workspace import CATALOG, list_competitors
from customer_workspace import CustomerWorkspace

class CompetitorWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);path=root/CATALOG;path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'competitors':[
            {'competitor_id':'EX001','company_en':'Shoe Company','store_url':'https://shoe.en.alibaba.com/',
             'product_direction':'casual shoes','store_verification':{'status':'verified','source_url':'https://shoe.en.alibaba.com/','checked_date':'2026-11-02'},
             'sales_observation':{'sold':224,'note':'单款展示，周期不明','source_url':'https://www.alibaba.com/picks/shoes.html'}},
            {'competitor_id':'EX002','company_en':'Only a Website','store_url':'','store_verification':{'status':'not_found','note':'仅找到官网'}},
            {'competitor_id':'EX003','company_en':'Misleading Domain','store_url':'https://alibaba.com.evil.test/',
             'store_verification':{'status':'verified','source_url':'https://www.alibaba.com/'}}
        ]}),encoding='utf8')
        app=SimpleNamespace(root=root,db=sqlite3.connect(':memory:'),lock=threading.RLock())
        self.addCleanup(app.db.close);self.work=CustomerWorkspace(app);app.customer_workspace=self.work;self.app=app

    def test_only_verified_official_shop_is_shown_and_buyer_link_is_private(self):
        buyer=self.work.create_discovery({'kind':'candidate','company':'Buyer One','related_competitors':['EX001'],
                                          'evidence':[{'text':'用户登记的查询记录'}]})
        result=list_competitors(self.app)
        self.assertEqual([x['company'] for x in result['items']],['Shoe Company'])
        self.assertEqual(result['items'][0]['buyers'],[{'id':buyer['id'],'company':'Buyer One'}])
        self.assertEqual(result['items'][0]['sales']['sold'],224)
        self.assertEqual(len(result['excluded']),2)
        self.assertNotIn('Buyer One',(self.app.root/CATALOG).read_text(encoding='utf8'))
        self.assertFalse(buyer['ready_for_customer'])

    def test_relations_validate_and_preserve_existing_candidate(self):
        buyer=self.work.create_discovery({'kind':'candidate','company':'Existing Buyer'})
        updated=self.work.update_discovery(buyer['id'],{'related_competitors':['EX001','EX001']})
        self.assertEqual(updated['related_competitors'],['EX001'])
        with self.assertRaises(ValueError):self.work.update_discovery(buyer['id'],{'related_competitors':['../bad']})
        self.assertEqual(self.work.get_discovery(buyer['id'])['related_competitors'],['EX001'])

if __name__=='__main__':unittest.main()
