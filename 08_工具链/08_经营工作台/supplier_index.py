"""Read-only supplier matching projection from the product centre.

The supplier profile is curated evidence, not a new supplier database.  Source
links and product relationships are clues and never establish current supply,
factory identity or customisation capability by themselves.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

from business import PRODUCTS, SUPPLY


# Do not put prices or contact details in this projection, even if someone
# mistakenly includes them in one of the otherwise public free-text fields.
_PRIVATE_TEXT = re.compile(
    r'(?i)(?<!\d)(?:(?:\+|00)?86[\s._:-]*)?1[\s._:-]*[3-9](?:[\s._:-]*\d){9}(?!\d)'
    r'|(?<![A-Za-z0-9])(?:(?:\+|00)?86[\s._:-]*)?0[1-9]\d{1,2}[\s._:-]+\d(?:[\s._:-]?\d){6,7}(?!\d)'
    r'|[\w.+-]+@[\w.-]+\.[a-z]{2,}'
    r'|(?:¥|￥|\$|人民币|美元|美金|\b(?:CNY|RMB|USD)\b)\s*\d'
    r'|\d(?:[\d,.]*\s*)(?:元|美元|人民币|美金)(?:\s*(?:/|每|一|每双|每件|每对|/双|/件))?'
    r'|(?:报价|成本价|拿货价|采购价|供货价|单价|批发价|出厂价)\D{0,6}\d'
    r'|(?:微信|wechat|weixin)\s*[:：]\s*\S+'
)
_PRIVATE_QUERY = re.compile(r'(?i)(?:token|auth|secret|session|password|passwd|pwd|phone|mobile|email|contact|wechat|weixin|price|cost)')
_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z')
_PHONE_IN_ID = re.compile(
    # Identifiers can embed mobile numbers directly next to letters, with an
    # optional China country code and punctuation within the number.
    r'(?<!\d)(?:(?:00)?86[-_.:]*)?1[-_.:]*[3-9](?:[-_.:]*\d){9}(?!\d)'
    # A landline area code must start with 01–09; model/page pairs such as
    # H008-2094876 and A009-2462264 are not valid area-code prefixes.
    r'|(?<![A-Za-z0-9])(?:(?:00)?86[-_.:]*)?0[1-9]\d{1,2}[-_.:]+\d(?:[-_.:]?\d){6,7}(?!\d)'
)


def _text(value):
    if not isinstance(value, str):
        return ''
    value = value.strip()
    return '' if _PRIVATE_TEXT.search(value) else value


def _identifier(value):
    """Source IDs are structured keys; a model followed by a page ID is not a telephone."""
    if not isinstance(value, str):
        return ''
    value = value.strip()
    return value if _IDENTIFIER.fullmatch(value) and not _PHONE_IN_ID.search(value) else ''


def _url(value):
    value = _text(value)
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() != 'https' or not parsed.hostname or parsed.username or parsed.password:
            return ''
        if _PRIVATE_TEXT.search(unquote(value)) or any(_PRIVATE_QUERY.search(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
            return ''
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))
    except ValueError:
        return ''


def _path(value):
    value = _text(value).replace('\\', '/')
    parts = value.split('/')
    if not value or value.startswith('/') or re.match(r'^[A-Za-z]:', value) or any(p in ('.', '..') or p.startswith('.') for p in parts):
        return ''
    return value


def _evidence(value):
    result = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        result.append({
            'kind': _text(item.get('kind')) or '未知',
            'url': _url(item.get('url')),
            'path': _path(item.get('path')),
            'observed_on': _text(item.get('observed_on')),
            'summary': _text(item.get('summary')),
        })
    return result


def _claims(value):
    result = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        result.append({
            'name': _text(item.get('name')),
            'scope': _text(item.get('scope')),
            'source_ids': [_identifier(s) for s in item.get('source_ids', []) if _identifier(s)] if isinstance(item.get('source_ids', []), list) else [],
            'evidence': _evidence(item.get('evidence')),
        })
    return result


def _claim(value):
    value = value if isinstance(value, dict) else {}
    return {'status': _text(value.get('status')) or '未知', 'summary': _text(value.get('summary')), 'evidence': _evidence(value.get('evidence'))}


def _profile(value):
    value = value if isinstance(value, dict) else {}
    location = value.get('location') if isinstance(value.get('location'), dict) else {}
    interactions = []
    for item in value.get('owner_interactions', []) if isinstance(value.get('owner_interactions'), list) else []:
        if isinstance(item, dict):
            interactions.append({'summary': _text(item.get('summary')), 'evidence': _evidence(item.get('evidence'))})
    return {
        'product_directions': _claims(value.get('product_directions')),
        'process_directions': _claims(value.get('process_directions')),
        'factory_identity': _claim(value.get('factory_identity')),
        'customization': _claim(value.get('customization')),
        'location': {'city': _text(location.get('city')), 'type': _text(location.get('type')), 'summary': _text(location.get('summary')), 'evidence': _evidence(location.get('evidence'))},
        'owner_interactions': interactions,
        'open_questions': [_text(q) for q in value.get('open_questions', []) if _text(q)] if isinstance(value.get('open_questions'), list) else [],
    }


def _contains(value, needle):
    def normalize(text):
        text = unicodedata.normalize('NFKC', text).casefold().replace('號', '号')
        digits = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9'}
        return re.sub(r'([一二三四五六七八九])号', lambda match: digits[match.group(1)] + '号', text)
    return not needle or normalize(needle) in normalize(json.dumps(value, ensure_ascii=False))


def supplier_index(root, *, q='', product='', process='', city='', identity='', customization_evidence=''):
    """Return safe fields and evidence from current source files; never cache them."""
    root = Path(root)
    supply = json.loads((root / SUPPLY).read_text(encoding='utf-8'))
    products = json.loads((root / PRODUCTS).read_text(encoding='utf-8'))
    relations = defaultdict(list)
    for item in products.get('products', []):
        if not isinstance(item, dict):
            continue
        classification = item.get('classification') if isinstance(item.get('classification'), dict) else {}
        intents = classification.get('local_intent_candidates', [])
        product_info = {
            'id': _identifier(item.get('id')),
            'current_model': _text(item.get('current_model')),
            'aliases': [_text(a) for a in item.get('aliases', []) if _text(a)] if isinstance(item.get('aliases'), list) else [],
            'source_state': _text(item.get('source_state')),
            'category_clues': [_text(a) for a in intents if _text(a)] if isinstance(intents, list) else [],
        }
        references = [('adopted', item.get('adopted_source_id')), ('reference', item.get('reference_source_id'))]
        candidates = item.get('candidate_source_ids', [])
        references.extend(('candidate', candidate) for candidate in candidates if isinstance(candidate, str)) if isinstance(candidates, list) else None
        for role, source_id in references:
            if isinstance(source_id, str) and source_id:
                relations[source_id].append({**product_info, 'role': role})

    sources = {}
    for item in supply.get('sources', []):
        if not isinstance(item, dict) or not _identifier(item.get('id')):
            continue
        source_id = _identifier(item['id'])
        sources[source_id] = {
            'id': source_id,
            'model': _text(item.get('model')),
            'supplier_label': _text(item.get('supplier')),
            'url': _url(item.get('url')),
            'observed_at': _text(item.get('observed_at')),
            'products': relations.get(source_id, []),
        }

    suppliers = []
    linked_ids = set()
    for item in supply.get('suppliers', []):
        if not isinstance(item, dict):
            continue
        source_ids = item.get('source_ids') if isinstance(item.get('source_ids'), list) else []
        linked_ids.update(source_id for source_id in source_ids if source_id in sources)
        names = item.get('names') if isinstance(item.get('names'), list) else []
        suppliers.append({
            'id': _identifier(item.get('id')),
            'names': [_text(name) for name in names if _text(name)],
            'shop_url': _url(item.get('shop_url')),
            'profile': _profile(item.get('matching_profile')),
            'has_profile': isinstance(item.get('matching_profile'), dict) and bool(item.get('matching_profile')),
            'sources': [sources[source_id] for source_id in source_ids if source_id in sources],
        })

    options = {
        'identities': sorted({row['profile']['factory_identity']['status'] for row in suppliers}),
        'cities': sorted({row['profile']['location']['city'] for row in suppliers if row['profile']['location']['city']}),
        'customization_evidence': sorted({e['kind'] for row in suppliers for e in row['profile']['customization']['evidence']}),
    }
    q, product, process, city, identity, customization_evidence = (str(v or '').strip() for v in (q, product, process, city, identity, customization_evidence))

    def matches(row):
        profile = row['profile']
        category_clues = [p['category_clues'] for src in row['sources'] for p in src['products']]
        custom_kinds = [e['kind'] for e in profile['customization']['evidence']]
        return (
            _contains(row, q)
            and _contains([profile['product_directions'], category_clues], product)
            and _contains(profile['process_directions'], process)
            and (not city or profile['location']['city'] == city)
            and (not identity or profile['factory_identity']['status'] == identity)
            and (not customization_evidence or customization_evidence in custom_kinds)
        )

    unmatched = [source for source_id, source in sources.items() if source_id not in linked_ids]
    # An unassociated source can be searched by item or associated product, but
    # cannot satisfy filters that imply a supplier profile.
    if process or city or identity or customization_evidence:
        unmatched = []
    else:
        unmatched = [source for source in unmatched if _contains(source, q) and _contains([p['category_clues'] for p in source['products']], product)]
    found = [row for row in suppliers if matches(row)]
    found.sort(key=lambda row: not row['has_profile'])
    if q:
        for row in found:
            row['sources'].sort(key=lambda source: not _contains(source, q))
    return {'suppliers': found, 'unassociated_sources': unmatched, 'options': options}
