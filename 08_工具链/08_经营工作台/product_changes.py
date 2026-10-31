"""Reviewed, title-only Alibaba change. No import-time I/O or automatic retries.

Drafts/receipts belong to the existing application database. The sole catalog
remains 国际站商品.json; only approved, formally read titles may be synchronized.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

CATALOG = '02_Alibaba运营/05_扩品工程/数据/国际站商品.json'
GET = 'alibaba.icbu.product.get'
RENDER = 'alibaba.icbu.product.schema.render'
UPDATE = 'alibaba.icbu.product.schema.update'
PROTECTED = ('keywords', 'main_image', 'product_sku', 'attributes', 'struct_detail_product',
             'struct_detail', 'sourcing_trade', 'price_type', 'rts', 'product_type',
             'sub_market_type', 'category_id', 'language')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


class ChangeError(Exception):
    def __init__(self, code):
        self.code = code


class ProductChanges:
    def __init__(self, app, client=None):
        self.app = app
        self.root = Path(app.root).resolve()
        self.catalog = self.root / CATALOG
        self.adapter = self._module('product_change_adapter', Path(__file__).parent / 'connectors/alibaba/adapter.py')
        self.client = client or self.adapter.ExistingClient()
        self.lock = threading.RLock()
        self._audit_id = None
        self._audit_refs = []
        self.contract = self._module('product_change_contract', Path(__file__).resolve().parents[1] / '01_业务脚本/国际站扩品/schema_publish_contract.py')
        registry = self._module('product_change_registry', Path(__file__).resolve().parents[1] / '06_工作区维护/product_registry.py')
        self.registry = registry.ProductRegistry(self.root)
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS product_changes (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            app.db.execute('CREATE TABLE IF NOT EXISTS product_change_claims (product_id TEXT PRIMARY KEY, change_id TEXT NOT NULL)')
            app.db.commit()

    @staticmethod
    def _module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run(self, function, *args, **kwargs):
        try:
            with self.lock:
                value = {'ok': True, 'change': function(*args, **kwargs), 'error': None}
                return self.client.safe(value) if hasattr(self.client, 'safe') else self.adapter.sanitize(value)
        except ChangeError as exc:
            return {'ok': False, 'change': None, 'error': {'code': exc.code}}
        except Exception:
            # No platform messages, paths, signed URLs or exception text to UI.
            return {'ok': False, 'change': None, 'error': {'code': 'CLIENT_OR_STORAGE_FAILURE'}}

    def _load(self, change_id):
        if not isinstance(change_id, str) or not re.fullmatch('[a-f0-9]{32}', change_id):
            raise ChangeError('INVALID_CHANGE_ID')
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM product_changes WHERE id=?', (change_id,)).fetchone()
        if not row:
            raise ChangeError('CHANGE_NOT_FOUND')
        return json.loads(row[0])

    def _save(self, change, previous=None):
        with self.app.lock:
            try:
                return self._save_locked(change, previous)
            except Exception:
                self.app.db.rollback()
                raise

    def _save_locked(self, change, previous=None):
        change['evidenceReceipts'] = list(self._audit_refs)
        change['version'] = uuid.uuid4().hex
        change['updatedAt'] = now()
        value = json.dumps(change, ensure_ascii=False)
        if previous is None:
            self.app.db.execute('INSERT INTO product_changes VALUES (?,?)', (change['id'], value))
        else:
            old = self.app.db.execute('SELECT data FROM product_changes WHERE id=?', (change['id'],)).fetchone()
            if not old or json.loads(old[0])['version'] != previous:
                raise ChangeError('VERSION_CONFLICT')
            cursor = self.app.db.execute('UPDATE product_changes SET data=? WHERE id=? AND data=?', (value, change['id'], old[0]))
            if cursor.rowcount != 1:
                raise ChangeError('VERSION_CONFLICT')
        self.app.db.commit()
        return change

    def _catalog(self, pid):
        raw = self.catalog.read_bytes()
        data = json.loads(raw.decode('utf-8-sig'))
        rows = data.get('listings')
        if not isinstance(rows, list):
            raise ChangeError('CATALOG_INVALID')
        matches = [r for r in rows if isinstance(r, dict) and r.get('id') == pid]
        if len(matches) != 1:
            raise ChangeError('LOCAL_PRODUCT_NOT_UNIQUE')
        return raw, data, matches[0]

    def _call(self, method, params):
        raw = self.client.call(method, params)
        self._capture(method, params, raw)
        if not isinstance(raw, dict) or isinstance(raw.get('error_response'), dict) or raw.get('success') is False or str(raw.get('code', '0')) not in ('0', ''):
            raise ChangeError('PLATFORM_ERROR')
        return raw

    def _start_audit(self, change_id, refs=()):
        self._audit_id = change_id
        self._audit_refs = list(refs)

    def _capture(self, method, params, raw):
        if not self._audit_id:
            return
        folder = Path(self.app.state) / 'product-changes' / self._audit_id
        folder.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + '.json'
        value = {'observedAt': now(), 'method': method, 'params': params, 'response': raw}
        value = self.client.safe(value) if hasattr(self.client, 'safe') else self.adapter.sanitize(value)
        target = folder / name
        with target.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        self._audit_refs.append('product-changes/' + self._audit_id + '/' + name)

    @staticmethod
    def _receipt(raw):
        result = {}
        for target, source in (('requestId', 'request_id'), ('traceId', '_trace_id_')):
            value = raw.get(source)
            if isinstance(value, str) and re.fullmatch('[A-Za-z0-9_-]{1,160}', value):
                result[target] = value
        return result

    def _read(self, pid):
        raw = self._call(GET, {'product_id': pid, 'language': 'ENGLISH'})
        product = raw.get('product')
        if not isinstance(product, dict) or not self.adapter.matches_requested_product(product, pid):
            raise ChangeError('PLATFORM_IDENTITY_MISMATCH')
        if not isinstance(product.get('subject'), str) or not product['subject']:
            raise ChangeError('PLATFORM_TITLE_MISSING')
        cat = product.get('category_id')
        if type(cat) not in (int, str) or not re.fullmatch(r'\d+', str(cat)):
            raise ChangeError('PLATFORM_CATEGORY_MISSING')
        if any(key not in product for key in ('keywords', 'main_image', 'product_sku', 'attributes')):
            raise ChangeError('PROTECTION_FIELDS_UNAVAILABLE')
        return {'title': product['subject'], 'status': product.get('status'),
                'display': product.get('display'), 'categoryId': str(cat),
                'protectedFields': {key: digest({'present': key in product, 'value': product.get(key)}) for key in PROTECTED},
                'observedAt': now(), **self._receipt(raw)}

    def _xml(self, pid, platform, title):
        raw = self._call(RENDER, {'param_product_top_publish_request': {
            'product_id': int(pid), 'cat_id': int(platform['categoryId']), 'language': 'en_US'}})
        if not isinstance(raw.get('data'), str) or '<!DOCTYPE' in raw['data'].upper() or '<!ENTITY' in raw['data'].upper():
            raise ChangeError('SCHEMA_UNAVAILABLE')
        schema = ET.fromstring(raw['data'])
        fields = schema.findall("./field[@id='productTitle']")
        if len(fields) != 1 or fields[0].get('type') != 'input' or len(fields[0].findall('./value')) != 1:
            raise ChangeError('TITLE_SCHEMA_UNVERIFIED')
        if fields[0].find('./value').text != platform['title']:
            raise ChangeError('TITLE_SCHEMA_MISMATCH')
        result = self.contract.values_only(schema, operation='update', field_ids=['productTitle'])
        result.find('./field/value').text = title
        return ET.tostring(result, encoding='unicode')

    def prepare(self, product_id, proposed_title, *, rationale, evidence, internal_test=False):
        return self._run(self._prepare, product_id, proposed_title, rationale=rationale, evidence=evidence, internal_test=internal_test)

    def _prepare(self, pid, title, *, rationale, evidence, internal_test=False):
        if (not isinstance(pid, str) or not re.fullmatch(r'\d{1,32}', pid)
                or not isinstance(title, str) or not title.strip() or len(title) > 1000
                or any(ord(c) < 32 for c in title)
                or not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4000
                or not isinstance(evidence, list) or not evidence or len(evidence) > 30
                or type(internal_test) is not bool):
            raise ChangeError('INVALID_ARGUMENT')
        refs = []
        for ref in evidence:
            if not isinstance(ref, str) or '\\' in ref or not ref or Path(ref).is_absolute() or '..' in Path(ref).parts:
                raise ChangeError('INVALID_EVIDENCE_PATH')
            path = (self.root / ref).resolve()
            asset_root = (self.root / '01_产品资产').resolve()
            asset_ref = Path(ref).parts[0] == '01_产品资产' and path.is_relative_to(asset_root)
            if ((not path.is_relative_to(self.root) and not asset_ref) or not path.is_file()
                    or any(part.lower() in ('.local', '.git', 'credentials', 'secrets', '.config') for part in Path(ref).parts)):
                raise ChangeError('INVALID_EVIDENCE_PATH')
            refs.append(Path(ref).as_posix())
        change_id = uuid.uuid4().hex
        self._start_audit(change_id)
        _, _, row = self._catalog(pid)
        if 'PROTECT_SOURCE' in json.dumps(row):
            raise ChangeError('PROTECTED_PRODUCT')
        local = row.get('current_platform_fields', row.get('catalog_fields', {})).get('title')
        if not isinstance(local, str):
            raise ChangeError('LOCAL_TITLE_MISSING')
        platform = self._read(pid)
        if platform['status'] != 'approved':
            raise ChangeError('PLATFORM_NOT_APPROVED')
        title = title.strip()
        if title == platform['title']:
            raise ChangeError('NO_CHANGE')
        xml = self._xml(pid, platform, title)
        change = {'id': change_id, 'productId': pid, 'state': 'prepared', 'createdAt': now(),
                  'internalTest': internal_test,
                  'diff': {'field': 'title', 'before': platform['title'], 'after': title, 'localBefore': local},
                  'rationale': rationale.strip(), 'evidence': refs, 'localRowHash': digest(row),
                  'baseline': platform, 'xml': xml, 'xmlHash': hashlib.sha256(xml.encode()).hexdigest(),
                  'submission': {'state': 'not-submitted', 'at': None},
                  'formal': {'state': 'not-verified'}, 'localSync': {'state': 'not-synced'},
                  'publicVerification': {'state': 'not-verified', 'at': None}}
        return self._save(change)

    def get(self, change_id):
        return self._run(self._load, change_id)

    def list_changes(self):
        with self.app.lock:
            values = [json.loads(row[0]) for row in self.app.db.execute('SELECT data FROM product_changes ORDER BY rowid DESC')]
            return self.client.safe(values) if hasattr(self.client, 'safe') else self.adapter.sanitize(values)

    def apply(self, change_id, *, confirmed, expected_version):
        return self._run(self._apply, change_id, confirmed=confirmed, expected_version=expected_version)

    def _apply(self, change_id, *, confirmed, expected_version):
        change = self._load(change_id)
        self._start_audit(change_id, change.get('evidenceReceipts', []))
        if confirmed is not True:
            raise ChangeError('CONFIRMATION_REQUIRED')
        if expected_version != change['version']:
            raise ChangeError('VERSION_CONFLICT')
        if change.get('internalTest') is True:
            raise ChangeError('INTERNAL_TEST_NOT_SUBMITTABLE')
        if change['submission']['state'] != 'not-submitted':
            raise ChangeError('ALREADY_ATTEMPTED_RECONCILE_ONLY')
        pid = change['productId']
        _, _, row = self._catalog(pid)
        if digest(row) != change['localRowHash']:
            raise ChangeError('LOCAL_VERSION_CONFLICT')
        current = self._read(pid)
        if (current['title'] != change['diff']['before'] or current['categoryId'] != change['baseline']['categoryId']
                or current['status'] != 'approved' or current['display'] != change['baseline']['display']
                or current['protectedFields'] != change['baseline']['protectedFields']):
            raise ChangeError('PLATFORM_VERSION_CONFLICT')
        xml = self._xml(pid, current, change['diff']['after'])
        if xml != change['xml']:
            raise ChangeError('SCHEMA_VERSION_CONFLICT')
        # Database uniqueness prevents competing prepared changes for one ID.
        try:
            with self.app.lock:
                self.app.db.execute('INSERT INTO product_change_claims VALUES (?,?)', (pid, change_id))
                change['submission'] = {'state': 'outcome-unknown', 'at': now()}
                change['state'] = 'outcome_unknown'
                self._save(change, expected_version)
        except Exception:
            with self.app.lock:
                self.app.db.rollback()
            raise ChangeError('PRODUCT_CHANGE_IN_PROGRESS')
        # Reservation is committed before sending. Crash/timeout never retries.
        try:
            params = {'param_product_top_publish_request': {
                'product_id': int(pid), 'cat_id': int(current['categoryId']), 'language': 'en_US', 'xml': xml}}
            # Persist the exact unsigned business request before transmission.
            self._capture(UPDATE, params, {'outcome': 'unknown-before-send'})
            raw = self.client.call(UPDATE, params)
            self._capture(UPDATE, params, raw)
            valid = isinstance(raw, dict)
            accepted = valid and raw.get('success') is not False and raw.get('biz_success') is True and not raw.get('error_response') and str(raw.get('code', '0')) in ('0', '')
            rejected = valid and (raw.get('success') is False or raw.get('biz_success') is False or isinstance(raw.get('error_response'), dict) or str(raw.get('code', '0')) not in ('0', ''))
            old = change['version']
            change['submission'].update(self._receipt(raw) if valid else {})
            if accepted:
                change['submission']['state'] = 'submitted'
                change['state'] = 'submitted'
            elif rejected:
                change['submission']['state'] = 'business-rejected'
                change['state'] = 'business_rejected'
            self._save(change, old)
        except Exception:
            return self._load(change_id)
        if change['state'] == 'business_rejected':
            with self.app.lock:
                self.app.db.execute('DELETE FROM product_change_claims WHERE product_id=? AND change_id=?', (pid, change_id))
                self.app.db.commit()
        return change

    def reconcile(self, change_id):
        return self._run(self._reconcile, change_id)

    def _reconcile(self, change_id):
        change = self._load(change_id)
        self._start_audit(change_id, change.get('evidenceReceipts', []))
        if change['submission']['state'] == 'not-submitted':
            raise ChangeError('NOT_SUBMITTED')
        old = change['version']
        formal = self._read(change['productId'])
        preserved = formal['protectedFields'] == change['baseline']['protectedFields']
        display_preserved = formal['display'] == change['baseline']['display']
        matched = formal['title'] == change['diff']['after'] and formal['status'] == 'approved' and preserved and display_preserved
        schema_state = 'not-verified'
        if matched:
            try:
                rendered = self._xml(change['productId'], formal, change['diff']['after'])
                schema_state = 'verified' if rendered == change['xml'] else 'mismatch'
            except Exception:
                schema_state = 'unavailable'
            matched = schema_state == 'verified'
        change['formal'] = {**formal, 'state': 'verified' if matched else 'pending',
                            'protectedFieldsMatch': preserved, 'displayPreserved': display_preserved,
                            'schemaState': schema_state}
        change['state'] = 'formal_verified' if matched else 'formal_pending'
        if matched:
            try:
                self._sync(change)
                change['localSync'] = {'state': 'synced', 'at': now(), 'indexState': 'pending-regeneration'}
                change['state'] = 'local_synced'
                with self.app.lock:
                    self.app.db.execute('DELETE FROM product_change_claims WHERE product_id=? AND change_id=?', (change['productId'], change_id))
                    self.app.db.commit()
            except ChangeError as exc:
                change['localSync'] = {'state': 'conflict', 'code': exc.code}
                change['state'] = 'local_conflict'
        return self._save(change, old)

    def _sync(self, change):
        # Same cross-process lock as the existing product-registry writers.
        with self.registry.locked():
            return self._sync_locked(change)

    def _sync_locked(self, change):
        raw, data, row = self._catalog(change['productId'])
        marker = row.get('local_sync', {}).get('title_change', {})
        title_fields = [row[key].get('title') for key in ('current_platform_fields', 'catalog_fields') if key in row]
        if marker.get('change_id') == change['id'] and title_fields and all(value == change['diff']['after'] for value in title_fields):
            return  # Recovery after file replace succeeded but DB commit failed.
        if digest(row) != change['localRowHash']:
            raise ChangeError('LOCAL_VERSION_CONFLICT')
        for key in ('current_platform_fields', 'catalog_fields'):
            if key in row:
                row[key]['title'] = change['formal']['title']
                # Do not freshen the timestamp of unrelated historical fields.
                row[key]['title_observed_at'] = change['formal']['observedAt']
        row.setdefault('local_sync', {})['title_change'] = {
            'change_id': change['id'], 'state': 'TITLE_FORMAL_SYNCED_PUBLIC_PENDING',
            'observed_at': change['formal']['observedAt'], 'request_id': change['formal'].get('requestId'),
            'receipt_store': 'workbench-db:product_changes', 'index_state': 'PENDING_REGENERATION'}
        row.setdefault('formal_fields', {})['title'] = {
            'change_id': change['id'], 'observed_at': change['formal']['observedAt'],
            'receipt_store': 'workbench-db:product_changes', 'scope': 'productTitle only; protected fields matched'}
        payload = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        handle, tmp = tempfile.mkstemp(prefix='.title-change-', suffix='.tmp', dir=self.catalog.parent)
        try:
            with os.fdopen(handle, 'wb') as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            if self.catalog.read_bytes() != raw:
                raise ChangeError('CATALOG_CHANGED_DURING_SYNC')
            os.replace(tmp, self.catalog)
        finally:
            Path(tmp).unlink(missing_ok=True)
