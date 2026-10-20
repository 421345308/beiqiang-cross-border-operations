"""Product identity, supply and Alibaba state have separate editable stores.

ProductRegistry is a compatibility boundary for existing local tools: JSON text
reads compose the stores; writes split them back without touching Douyin data.
New consumers should read the domain file they actually need.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from contextlib import contextmanager

PRODUCTS = Path('00_总控台/产品中心/数据/产品.json')
SUPPLY = Path('00_总控台/产品中心/数据/供应来源.json')
ALIBABA = Path('02_Alibaba运营/05_扩品工程/数据/国际站商品.json')
CHANNEL_FIELDS = ('next_action', 'dossier_path', 'content_quality_revision')
CHANNEL_CLASSIFICATION = ('platform_category_ids', 'store_groups')


def split(data):
    data = copy.deepcopy(data)
    header = {k: data[k] for k in ('schema_version', 'updated_on')}
    products = {**header, 'products': data.pop('products')}
    supply = {**header, 'sources': data.pop('sources')}
    for key in ('imported_evidence', 'suppliers'):
        if key in data:
            supply[key] = data.pop(key)
    if 'identity_consolidation' in data:
        products['identity_consolidation'] = data.pop('identity_consolidation')
    states = {}
    for product in products['products']:
        state = {k: product.pop(k) for k in CHANNEL_FIELDS if k in product}
        classification = product.get('classification', {})
        channel = {k: classification.pop(k) for k in CHANNEL_CLASSIFICATION if k in classification}
        if channel:
            state['classification'] = channel
        if state:
            states[product['id']] = state
    data['product_state'] = states
    return {PRODUCTS: products, SUPPLY: supply, ALIBABA: data}


def compose(parts):
    products, supply, channel = (copy.deepcopy(parts[p]) for p in (PRODUCTS, SUPPLY, ALIBABA))
    states = channel.pop('product_state', {})
    result = {**channel, **supply, **products}
    # Store maintenance dates do not replace observation dates on actual objects.
    result['updated_on'] = max(p.get('updated_on', '') for p in parts.values())
    for product in result['products']:
        state = states.get(product['id'], {})
        for key, value in state.items():
            if key == 'classification':
                product.setdefault(key, {}).update(value)
            else:
                product[key] = value
    return result


def atomic_write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes().replace(b'\r\n', b'\n') == body.replace(b'\r\n', b'\n'):
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(body)
        temporary = Path(stream.name)
    try:
        # Antivirus/indexer reads can briefly deny replacement on Windows.
        # Keep the atomic operation and the surrounding stale-writer lock.
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.2 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


class ProductRegistry:
    """Compatibility JSON-text interface; never a fourth editable registry file.

    A stale writer fails rather than replacing another task's newer domain data.
    Domain operations should finish a read/modify/write cycle in one process.
    """
    def __init__(self, root):
        self.root = Path(root)
        self._snapshot = None

    def exists(self):
        return all((self.root / p).is_file() for p in (PRODUCTS, SUPPLY, ALIBABA))

    def __str__(self):
        return str(self.root / PRODUCTS)

    @contextmanager
    def locked(self):
        path = self.root/'08_工具链/06_工作区维护/.local/product-registry.lock'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+b') as stream:
            if stream.tell() == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def read_bytes(self):
        return self.read_text().encode('utf-8')

    def write_registry(self, data):
        return self.write_text(json.dumps(data, ensure_ascii=False))

    def read_text(self, *args, **kwargs):
        with self.locked():
            return self._read_text()

    def _read_text(self):
        parts = {}
        self._snapshot = {}
        for path in (PRODUCTS, SUPPLY, ALIBABA):
            raw = (self.root / path).read_bytes()
            self._snapshot[path] = hashlib.sha256(raw).hexdigest()
            parts[path] = json.loads(raw.decode('utf-8-sig'))
        return json.dumps(compose(parts), ensure_ascii=False)

    def write_text(self, text, *args, **kwargs):
        with self.locked():
            return self._write_text(text)

    def _write_text(self, text):
        if self._snapshot is None:
            raise RuntimeError('Read the product stores before writing')
        for path, digest in self._snapshot.items():
            if hashlib.sha256((self.root / path).read_bytes()).hexdigest() != digest:
                raise RuntimeError(f'Product store changed concurrently; reload: {path}')
        parts = split(json.loads(text))
        for path, data in parts.items():
            # Keep an unchanged domain's own maintenance date.
            previous = json.loads((self.root / path).read_text(encoding='utf-8-sig'))
            if {k: v for k, v in previous.items() if k != 'updated_on'} == {k: v for k, v in data.items() if k != 'updated_on'}:
                data['updated_on'] = previous['updated_on']
            atomic_write(self.root / path, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        self._read_text()
        return len(text)
