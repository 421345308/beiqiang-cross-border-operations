import tempfile
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from channel_overview import ChannelOverview, REPORT

class OverviewTest(unittest.TestCase):
    def test_exact_listing_join_history_priority_and_nulls(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/REPORT;path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'summary':{'period':'2026-10-11~2026-10-17'},'products':[
                {'id':'1','model':'BQ001','current_action':'样本较少，补需求与竞品依据'},
                {'id':'2','model':'BQ001','current_action':'已有咨询，改善有效采购承接','week41':{'inquiries':0}},
                {'id':'3','current_action':'换款与统计窗口重叠，先按新鞋核对'}]}),encoding='utf8')
            class Business:
                def list_objects(self,kind):
                    return [{'id':'product:BQ001','channel_listings':[{'id':'2'},{'id':'3'}]},
                            {'id':'product:BQ002','channel_listings':[{'id':'3'}]}]
            result=ChannelOverview(SimpleNamespace(root=Path(root),business=Business()),None).product_analysis()
            self.assertEqual(result['period'],'2026-10-11~2026-10-17')
            self.assertEqual(result['items'][0]['listing_id'],'2')
            rows={row['listing_id']:row for row in result['items']}
            self.assertEqual(rows['2']['object_id'],'product:BQ001')
            self.assertEqual(rows['2']['metrics']['inquiries'],0)
            self.assertIsNone(rows['1']['metrics']['inquiries'])
            self.assertEqual(rows['1']['association'],'unmatched')
            self.assertIsNone(rows['3']['object_id'])
            self.assertEqual(rows['3']['association'],'ambiguous')

    def test_missing_or_invalid_analysis_is_unavailable(self):
        with tempfile.TemporaryDirectory() as root:
            overview=ChannelOverview(SimpleNamespace(root=Path(root)),None)
            self.assertFalse(overview.product_analysis()['available'])
            path=Path(root)/REPORT;path.parent.mkdir(parents=True);path.write_text('{',encoding='utf8')
            self.assertFalse(overview.product_analysis()['available'])

    def test_snapshot_never_refreshes_and_keeps_historical_scope(self):
        class Website:
            def status(self, start_refresh=True):
                assert start_refresh is False
                return {'state':'error','stale':True,'last_success_at':'2026-10-01'}
        class Workspaces:
            def receipts(self):
                return [{'provider':'alibaba','at':'2026-10-02','ok':False,'operation':'products'},
                        {'provider':'alibaba','at':'2026-10-01','ok':True,'operation':'orders'}]
            def metrics(self):
                return {'ok':True,'observed_at':'2026-09-27','metrics':{'clicks':32}}
        with tempfile.TemporaryDirectory() as root:
            result=ChannelOverview(SimpleNamespace(root=Path(root),website_inquiries=Website()),Workspaces()).snapshot()
        ali,web,douyin=result['channels']
        self.assertEqual(ali['connection']['last_success_at'],'2026-10-01')
        self.assertFalse(ali['connection']['latest_attempt']['ok'])
        self.assertEqual(ali['data']['observed_at'],'2026-09-27')
        self.assertTrue(web['connection']['stale'])
        self.assertIsNone(douyin['connection']['last_success_at'])
        self.assertEqual(douyin['actions'],['读取抖店商品'])
        self.assertFalse(ali['quality']['available'])

    def test_quality_links_only_unique_current_listing_identity(self):
        class Business:
            def list_objects(self,kind):
                return [{'id':'product:A','channel_listings':[{'id':'11'},{'id':'22'}]},
                        {'id':'product:B','channel_listings':[{'id':'22'}]}]
        class Workspaces:
            def receipts(self):return []
            def metrics(self):return {}
        with tempfile.TemporaryDirectory() as root, patch('channel_overview.latest_quality',return_value={'below_5':[{'id':'11'},{'id':'22'}]}):
            quality=ChannelOverview(SimpleNamespace(root=Path(root),business=Business()),Workspaces()).snapshot()['channels'][0]['quality']
        self.assertEqual(quality['below_5'][0]['object_id'],'product:A')
        self.assertIsNone(quality['below_5'][1]['object_id'])

if __name__=='__main__':unittest.main()
