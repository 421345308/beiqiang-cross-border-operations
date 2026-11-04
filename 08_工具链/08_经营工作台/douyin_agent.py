"""Reuse the workbench's read-only shop checks and explicitly dated snapshot."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, ProxyHandler, build_opener

SCRIPT = Path(__file__).resolve().parent / 'douyin_overview.mjs'


def read_store(shop, mode, *, runner=subprocess.run, page=1, page_size=100, is_draft=None):
    if shop not in ('brand', 'legacy'):
        raise ValueError('请选择品牌店或旧店')
    if mode not in ('check', 'snapshot', 'live'):
        raise ValueError('请选择连接检查、本地快照或浏览器实时读取')
    if mode == 'live':
        if shop!='brand':return {'shop':shop,'mode':'live','ok':False,'error':'shop_not_connected'}
        if type(page) is not int or page<1 or type(page_size) is not int or page_size not in (20,40,50,100) or (is_draft is not None and type(is_draft) is not bool):raise ValueError('分页参数无效')
        url=os.environ.get('BEIQIANG_MIAOSHOU_BRIDGE_URL','');token=os.environ.get('BEIQIANG_MIAOSHOU_BRIDGE_TOKEN','')
        if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/api/desk/miaoshou-bridge/agent-read',url) or not token:
            return {'shop':shop,'mode':'live','ok':False,'error':'bridge_service_unavailable'}
        body={'shop':shop,'page':page,'pageSize':page_size}
        if is_draft is not None:body['isDraft']=is_draft
        origin=url.split('/api/',1)[0]
        request=Request(url,data=json.dumps(body).encode(),method='POST',headers={'Content-Type':'application/json','Origin':origin,'X-Bridge-Agent-Token':token})
        try:
            with build_opener(ProxyHandler({})).open(request,timeout=25) as response:value=json.load(response)
            if not isinstance(value,dict) or value.get('shop')!=shop or value.get('mode')!='live' or type(value.get('ok')) is not bool:raise ValueError()
            return value
        except (OSError,URLError,ValueError,TimeoutError):
            return {'shop':shop,'mode':'live','ok':False,'error':'bridge_service_unavailable'}
    if mode == 'snapshot' and shop != 'brand':
        return {'available': False, 'shop': shop, 'notice': '旧店没有已接入的本地快照，不能使用品牌店数据代替。'}
    args = ['node', str(SCRIPT)]
    if mode == 'snapshot':
        args.append('--snapshot-only')
    else:
        args.extend(['--shop=' + shop, '--check-unbound'])
    try:
        result = runner(args, capture_output=True, text=True, encoding='utf8', timeout=50,
                        **({'creationflags': subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, 'CREATE_NO_WINDOW') else {}))
        if result.returncode:
            raise ValueError('抖店只读工具不可用，请查看连接状态。')
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError('抖店返回格式无法识别。')
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError('抖店只读工具不可用或返回格式无法识别。') from None
    if mode == 'snapshot':
        return {**value, 'store_name': value.get('shop'), 'shop': shop, 'mode': mode}
    shops = value.get('shops')
    if not isinstance(shops, list) or len(shops) != 1 or not isinstance(shops[0], dict) or shops[0].get('id') != shop:
        raise ValueError('抖店只读结果与所选店铺不一致。')
    return {'shop': shop, 'mode': mode, 'result': shops[0], 'notice': value.get('notice')}
