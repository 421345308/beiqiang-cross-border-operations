import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from channel_overview import ChannelOverview

class OverviewTest(unittest.TestCase):
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

if __name__=='__main__':unittest.main()

