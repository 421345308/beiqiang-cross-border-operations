"""Read-only channel overview. Viewing never contacts a platform."""
from pathlib import Path

class ChannelOverview:
    def __init__(self, app, workspaces):
        self.app, self.workspaces = app, workspaces

    def snapshot(self):
        receipts = self.workspaces.receipts()
        try:
            metrics = self.workspaces.metrics()
        except (ValueError, KeyError, OSError):
            metrics = {'ok': False, 'error': '本地经营档案无法读取，请核原文件'}
        website = getattr(self.app, 'website_inquiries', None)
        if website is None:
            website = getattr(getattr(self.app, 'business', None), 'website', None)
        web_status = website.status(start_refresh=False) if website else {'state': 'not_configured'}
        def history(provider):
            rows = [r for r in receipts if r.get('provider') == provider]
            latest = rows[0] if rows else None
            success = next((r for r in rows if r.get('ok') is True), None)
            return {'latest_attempt': {k: latest.get(k) for k in ('at','operation','ok')} if latest else None,
                    'last_success_at': success.get('at') if success else None,
                    'scope': '最近50条工具回执中的记录；历史成功不代表当前在线'}
        return {'channels': [
            {'id':'alibaba','title':'国际站','connection':history('alibaba'),
             'data':metrics,'actions':['connection-check','products','product','orders','order'],
             'gaps':['自然流量实时指标未接通；本地指标保留原日期','询盘与报价未验证接通','标题可准备并人工审核；其他商品字段尚未接入']},
            {'id':'website','title':'独立站','connection':web_status,
             'data':{'source':'网站询盘连接器缓存','scope':'询盘读取状态，不代表网站流量或销售额'},
             'actions':['读取网站询盘','刷新网站询盘'],
             'gaps':['网站流量、搜索和成交指标未汇入此页']},
            {'id':'douyin','title':'抖店','connection':{'state':'not_integrated','last_success_at':None},
             'data':{'source':'09_国内电商/抖店/README.md','available':(Path(self.app.root)/'09_国内电商/抖店/README.md').is_file(),
                     'scope':'原业务档案；不是实时经营指标','observed_at':None},
             'actions':['读取抖店商品'], 'connector_capabilities':['妙手独立只读连接器支持验店、商品和SKU读取'],
             'gaps':['妙手商品读取需手动触发，当前不保存商品快照','需每店独立私有会话与目标店铺配置','成交、流量和售后指标未接通']}
        ], 'notice':'概览仅读取原档案和已有回执；打开或刷新此页不会重新采集平台数据。'}
