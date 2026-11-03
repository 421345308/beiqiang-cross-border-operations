"""Reviewed single-position detail image replacements using the existing bank.

Image count, group roles, captions and all other content remain unchanged.
"""
import hashlib
import json
import re
import uuid
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

from product_changes import ChangeError, digest, now
from product_detail_changes import DetailChanges
from product_gallery_changes import GalleryChanges, official_image
from product_gallery_uploads import LocalGalleryPlans


class ReplacementDetailChanges(DetailChanges):
    change_kind = 'detail_replace'
    _bank_values = GalleryChanges._bank_values
    _image_identity = staticmethod(GalleryChanges._image_identity)

    def __init__(self, app, client=None):
        super().__init__(app, client)
        self._image_bank_cache = {}

    def _target(self, product):
        self._current_main_images = deepcopy(product.get('main_image', {}).get('images', []))
        return super()._target(product)

    def _read(self, pid):
        result = super()._read(pid)
        result['availableMainImages'] = self._current_main_images
        return result

    def _valid_target(self, value):
        try:
            return (isinstance(value, list) and bool(value) and len(value) <= 150
                    and all(isinstance(row, dict) and official_image(row.get('image_url')) for row in value))
        except ChangeError:
            return False

    def _normalize_target(self, value, platform):
        if len(value) != len(platform[self.field]):
            raise ChangeError('DETAIL_REPLACEMENT_COUNT_MISMATCH')
        result = deepcopy(value)
        for row in result:
            row['image_url'] = official_image(row['image_url'])
        return result

    def _xml(self, pid, platform, proposed):
        # Validate and reuse the entire current group/entry nodes. Only the URL
        # value at the reviewed position is replaced; no captions are invented.
        root = ET.fromstring(super()._xml(pid, platform, platform[self.field]))
        current = platform[self.field]
        if len(proposed) != len(current):
            raise ChangeError('DETAIL_REPLACEMENT_COUNT_MISMATCH')
        changes = []
        for index, (before, after) in enumerate(zip(current, proposed)):
            expected = deepcopy(before)
            expected['image_url'] = after.get('image_url')
            if expected != after:
                raise ChangeError('DETAIL_REPLACEMENT_URL_ONLY')
            official_image(after['image_url'])
            if before['image_url'] != after['image_url']:
                changes.append(index)
        bank = self._bank_values([proposed[index]['image_url'] for index in changes]) if changes else {}
        values = root.findall("./field[@id='detailImage']/complex-values/field[@id='images']/complex-values/field[@id='imageURL']/value")
        if len(values) != len(current):
            raise ChangeError('DETAIL_SCHEMA_MISMATCH')
        for index, row in enumerate(proposed):
            url = row['image_url']
            # Resolve ownership through the seller bank; detailImage's verified
            # Schema stores URL only, unlike scImages' fileId-valued contract.
            if index in changes and self._image_identity(url) not in bank:
                raise ChangeError('IMAGE_BANK_ASSET_NOT_FOUND')
            values[index].text = url.removeprefix('https:')
        return ET.tostring(root, encoding='unicode')


class LocalDetailPlans(LocalGalleryPlans):
    def __init__(self, app, client=None, uploader=None):
        self.changes = ReplacementDetailChanges(app, client)
        self.app = app
        self.uploader = uploader or self._official_upload
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS local_detail_plans (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            app.db.commit()

    def _save(self, plan):
        plan['version'] = uuid.uuid4().hex
        plan['updatedAt'] = now()
        with self.app.lock:
            self.app.db.execute('INSERT OR REPLACE INTO local_detail_plans VALUES (?,?)', (plan['id'], json.dumps(plan, ensure_ascii=False)))
            self.app.db.commit()
        return plan

    def _load(self, plan_id):
        if not isinstance(plan_id, str) or not re.fullmatch('[a-f0-9]{32}', plan_id):
            raise ChangeError('INVALID_CHANGE_ID')
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM local_detail_plans WHERE id=?', (plan_id,)).fetchone()
        if not row:
            raise ChangeError('CHANGE_NOT_FOUND')
        return json.loads(row[0])

    def get(self, plan_id):
        return self.changes._run(self._load, plan_id)

    def list_plans(self):
        with self.app.lock:
            rows = self.app.db.execute('SELECT data FROM local_detail_plans ORDER BY rowid DESC').fetchall()
        values = [json.loads(row[0]) for row in rows]
        return self.changes.client.safe(values) if hasattr(self.changes.client, 'safe') else self.changes.adapter.sanitize(values)

    def prepare(self, product_id, slots, *, rationale, evidence, internal_test=False):
        return self.changes._run(self._prepare, product_id, slots, rationale, evidence, internal_test)

    def _prepare(self, pid, slots, rationale, evidence, internal_test):
        if (not isinstance(pid, str) or not re.fullmatch(r'\d{1,32}', pid)
                or not isinstance(slots, list) or not slots or len(slots) > 150
                or not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4000
                or not isinstance(evidence, list) or not evidence or len(evidence) > 30 or type(internal_test) is not bool):
            raise ChangeError('INVALID_ARGUMENT')
        c = self.changes
        for ref in evidence:
            if (not isinstance(ref, str) or not ref or '\\' in ref or Path(ref).is_absolute()
                    or '..' in Path(ref).parts
                    or any(p.lower() in ('.local', '.git', '.config', 'secrets', 'credentials') for p in Path(ref).parts)):
                raise ChangeError('INVALID_EVIDENCE_PATH')
            path = (c.root / ref).resolve()
            asset_root = (c.root / '01_产品资产').resolve()
            if (not path.is_file() or not (path.is_relative_to(c.root) or
                    (Path(ref).parts[0] == '01_产品资产' and path.is_relative_to(asset_root)))):
                raise ChangeError('INVALID_EVIDENCE_PATH')
        _, _, row = c._catalog(pid)
        if 'PROTECT_SOURCE' in json.dumps(row):
            raise ChangeError('PROTECTED_PRODUCT')
        plan_id = uuid.uuid4().hex
        c._start_audit(plan_id)
        baseline = c._read(pid)
        if baseline['status'] != 'approved':
            raise ChangeError('PLATFORM_NOT_APPROVED')
        c._xml(pid, baseline, baseline[c.field])
        if len(slots) != len(baseline[c.field]):
            raise ChangeError('DETAIL_REPLACEMENT_COUNT_MISMATCH')
        previews = []
        for slot in slots:
            if type(slot) is int and 1 <= slot <= len(baseline[c.field]):
                previews.append({'url': baseline[c.field][slot - 1]['image_url'], 'existingSlot': slot})
            elif isinstance(slot, dict) and set(slot) == {'mainSlot'}:
                number = slot['mainSlot']
                if type(number) is not int or not 1 <= number <= len(baseline['availableMainImages']):
                    raise ChangeError('INVALID_GALLERY_SLOT')
                previews.append({'url': official_image(baseline['availableMainImages'][number - 1]), 'mainSlot': number})
            elif isinstance(slot, dict) and set(slot) == {'path'}:
                _, asset = self._asset(slot['path'])
                previews.append(asset)
            else:
                raise ChangeError('INVALID_GALLERY_SLOT')
        if len({v.get('sha256', v.get('url')) for v in previews}) != len(previews):
            raise ChangeError('DUPLICATE_GALLERY_IMAGE')
        if all(preview.get('url') == before['image_url'] for preview, before in zip(previews, baseline[c.field])):
            raise ChangeError('NO_CHANGE')
        return self._save({'id': plan_id, 'productId': pid, 'state': 'prepared', 'internalTest': internal_test,
                           'baseline': baseline, 'localRowHash': digest(row), 'before': baseline[c.field],
                           'previews': previews, 'rationale': rationale, 'evidence': evidence,
                           'uploads': [], 'changeId': None, 'createdAt': now()})

    def submit(self, plan_id, *, confirmed, expected_version):
        return self.changes._run(self._submit, plan_id, confirmed, expected_version)

    def _submit(self, plan_id, confirmed, expected_version):
        c = self.changes
        plan = self._load(plan_id)
        if confirmed is not True:
            raise ChangeError('CONFIRMATION_REQUIRED')
        if plan['version'] != expected_version:
            raise ChangeError('VERSION_CONFLICT')
        if plan['internalTest']:
            raise ChangeError('INTERNAL_TEST_NOT_SUBMITTABLE')
        if plan['state'] != 'prepared':
            raise ChangeError('ALREADY_ATTEMPTED_RECONCILE_ONLY')
        _, _, row = c._catalog(plan['productId'])
        if digest(row) != plan['localRowHash']:
            raise ChangeError('LOCAL_VERSION_CONFLICT')
        current = c._read(plan['productId'])
        if any(current.get(key) != plan['baseline'].get(key) for key in ('detail_images', 'categoryId', 'status', 'display', 'protectedFields')):
            raise ChangeError('PLATFORM_VERSION_CONFLICT')
        paths = {}
        frozen = Path(self.app.state) / 'product-changes' / plan_id / 'upload-assets'
        for preview in plan['previews']:
            if 'previewRef' in preview:
                path, asset = self._asset(preview['previewRef'])
                if asset != preview:
                    raise ChangeError('LOCAL_IMAGE_CHANGED')
                # Upload the reviewed bytes even if the source changes afterward.
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != preview['sha256']:
                    raise ChangeError('LOCAL_IMAGE_CHANGED')
                frozen.mkdir(parents=True, exist_ok=True)
                target = frozen / (preview['sha256'][:20] + path.suffix.lower())
                if not target.exists():
                    with target.open('xb') as output:
                        output.write(content)
                if hashlib.sha256(target.read_bytes()).hexdigest() != preview['sha256']:
                    raise ChangeError('LOCAL_IMAGE_CHANGED')
                paths[preview['previewRef']] = target
        # Atomically reserve this plan before any externally visible upload.
        with self.app.lock:
            old = self.app.db.execute('SELECT data FROM local_detail_plans WHERE id=?', (plan_id,)).fetchone()
            if not old or json.loads(old[0])['version'] != expected_version:
                raise ChangeError('VERSION_CONFLICT')
            plan['state'] = 'upload_outcome_unknown'
            plan['version'] = uuid.uuid4().hex
            plan['updatedAt'] = now()
            cursor = self.app.db.execute('UPDATE local_detail_plans SET data=? WHERE id=? AND data=?',
                                         (json.dumps(plan, ensure_ascii=False), plan_id, old[0]))
            if cursor.rowcount != 1:
                self.app.db.rollback()
                raise ChangeError('VERSION_CONFLICT')
            self.app.db.commit()
        c._start_audit(plan_id)
        urls = []
        for preview in plan['previews']:
            if 'url' in preview:
                urls.append(preview['url'])
                continue
            raw = self.uploader(paths[preview['previewRef']])
            c._capture('alibaba.icbu.photobank.upload', {'previewRef': preview['previewRef'], 'sha256': preview['sha256']}, raw)
            plan['uploadEvidenceReceipts'] = list(c._audit_refs)
            uploaded = raw.get('upload_image_response', {}) if isinstance(raw, dict) else {}
            file_id = str(uploaded.get('file_id', ''))
            if not re.fullmatch('[1-9][0-9]*', file_id):
                raise ChangeError('IMAGE_UPLOAD_NOT_VERIFIED')
            url = official_image(uploaded.get('photobank_url'))
            value = ET.Element('value', fileId=file_id)
            value.text = url.removeprefix('https:')
            c._image_bank_cache[c._image_identity(url)] = value
            urls.append(url)
            plan['uploads'].append({'previewRef': preview['previewRef'], 'url': url, 'fileId': file_id, **c._receipt(raw)})
            self._save(plan)
        targets = deepcopy(plan['before'])
        for row, url in zip(targets, urls):
            row['image_url'] = url
        result = c.prepare(plan['productId'], targets, rationale=plan['rationale'], evidence=plan['evidence'])
        if not result['ok']:
            plan['state'] = 'uploaded_preparation_failed'
            plan['error'] = result['error']
            return self._save(plan)
        change = result['change']
        plan['changeId'] = change['id']
        plan['state'] = 'uploaded'
        self._save(plan)
        applied = c.apply(change['id'], confirmed=True, expected_version=change['version'])
        plan['state'] = applied['change']['state'] if applied['ok'] else 'uploaded_submission_blocked'
        plan['submissionResult'] = applied
        return self._save(plan)

    def reconcile(self, plan_id):
        return self.changes._run(self._reconcile, plan_id)

    def _reconcile(self, plan_id):
        plan = self._load(plan_id)
        if not plan['changeId']:
            raise ChangeError('NO_PRODUCT_SUBMISSION_RECORDED')
        result = self.changes.reconcile(plan['changeId'])
        plan['formalResult'] = result
        if result['ok']:
            plan['state'] = result['change']['state']
        return self._save(plan)
