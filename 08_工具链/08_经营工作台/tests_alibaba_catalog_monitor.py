import json
import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from alibaba_catalog_monitor import CatalogMonitor, CHANNEL, main


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
        self.calls=[];self.page_sizes=[];self.pages={}
        def fetch(command,**kwargs):
            self.calls.append((command,kwargs['page']));self.page_sizes.append(kwargs['page_size']);return self.pages[kwargs['page']]
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
        self.assertEqual(self.page_sizes,[30,30])
        self.assertEqual(self.local.read_bytes(),before)

    def test_partial_failure_preserves_last_success_and_does_not_report_empty(self):
        self.monitor.seed(self.snapshot);self.now+=timedelta(hours=6,minutes=1)
        self.pages={1:self.page(1,2,[{'id':'101','status':'approved','display':'Y'}],True),
                    2:{'ok':False,'error':{'code':'CLIENT_FAILURE'}}}
        result=self.monitor.collect()
        self.assertEqual(result['state'],'error');self.assertEqual(result['error']['code'],'CLIENT_FAILURE')
        self.assertEqual(result['total'],2);self.assertEqual(result['last_success_at'],self.snapshot_time())
        self.assertEqual(result['audit'][-1]['outcome'],'error')
        self.assertEqual(result['audit'][-1]['error_code'],'CLIENT_FAILURE')
        self.assertEqual(result['audit'][-1]['pages_attempted'],2)
        self.assertEqual(self.monitor.collect()['state'],'error');self.assertEqual(len(self.calls),2)
        self.assertEqual(len(self.monitor.status()['audit']),1)
        self.now+=timedelta(hours=1,minutes=1);self.pages[2]=self.page(2,2,[{'id':'102','status':'approved','display':'N'}])
        recovered=self.monitor.collect();self.assertEqual(recovered['state'],'ready')
        self.assertEqual([item['outcome'] for item in recovered['audit']],['error','ready'])
        self.assertEqual(recovered['last_failure']['error_code'],'CLIENT_FAILURE')
        self.assertEqual(recovered['audit'][-1]['records_seen'],2)

    def test_final_short_page_stops_when_all_unique_ids_are_collected(self):
        # The official API reports the final page's returned size as page_size.
        # Its derived hasMore can therefore still be true on a complete page.
        self.pages={1:self.page(1,3,[{'id':'101','status':'approved','display':'Y'},
                                    {'id':'102','status':'approved','display':'N'}],True),
                    2:self.page(2,3,[{'id':'103','status':'tbd','display':'N'}],True)}
        result=self.monitor.collect()
        self.assertEqual(result['state'],'ready');self.assertEqual(result['total'],3)
        self.assertEqual(result['pages'],2);self.assertEqual(self.calls,[('products',1),('products',2)])

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

    def test_running_local_collector_excludes_an_overlapping_attempt(self):
        self.monitor.seed(self.snapshot)
        with self.monitor._locked() as acquired:
            self.assertTrue(acquired)
            other=CatalogMonitor(self.root,self.state,fetch=self.monitor.fetch,clock=lambda:self.now)
            self.assertEqual(other.collect(force=True)['state'],'busy')
        self.assertEqual(self.calls,[])

    def test_local_lock_excludes_a_separate_process(self):
        script=('import json,sys; from alibaba_catalog_monitor import CatalogMonitor; '
                'm=CatalogMonitor(sys.argv[1],sys.argv[2],fetch=lambda *a,**k: 1/0); '
                'print(json.dumps(m.collect(force=True)))')
        with self.monitor._locked() as acquired:
            self.assertTrue(acquired)
            child=subprocess.run([sys.executable,'-c',script,str(self.root),str(self.state)],
                                 capture_output=True,text=True,encoding='utf-8',timeout=10)
        self.assertEqual(child.returncode,0,child.stderr)
        self.assertEqual(json.loads(child.stdout)['state'],'busy')
        self.assertEqual(self.calls,[])

    def test_process_interruption_keeps_snapshot_and_records_unconfirmed_attempt(self):
        self.monitor.seed(self.snapshot);self.now+=timedelta(hours=6,minutes=1)
        self.monitor.fetch=lambda *args,**kwargs: (_ for _ in ()).throw(SystemExit('simulated interruption'))
        with self.assertRaises(SystemExit):self.monitor.collect()
        interrupted=self.monitor.status()
        self.assertEqual(interrupted['total'],2)
        self.assertEqual(interrupted['last_success_at'],self.snapshot_time())
        self.assertEqual(interrupted['audit'][-1]['outcome'],'started')
        self.assertEqual(interrupted['unconfirmed_attempts'],1)
        self.monitor.fetch=lambda *args,**kwargs:self.page(1,2,[
            {'id':'101','status':'approved','display':'Y'},{'id':'102','status':'approved','display':'N'}])
        recovered=self.monitor.collect()
        self.assertEqual([row['outcome'] for row in recovered['audit']],['started','ready'])
        self.assertEqual(recovered['unconfirmed_attempts'],1)

    def test_client_initialization_failure_is_audited_and_preserves_snapshot(self):
        self.monitor.seed(self.snapshot);self.now+=timedelta(hours=6,minutes=1)
        self.monitor.fetch=None
        with patch('alibaba_catalog_monitor.adapter.ExistingClient',side_effect=RuntimeError('private detail')):
            result=self.monitor.collect()
        self.assertEqual(result['state'],'error');self.assertEqual(result['total'],2)
        self.assertEqual(result['last_success_at'],self.snapshot_time())
        self.assertEqual(result['audit'][-1]['outcome'],'error')
        self.assertEqual(result['audit'][-1]['error_code'],'READ_FAILED')
        self.assertNotIn('private detail',json.dumps(result['audit']))

    def test_audit_is_bounded_and_does_not_expose_unexpected_fields(self):
        self.monitor.seed(self.snapshot)
        previous=self.monitor._read()
        previous['audit']=[{'started_at':self.now.isoformat(),'finished_at':self.now.isoformat(),
                            'outcome':'ready','mode':'due','pages_attempted':1,'records_seen':2,
                            'expected_total':2,'unexpected_secret':'must-not-be-returned'} for _ in range(70)]
        self.monitor._write(previous)
        self.pages={1:self.page(1,2,[{'id':'101','status':'approved','display':'Y'},
                                     {'id':'102','status':'approved','display':'N'}])}
        result=self.monitor.collect(force=True)
        self.assertEqual(len(result['audit']),64)
        self.assertNotIn('unexpected_secret',json.dumps(result['audit']))
        self.assertEqual(result['audit'][-1]['mode'],'forced')

    def test_status_cli_never_collects_or_changes_the_snapshot(self):
        state=self.root/'08_工具链/08_经营工作台/.local'
        monitor=CatalogMonitor(self.root,state,fetch=self.monitor.fetch,clock=lambda:self.now)
        monitor.seed(self.snapshot);before=monitor.path.read_bytes();out=io.StringIO()
        with patch.object(CatalogMonitor,'collect',side_effect=AssertionError('must not collect')),redirect_stdout(out):
            code=main(['--root',str(self.root),'--status'])
        self.assertEqual(code,0);self.assertEqual(json.loads(out.getvalue())['total'],2)
        self.assertEqual(monitor.path.read_bytes(),before);self.assertEqual(self.calls,[])

    def snapshot_time(self): return '2026-11-10T12:00:00+00:00'


if __name__=='__main__':unittest.main()
