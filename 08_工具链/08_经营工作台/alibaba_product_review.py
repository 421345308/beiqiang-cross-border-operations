"""Read the selected Alibaba listing and compare it with its local catalog record."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import re
import threading
import time
from urllib.parse import urlsplit, urlunsplit

from business import CHANNEL
from connectors.alibaba.adapter import matches_requested_product
from gmail_translation import translate_with_codex


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'img':
            value = dict(attrs).get('src') or dict(attrs).get('data-src')
            if value:
                self.images.append(value)


def image_url(value):
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if value.startswith('//'):
        value = 'https:' + value
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return ''
    return urlunsplit(('https' if parsed.scheme == 'http' else parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))


def images(value):
    if isinstance(value, dict):
        value = value.get('images') or []
    if not isinstance(value, list):
        return []
    result = []
    for row in value:
        raw = row if isinstance(row, str) else row.get('image_url') if isinstance(row, dict) else ''
        url = image_url(raw)
        if url:
            image_set = row.get('image_set') if isinstance(row, dict) else None
            role = image_set.get('name', '') if isinstance(image_set, dict) else ''
            result.append({'url': url, 'role': role})
    return result


def comparison(local, remote):
    if remote is None:
        return 'unavailable'
    if local is None:
        return 'not_recorded'
    return 'same' if local == remote else 'different'


class AlibabaProductReview:
    def __init__(self, app, *, client=None, clock=time.time, ttl=120, translate=None):
        self.app, self.client, self.clock, self.ttl = app, client or app.product_changes.client, clock, ttl
        self.cache, self.lock = {}, threading.RLock()
        self.translate = translate or (lambda rows: translate_with_codex(app.state, rows))
        self.translations_enabled = hasattr(app, 'db') and hasattr(app, 'lock') and hasattr(app, 'state')
        self.pending, self.failed, self.translation_gate = set(), set(), threading.Semaphore(1)
        if self.translations_enabled:
            with app.lock:
                app.db.execute('CREATE TABLE IF NOT EXISTS alibaba_title_translations (listing_id TEXT NOT NULL,title_hash TEXT NOT NULL,translation TEXT NOT NULL,PRIMARY KEY(listing_id,title_hash))')
                app.db.commit()

    def _title_translation(self, listing_id, title, retry=False):
        if not title or not self.translations_enabled:
            return {'state':'unavailable','text':''}
        digest = hashlib.sha256(title.encode('utf8')).hexdigest()
        key = (listing_id, digest)
        with self.app.lock:
            row = self.app.db.execute('SELECT translation FROM alibaba_title_translations WHERE listing_id=? AND title_hash=?', key).fetchone()
        if row:
            return {'state':'ready','text':row[0]}
        with self.lock:
            if retry:
                self.failed.discard(key)
            if key in self.failed:
                return {'state':'error','text':''}
            if key not in self.pending:
                self.pending.add(key)
                threading.Thread(target=self._translate_title,args=(key,title),daemon=True,name='product-title-translation').start()
        return {'state':'translating','text':''}

    def _translate_title(self, key, title):
        try:
            with self.translation_gate:
                result = self.translate([{'id':key[0],'subject':title,'body':''}])
            row = next(item for item in result if str(item.get('id')) == key[0])
            translated = row.get('subject_zh')
            if not isinstance(translated, str) or not translated.strip():
                raise ValueError('译文为空')
            with self.app.lock:
                self.app.db.execute('INSERT OR REPLACE INTO alibaba_title_translations VALUES (?,?,?)',(*key,translated.strip()))
                self.app.db.commit()
        except Exception:
            with self.lock:
                self.failed.add(key)
        finally:
            with self.lock:
                self.pending.discard(key)

    def _listings(self, object_id):
        obj = self.app.business.get_object(object_id)
        if obj.get('kind') != 'product' or not object_id.startswith('product:'):
            raise ValueError('请选择商品')
        product_id = object_id.split(':', 1)[1]
        rows = self.app.business._json(CHANNEL, 'listings')
        return [row for row in rows if row.get('product_id') == product_id and re.fullmatch(r'\d+', str(row.get('id') or ''))]

    def _read(self, listing_id):
        with self.lock:
            cached = self.cache.get(listing_id)
            if cached and self.clock() - cached['time'] < self.ttl:
                return cached['value']
        raw = self.client.call('alibaba.icbu.product.get', {'product_id': listing_id, 'language': 'ENGLISH'})
        if not isinstance(raw, dict) or raw.get('error_response') or raw.get('success') is False or str(raw.get('code', '0')) not in ('0', ''):
            raise ValueError('国际站接口暂未返回商品，请稍后重试')
        product = raw.get('product')
        if not isinstance(product, dict) or not matches_requested_product(product, listing_id):
            raise ValueError('国际站返回的商品与选择的链接不一致')
        details = product.get('struct_detail') if isinstance(product.get('struct_detail'), dict) else {}
        detail_images = images(details['detail_image']) if details.get('detail_image') is not None else None
        if not detail_images:
            for field in ('detail', 'description', 'product_detail'):
                if isinstance(product.get(field), str):
                    parser = ImageParser(); parser.feed(product[field])
                    if detail_images is None:
                        detail_images = []
                    detail_images.extend(images(parser.images))
        value = {'title': product.get('subject') or '', 'status': product.get('status'), 'display': product.get('display'),
                 'url': product.get('pc_detail_url') or '', 'main_images': images(product['main_image']) if product.get('main_image') is not None else None,
                 'detail_images': detail_images, 'company_images': images(details.get('company_image')),
                 'product_summary': details.get('product_summary') or '',
                 'observed_at': datetime.now(timezone.utc).isoformat()}
        if hasattr(self.client, 'safe'):
            value = self.client.safe(value)
        with self.lock:
            self.cache[listing_id] = {'time': self.clock(), 'value': value}
        return value

    def get(self, object_id, listing_id='', refresh=False):
        listings = self._listings(object_id)
        choices = [{'id': str(row['id']), 'title': (row.get('current_platform_fields') or {}).get('title')
                    or (row.get('catalog_fields') or {}).get('title') or '',
                    'url': (row.get('current_platform_fields') or {}).get('url') or row.get('url') or ''}
                   for row in listings]
        result = {'listings': choices, 'selected': None}
        if not choices:
            return result
        selected = str(listing_id or choices[0]['id'])
        row = next((row for row in listings if str(row['id']) == selected), None)
        if row is None:
            raise ValueError('该国际站链接不属于当前商品')
        local = row.get('current_platform_fields') or {}
        local_title = local.get('title') or (row.get('catalog_fields') or {}).get('title') or ''
        local_main = images(local['main_images']) if local.get('main_images') is not None else None
        local_detail = images(local['detail_images']) if local.get('detail_images') is not None else None
        record = {'id': selected, 'local': {'title': local_title, 'main_images': local_main,
                                          'detail_images': local_detail, 'observed_at': local.get('at')},
                  'platform': None, 'comparison': {}, 'state': 'error'}
        if refresh:
            with self.lock:
                self.cache.pop(selected, None)
        try:
            live = dict(self._read(selected))
            live['title_zh'] = self._title_translation(selected, live['title'], retry=refresh)
            urls = lambda items: [item['url'].split('?', 1)[0] for item in items]
            record.update(state='ready', platform=live, comparison={
                'title': comparison(local_title or None, live['title'] or None),
                'main_images': comparison(urls(local_main) if local_main is not None else None, urls(live['main_images']) if live['main_images'] is not None else None),
                'detail_images': comparison(urls(local_detail) if local_detail is not None else None, urls(live['detail_images']) if live['detail_images'] is not None else None)})
        except Exception as exc:
            record['error'] = str(exc) if isinstance(exc, ValueError) else '国际站连接暂不可用，请稍后重试'
        result['selected'] = record
        return result
