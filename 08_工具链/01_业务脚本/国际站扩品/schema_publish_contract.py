"""Offline evidence routing and shared Schema payload contract. No API calls."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import math
import re
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

METHODS = {"createDraft": "alibaba.icbu.product.schema.add.draft",
           "create": "alibaba.icbu.product.schema.add",
           "update": "alibaba.icbu.product.schema.update"}
CREATE_FIELDS = frozenset("catId icbuCatProp saleProp sku productTitle productKeywords scImages pkgMeasure pkgWeight ladderPeriod priceUnit shippingTemplate productGroup ladderPrice customMoreProperty saleType scPrice minOrderQuantity productDescType detailImage textDesc companyImage companyDesc companyFaqDesc logisticsProperty semiManagedPeriod".split())

def values_only(full_root, *, operation="create", field_ids=None):
    """Strip UI definitions, preserve actual nested values; updates keep SKU IDs.

    Explicit field_ids come from the current category Schema and intended scope.
    No inferred defaults or generic deletion semantics are introduced here.
    """
    if operation not in METHODS:
        raise ValueError("unknown operation")
    if operation == "update" and field_ids is None:
        raise ValueError("update requires explicit target fields and dependencies")
    allowed = CREATE_FIELDS if field_ids is None else set(field_ids)
    root = ET.Element("itemSchema")
    for field in full_root.findall("./field"):
        if field.get("id") not in allowed:
            continue
        clone = deepcopy(field)
        for parent in list(clone.iter()):
            for child in list(parent):
                if child.tag in ("rules", "options", "fields", "label-group") or (
                    operation != "update" and child.tag == "field" and child.get("id") == "skuId"
                ):
                    parent.remove(child)
        root.append(clone)
    return root

class UnsupportedProductModel(ValueError):
    """Current Schema does not supply a model field/known input representation."""

def model_field_definition(current_schema):
    parent = current_schema.find("./field[@id='icbuCatProp']")
    if parent is None:
        raise UnsupportedProductModel('unsupported_model_field: icbuCatProp absent')
    candidates = {}
    names = {'model number', 'model no.', 'model no', '型号', '产品型号'}
    for path in ('./fields/field', './complex-value/field'):
        for field in parent.findall(path):
            if field.get('name', '').strip().casefold() in names:
                candidates.setdefault(field.get('id'), field)
    if len(candidates) != 1:
        raise UnsupportedProductModel('unsupported_model_field: current Schema has no unique model field; never infer p-3 from SKU')
    return next(iter(candidates.values()))

def serialize_product_attribute(current_schema, field_id, expected_text, *, format_reference=None):
    """Serialize a product input property using current/verified value shape.

    No marker is derived from a field ID. Known fixture formats are narrowly
    matched by the current field ID, type and semantic name, not category support.
    """
    if not isinstance(expected_text, str) or not expected_text.strip():
        raise ValueError('expected product attribute text is required')
    parent = current_schema.find("./field[@id='icbuCatProp']")
    if parent is None:
        raise UnsupportedProductModel('unsupported_attribute_field')
    definition = parent.find("./fields/field[@id='" + field_id + "']")
    actual = parent.find("./complex-value/field[@id='" + field_id + "']")
    if definition is None:
        definition = actual
    if definition is None or definition.get('type') != 'input':
        raise UnsupportedProductModel('unsupported_attribute_field_or_type')
    for rule in definition.findall('./rules/rule'):
        if rule.get('name') == 'maxLengthRule' and rule.get('unit') == 'byte':
            length, limit = len(expected_text.encode('utf-8')), int(rule.get('value'))
            if length > limit or (rule.get('exProperty') == 'exclude' and length == limit):
                raise ValueError('product attribute exceeds current byte limit')
        if rule.get('name') == 'valueAttributeRule' and rule.get('value') != 'inputValue':
            raise UnsupportedProductModel('unsupported_attribute_value_rule')
    value = actual.find('./value') if actual is not None else None
    if value is None or 'inputValue' not in value.attrib or not re.fullmatch(r'-\d+', value.text or ''):
        value = None
        if format_reference is not None:
            if format_reference.get('id') != field_id or format_reference.get('type') != definition.get('type'):
                raise UnsupportedProductModel('attribute_format_reference_mismatch')
            value = format_reference.find('./value')
        else:
            registry = json.loads(Path(__file__).with_name('schema_contract_fixtures').joinpath('model_number_formats.json').read_text(encoding='utf-8'))
            for item in registry['formats']:
                if item['field_id'] == field_id and item['field_type'] == definition.get('type') and item['field_name'].casefold() == definition.get('name', '').casefold():
                    value = ET.fromstring(item['value_template'])
                    break
    if value is None or 'inputValue' not in value.attrib or not re.fullmatch(r'-\d+', value.text or ''):
        raise UnsupportedProductModel('unsupported_attribute_value_format: acquire rendered or verified format; never guess negative marker')
    field = ET.Element('field', dict(definition.attrib))
    value = deepcopy(value)
    value.set('inputValue', expected_text)
    field.append(value)
    return field

def serialize_product_model(current_schema, expected_model, *, format_reference=None):
    definition = model_field_definition(current_schema)
    return serialize_product_attribute(current_schema, definition.get('id'), expected_model,
                                       format_reference=format_reference)

def validate_model_payload(payload, record):
    """A product attribute must contain the model; SKU outer codes cannot satisfy it."""
    if not record:
        raise ValueError('expected_model/product attribute representation required')
    nodes = payload.findall("./field[@id='icbuCatProp']/complex-value/field[@id='" + record['field_id'] + "']")
    if len(nodes) != 1 or nodes[0].get('type') != record['field_type']:
        raise ValueError('product-level model missing/ambiguous; SKU outerId is not product model')
    value = nodes[0].find('./value')
    if value is None or value.text != record['value_text'] or value.attrib != record['value_attributes'] or value.get('inputValue') != record['expected_model']:
        raise ValueError('model representation differs from current/verified inputValue format')

def create_inventory_input_record(payload, current_schema=None):
    """Observe literal create-side fields, never infer stock or deletion semantics."""
    sku = payload.find("./field[@id='sku']")
    items = sku.findall('./complex-values') if sku is not None else []
    present, omitted = [], []
    for index, item in enumerate(items):
        stock = item.find("./field[@id='skuStock']")
        if stock is None:
            omitted.append(index)
        else:
            present.append({'sku_index': index, 'raw_field_xml': ET.tostring(stock, encoding='unicode'),
                            'raw_values': [{'text':v.text, 'attributes':dict(v.attrib)} for v in stock.findall('./values/value')]})
    definitions = current_schema.findall("./field[@id='sku']/fields/field[@id='skuStock']") if current_schema is not None else []
    required = any(r.get('name') == 'requiredRule' and r.get('value') == 'true' for f in definitions for r in f.findall('./rules/rule'))
    requirement = 'required' if required else ('no_required_rule_declared' if definitions else 'not_exposed')
    return {'phase':'create_input', 'sku_field_present':sku is not None, 'sku_count':len(items),
            'status':'omitted_all' if not present else ('explicit_all' if not omitted else 'mixed'),
            'omitted_sku_indexes':omitted, 'raw_present_fields':present,
            'schema_requirement':requirement,
            'limits':'Literal request fields only; omitted/empty/999 do not establish physical stock or deletion semantics.'}

def validate_create_inventory_payload(payload, record):
    if record is None:
        raise ValueError('create inventory input provenance required')
    def signature(data):
        return (data['sku_field_present'], data['sku_count'], data['status'], data['omitted_sku_indexes'],
                [(row['sku_index'],ET.fromstring(row['raw_field_xml']).attrib,row['raw_values']) for row in data['raw_present_fields']])
    if signature(create_inventory_input_record(payload)) != signature(record):
        raise ValueError('create-side inventory changed from explicit input; never add Schema defaults')

def safe_exception_evidence(exc, config=None):
    """Bounded diagnostics only: no request, argv, headers or credential dumps."""
    from urllib.parse import quote, quote_plus
    secret_keys = {'accesstoken', 'refreshtoken', 'appsecret', 'clientsecret',
                   'appkey', 'clientid', 'password', 'secret', 'token', 'sign',
                   'signature', 'session', 'authorization', 'apikey'}
    def keyname(key):
        return re.sub(r'[^a-z0-9]', '', str(key).lower())
    secrets = set()
    def collect_secret_values(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if keyname(key) in secret_keys and isinstance(value, str) and value:
                    secrets.update((value, quote(value, safe=''), quote_plus(value),
                                    json.dumps(value)[1:-1]))
                elif isinstance(value, dict):
                    collect_secret_values(value)
    collect_secret_values(config or {})
    secret_label = r'(?:access[_-]?token|refresh[_-]?token|app[_-]?secret|client[_-]?secret|app[_-]?key|client[_-]?id|password|secret|token|sign|signature|session|authorization|api[_-]?key)'
    value_pattern = r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s&,;<>}\]]+)'''
    labelled = re.compile(r'(?i)(?<![\w])(["\x27]?' + secret_label + r'["\x27]?\s*[:=]\s*)' + value_pattern)
    def text(value, limit=1200):
        if isinstance(value, bytes):
            value = value.decode('utf-8', errors='replace')
        value = str(value)
        # A RuntimeError may stringify argv without having a .cmd attribute.
        # Never retain any part of such free text (including a multiline body).
        if re.search(r'(?i)\b(?:command|cmd|argv)\b|\bcurl(?:\.exe)?\b|--(?:data(?:-binary|-raw)?|url|header)\b', value):
            return '[COMMAND_TEXT_OMITTED]'
        # Authentication is a whole header value, not its first word. Discard
        # the rest of the line rather than retain Basic/base64 or extra tokens.
        value = re.sub(r'''(?im)(["\x27]?authorization["\x27]?\s*[:=]\s*)[^\r\n]*''',
                       lambda m:m.group(1)+'[AUTHORIZATION_REDACTED]', value)
        value = re.sub(r'(?i)\b(?:Basic|Bearer)\s+[^\s,;"\x27]+',
                       '[AUTH_SCHEME_REDACTED]', value)
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'https?://[^\s"\x27<>]+', '[URL_REDACTED]', value, flags=re.I)
        value = re.sub(r'(?i)\bBearer\s+[^\s,;"\x27]+', 'Bearer [REDACTED]', value)
        value = labelled.sub(lambda m:m.group(1)+'[REDACTED]', value)
        value = re.sub(r'(?i)(?<![a-z0-9])[a-f0-9]{32,128}(?![a-z0-9])', '[HEX_REDACTED]', value)
        return value[:limit]
    chain, seen = [], set()
    current = exc
    while current is not None and id(current) not in seen and len(chain) < 4:
        chain.append(current); seen.add(id(current))
        current = current.__cause__ or current.__context__
    telemetry = {}
    for error in reversed(chain):
        item = getattr(error, 'transport_evidence', None)
        if isinstance(item, dict):
            telemetry.update(item)
    def number(value):
        return value if type(value) is int else None
    exit_code = number(telemetry.get('curl_exit_code'))
    http_status = number(telemetry.get('http_status'))
    raw = telemetry.get('response_body')
    stderr = telemetry.get('stderr')
    for error in chain:
        if exit_code is None:
            exit_code = number(getattr(error, 'returncode', None))
        if http_status is None and type(getattr(error, 'code', None)) is int:
            candidate = error.code
            if 100 <= candidate <= 599:
                http_status = candidate
        if raw is None:
            raw = getattr(error, 'stdout', None) or getattr(error, 'output', None)
        if stderr is None:
            stderr = getattr(error, 'stderr', None)
    # Legacy strings can retain explicit codes but cannot prove send phase.
    if exit_code is None:
        match = re.search(r'(?i)curl exit\s+(-?\d+)', str(exc))
        if match: exit_code = int(match.group(1))
    if http_status is None:
        match = re.search(r'\bHTTP\s+(\d{3})\b', str(exc))
        if match: http_status = int(match.group(1))
    allowed = {'code','sub_code','error_code','message','msg','sub_msg','error_message',
               'request_id','requestId','trace_id','traceId','biz_success','success','product_id','productId'}
    refs = {}
    def summarize(obj, depth=0):
        if depth > 6:return '[DEPTH_LIMIT]'
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key in allowed and isinstance(value, (str,int,float,bool,type(None))):
                    result[key] = text(value) if isinstance(value,str) else value
                    if key in ('request_id','requestId','trace_id','traceId') and value:
                        refs[key] = result[key]
                elif key in ('error_response','error','data','result','model','response'):
                    if isinstance(value,str):
                        try:value=json.loads(value)
                        except (ValueError,TypeError):continue
                    result[key] = summarize(value,depth+1)
            return result
        if isinstance(obj,list):return [summarize(v,depth+1) for v in obj[:8]]
        return None
    if isinstance(raw, bytes):raw=raw.decode('utf-8',errors='replace')
    if isinstance(raw,str):
        try:parsed=json.loads(raw)
        except (ValueError,TypeError):parsed=None
    elif isinstance(raw,(dict,list)):
        parsed=raw
    else:parsed=None
    summary = {'format':'json', 'fields':summarize(parsed)} if parsed is not None else {
        'format':'text' if raw is not None else 'not_captured',
        'excerpt':text(raw) if raw is not None else None}
    # Explicit transport metadata only, not curl-code heuristics about sending.
    phase = telemetry.get('phase', 'unknown')
    if phase not in ('pre_request','subprocess_launch','transport','http_response','response_decode'):
        phase = 'unknown'
    sent = telemetry.get('request_sent')
    sent = sent if type(sent) is bool else None
    message = type(exc).__name__ + ': transport process exception; command omitted' if hasattr(exc, 'cmd') else str(exc)
    return {'exception_type':type(exc).__name__, 'message':text(message),
            'transport_phase':phase, 'request_sent':sent,
            'curl_exit_code':exit_code, 'http_status':http_status,
            'business_refs':refs, 'response_summary':summary,
            'stderr_excerpt':text(stderr) if stderr is not None else None,
            'cause_types':[type(error).__name__ for error in chain[1:]],
            'limits':'Unavailable facts remain null/unknown. Curl errors and absence in catalog do not prove an uncommitted write; no automatic retry.'}


def classify_result(operation, response):
    """Business acceptance is separate from formal/public verification."""
    if operation not in METHODS:
        raise ValueError("unknown operation")
    if not isinstance(response, dict):
        return "unverified_business_result"
    objects = []
    def collect(value):
        if isinstance(value, dict):
            objects.append(value)
            for key, child in value.items():
                if key in ('data', 'result', 'model') and isinstance(child, str) and child.lstrip().startswith(('{', '[')):
                    try:
                        collect(json.loads(child))
                    except (ValueError, TypeError):
                        pass
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    collect(response)
    if any(o.get("error_response") or o.get("error") or o.get("error_code") or
           o.get("sub_code") or o.get("biz_success") is False or
           o.get("success") is False or o.get("model") is False or
           str(o.get("code", "0")) not in ("0", "", "None") for o in objects):
        return "business_rejected"
    # Boolean-looking strings and conflicting/malformed flags are ambiguous.
    if any(k in o and type(o[k]) is not bool for o in objects for k in ("success", "biz_success")):
        return "unverified_business_result"
    accepted = any(o.get("biz_success") is True for o in objects)
    product_id = next((o[k] for o in objects for k in ("product_id", "productId") if o.get(k)), None)
    if not accepted or (operation != "update" and not product_id):
        return "unverified_business_result"
    return "draft_created_needs_readback" if operation == "createDraft" else "submitted_needs_readback"

def field_snapshot(root):
    """Canonical value-tree comparison, ignoring UI names/types/rules."""
    root = values_only(root, operation="update", field_ids={f.get('id') for f in root.findall('./field')})
    # The platform normalizes typed model -3 to -2. Compare its actual inputValue,
    # not this internal negative marker; serialized requests retain the raw marker.
    try:
        definition = model_field_definition(root)
        value = root.find("./field[@id='icbuCatProp']/complex-value/field[@id='" + definition.get('id') + "']/value")
        if value is not None and 'inputValue' in value.attrib and re.fullmatch(r'-\d+', value.text or ''):
            value.text = '__typed_model_marker__'
    except UnsupportedProductModel:
        pass
    def tree(node):
        attrs = {k: v for k, v in node.attrib.items() if k not in ('name', 'type', 'displayName')}
        return [node.tag, [[k, v] for k, v in sorted(attrs.items())], (node.text or '').strip(), [tree(c) for c in node]]
    return {f.get('id'): tree(f) for f in root.findall('./field')}

def replacement_payload_snapshot(payload):
    """Create-side content, excluding only inventory and prior platform SKU IDs."""
    clone=values_only(payload,operation='create',field_ids={f.get('id') for f in payload.findall('./field')})
    for parent in list(clone.iter()):
        for child in list(parent):
            if child.tag=='field' and child.get('id')=='skuStock':parent.remove(child)
    return field_snapshot(clone)


def validate_replacement_acceptance(accepted_xml, replacement):
    """Recompute formal/SKU checks; bind visual reviews to actual hashed bytes."""
    import hashlib
    accepted=ET.fromstring(accepted_xml)
    digest=hashlib.sha256(accepted_xml.encode('utf-8')).hexdigest()
    old_id=str(replacement['replacement_source_product_id'])
    expected=replacement_payload_snapshot(accepted)
    media_ids={f.get('id') for f in accepted.findall('./field') if f.get('id') in ('scImages','detailImage','companyImage')}
    urls={fid:set() for fid in media_ids}
    for field in accepted.findall('./field'):
        if field.get('id') not in media_ids:continue
        for value in field.iter('value'):
            for text in [value.text,*value.attrib.values()]:
                if isinstance(text,str) and text.startswith(('https://','http://')):urls[field.get('id')].add(text)
    for record in replacement.get('acceptance_records') or []:
        if str(record.get('product_id'))!=old_id or record.get('accepted_payload_sha256')!=digest:continue
        formal=record.get('formal_readback') or {}
        raw=formal.get('xml')
        if not isinstance(raw,str) or not formal.get('request_id') or str(formal.get('product_id'))!=old_id:continue
        try:stamp=datetime.fromisoformat(formal.get('acquired_at'))
        except (ValueError,TypeError):continue
        if stamp.tzinfo is None or hashlib.sha256(raw.encode('utf-8')).hexdigest()!=formal.get('schema_sha256'):continue
        result=verify_content_details('submitted_needs_readback',expected,field_snapshot(ET.fromstring(raw)),operation='create')
        if result['content_status']!='formal_fields_verified':continue
        media=record.get('media_acceptance') or {}
        if (media.get('status')!='verified' or str(media.get('product_id'))!=old_id or
            media.get('accepted_payload_sha256')!=digest or set(media.get('verified_field_ids') or [])!=media_ids):continue
        covered={fid:set() for fid in media_ids};bad=False
        for check in media.get('checks') or []:
            fid=check.get('field_id');url=check.get('url')
            if fid not in urls or url not in urls[fid] or check.get('content_match') is not True or not check.get('review_evidence'):
                bad=True;break
            for prefix in ('source','actual'):
                data=check.get(prefix+'_bytes')
                if not isinstance(data,bytes) or not data or hashlib.sha256(data).hexdigest()!=check.get(prefix+'_sha256'):
                    bad=True;break
            if bad:break
            covered[fid].add(url)
        if bad or any(not urls[fid] or covered[fid]!=urls[fid] for fid in media_ids):continue
        return {'status':'verified','product_id':old_id,'accepted_payload_sha256':digest,
                'formal_field_ids':sorted(expected),'formal_request_id':formal['request_id'],
                'sku_verification':result['sku_verification'],'media_field_ids':sorted(media_ids),
                'media_url_count':sum(len(v) for v in covered.values())}
    raise ValueError('replacement requires complete hash-bound formal fields/SKU and actual media acceptance; submission success or partial review is insufficient')


def validate_replacement_mapping(payload, replacement):
    """Bind a single authorized old product to the complete accepted payload.

    This is a pre-create transition only. It never authorizes old-product off,
    changes a model to hide duplication, or exempts another catalog product.
    """
    import hashlib
    replacement=deepcopy(replacement)
    old_id=replacement.get('replacement_source_product_id')
    if type(old_id) not in (str,int) or not str(old_id).isdigit():
        raise ValueError('replacement requires one explicit source product ID')
    if not replacement.get('authorization_evidence'):
        raise ValueError('replacement requires explicit authorization evidence')
    accepted_xml=replacement.get('accepted_payload_xml')
    if not isinstance(accepted_xml,str):
        raise ValueError('replacement requires the complete accepted source payload')
    accepted=ET.fromstring(accepted_xml)
    mapping=replacement.get('acceptance_map') or {}
    digest=hashlib.sha256(accepted_xml.encode('utf-8')).hexdigest()
    ids={f.get('id') for f in accepted.findall('./field')}
    if (str(mapping.get('product_id'))!=str(old_id) or
            mapping.get('accepted_payload_sha256')!=digest or not mapping.get('evidence') or
            set(mapping.get('accepted_field_ids') or [])!=ids or
            set(mapping.get('verified_field_ids') or [])!=ids):
        raise ValueError('replacement acceptance map must bind old ID/hash and every accepted payload field')
    acceptance=validate_replacement_acceptance(accepted_xml,replacement)
    if payload.findall(".//field[@id='skuStock']"):
        raise ValueError('replacement clean create requires omitted SKU inventory; never copy stock defaults')
    expected=replacement_payload_snapshot(accepted)
    actual=replacement_payload_snapshot(payload)
    if not expected or expected!=actual:
        raise ValueError('replacement payload differs from complete accepted mapping beyond omitted stock/platform SKU IDs')
    fingerprint=hashlib.sha256(json.dumps(actual,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
    return {'replacement_source_product_id':str(old_id),'authorization_evidence':replacement['authorization_evidence'],
            'acceptance_map':{**mapping,'validation_status':'verified'},'acceptance_validation':acceptance,'payload_fingerprint':fingerprint,
            'status':'AUTHORIZED_TRANSITION_OLD_RETAINED',
            'old_product_disposition':'NOT_OFFLINED_PENDING_NEW_ACCEPTANCE',
            'finish_requirements':{'target_score':5.0,'public_qa':True,'full_content_acceptance':True,
                                   'old_off_requires_separate_authorized_action':True},
            'limits':'Allows only temporary replacement coexistence with the one specified old ID. This code performs no publishing/off or completion-state write.'}


def check_listing_differentiation(candidate, catalog, *, operation='create', target_product_id=None, replacement=None):
    """One offline preflight using existing catalog/source/visual evidence.

    Same supplier page is not the same shoe. A different URL, suffix or title
    alone is not proof of a different product. No live calls or state writes.
    """
    from urllib.parse import urlsplit
    def norm(value):
        return ' '.join(str(value or '').casefold().split())
    def image_key(url):
        return urlsplit(url or '').path.rsplit('/',1)[-1].split('.')[0]
    def source_key(record):
        source = record.get('source') or {}
        reference = source.get('reference')
        if reference:
            parsed = urlsplit(reference)
            reference = (parsed.netloc.casefold(), parsed.path.rstrip('/'))
        return reference, norm(source.get('style'))
    def hero_match(left,right):
        a,b=left.get('hero_review') or {},right.get('hero_review') or {}
        urls_a={image_key(x) for x in [left.get('hero_url'),*a.get('aliases',[])] if x}
        urls_b={image_key(x) for x in [right.get('hero_url'),*b.get('aliases',[])] if x}
        if urls_a & urls_b:return True
        if a.get('sha256') and a.get('sha256')==b.get('sha256'):return True
        if a.get('content_key') and a.get('content_key')==b.get('content_key'):return True
        # Different file hashes/URLs alone cannot prove visually different art.
        if a.get('content_key') and b.get('content_key') and a.get('evidence') and b.get('evidence'):
            return False
        return None
    conflicts, comparisons, unknown = [], [], []
    replacement_used=False
    model=norm(candidate.get('model_number')); source=candidate.get('source') or {}
    intent=candidate.get('search_intent') or {};hero=candidate.get('hero_review') or {}
    missing=[]
    for name,valid in [('model_number',bool(model)),('source_identity',all(source_key(candidate)) and bool(source.get('evidence'))),
                       ('search_intent',bool(intent.get('key') and intent.get('evidence'))),
                       ('hero_review',bool(candidate.get('hero_url') and hero.get('evidence') and hero.get('content_key') and hero.get('label_status') in ('not_present','observed')))]:
        if not valid:missing.append(name)
    if hero.get('label_status')=='observed':
        observed=norm(hero.get('visible_model_number'));expected=norm(hero.get('expected_visible_model_number'))
        if not observed or not expected:missing.append('hero_visible_model_number')
        elif observed!=expected:
            conflicts.append({'product_id':target_product_id or candidate.get('product_id'),
                              'fields':['hero_visible_model_number'],'kind':'identity_mismatch',
                              'observed':hero['visible_model_number'],'expected':hero['expected_visible_model_number']})
    critical={'profile','upper_structure','outsole_structure','closure','lining','functional_use'}
    for other in catalog:
        other_id=str(other.get('product_id') or '')
        if target_product_id and other_id==str(target_product_id):continue
        other_source=other.get('source') or {};same_reference=source_key(candidate)[0] and source_key(candidate)[0]==source_key(other)[0]
        same_style=bool(same_reference and source_key(candidate)[1] and source_key(candidate)[1]==source_key(other)[1])
        same_model=bool(model and model==norm(other.get('model_number')))
        same_hero=hero_match(candidate,other)
        if not (same_reference or same_model or same_hero is True):
            if not all(source_key(other)):unknown.append(other_id)
            continue
        facts=source.get('critical_facts') or {};other_facts=other_source.get('critical_facts') or {}
        differences=[key for key in sorted(critical) if facts.get(key) and other_facts.get(key) and
                     norm(facts[key])!=norm(other_facts[key])]
        facts_proven=bool(source.get('evidence') and other_source.get('evidence'))
        other_intent=other.get('search_intent') or {}
        distinct_intent=bool(intent.get('key') and other_intent.get('key') and intent.get('evidence') and
                             other_intent.get('evidence') and norm(intent['key'])!=norm(other_intent['key']))
        family=norm(candidate.get('existing_family'));same_family=bool(family and family==norm(other.get('existing_family')))
        existing_siblings=(operation=='update' and target_product_id and same_family and
                           model.startswith(family+'-') and norm(other.get('model_number')).startswith(family+'-') and
                           re.fullmatch(r'hr\d+-[a-z]+',model) and
                           re.fullmatch(r'hr\d+-[a-z]+',norm(other.get('model_number'))))
        row={'product_id':other_id,'same_source_style':same_style,'critical_differences':differences,
             'same_model':same_model,'same_hero':same_hero,'distinct_search_intent':distinct_intent}
        comparisons.append(row)
        # An explicit replacement waives only this selected old ID, after full
        # accepted-content validation. It preserves the real public model.
        eligible_replacement=(operation=='create' and replacement and
            str(replacement.get('replacement_source_product_id'))==other_id and
            replacement.get('status')=='AUTHORIZED_TRANSITION_OLD_RETAINED' and
            (replacement.get('acceptance_map') or {}).get('validation_status')=='verified' and
            same_style and facts_proven and not differences and same_model and same_hero is True and
            intent.get('key') and other_intent.get('key') and intent.get('evidence') and other_intent.get('evidence') and
            norm(intent['key'])==norm(other_intent['key']))
        if eligible_replacement:
            replacement_used=True
            row['status']='authorized_replacement_transition'
            continue
        fields=[]
        if same_model:fields.append('model_number')
        if same_hero is True:fields.append('hero_image')
        if intent.get('key') and other_intent.get('key') and norm(intent['key'])==norm(other_intent['key']):fields.append('search_intent')
        # Real structure differences or already-existing family expressions are
        # the only eligible relationships; a new same-shoe ABC is not allowed.
        eligible=bool((differences and facts_proven) or existing_siblings)
        if same_style and facts_proven and not differences and not existing_siblings:
            fields.append('source_identity')
            conflicts.append({'product_id':other_id,'fields':fields,'kind':'duplicate_product'})
        elif fields:
            conflicts.append({'product_id':other_id,'fields':fields,'kind':'differentiation_conflict'})
        elif eligible and distinct_intent and same_hero is False:
            row['status']='distinct_real_style' if differences else 'existing_family_expression'
        else:
            row['status']='unverified';missing.append('comparison:'+other_id)
    if replacement and not replacement_used:missing.append('replacement_source_identity_or_acceptance_not_matched')
    status='BLOCKED_DUPLICATE' if any(x['kind']=='duplicate_product' for x in conflicts) else (
        'BLOCKED_DIFFERENTIATION' if conflicts else ('UNVERIFIED' if missing else 'PASS'))
    return {'status':status,'conflicts':conflicts,'comparisons':comparisons,
            'replacement_transition':replacement if replacement_used else None,
            'missing_evidence':sorted(set(missing)),'unassociated_catalog_ids':unknown,
            'scope':'Provided local catalog/source evidence only; unknown records are not duplicates or proof of global clearance. No authorization, traffic or platform-policy exemption inferred.'}


def differentiation_payload_binding(payload):
    """Bind the review to actual model and hero values, not a handwritten label."""
    definition=model_field_definition(payload)
    value=payload.find("./field[@id='icbuCatProp']/complex-value/field[@id='"+definition.get('id')+"']/value")
    hero=payload.find("./field[@id='scImages']/complex-value/field[@id='scImages_0']/value")
    title=payload.find("./field[@id='productTitle']/value")
    return {'model_number':value.get('inputValue') or value.text if value is not None else None,
            'hero_url':hero.text if hero is not None else None,
            'title':title.text if title is not None else None}


def prepare_differentiation_review(payload, context, *, operation, target_product_id=None):
    binding=differentiation_payload_binding(payload)
    candidate=deepcopy((context or {}).get('candidate') or {})
    review=candidate.get('hero_review') or {}
    reviewed_urls=[review.get('url'),*review.get('aliases',[])]
    # Visual evidence must correspond to the actual uploaded image being sent.
    candidate.update(binding)
    replacement=None
    if (context or {}).get('replacement') is not None:
        replacement=validate_replacement_mapping(payload,context['replacement'])
    report=check_listing_differentiation(candidate,(context or {}).get('catalog') or [],
        operation=operation,target_product_id=target_product_id,replacement=replacement)
    if binding['hero_url'] not in reviewed_urls:
        report['missing_evidence'].append('hero_review_url_not_bound_to_payload')
        if report['status']=='PASS':report['status']='UNVERIFIED'
    report['payload_binding']=binding
    report['evidence_provenance']=(context or {}).get('provenance')
    return report


def require_differentiation_review(payload, listing, *, operation):
    # This guard is for actual new listings with a hero. Low-level serializer
    # unit fixtures with no images and scoped non-image updates are unaffected.
    if operation=='update' or payload.find("./field[@id='scImages']") is None:return
    report=listing.get('differentiation_review')
    if not report or report.get('status')!='PASS':
        raise ValueError('listing differentiation preflight: '+json.dumps(report or {
            'status':'UNVERIFIED','missing_evidence':['local_catalog/source/hero review']},ensure_ascii=False))
    if report.get('payload_binding')!=differentiation_payload_binding(payload):
        raise ValueError('listing differentiation review differs from actual model/hero/title')
    transition=report.get('replacement_transition')
    if transition:
        import hashlib
        if payload.findall(".//field[@id='skuStock']"):
            raise ValueError('replacement inventory omission changed after review')
        fingerprint=hashlib.sha256(json.dumps(replacement_payload_snapshot(payload),sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
        if fingerprint!=transition.get('payload_fingerprint'):
            raise ValueError('replacement accepted payload changed after review')


def keyword_input_contract(current_schema):
    parent=current_schema.find("./field[@id='productKeywords']")
    if parent is None or parent.get('type')!='complex':raise ValueError('current Schema has no supported keyword complex field')
    definitions=parent.findall('./fields/field')
    if not definitions or any(n.get('type')!='input' for n in definitions):raise ValueError('current keyword input definitions unavailable')
    def limit(name):
        rows=parent.findall("./rules/rule[@name='"+name+"']")
        if len(rows)!=1:raise ValueError('current keyword count rule unavailable: '+name)
        value=int(rows[0].get('value'));return value if rows[0].get('exProperty')!='not include' else value+(1 if name.startswith('min') else -1)
    return {'parent':parent,'definitions':definitions,'minimum':limit('minInputNumRule'),'maximum':limit('maxInputNumRule')}


def serialize_product_keywords(current_schema, keywords):
    """Follow actual current input IDs/count/byte/regex rules, without punctuation coercion."""
    values=[keywords] if isinstance(keywords,str) else keywords
    if not isinstance(values,list) or any(not isinstance(v,str) or not v.strip() for v in values):raise ValueError('keywords must be nonempty reviewed strings')
    contract=keyword_input_contract(current_schema)
    if not contract['minimum']<=len(values)<=min(contract['maximum'],len(contract['definitions'])):raise ValueError('keyword count violates current Schema')
    parent=ET.Element('field',id='productKeywords',type='complex');cv=ET.SubElement(parent,'complex-value')
    for text,definition in zip(values,contract['definitions']):
        for rule in [*contract['parent'].findall('./rules/rule'),*definition.findall('./rules/rule')]:
            name=rule.get('name');raw=rule.get('value')
            if name in ('maxLengthRule','minLengthRule'):
                length=len(text.encode('utf-8')) if rule.get('unit')=='byte' else len(text)
                limit=int(raw);exclusive=rule.get('exProperty')=='not include'
                if (name=='maxLengthRule' and (length>limit or exclusive and length==limit)) or (name=='minLengthRule' and (length<limit or exclusive and length==limit)):raise ValueError('keyword length violates current Schema')
            if name=='regexRule':
                matched=re.search(raw,text) is not None
                if (rule.get('exProperty')=='not include' and matched) or (rule.get('exProperty')=='include' and not matched):raise ValueError('keyword content violates current Schema regex')
        child=ET.SubElement(cv,'field',id=definition.get('id'),type='input');ET.SubElement(child,'value').text=text
    return parent


def validate_keyword_payload(current_schema, payload):
    node=payload.find("./field[@id='productKeywords']")
    if node is None:return None
    values=node.findall('./complex-value/field/value')
    if not values or any(v.attrib or list(v) for v in values):raise ValueError('keywords require direct text values; never infer inputValue/negative markers')
    proposed=[v.text for v in values]
    correct=serialize_product_keywords(current_schema,proposed)
    if field_snapshot(ET.fromstring('<itemSchema>'+ET.tostring(node,encoding='unicode')+'</itemSchema>'))!=field_snapshot(ET.fromstring('<itemSchema>'+ET.tostring(correct,encoding='unicode')+'</itemSchema>')):raise ValueError('keyword field IDs/shape differ from current Schema')
    return {'values':proposed,'input_ids':[n.get('id') for n in correct.findall('./complex-value/field')],
            'limits':'Valid request serialization only, never proof of keyword persistence.'}


def compare_keyword_readback(expected, product_get, rendered_schema=None, *, expected_product_id):
    """Official get supports keywords; definitions-only render is unavailable value evidence."""
    expected=[expected] if isinstance(expected,str) else expected
    product=(product_get or {}).get('product')
    result={'status':'unverified_keyword_readback','expected':expected,'get_values':None,'render_values':None,'render_status':'not_read'}
    if rendered_schema is not None:
        node=rendered_schema.find("./field[@id='productKeywords']")
        children=node.findall('./complex-value/field/value') if node is not None else []
        if children:result.update(render_status='values_returned',render_values=[n.text or '' for n in children])
        else:result['render_status']='definitions_only_or_absent'
    if not isinstance(product,dict) or str(product.get('product_id'))!=str(expected_product_id):return result
    actual=product.get('keywords')
    if not isinstance(actual,list) or any(not isinstance(v,str) for v in actual):return result
    result['get_values']=actual
    if product.get('status')!='approved':result['status']='pending_review';return result
    if result['render_values'] is not None and result['render_values']!=actual:result['status']='readback_disagrees';return result
    result['status']='keyword_verified_get' if actual==expected and all(v.strip() for v in actual) else 'keyword_not_persisted'
    return result


def validate_sku_property_pairs(payload):
    """Reject malformed TOP SKU pairs before a create request is sent.

    Evidence: successful 929 pairs use propId:propValueId and p-<id> propName;
    M001 2026-10-03 was explicitly rejected for display labels/bare value IDs.
    This validates serialization only, not category or material support.
    """
    for value in payload.findall("./field[@id='sku']/complex-values/field[@id='props']/values/value"):
        pid, vid = value.get('propId'), value.get('propValueId')
        if not pid or not vid or value.get('propName') != 'p-' + pid or value.text != pid + ':' + vid:
            raise ValueError('SKU property requires p-<propId> name and propId:propValueId value')


def prepare_scoped_listing(current_schema, intended_xml, *, operation, category_id,
                           target_product_id=None, field_ids=(), dependency_ids=(),
                           expected_model=None, model_format_reference=None, differentiation_context=None):
    """Prepare approved explicit values against the target's current Schema.

    Update dependencies are selected from the current target, not historical
    source fields. Their discovery remains the caller's current-Schema review.
    """
    if operation not in METHODS:
        raise ValueError('unknown operation')
    intended_xml = deepcopy(intended_xml)
    current = {f.get('id'): f for f in current_schema.findall('./field')}
    intended = {f.get('id'): f for f in intended_xml.findall('./field')}
    fields, dependencies = set(field_ids), set(dependency_ids)
    if not fields or fields & dependencies:
        raise ValueError('explicit disjoint target fields and dependencies required')
    inventory_input = None
    if operation != 'update':
        if dependencies:
            raise ValueError('new-product dependency values must be explicit verified payload fields; Schema defaults are not product facts')
        inventory_input = create_inventory_input_record(intended_xml, current_schema)
        if inventory_input['schema_requirement'] == 'required' and (inventory_input['omitted_sku_indexes'] or
                any(not row['raw_values'] for row in inventory_input['raw_present_fields'])):
            raise ValueError('current Schema requires stock; obtain verified intended values, never autofill 999')
    if len(intended) != len(intended_xml.findall('./field')) or set(intended) != fields:
        raise ValueError('payload must contain exactly the intended fields; historical full payloads forbidden')
    if not fields.union(dependencies) <= current.keys():
        raise ValueError('target fields/dependencies absent from current Schema')
    model_record = None
    if operation == 'update' and expected_model is None and 'icbuCatProp' in fields:
        try:
            definition = model_field_definition(current_schema)
        except UnsupportedProductModel:
            definition = None
        if definition is not None and intended['icbuCatProp'].find("./complex-value/field[@id='" + definition.get('id') + "']") is not None:
            raise ValueError('model update requires expected_model; cannot accept bare text or SKU substitute')
    if operation != 'update' or expected_model is not None:
        definition = model_field_definition(current_schema)
        if expected_model is None:
            raise ValueError('new product requires expected_model; SKU outerId cannot substitute')
        if 'icbuCatProp' not in fields:
            raise ValueError('icbuCatProp must be an explicit intended field for product model')
        model = serialize_product_model(current_schema, expected_model, format_reference=model_format_reference)
        parent = intended['icbuCatProp']
        cv = parent.find('./complex-value')
        if cv is None:
            cv = ET.SubElement(parent, 'complex-value')
        for old in list(cv.findall("./field[@id='" + definition.get('id') + "']")):
            cv.remove(old)
        cv.append(model)
        value = model.find('./value')
        model_record = {'field_id':model.get('id'), 'field_type':model.get('type'),
                        'expected_model':expected_model, 'value_text':value.text,
                        'value_attributes':dict(value.attrib)}
    if operation == 'update' and not target_product_id:
        raise ValueError('update requires a bound target product ID')
    cat = current_schema.find("./field[@id='catId']/value")
    if cat is not None and cat.text != str(category_id):
        raise ValueError('category differs from current target Schema')
    intended_cat = intended_xml.find("./field[@id='catId']/value")
    if intended_cat is not None and intended_cat.text != str(category_id):
        raise ValueError('payload category differs from current target category')
    merged = ET.Element('itemSchema')
    for field in intended_xml.findall('./field'):
        merged.append(deepcopy(field))
    for field in current_schema.findall('./field'):
        if field.get('id') in dependencies:
            merged.append(deepcopy(field))
    keyword_input=validate_keyword_payload(current_schema,merged) if 'productKeywords' in fields else None
    if 'companyFaqDesc' in fields:
        validate_current_faq(current['companyFaqDesc'], intended['companyFaqDesc'], require_types=operation != 'update')
    if operation == 'update' and 'sku' in fields.union(dependencies):
        old = [n.text for n in current['sku'].findall(".//field[@id='skuId']/value")]
        new = [n.text for n in merged.find("./field[@id='sku']").findall(".//field[@id='skuId']/value")]
        if not old or old != new:
            raise ValueError('SKU update must preserve current target SKU IDs')
    payload = values_only(merged, operation=operation, field_ids=fields.union(dependencies))
    if operation != 'update':
        validate_sku_property_pairs(payload)
    if model_record:
        validate_model_payload(payload, model_record)
    if inventory_input is not None:
        validate_create_inventory_payload(payload, inventory_input)
    differentiation_review = None
    if operation != 'update' and payload.find("./field[@id='scImages']") is not None:
        differentiation_review = prepare_differentiation_review(payload, differentiation_context,
            operation=operation, target_product_id=target_product_id)
    return {'keyword_input':keyword_input,'differentiation_review':differentiation_review,
            'category_id': int(category_id), 'operation': operation,
            'inventory_input': inventory_input,
            'model_serialization': model_record,
            'target_product_id': str(target_product_id) if target_product_id else None,
            'field_ids': sorted(fields), 'dependency_ids': sorted(dependencies),
            'xml': ET.tostring(payload, encoding='unicode'),
            'expected_fields': {k: v for k, v in field_snapshot(payload).items() if k in fields},
            'prepared_from_current_schema': True}

def validate_current_faq(definition, payload, *, require_types=False):
    """Enforce current FAQ shape/rules; formal create requires explicit types.

    Actual 725 create rejection 31002 exposed a type-free update fragment.
    Do not guess types or silently repair an intended payload from another SKU.
    Incremental update retains its existing omission contract.
    """
    items = payload.findall('./complex-values')
    if require_types:
        if not definition.get('type') or payload.get('type') != definition.get('type'):
            raise ValueError('FAQ create field type must match current Schema: companyFaqDesc')
        definitions = {f.get('id'): f for f in definition.findall('./fields/field')}
        for item in items:
            for field in item.findall('./field'):
                expected = definitions.get(field.get('id'))
                if expected is None or not expected.get('type') or field.get('type') != expected.get('type'):
                    raise ValueError('FAQ create item field type must match current Schema: ' + str(field.get('id')))
    for rule in definition.findall('./rules/rule'):
        name, value = rule.get('name'), rule.get('value')
        if name not in ('maxItemsRule', 'minItemsRule'):
            continue
        limit = int(value)
        inclusive = rule.get('exProperty', 'include') == 'include'
        invalid = (len(items) > limit if inclusive else len(items) >= limit) if name == 'maxItemsRule' else (len(items) < limit if inclusive else len(items) <= limit)
        if invalid:
            raise ValueError('FAQ item count violates current Schema ' + name)
    for field in definition.findall('./fields/field'):
        if not any(r.get('name') == 'requiredRule' and r.get('value') == 'true' for r in field.findall('./rules/rule')):
            continue
        field_id = field.get('id')
        for item in items:
            value = item.find("./field[@id='" + field_id + "']/value")
            if value is None or not (value.get('inputValue') or value.text or '').strip():
                raise ValueError('FAQ required field missing: ' + field_id)

def verify_create_skus(expected_sku, formal_sku, *, bound_ids=None):
    """Match submitted rows by stable outer code, not order or generated fields.

    Submitted properties and every submitted value remain strict. First formal
    read establishes the one-to-one platform-ID binding; subsequent reads must
    preserve that binding. Unsubmitted fields are observations, never defaults
    or deletion instructions. A first read cannot prove an ID's earlier history.
    """
    def attrs(node):
        return dict(node[1])
    def fields(row):
        result = {}
        for child in row[3]:
            if child[0] != 'field' or not attrs(child).get('id'):
                raise ValueError('unexpected SKU row structure')
            key = attrs(child)['id']
            if key in result:
                raise ValueError('duplicate SKU child field')
            result[key] = child
        return result
    def scalar(field):
        if field is None or len(field[3]) != 1 or field[3][0][0] != 'value' or not field[3][0][2]:
            raise ValueError('missing/ambiguous SKU identity')
        return field[3][0][2]
    def rows(sku):
        result = {}
        if sku[0] != 'field' or attrs(sku).get('id') != 'sku':
            raise ValueError('invalid SKU snapshot')
        for row in sku[3]:
            if row[0] != 'complex-values':
                raise ValueError('unexpected SKU structure')
            data = fields(row)
            key = scalar(data.get('skuOuterId'))
            if key in result:
                raise ValueError('duplicate stable SKU code')
            props = data.get('props')
            if props is None or len(props[3]) != 1 or props[3][0][0] != 'values' or not props[3][0][3]:
                raise ValueError('missing SKU properties')
            result[key] = data
        if not result:
            raise ValueError('empty SKU set')
        return result
    try:
        expected, formal = rows(expected_sku), rows(formal_sku)
        if set(expected) != set(formal):
            raise ValueError('missing/extra SKU code')
        bindings, observations = {}, {}
        for key, submitted in expected.items():
            actual = formal[key]
            # skuId is never supplied by create. All other explicit input is
            # compared exactly, including props value attributes and inventory.
            if 'skuId' in submitted:
                raise ValueError('create snapshot must not carry prior SKU IDs')
            if any(actual.get(fid) != value for fid, value in submitted.items()):
                raise ValueError('submitted SKU values/variant binding changed')
            platform_id = scalar(actual.get('skuId'))
            if platform_id == '0' or platform_id in bindings.values():
                raise ValueError('unassigned/duplicate platform SKU ID')
            bindings[key] = platform_id
            observations[key] = {fid: value for fid, value in actual.items()
                                 if fid not in submitted and fid != 'skuId'}
        if bound_ids is not None and bindings != bound_ids:
            raise ValueError('established platform SKU binding changed')
        return {'status':'verified', 'bindings':bindings, 'unsubmitted_observations':observations,
                'limits':'Formal API row/ID binding only; first read establishes IDs, not prior history, physical stock or image pixel truth.'}
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        return {'status':'mismatch', 'reason':str(exc), 'bindings':{}, 'unsubmitted_observations':{}}

def _created_image_identity(value):
    """Only the observed Alibaba kf original/350px forms share an identity."""
    from urllib.parse import urlsplit
    value = str(value or '')
    parsed = urlsplit('https:' + value if value.startswith('//') else value)
    if parsed.hostname != 'sc04.alicdn.com' or parsed.query or parsed.fragment:
        return value
    original = re.fullmatch(r'/kf/(H[A-Za-z0-9]+)/([0-9]+)/\1\.(?:jpg|jpeg|png)', parsed.path)
    thumbnail = re.fullmatch(r'/kf/(H[A-Za-z0-9]+)\.(jpg|jpeg|png)_350x350\.\2', parsed.path)
    compact = re.fullmatch(r'/kf/(H[A-Za-z0-9]+)\.(?:jpg|jpeg|png)', parsed.path)
    match = original or thumbnail or compact
    return 'sc04-kf-asset:' + match.group(1) if match else value


def created_field_equivalent(field_id, expected, actual):
    """Narrow create readback comparison, based on actual 989/725 receipts.

    Updates keep their strict snapshots. Main-image slots remain ordered by ID;
    gallery grouping preserves image multiplicity and gallery associations.
    Unknown URL forms/fields/attributes remain literal, never guessed aliases.
    """
    if expected == actual:
        return True
    supported = {'icbuCatProp', 'scImages', 'saleProp', 'minOrderQuantity',
                 'ladderPrice', 'ladderPeriod', 'detailImage', 'companyImage', 'pkgMeasure'}
    if field_id not in supported or expected is None or actual is None:
        return False
    def element(tree):
        if not isinstance(tree, list) or len(tree) != 4:
            raise ValueError('Invalid field snapshot')
        node = ET.Element(tree[0], dict(tree[1])); node.text = tree[2]
        for child in tree[3]: node.append(element(child))
        return node
    try:
        before, after = element(expected), element(actual)
        if before.get('id') != field_id or after.get('id') != field_id:
            return False
        zero_ids = set()
        if field_id == 'scImages':
            for field in after.findall('./complex-value/field'):
                value = field.find('value')
                if value is not None and value.get('fileId') == '0':
                    zero_ids.add(field.get('id'))
        def numeric(text):
            from decimal import Decimal
            if re.fullmatch(r'-?\d+(?:\.\d+)?', text or ''):
                return format(Decimal(text).normalize(), 'f')
            return text
        def signature(node, parent_field=None):
            fid = node.get('id') if node.tag == 'field' else parent_field
            attrs = dict(node.attrib); text = node.text or ''
            if node.tag == 'value':
                if field_id in {'icbuCatProp', 'saleProp'}:
                    if attrs.get('remark') is not None and attrs['remark'] == attrs.get('inputValue'):
                        attrs.pop('remark')  # Render drops the redundant exact color label.
                    if 'inputValue' in attrs and re.fullmatch(r'-\d+', text):
                        text = '__create_custom_value__'
                    elif 'inputValue' in attrs and re.fullmatch(r'\d+', text):
                        # The positive option ID is authoritative; render adds its label.
                        attrs.pop('inputValue')
                if field_id == 'scImages' and fid in zero_ids:
                    attrs.pop('fileId', None)
                if 'img' in attrs:
                    attrs['img'] = _created_image_identity(attrs['img'])
                text = _created_image_identity(text)
                if field_id in {'minOrderQuantity','ladderPrice','ladderPeriod','pkgMeasure'}:
                    text = numeric(text)
            children = [signature(child, fid) for child in node]
            if node.tag == 'complex-value' and all(c.tag == 'field' for c in node):
                ids = [c.get('id') for c in node]
                if len(ids) != len(set(ids)):
                    raise ValueError('Duplicate child field')
                children.sort(key=repr)
            if node.tag == 'values' and field_id in {'icbuCatProp','saleProp'}:
                children.sort(key=repr)
            return [node.tag, sorted(attrs.items()), text, children]
        def gallery_signature(root):
            from collections import Counter
            groups = {}
            rows = root.findall('./complex-values')
            if not rows or len(rows) != len(root):
                raise ValueError('Unrecognized gallery shape')
            for row in rows:
                fields = {f.get('id'): f for f in row.findall('field')}
                if len(fields) != len(row) or set(fields) != {'images','gallery'}:
                    raise ValueError('Unrecognized gallery fields')
                gallery = fields['gallery'].find('value')
                if gallery is None or len(fields['gallery']) != 1 or gallery.attrib:
                    raise ValueError('Unrecognized gallery ID')
                key = gallery.text; counts = groups.setdefault(key, Counter())
                images = fields['images'].findall('./complex-values')
                if not images or len(images) != len(fields['images']):
                    raise ValueError('Unrecognized gallery images')
                for image in images:
                    urls = image.findall("./field[@id='imageURL']/value")
                    if len(image) != 1 or len(urls) != 1 or urls[0].attrib:
                        raise ValueError('Unrecognized gallery image attributes')
                    counts[_created_image_identity(urls[0].text)] += 1
            return [(key, sorted(counts.items())) for key, counts in sorted(groups.items())]
        if field_id in {'detailImage','companyImage'}:
            return gallery_signature(before) == gallery_signature(after)
        return signature(before) == signature(after)
    except (ValueError, TypeError, KeyError):
        return False


def verify_content_details(submission_status, expected, formal_readback, *, operation='update', sku_bindings=None, versioned_content=None):
    """Operation-aware comparison against an independently acquired snapshot."""
    result = {'content_status':'unverified_content', 'sku_verification':None}
    if operation not in METHODS:
        raise ValueError('unknown operation')
    if submission_status != 'submitted_needs_readback' or not expected:
        return result
    # Whole-listing content may use the verified migrated selling-point target.
    # An explicit keyword-only request retains its exact write/readback contract.
    if (isinstance(versioned_content, dict) and versioned_content.get('status') == 'product_summary_verified'
            and 'productKeywords' in expected and len(expected) > 1):
        result['legacy_keyword_snapshot'] = {'expected': expected['productKeywords'],
            'actual': (formal_readback or {}).get('productKeywords'),
            'write_verified': False, 'status': 'LEGACY_FIELD_UI_MIGRATED'}
        expected = {k:v for k,v in expected.items() if k != 'productKeywords'}
    if formal_readback is None or any(k not in formal_readback for k in expected):
        result['content_status'] = 'pending_readback'
        return result
    matching = True
    for key, value in expected.items():
        if operation == 'create' and key == 'sku':
            result['sku_verification'] = verify_create_skus(value, formal_readback[key], bound_ids=sku_bindings)
            matching = matching and result['sku_verification']['status'] == 'verified'
        elif operation == 'create':
            matching = matching and created_field_equivalent(key, value, formal_readback[key])
        else:
            # Updates retain full strict snapshots, including existing skuId.
            matching = matching and formal_readback[key] == value
    result['content_status'] = 'formal_fields_verified' if matching else 'content_mismatch_or_noop'
    return result

def verify_content(submission_status, expected, formal_readback, *, operation='update', sku_bindings=None):
    return verify_content_details(submission_status, expected, formal_readback,
                                  operation=operation, sku_bindings=sku_bindings)['content_status']

COMPLETION_CHECKS = ('formal_fields', 'review_approved', 'public_page', 'sku_binding',
                     'media_review', 'source_truth', 'keyword_persistence')

def post_publish_acceptance(content_checks, *, actual_score=None, observed_at=None,
                            score_source=None, diagnostics=None, versioned_content=None):
    """Post-publication completion gate; never used to authorize first publish.

    The platform score measures its listing rubric, not authentic product quality.
    Unknown score/evidence/content is pending, never a complete PASS.
    """
    diagnostics = diagnostics if diagnostics is not None else {'status': 'not_read'}
    checks = dict(content_checks) if isinstance(content_checks, dict) else {}
    required = COMPLETION_CHECKS
    if versioned_content is not None:
        required = tuple(k for k in COMPLETION_CHECKS if k != 'keyword_persistence') + ('current_search_content',)
        checks.pop('keyword_persistence', None)  # Preserve its actual value in versioned_content.
        checks['current_search_content'] = (isinstance(versioned_content, dict)
            and versioned_content.get('status') == 'product_summary_verified')
    incomplete = [key for key in required if checks.get(key) is not True]
    incomplete += [key for key, value in checks.items() if key not in required and value is not True]
    score_status = 'pending_score'
    if actual_score is not None:
        if type(actual_score) not in (int, float) or not math.isfinite(actual_score):
            raise ValueError('actual_score must be a finite number or null')
        if actual_score < 5.0:
            score_status = 'pending_optimization'
        else:
            try:
                stamp = datetime.fromisoformat(observed_at)
                metadata_ok = stamp.tzinfo is not None and bool(score_source)
            except (ValueError, TypeError):
                metadata_ok = False
            score_status = 'threshold_met' if metadata_ok else 'pending_score_evidence'
    if score_status == 'pending_score':
        overall = 'PENDING_SCORE'
    elif score_status == 'pending_optimization':
        overall = 'PENDING_OPTIMIZATION'
    elif score_status == 'pending_score_evidence':
        overall = 'PENDING_SCORE_EVIDENCE'
    elif incomplete:
        overall = 'PENDING_CONTENT'
    elif not isinstance(diagnostics, dict) or diagnostics.get('status') != 'clear':
        overall = 'PENDING_DIAGNOSTICS'
    else:
        overall = 'PASS'
    return {'phase': 'post_publish_completion', 'target_score': 5.0,
            'actual_score': actual_score, 'observed_at': observed_at,
            'score_source': score_source, 'diagnostics': diagnostics,
            'score_status': score_status, 'overall_status': overall,
            'unverified_content_checks': incomplete,
            'versioned_content': versioned_content,
            'required_content_checks': list(required),
            'limits': 'Platform listing score does not prove public content, source truth or real product quality.'}

def faq_constraints(current_schema):
    """Preserve current raw FAQ rules; unitless limits are not character counts."""
    field = current_schema.find("./field[@id='companyFaqDesc']")
    if field is None:
        return {"status": "absent_in_current_schema"}
    return {"status": "current_schema_rules", "rules": [dict(r.attrib) for r in field.findall('.//rule')],
            "item_fields": [dict(f.attrib) for f in field.findall('.//fields/field')],
            "unit_interpretation": "unverified_unless_current_schema_defines_unit"}

def capability(operation, detail_type, category_id, registry=None, field=None, product_id=None):
    registry = registry or json.loads(Path(__file__).with_name("schema_capabilities.json").read_text(encoding="utf-8"))
    matches = [r for r in registry["evidence"] if r["operation"] == operation and
               r["detail_type"] == str(detail_type) and r["category_id"] == str(category_id)]
    field_matches = [r for r in registry.get("field_evidence", []) if r["operation"] == operation and r["field"] == field and r["detail_type"] == str(detail_type) and r["category_id"] == str(category_id)] if field else []
    status = field_matches[-1]["status"] if field_matches else ("unverified" if field else ("historically_verified" if matches else "unverified"))
    content_versions = [r for r in registry.get('content_acceptance_evidence', [])
                        if product_id is not None and str(r.get('product_id')) == str(product_id)
                        and str(r.get('category_id')) == str(category_id)
                        and str(r.get('detail_type')) == str(detail_type)]
    return {"status": status, "field": field, "field_evidence": field_matches,
            "content_acceptance_evidence": content_versions,
            "content_next_step": "evaluate_versioned_content_with_current_reads" if content_versions else "verify_current_edit_version_before_changing_acceptance",
            "operation": operation, "method": METHODS[operation],
            "detail_type": str(detail_type), "category_id": str(category_id),
            "implementation": "publish_hot_rank_hr_a_batch.py: prepare_scoped_listing / set_gallery / values_only / api_submit" if matches or any(r['status'].startswith('formal_fields_verified') for r in field_matches) else None,
            "evidence": matches, "next_step": "fetch_current_schema_and_validate_target",
            "limits": "Historical submission only; no global category support, current permission, source truth, review approval or public-page acceptance inferred."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=METHODS, required=True)
    parser.add_argument("--detail-type", choices=("2", "4", "5"), required=True)
    parser.add_argument("--category-id", required=True)
    parser.add_argument("--field", help="Exact field; operation receipts do not verify content")
    parser.add_argument("--product-id", help="Exact existing product for scoped edit-version evidence; no platform call")
    args = parser.parse_args()
    print(json.dumps(capability(args.operation, args.detail_type, args.category_id, field=args.field, product_id=args.product_id), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()


def diagnose_keyword_attempt(current_schema, payload, before_get, after_get, receipt, *, expected_product_id):
    """Offline attempt diagnosis. Never infers write support from field definitions.

    Both get objects must be the SDK's flattened, bound formal responses. A
    verified existing value alone does not prove that this request wrote it.
    """
    payload = ET.fromstring(payload) if isinstance(payload, str) else payload
    fields = [n.get('id') for n in payload.findall('./field')]
    if len(fields) != len(set(fields)):
        raise ValueError('duplicate payload fields')
    keyword_sent = 'productKeywords' in fields
    if keyword_sent:
        validate_keyword_payload(current_schema, payload)
        expected = [v.text for v in payload.findall("./field[@id='productKeywords']/complex-value/field/value")]
    else:
        expected = ((before_get or {}).get('product') or {}).get('keywords')
    result = {'status': 'unverified_keyword_attempt', 'keyword_field_submitted': keyword_sent,
              'submitted_fields': fields, 'write_capability_verified': False, 'retry_same_request': False}
    error = (receipt or {}).get('error') or ((receipt or {}).get('response') or {}).get('error_response') or {}
    if error.get('sub_code') == 'INTERFACE_HAS_BEEN_OFFLINE':
        result['status'] = 'retired_interface_rejected'
        return result
    if error or (receipt or {}).get('status') == 'business_rejected' or ((receipt or {}).get('response') or {}).get('biz_success') is False:
        result['status'] = 'business_rejected'
        return result
    if (receipt or {}).get('status') in ('write_outcome_unknown', 'WRITE_OUTCOME_UNKNOWN_STOP_NO_RETRY', 'write_attempt_reserved'):
        result['status'] = 'unknown_write_outcome_stop'
        return result
    before = (before_get or {}).get('product') or {}
    if str(before.get('product_id')) != str(expected_product_id) or not isinstance(expected, list) or any(not isinstance(v, str) for v in expected):
        return result
    readback = compare_keyword_readback(expected, after_get, current_schema, expected_product_id=expected_product_id)
    result['readback'] = readback
    if readback['status'] in ('pending_review', 'unverified_keyword_readback', 'readback_disagrees'):
        result['status'] = readback['status']
        return result
    actual = readback['get_values']
    prior = before.get('keywords')
    if not keyword_sent:
        result['status'] = 'unexpected_keyword_loss' if actual != prior else 'keywords_preserved'
    elif actual == expected and all(v.strip() for v in actual):
        changed = prior != actual
        proved = changed and (receipt or {}).get('status') == 'submitted_needs_readback'
        result['status'] = 'keyword_update_verified' if proved else 'keyword_value_verified_write_effect_unproven'
        result['write_capability_verified'] = proved
    elif actual == prior:
        result['status'] = 'accepted_keyword_noop' if (receipt or {}).get('status') == 'submitted_needs_readback' else 'keyword_unchanged_unverified_submission'
    else:
        result['status'] = 'keyword_value_mismatch'
    return result


def evaluate_versioned_content(current_schema, product_get, public_text, *, product_id,
                               category_id, editor_observation_id, observed_at,
                               registry=None, evidence_root=None):
    """Read-only, per-product content acceptance; never proves a keyword write.

    The observation ID identifies captured UI behavior, not an invented platform
    build number. Its date and exact target must match this acceptance snapshot.
    """
    import hashlib
    from urllib.parse import urlparse, parse_qs
    registry = registry if registry is not None else json.loads(
        Path(__file__).with_name('schema_capabilities.json').read_text(encoding='utf-8'))
    result = {'status':'content_version_unverified', 'target':None,
              'product_id':str(product_id), 'category_id':str(category_id),
              'editor_observation_id':editor_observation_id,
              'legacy_keywords':((product_get or {}).get('product') or {}).get('keywords'),
              'keyword_write_verified':False, 'replacement_closeout_verified':False}
    rows = [r for r in registry.get('content_acceptance_evidence', [])
            if str(r.get('product_id')) == str(product_id)
            and str(r.get('category_id')) == str(category_id)
            and r.get('editor_observation_id') == editor_observation_id]
    if len(rows) != 1:
        return result
    row = rows[0]
    try:
        stamp = datetime.fromisoformat(observed_at)
        ui_stamp = datetime.fromisoformat(row['observed_at'])
        if stamp.tzinfo is None or ui_stamp.tzinfo is None or stamp.astimezone(ui_stamp.tzinfo).date() != ui_stamp.date():
            return result
        url = urlparse(row['editor_url'])
        if (url.hostname != 'post.alibaba.com' or url.path != '/product/publish.htm'
                or parse_qs(url.query).get('itemId') != [str(product_id)]
                or parse_qs(url.query).get('catId') != [str(category_id)]):
            return result
        if row.get('notice') != '【副标题和关键词】已经合并升级为新版商品详描的【商品卖点】了！合并后可聚焦在商品卖点表达更多核心卖点，提升商品转化率，':
            return result
        base = Path(evidence_root) if evidence_root else Path(__file__).resolve().parents[3]
        kinds = set()
        for ref in row.get('sources') or []:
            path = (base / ref['path']).resolve()
            if not path.is_relative_to(base.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
                return result
            kinds.add(ref['kind'])
        if 'ui_notice' not in kinds:
            return result
    except (OSError, ValueError, TypeError, KeyError):
        return result
    result.update(target='product_summary', status='selling_point_content_pending',
                  legacy_field_status='LEGACY_FIELD_EMPTY_UI_MIGRATED' if result['legacy_keywords'] == [''] else 'LEGACY_FIELD_OBSERVED_UI_MIGRATED')
    if row.get('level') != 'ui_schema_formal_public_verified' or not {'ui_selling_points','formal_get','render','public_summary'} <= kinds:
        return result
    if (product_get or {}).get('error_response') or (product_get or {}).get('biz_success') is False:
        return result
    product = (product_get or {}).get('product') or {}
    if (str(product.get('product_id')) != str(row.get('encrypted_product_id'))
            or str(product.get('category_id')) != str(category_id)
            or product.get('status') != 'approved' or product.get('display') != 'Y'):
        return result
    field = current_schema.find("./field[@id='textDesc']")
    rendered = field.findtext('value') if field is not None else None
    actual = (product.get('struct_detail') or {}).get('product_summary')
    if not isinstance(actual, str) or not actual.strip() or rendered != actual or not isinstance(public_text, str):
        return result
    if hashlib.sha256(actual.encode('utf-8')).hexdigest() != row.get('ui_verified_summary_sha256'):
        return result  # Current text changed since the hash-bound UI observation.
    # Only normalize layout whitespace; preserve the actual words and claims.
    normalize = lambda text: re.sub(r'\s+', ' ', text).strip()
    if normalize(actual) not in normalize(public_text):
        return result
    constraints = []
    for rule in field.findall('./rules/rule'):
        if rule.get('name') not in ('maxLengthRule','minLengthRule'):
            continue
        unit = rule.get('unit')
        if unit in ('byte','bytes'):
            size = len(actual.encode('utf-8'))
        elif unit in ('character','characters','char','chars'):
            size = len(actual)
        else:
            constraints.append({'name':rule.get('name'),'unit':unit,'interpretation':'unverified_unit; no guessed length'})
            continue
        try:
            bound = int(rule.get('value'))
        except (ValueError, TypeError):
            return result
        if (rule.get('name') == 'maxLengthRule' and size > bound
                or rule.get('name') == 'minLengthRule' and size < bound):
            return result
        constraints.append({'name':rule.get('name'),'unit':unit,'value':bound,'actual':size})
    result.update(status='product_summary_verified', content_complete=True,
                  schema_field='textDesc', formal_field='product.struct_detail.product_summary',
                  summary_characters=len(actual), constraints=constraints,
                  limits='This exact observed edit version and product only; no keyword restoration, global support, source truth, score or old-product retirement inferred.')
    return result
