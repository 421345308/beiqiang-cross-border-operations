"""Review and reorder an existing six-image gallery using the shared change lifecycle.

Only existing image-bank values from the selected product Schema are reused.
No upload, video binding, arbitrary URL ingestion or live call at import time.
"""
from copy import deepcopy
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from product_changes import ProductChanges, ChangeError, PROTECTED, RENDER


def official_image(value):
    if not isinstance(value, str):
        raise ChangeError('GALLERY_IMAGE_UNAVAILABLE')
    value = 'https:' + value if value.startswith('//') else value
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.hostname != 'sc04.alicdn.com'
            or parsed.port is not None or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not parsed.path.startswith('/kf/')):
        raise ChangeError('GALLERY_IMAGE_NOT_OFFICIAL')
    return value


class GalleryChanges(ProductChanges):
    field = 'main_images'
    protected = tuple(key for key in PROTECTED if key != 'main_image') + ('subject',)

    def __init__(self, app, client=None):
        super().__init__(app, client=client)
        self._image_bank_cache = {}

    def _target(self, product):
        images = product.get('main_image', {}).get('images')
        if not isinstance(images, list) or len(images) != 6:
            raise ChangeError('SIX_IMAGE_GALLERY_REQUIRED')
        result = [official_image(value) for value in images]
        if len(set(result)) != 6:
            raise ChangeError('DUPLICATE_GALLERY_IMAGE')
        return result

    def _valid_target(self, value):
        return (isinstance(value, list) and len(value) == 6
                and all(type(slot) is int for slot in value)
                and sorted(value) == list(range(1, 7)))

    def _normalize_target(self, order, platform):
        return [platform[self.field][slot - 1] for slot in order]

    def prepare_reorder(self, product_id, order, *, rationale, evidence, internal_test=False):
        """order uses visible 1-based slots, e.g. [2,1,3,4,5,6]. Never writes."""
        return self.prepare(product_id, order, rationale=rationale, evidence=evidence,
                            internal_test=internal_test)

    @staticmethod
    def _image_identity(url):
        # Reuse the existing helper's observed compact/350px KF identity rule;
        # do not generalize arbitrary CDN transformations.
        url = official_image(url)
        path = urlsplit(url).path
        match = re.fullmatch(r'/kf/([HAS][A-Za-z0-9]+)\.(jpg|jpeg|png)(?:_350x350\.(?:jpg|jpeg|png))?', path)
        return 'sc04-kf:' + match.group(1) if match else url

    def _bank_values(self, urls):
        wanted = {self._image_identity(url) for url in urls}
        found = {key: self._image_bank_cache[key] for key in wanted if key in self._image_bank_cache}
        if set(found) == wanted:
            return found
        for page in range(1, 101):
            raw = self._call('alibaba.icbu.photobank.list', {
                'extra_context': {}, 'location_type': 'ALL_GROUP',
                'current_page': page, 'page_size': 500})
            rows = raw.get('pagination_query_list', {}).get('list')
            if not isinstance(rows, list):
                raise ChangeError('IMAGE_BANK_UNAVAILABLE')
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('url'), str):
                    continue
                try:
                    key = self._image_identity(row['url'])
                except ChangeError:
                    continue
                file_id = str(row.get('id', ''))
                if key in wanted and re.fullmatch(r'[1-9]\d*', file_id):
                    value = ET.Element('value', fileId=file_id)
                    value.text = official_image(row['url']).removeprefix('https:')
                    if key in found and found[key].get('fileId') != file_id:
                        raise ChangeError('IMAGE_BANK_ASSET_AMBIGUOUS')
                    found[key] = value
            if set(found) == wanted:
                self._image_bank_cache.update(found)
                return found
            if len(rows) < 500:
                break
        raise ChangeError('IMAGE_BANK_ASSET_NOT_FOUND')

    def _xml(self, pid, platform, proposed):
        raw = self._call(RENDER, {'param_product_top_publish_request': {
            'product_id': int(pid), 'cat_id': int(platform['categoryId']), 'language': 'en_US'}})
        xml = raw.get('data')
        if not isinstance(xml, str) or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
            raise ChangeError('SCHEMA_UNAVAILABLE')
        schema = ET.fromstring(xml)
        groups = schema.findall("./field[@id='scImages']")
        if len(groups) != 1 or groups[0].get('type') != 'complex':
            raise ChangeError('GALLERY_SCHEMA_UNVERIFIED')
        current = groups[0].findall('./complex-value/field')
        if len(current) != 6 or len(groups[0].findall('./complex-value')) != 1:
            raise ChangeError('GALLERY_SCHEMA_UNVERIFIED')
        slot_ids = [field.get('id', '') for field in current]
        if set(slot_ids) != {f'scImages_{slot}' for slot in range(6)}:
            raise ChangeError('GALLERY_SCHEMA_UNVERIFIED')
        current.sort(key=lambda field: int(field.get('id').split('_')[1]))
        values = {}
        urls = []
        for slot, field in enumerate(current):
            children = field.findall('./value')
            if (field.get('id') != f'scImages_{slot}' or field.get('type') != 'input'
                    or len(children) != 1 or not re.fullmatch(r'\d+', children[0].get('fileId', ''))):
                raise ChangeError('GALLERY_SCHEMA_UNVERIFIED')
            url = official_image(children[0].text)
            identity = self._image_identity(url)
            urls.append(identity)
            values[identity] = deepcopy(children[0])
        if urls != [self._image_identity(url) for url in platform[self.field]] or len(values) != 6:
            raise ChangeError('GALLERY_SCHEMA_MISMATCH')
        if sorted(self._image_identity(url) for url in proposed) != sorted(urls):
            raise ChangeError('GALLERY_REORDER_ONLY')
        if any(value.get('fileId') == '0' for value in values.values()):
            values = self._bank_values(platform[self.field])
        # Same scImages field shape as the existing gallery helper; preserve the
        # current target's actual fileId and strip UI definitions via contract.
        root = self.contract.values_only(schema, operation='update', field_ids=['scImages'])
        target = root.find('./field/complex-value')
        target.clear()
        for slot, url in enumerate(proposed):
            field = ET.SubElement(target, 'field', id=f'scImages_{slot}', type='input')
            value = deepcopy(values[self._image_identity(url)])
            # Submit the exact current formal URL together with the verified bank ID.
            value.text = url.removeprefix('https:')
            field.append(value)
        return ET.tostring(root, encoding='unicode')
