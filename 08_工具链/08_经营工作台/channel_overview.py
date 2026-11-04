"""Read-only channel overview. Viewing never contacts a platform."""
from pathlib import Path
import json

REPORT = '02_Alibaba运营/01_店铺与全店诊断/经营复核.json'

class ChannelOverview:
    def __init__(self, app, workspaces):
        self.app, self.workspaces = app, workspaces

    def product_analysis(self):
        """Historical listing evidence joined only by exact current platform ID."""
        try:
            report = json.loads((Path(self.app.root) / REPORT).read_text(encoding='utf-8-sig'))
            summary = report['summary']
            products = report['products']
            if not isinstance(summary, dict) or not isinstance(products, list):
                raise ValueError('invalid report')
        except (OSError, ValueError, KeyError, TypeError):
            return {'available': False, 'notice': '历史商品经营档案暂不可读。', 'items': []}
        business = getattr(self.app, 'business', None)
        matches = {}
        for obj in business.list_objects(kind='product') if business else []:
            for listing in obj.get('channel_listings') or []:
                if listing.get('id') is not None:
                    matches.setdefault(str(listing['id']), set()).add(obj['id'])
        priority = {'已有咨询，改善有效采购承接': 0, '有访客无咨询，优先核流量与报价': 1,
                    '有曝光低点击，核关键词与首图': 2, '曝光不足，核类目需求与检索覆盖': 3}
        rows = []
        for row in products:
            if not isinstance(row, dict) or row.get('id') is None:
                continue
            listing_id = str(row['id'])
            objects = matches.get(listing_id, set())
            metrics = row.get('week41') if isinstance(row.get('week41'), dict) else {}
            rows.append({'listing_id': listing_id, 'model': row.get('model') or '',
                         'title': row.get('title') or '', 'action': row.get('current_action') or '查看原经营记录',
                         'metrics': {k: metrics.get(k) for k in ('search_impressions', 'search_clicks', 'visitors', 'inquiries', 'tm_buyers')},
                         'object_id': next(iter(objects)) if len(objects) == 1 else None,
                         'association': 'matched' if len(objects) == 1 else 'ambiguous' if objects else 'unmatched'})
        rows.sort(key=lambda row: (priority.get(row['action'], 4), -(row['metrics'].get('search_impressions') or 0), row['listing_id']))
        return {'available': True, 'period': summary.get('period'), 'observed_at': summary.get('observed_at'),
                'timezone': summary.get('timezone'), 'items': rows, 'total': len(rows),
                'notice': '历史统计与当时建议，仅供选择核查顺序；不代表当前表现。换款与统计窗口重叠时，先核当前鞋款。缺报表数据保留为空，人数不去重，不合并计算转化率。'}

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
             'data':metrics,'product_analysis':self.product_analysis(),'actions':['connection-check','products','product','orders','order'],
             'gaps':['自然流量实时指标未接通；本地指标保留原日期','询盘与报价未验证接通','标题、主图和详情图支持准备变更；具体提交与正式回读状态须逐商品核对，其他字段尚未接入']},
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
