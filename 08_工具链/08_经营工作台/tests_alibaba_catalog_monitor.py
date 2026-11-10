import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from alibaba_catalog_monitor import CatalogMonitor, CHANNEL


class CatalogMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.state=self.root/'private'
        self.now=datetime(2026,11,10,12,tzinfo=timezone.utc)
        self.snapshot=self.root/'baseline.json'
        self.snapshot.write_text(json.dumps({'complete':True,'collected_at_utc':self.now.isoformat(),
            'platform_total':2,'pages':1,'records':[{'platform_id':'101','status':'approved','display':'Y'},
                                                    {'platform_id':'102','status':'approved','display':'N'}]}),encoding='utf8')
        self.local=self.root/CHANNEL;self.local.parent.mkdir(parents=True)
        self.local.write_text(json.dumps({'listings':[
            {'id':'101','product_id':'BQ001','current_platform_fields':{'model':'BQ001','status':'approved','display':'Y'}},
            {'id':'102','product_id':'BQ002','current_platform_fields':{'model':'BQ002','status':'approved','display':'N'}},
            {'id':'999','current_platform_fields':{'status':'approved','display':'Y'}}]}),encoding='utf8')
        self.calls=[];self.pages={}
        def fetch(command,**kwargs):
            self.calls.append((command,kwargs['page']));return self.pages[kwargs['page']]
        self.monitor=CatalogMonitor(self.root,self.state,fetch=fetch,clock=lambda:self.now)

    @staticmethod
    def page(number,total,rows,more=False):
        return {'ok':True,'data':rows,'pagination':{'page':number,'total':total,'hasMore':more,'nextPage':number+1 if more else None}}

    def test_seed_reuses_complete_real_shape_without_fetch_and_keeps_history(self):
        result=self.monitor.seed(self.snapshot)
        self.assertEqual(result['total'],2);self.assertEqual(result['comparison']['local_not_seen'],1)
        self.assertEqual(result['review_required'],0);self.assertEqual(self.calls,[])
        self.assertEqual(self.monitor.seed(self.snapshot)['state'],'already_present')
        self.assertEqual(self.monitor.collect()['state'],'ready');self.assertEqual(self.calls,[])

    def test_incremental_comparison_keeps_exact_id_and_no_auto_write(self):
        self.monitor.seed(self.snapshot);before=self.local.read_bytes();self.now+=timedelta(hours=6,minutes=1)
        self.pages={1:self.page(1,2,[{'id':'101','status':'tbd','display':'N'}],True),
                    2:self.page(2,2,[{'id':'103','status':None,'display':'Y'}])}
        result=self.monitor.collect()
        self.assertEqual(result['state'],'ready');self.assertEqual(result['review_required'],1)
        self.assertEqual(result['unknown_state'],1)
        self.assertEqual({row['id'] for row in result['review_items']},{'101','103'})
        self.assertEqual(result['changes']['added'],['103']);self.assertEqual(result['changes']['not_seen'],['102'])
        self.assertEqual(result['changes']['status_or_display'][0]['id'],'101')
        self.assertEqual(result['comparison']['different'][0]['product_id'],'BQ001')
        self.assertEqual(result['comparison']['local_not_seen'],2)
        self.assertEqual(self.calls,[('products',1),('products',2)])
        self.assertEqual(self.local.read_bytes(),before)

    def test_partial_failure_preserves_last_success_and_does_not_report_empty(self):
        self.monitor.seed(self.snapshot);self.now+=timedelta(hours=6,minutes=1)
        self.pages={1:self.page(1,2,[{'id':'101','status':'approved','display':'Y'}],True),
                    2:{'ok':False,'error':{'code':'CLIENT_FAILURE'}}}
        result=self.monitor.collect()
        self.assertEqual(result['state'],'error');self.assertEqual(result['error']['code'],'CLIENT_FAILURE')
        self.assertEqual(result['total'],2);self.assertEqual(result['last_success_at'],self.snapshot_time())
        self.assertEqual(self.monitor.collect()['state'],'error');self.assertEqual(len(self.calls),2)
        self.now+=timedelta(hours=1,minutes=1);self.pages[2]=self.page(2,2,[{'id':'102','status':'approved','display':'N'}])
        self.assertEqual(self.monitor.collect()['state'],'ready')

    def test_initial_failure_and_duplicate_ids_are_not_complete_snapshots(self):
        self.pages={1:self.page(1,2,[{'id':'101','status':'approved','display':'Y'}],True),
                    2:self.page(2,2,[{'id':'101','status':'approved','display':'Y'}])}
        result=self.monitor.collect();self.assertEqual(result['state'],'error')
        self.assertEqual(result['error']['code'],'DUPLICATE_ID');self.assertIsNone(result['total'])
        self.assertIsNone(result['comparison'])

    def test_ambiguous_local_listing_id_is_never_silently_matched(self):
        data=json.loads(self.local.read_text(encoding='utf8'));data['listings'].append(data['listings'][0])
        self.local.write_text(json.dumps(data),encoding='utf8')
        result=self.monitor.seed(self.snapshot)
        self.assertEqual(result['comparison']['ambiguous_ids'],1)
        self.assertEqual(result['comparison']['matched'],1)

    def snapshot_time(self): return '2026-11-10T12:00:00+00:00'


if __name__=='__main__':unittest.main()
