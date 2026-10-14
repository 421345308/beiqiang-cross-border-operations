"""抖店协议适配：离线签名与请求构造，不发送网络请求、不保存凭证。

依据官方调用指南及新版语言示例实现。真实联调须在应用获批、店铺授权、
接口权限与参数核对后进行；本模块本身不赋予任何平台调用权限。
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

HOST = 'https://openapi-fxg.jinritemai.com'
METHOD = re.compile(r'^[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)+$')


def serialize(params):
    """签名与发送必须使用完全相同的UTF-8字节，不改变字段原有数据类型。"""
    if not isinstance(params, dict):
        raise ValueError('业务参数须为对象')
    return json.dumps(params, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def signature(app_key, app_secret, method, timestamp, param_json):
    """HMAC-SHA256；access_token与sign_method不参与拼接。"""
    pattern = (f'app_key{app_key}method{method}param_json{param_json}'
               f'timestamp{timestamp}v2')
    message = (app_secret + pattern + app_secret).encode('utf-8')
    return hmac.new(app_secret.encode('utf-8'), message, hashlib.sha256).hexdigest()


@dataclass(repr=False, frozen=True)
class PreparedRequest:
    method: str
    url: str = field(repr=False)
    body: bytes = field(repr=False)
    headers: dict = field(repr=False)

    def __repr__(self):
        return f'PreparedRequest(method={self.method!r}, credentials=redacted, sent=False)'

    def preview(self):
        """供检查的脱敏摘要，不输出签名、令牌、业务参数或完整URL。"""
        return {'api': self.method, 'transport': 'POST', 'host': HOST,
                'path': '/' + self.method.replace('.', '/'),
                'body_bytes': len(self.body), 'encoding': 'UTF-8',
                'sign_method': 'hmac-sha256', 'sent': False}


def prepare(app_key, app_secret, access_token, method, params, timestamp=None):
    if not METHOD.fullmatch(method):
        raise ValueError('接口方法格式错误')
    for credential in (app_key, app_secret, access_token):
        if not isinstance(credential, str) or not credential.strip():
            raise ValueError('须先取得真实应用凭证和店铺授权；不可用占位值联调')
    if timestamp is None:
        timestamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    if not isinstance(timestamp, str) or not timestamp:
        raise ValueError('时间戳格式错误')
    param_json = serialize(params)
    query = {'method': method, 'app_key': app_key, 'access_token': access_token,
             'timestamp': timestamp, 'v': '2', 'sign_method': 'hmac-sha256',
             'sign': signature(app_key, app_secret, method, timestamp, param_json)}
    return PreparedRequest(method, HOST + '/' + method.replace('.', '/') + '?' + urlencode(query),
                           param_json.encode('utf-8'), {'Content-Type': 'application/json; charset=utf-8'})


def main():
    parser = argparse.ArgumentParser(description='抖店接口离线准备演示，不调用平台')
    parser.parse_args()
    request = prepare('DEMO_APP_KEY', 'DEMO_SECRET', 'DEMO_TOKEN', 'product.detail',
                      {'product_id': 'DEMO_PRODUCT'}, '2026-10-15 00:00:00')
    print(json.dumps(request.preview(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
