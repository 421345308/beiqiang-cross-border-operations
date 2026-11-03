"""Reorder existing type-4 product detail images, retaining roles and text.

No upload or arbitrary URL input. Uses the shared reviewed-change lifecycle.
"""
from copy import deepcopy
import re
import uuid
from xml.etree import ElementTree as ET

from product_changes import ProductChanges, ChangeError, PROTECTED, RENDER, digest
from product_gallery_changes import GalleryChanges, official_image


class DetailChanges(ProductChanges):
    field = 'detail_images'
    change_kind = 'detail_reorder'
    protected = tuple(k for k in PROTECTED if k != 'struct_detail') + ('subject',)

    @staticmethod
    def _kind(change):
        kind = change.get('changeKind')
        if kind is not None:
            return kind
        # Older records predate the discriminator. Reordering preserves the
        # complete multiset of image rows; a URL replacement changes that set.
        diff = change.get('diff', {})
        before, after = diff.get('before'), diff.get('after')
        if isinstance(before, list) and isinstance(after, list):
            return ('detail_reorder' if sorted(map(digest, before)) == sorted(map(digest, after))
                    else 'detail_replace')
        return None

    def _load(self, change_id):
        change = super()._load(change_id)
        if self._kind(change) != self.change_kind:
            raise ChangeError('CHANGE_KIND_MISMATCH')
        return change

    def _save(self, change, previous=None):
        if change.get('changeKind', self.change_kind) != self.change_kind:
            raise ChangeError('CHANGE_KIND_MISMATCH')
        change['changeKind'] = self.change_kind
        return super()._save(change, previous)

    def list_changes(self):
        return [change for change in super().list_changes() if self._kind(change) == self.change_kind]

    def _target(self, product):
        rows = product.get('struct_detail', {}).get('detail_image', {}).get('images')
        if product.get('struct_detail_product') is not True or not isinstance(rows, list) or not rows:
            raise ChangeError('DETAIL_IMAGES_UNAVAILABLE')
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('image_set'), dict):
                raise ChangeError('DETAIL_IMAGE_ROLE_UNAVAILABLE')
            official_image(row.get('image_url'))
        rows = deepcopy(rows)
        # GET array order is not display order: the platform exposes group order
        # on image_set.order. It is positional metadata, not an image role.
        orders = [r['image_set'].get('order') for r in rows]
        if any(value is not None for value in orders):
            if not all(re.fullmatch(r'\d+', str(value)) for value in orders):
                raise ChangeError('DETAIL_GROUP_ORDER_UNAVAILABLE')
            rows.sort(key=lambda row: int(row['image_set']['order']))
        for row in rows:
            row['image_set'].pop('order', None)
        return rows

    def _read(self, pid):
        # Capture the non-target part of struct_detail in the same GET snapshot.
        self._detail_remainder = None
        result = super()._read(pid)
        result['protectedFields']['detail_remainder'] = self._detail_remainder
        # Without explicit order, GET may also return roles in arbitrary order.
        # Approved editable Schema is the authoritative display sequence.
        if result['status'] == 'approved':
            raw = self._call(RENDER, {'param_product_top_publish_request': {
                'product_id': int(pid), 'cat_id': int(result['categoryId']), 'language': 'en_US'}})
            xml = raw.get('data')
            if not isinstance(xml, str) or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
                raise ChangeError('SCHEMA_UNAVAILABLE')
            schema = ET.fromstring(xml)
            rows = result[self.field]
            remaining = list(rows)
            ordered = []
            for block in schema.findall("./field[@id='detailImage']/complex-values"):
                role = block.find("./field[@id='gallery']/value")
                if role is None:
                    raise ChangeError('DETAIL_SCHEMA_UNVERIFIED')
                for value in block.findall("./field[@id='images']/complex-values/field[@id='imageURL']/value"):
                    matches = [r for r in remaining if str(r['image_set'].get('id')) == role.text
                        and GalleryChanges._image_identity(r['image_url']) == GalleryChanges._image_identity(value.text)]
                    if len(matches) != 1:
                        raise ChangeError('DETAIL_SCHEMA_MISMATCH')
                    ordered.append(matches[0])
                    remaining.remove(matches[0])
            if remaining or not ordered:
                raise ChangeError('DETAIL_SCHEMA_MISMATCH')
            result[self.field] = ordered
        return result

    def _call(self, method, params):
        raw = super()._call(method, params)
        if method == 'alibaba.icbu.product.get' and isinstance(raw.get('product'), dict):
            detail = deepcopy(raw['product'].get('struct_detail', {}))
            if isinstance(detail, dict):
                if isinstance(detail.get('detail_image'), dict):
                    detail['detail_image'].pop('images', None)
            self._detail_remainder = digest(detail)
        return raw

    def _valid_target(self, value):
        return (isinstance(value, list) and bool(value) and len(value) <= 150
                and all(type(i) is int for i in value)
                and sorted(value) == list(range(1, len(value) + 1)))

    def _normalize_target(self, order, platform):
        if len(order) != len(platform[self.field]):
            raise ChangeError('DETAIL_ORDER_LENGTH_MISMATCH')
        return [deepcopy(platform[self.field][i - 1]) for i in order]

    def prepare_reorder(self, product_id, order, *, rationale, evidence, internal_test=False):
        return self.prepare(product_id, order, rationale=rationale, evidence=evidence,
                            internal_test=internal_test)

    def diagnose(self, product_id, *, read_platform=True):
        return self._run(self._diagnose_details, product_id, read_platform=read_platform)

    def _diagnose_details(self, pid, *, read_platform=True):
        if not isinstance(pid, str) or not re.fullmatch(r'\d{1,32}', pid) or type(read_platform) is not bool:
            raise ChangeError('INVALID_ARGUMENT')
        _, _, row = self._catalog(pid)
        self._start_audit(uuid.uuid4().hex)
        platform = self._read(pid) if read_platform else None
        groups = []
        if platform:
            self._xml(pid, platform, platform[self.field])
            groups = self._detail_groups
        return {'productId': pid, 'sharedProductId': row.get('product_id'),
                'platform': platform, 'detailGroups': groups, 'readOnly': True,
                'evidenceReceipts': list(self._audit_refs),
                'nextStep': 'review_detail_image_order',
                'requiredPreparation': ['image_order', 'rationale', 'existing_evidence_paths'],
                'submission': {'state': 'not-submitted'}, 'localSync': {'state': 'not-synced'},
                'publicVerification': {'state': 'not-verified'},
                'boundary': '可调整组内顺序或整组顺序，保留原图、分组、图片角色与文字。'}

    def _xml(self, pid, platform, proposed):
        raw = self._call(RENDER, {'param_product_top_publish_request': {
            'product_id': int(pid), 'cat_id': int(platform['categoryId']), 'language': 'en_US'}})
        xml = raw.get('data')
        if not isinstance(xml, str) or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
            raise ChangeError('SCHEMA_UNAVAILABLE')
        schema = ET.fromstring(xml)
        if len(schema.findall("./field[@id='detailImage']")) != 1:
            raise ChangeError('DETAIL_SCHEMA_UNVERIFIED')
        types = schema.findall("./field[@id='productDescType']/value")
        if len(types) != 1 or types[0].text != '4':
            raise ChangeError('DETAIL_TYPE_UNVERIFIED')
        root = self.contract.values_only(schema, operation='update', field_ids=['detailImage', 'productDescType'])
        group = root.find("./field[@id='detailImage']")
        if group.get('type') != 'multiComplex':
            raise ChangeError('DETAIL_SCHEMA_UNVERIFIED')
        offset = 0
        baseline = platform[self.field]
        identity = GalleryChanges._image_identity
        blocks = []
        row_to_group = {}
        self._detail_groups = []
        for index, block in enumerate(group.findall('./complex-values')):
            galleries = block.findall("./field[@id='gallery']/value")
            images = block.findall("./field[@id='images']")
            if len(galleries) != 1 or len(images) != 1:
                raise ChangeError('DETAIL_SCHEMA_UNVERIFIED')
            entries = images[0].findall('./complex-values')
            if not entries:
                raise ChangeError('DETAIL_SCHEMA_UNVERIFIED')
            source = baseline[offset:offset + len(entries)]
            if len(source) != len(entries):
                raise ChangeError('DETAIL_SCHEMA_MISMATCH')
            mapped = {}
            for entry, row in zip(entries, source):
                urls = entry.findall("./field[@id='imageURL']/value")
                if (len(urls) != 1 or identity(urls[0].text) != identity(row['image_url'])
                        or str(row['image_set'].get('id')) != galleries[0].text):
                    raise ChangeError('DETAIL_SCHEMA_MISMATCH')
                key = digest(row)
                if key in row_to_group:
                    raise ChangeError('DETAIL_DUPLICATE_IMAGE_AMBIGUOUS')
                row_to_group[key] = index
                mapped[key] = deepcopy(entry)
            blocks.append((block, images[0], mapped))
            self._detail_groups.append({'groupId': digest(sorted(mapped)),
                'roleId': galleries[0].text,
                'roleName': galleries[0].get('displayName') or source[0]['image_set'].get('name'),
                'slots': list(range(offset + 1, offset + len(entries) + 1))})
            offset += len(entries)
        if (offset != len(baseline) or len(proposed) != len(baseline)
                or sorted(map(digest, proposed)) != sorted(map(digest, baseline))):
            raise ChangeError('DETAIL_SCHEMA_MISMATCH')
        # Each original group must remain contiguous. Move the full group node,
        # including its role and every non-image field, without reconstructing it.
        ordered_groups = []
        rows_by_group = {}
        for row in proposed:
            key = digest(row)
            index = row_to_group[key]
            if not ordered_groups or ordered_groups[-1] != index:
                if index in ordered_groups:
                    raise ChangeError('DETAIL_GROUP_MUST_REMAIN_CONTIGUOUS')
                ordered_groups.append(index)
            rows_by_group.setdefault(index, []).append(key)
        if ordered_groups != list(range(len(blocks))):
            support = schema.find("./field[@id='detailImage']/rules/rule[@name='supportCustomOrder']")
            if support is None or support.get('value') != 'true':
                raise ChangeError('DETAIL_GROUP_ORDER_UNVERIFIED')
        for block, _, _ in blocks:
            group.remove(block)
        for index in ordered_groups:
            block, images, mapped = blocks[index]
            for entry in images.findall('./complex-values'):
                images.remove(entry)
            for key in rows_by_group[index]:
                images.append(mapped[key])
            group.append(block)
        return ET.tostring(root, encoding='unicode')
