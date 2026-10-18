"""Source-reviewed, exact-ID sole-role repairs. Never replay a reserved write.

Current target Schema names determine IDs. Full category-property values are
preserved except the two explicitly reviewed material roles; title is included
unchanged to protect it against platform attribute-based title regeneration.
"""
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as E
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, importlib.util, json, sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08'
AUDIT = BASE / '质量复核_2026-10-09/材料字段复核'
REG = ROOT / '02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
sys.path.insert(0, str(Path(__file__).parent))
import publish_hot_rank_hr_a_batch as pub
from read_only_catalog import read_only_call, product_readiness, ReadBusinessError


def now(): return datetime.now(timezone.utc).isoformat()
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return p.relative_to(ROOT).as_posix()


def replace_named_attribute(schema, values, name, labels):
    definitions = [f for f in schema.findall("./field[@id='icbuCatProp']/fields/field") if f.get('name') == name]
    assert len(definitions) == 1, 'Ambiguous or absent current attribute name'
    definition = definitions[0]
    fid, typ = definition.get('id'), definition.get('type')
    assert typ in ('singleCheck', 'multiCheck')
    assert labels and len(labels) == len(set(labels)) and (typ != 'singleCheck' or len(labels) == 1)
    old = values.find(f"./field[@id='{fid}']")
    assert old is not None, 'Expected current target attribute is absent'
    index = list(values).index(old)
    values.remove(old)
    field = E.Element('field', id=fid, type=typ)
    values.insert(index, field)
    parent = E.SubElement(field, 'values') if typ == 'multiCheck' else field
    options = {o.get('displayName').casefold(): (o.get('value'), o.get('displayName')) for o in definition.findall('./options/option')}
    effective = []
    for i, label in enumerate(labels):
        option = options.get(label.casefold())
        if option:
            value, text = option
        else:
            assert any(r.get('name') == 'tipRule' and '负数' in r.get('value', '') for r in definition.findall('./rules/rule'))
            value, text = str(-701-i), label
        E.SubElement(parent, 'value', inputValue=text).text = value
        effective.append(text)
    return {'name': name, 'field_id': fid, 'attribute_id': fid.removeprefix('p'), 'effective_values': effective}


def attributes(product, exclude=()):
    result = {}
    for a in product['attributes']:
        name = a['attribute_name']
        if name not in exclude: result.setdefault(name, []).append(a['value_name'])
    return {k: sorted(v) for k, v in result.items()}


def stable_product(p):
    return {k:v for k,v in p.items() if k not in ('gmt_modified', 'status', 'display')}


def operate(row, mode, client, cfg):
    pid = str(row['id']); folder = AUDIT/'商品'/pid
    folder.mkdir(parents=True, exist_ok=True)
    ledger = folder/'update_once.json'
    if mode == 'prepare' and ledger.exists(): return {'id':pid, 'state':'EXISTING_LEDGER_READBACK_ONLY'}
    if mode == 'submit':
        if ledger.exists(): return {'id':pid, 'state':'EXISTING_LEDGER_READBACK_ONLY'}
        manifest = folder/'manifest.json'
        assert manifest.exists(), 'Prepare before submit'
        listing = pub.load_submission_manifest(manifest, 'update', pid)
        current = read_only_call(client, cfg, 'alibaba.icbu.product.get', {'product_id':pid, 'language':'ENGLISH'})
        save(folder/'immediate_prewrite_get.json', current)
        before = load(folder/'prepared_before_get.json')['product']
        assert current['product']['status'] == 'approved' and current['product']['display'] == 'Y'
        assert stable_product(current['product']) == stable_product(before), 'Product changed since preparation; do not write stale values'
        with ledger.open('x', encoding='utf-8') as f:
            json.dump({'id':pid, 'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY', 'at':now()}, f)
        receipt = pub.api_submit(client, cfg, listing, False, update_product_id=pid)
        save(folder/'update_receipt.json', receipt)
        save(ledger, {'id':pid, 'state':receipt['status'], 'at':receipt['attempted_at'], 'refs':receipt.get('refs')})
        return {'id':pid, 'state':receipt['status']}
    got = read_only_call(client, cfg, 'alibaba.icbu.product.get', {'product_id':pid, 'language':'ENGLISH'})
    save(folder/('prepared_before_get.json' if mode == 'prepare' else 'after_get.json'), got)
    product = got['product']
    # product.get returns the platform encrypted product_id, not the requested
    # numeric ID. Bind the request plus exact model/category and preserve that
    # encrypted identity across before/after; never compare it to numeric pid.
    assert int(product['category_id']) == row['category_id'], 'Unexpected current category'
    assert attributes(product)['Model Number'] == ['BQ-LQ'+row['style']]
    ready = product_readiness(product['status'])
    if ready != 'APPROVED' or product['display'] != 'Y':
        report = {'id':pid, 'style':row['style'], 'at':now(), 'state':ready, 'display':product['display'], 'actual_score':None}
        if mode == 'verify': save(folder/'verification.json', report)
        return report
    rendered = read_only_call(client, cfg, 'alibaba.icbu.product.schema.render', {'param_product_top_publish_request':{'product_id':int(pid), 'cat_id':row['category_id'], 'language':'en_US'}})
    save(folder/('before_render.json' if mode == 'prepare' else 'after_render.json'), rendered)
    if not rendered.get('data'): return {'id':pid, 'state':'EDITABLE_SCHEMA_UNAVAILABLE'}
    schema = E.fromstring(rendered['data'])
    (folder/('current_schema.xml' if mode == 'prepare' else 'after_schema.xml')).write_text(rendered['data'], encoding='utf-8')
    if mode == 'prepare':
        facts = ROOT/row['source_facts']; assert facts.exists()
        root = pub.values_only(schema, operation='update', field_ids=['icbuCatProp','productTitle'])
        cv = root.find("./field[@id='icbuCatProp']/complex-value")
        original = {x.get('id'):E.tostring(x,encoding='unicode') for x in cv}
        roles = [replace_named_attribute(schema, cv, name, labels) for name, labels in row['target_materials'].items()]
        changed_ids = {x['field_id'] for x in roles}
        assert all(E.tostring(x,encoding='unicode') == original[x.get('id')] for x in cv if x.get('id') not in changed_ids)
        pub.set_direct_value(root, 'productTitle', product['subject'])
        assert {x.get('id') for x in root} == {'icbuCatProp','productTitle'}
        payload = folder/'payload.xml'; payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf-8')
        manifest = {'operation':'update','product_id':pid,'category_id':row['category_id'],'facts_reviewed':True,'source_evidence':[rel(facts),rel(AUDIT/'修正清单.json')], 'current_schema':'current_schema.xml','current_schema_sha256':sha(folder/'current_schema.xml'),'schema_request_id':rendered['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':['icbuCatProp','productTitle'],'dependency_ids':[],'expected_model':'BQ-LQ'+row['style']}
        save(folder/'manifest.json', manifest)
        save(folder/'prepared.json', {'id':pid,'style':row['style'],'at':now(),'state':'PREPARED_SOURCE_REVIEWED','material_roles':roles,'unchanged_title':product['subject'],'source_facts_sha256':sha(facts),'source':row['source']})
        pub.load_submission_manifest(folder/'manifest.json','update',pid)
        return {'id':pid,'state':'PREPARED'}
    assert ledger.exists(), 'Verification requires a reserved or acknowledged write'
    before = load(folder/'prepared_before_get.json')['product']; prepared = load(folder/'prepared.json')
    roles = prepared['material_roles']; excluded = [x['name'] for x in roles]
    unchanged = {k:product.get(k) == v for k,v in before.items() if k not in ('attributes','gmt_modified','status','display')}
    unchanged['other_attributes'] = attributes(before,excluded) == attributes(product,excluded)
    actual_attrs = attributes(product)
    target_match = all(actual_attrs.get(x['name']) == sorted(x['effective_values']) for x in roles)
    rendered_values = pub.values_only(schema,operation='update',field_ids=['icbuCatProp']).find('./field/complex-value')
    payload_values = E.parse(folder/'payload.xml').getroot().find("./field[@id='icbuCatProp']/complex-value")
    # Platform may normalize custom/native markers. Compare actual effective text,
    # and demand that current Schema still defines the reviewed semantic roles.
    schema_names_match = all(len([d for d in schema.findall("./field[@id='icbuCatProp']/fields/field") if d.get('name')==x['name'] and d.get('id')==x['field_id']])==1 for x in roles)
    def effective(f):
        return sorted(v.get('inputValue') or v.text for v in f.iter('value'))
    rendered_match = all(effective(rendered_values.find(f"./field[@id='{x['field_id']}']")) == effective(payload_values.find(f"./field[@id='{x['field_id']}']")) for x in roles)
    passed = target_match and schema_names_match and rendered_match and all(unchanged.values())
    report = {'id':pid,'style':row['style'],'at':now(),'get_observed_at':now(),'state':'FORMAL_FIELDS_PASS_PENDING_SCORE' if passed else 'FORMAL_MISMATCH_DIAGNOSE','target_materials':{x['name']:x['effective_values'] for x in roles},'effective_formal_match':target_match,'schema_semantic_roles_match':schema_names_match,'rendered_values_match':rendered_match,'protected_fields':unchanged,'status':product['status'],'display':product['display'],'request_id':got['request_id'],'actual_score':None,'public_qa':'NOT_RETESTED_SCOPED_API_REPAIR'}
    enc = client.top_call(cfg, 'alibaba.icbu.product.id.encrypt', {'product_id':pid,'language':'ENGLISH'})
    save(folder/'encrypted_id_response.json',enc)
    if enc.get('secret_id'):
        try:
            score = read_only_call(client,cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']})
        except ReadBusinessError as exc:
            report['score_read_error']=exc.api_evidence
            save(folder/'verification.json',report)
            return {k:report[k] for k in ('id','style','state','actual_score')}
        save(folder/'score.json',score); result=score.get('result',{}); report['actual_score']=result.get('final_score')
        problem = result.get('problem_map') or {}; problem=json.loads(problem) if isinstance(problem,str) else problem
        diag={'flags':{k:v for k,v in problem.get('extendProblemMap',{}).items() if v is True},'deductions':{k:v for k,v in problem.get('ruleScoreMap',{}).items() if Decimal(str(v)) != 0},'errors':problem.get('errorReasonList',[])}
        report['score_diagnostics']=diag
        if passed and report['actual_score'] is not None and Decimal(str(report['actual_score']))>=5 and not any(diag.values()): report['state']='FORMAL_FIELDS_SCORE_PASS'
    save(folder/'verification.json',report)
    return {k:report[k] for k in ('id','style','state','actual_score')}


def sanitized(v):
    if isinstance(v,dict): return {k:sanitized(x) for k,x in v.items() if k not in ('owner_member','owner_member_display_name','owner_member_id')}
    if isinstance(v,list): return [sanitized(x) for x in v]
    return v


def sync(rows):
    d=load(REG); listings={l['id']:l for l in d['listings']}; products={p['id']:p for p in d['products']}; result=[]
    for row in rows:
        pid=str(row['id']);folder=AUDIT/'商品'/pid
        if not (folder/'verification.json').exists():continue
        report=load(folder/'verification.json'); l=listings[pid]
        evidence=[rel(folder/name) for name in ('prepared.json','manifest.json','update_once.json','update_receipt.json','after_get.json','after_render.json','verification.json','score.json') if (folder/name).exists()]
        l.setdefault('optimization',{})['material_role_repair']={'state':report['state'],'at':report['at'],'target_materials':report.get('target_materials'),'actual_score':report['actual_score'],'evidence':evidence,'source_id_unchanged':l.get('bound_source_id'),'scope':'Exact two source-reviewed material roles; all non-target formal fields preserved; no public presentation PASS inferred.'}
        if report['state'] not in ('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE'):
            current_get=load(folder/'after_get.json')['product']
            l['current_repair_phase']={'state':report['state'],'status':current_get['status'],'display':current_get['display'],'at':report['at'],'get_file':rel(folder/'after_get.json'),'last_accepted_fields_remain_historical':True}
        if report['state'] in ('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE'):
            l.pop('current_repair_phase',None)
            got=load(folder/'after_get.json'); p=got['product'];current=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid;current.mkdir(parents=True,exist_ok=True)
            save(current/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':report['get_observed_at'],'method':'alibaba.icbu.product.get','response':sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(folder/'after_get.json')})
            save(current/'formal_render.json',load(folder/'after_render.json'))
            l['formal_fields']={'file':rel(current/'formal_get.json'),'at':report['at'],'scope':'完整正式商品回读；本次仅材料角色修正，非目标字段保全'}
            l['current_platform_fields']={**l.get('current_platform_fields',{}),'at':report['at'],'title':p['subject'],'keywords':p.get('keywords',[]),'main_images':p['main_image']['images'],'category_id':p['category_id'],'status':p['status'],'display':p['display'],'materials':report['target_materials']}
            l['catalog_fields']={**l.get('catalog_fields',{}),**l['current_platform_fields']}
            l['local_sync']={**l.get('local_sync',{}),'state':report['state'],'current_fields_file':rel(current/'formal_get.json'),'current_schema_file':rel(current/'formal_render.json'),'material_role_verification':rel(folder/'verification.json'),'observed_at':report['at']}
            l['observation']={**l.get('observation',{}),'audit':p['status'],'display':p['display'],'at':report['at'],'score':report['actual_score'],'scope':'当前正式商品材料角色修正；旧公开抽检不视为本次修改终验'}
            product=products[l['product_id']]
            product.setdefault('local_assets',{})['current_fields_file']=rel(current/'formal_get.json')
            product['material_role_review']={'state':report['state'],'source_facts':row['source_facts'],'target_materials':report['target_materials'],'evidence':rel(folder/'verification.json')}
            for ref in evidence:
                if ref not in l['evidence']:l['evidence'].append(ref)
                if ref not in product['evidence']:product['evidence'].append(ref)
        result.append({'id':pid,'state':report['state']})
    d['updated_on']=datetime.now(timezone.utc).date().isoformat();save(REG,d)
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    outputs=workspace.build(d)
    for path,body in outputs.items():workspace.write_generated(ROOT/path,body)
    save(AUDIT/'双改核验.json',{'at':now(),'rows':result,'registry':rel(REG),'generated_current_dossiers':len(outputs),'source_bindings_unchanged':True})
    print(json.dumps({'mode':'sync','rows':result,'generated_current_dossiers':len(outputs)}),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('prepare','submit','verify','sync'));args=ap.parse_args()
    rows=load(AUDIT/'修正清单.json')['rows'];assert len(rows)==8 and len({str(x['id']) for x in rows})==8
    if args.mode=='sync':sync(rows);return
    spec=importlib.util.spec_from_file_location('alibaba_client',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client);cfg=client.load_config(client.DEFAULT_CONFIG)
    original_http=client.http_json;client.http_json=lambda request:original_http(request,timeout=25)
    def work(row):
        try:return operate(row,args.mode,client,cfg)
        except Exception as exc:
            diagnostic={'id':str(row['id']),'state':'ERROR_DIAGNOSE','type':type(exc).__name__,'at':now()}
            # Only own assertion messages are safe; client exceptions can contain sensitive request data.
            if isinstance(exc,AssertionError):diagnostic['assertion']=str(exc)
            if hasattr(exc,'api_evidence'):diagnostic['api_evidence']=exc.api_evidence
            save(AUDIT/'商品'/str(row['id'])/(args.mode+'_error.json'),diagnostic);return diagnostic
    results=[]
    if args.mode=='submit':
        for row in rows:
            result=work(row);results.append(result);print(json.dumps(result),flush=True)
    else:
        with ThreadPoolExecutor(max_workers=4) as executor:
            for result in executor.map(work,rows):results.append(result);print(json.dumps(result),flush=True)
    save(AUDIT/(args.mode+'_汇总.json'),{'at':now(),'mode':args.mode,'rows':results})
    if any(x['state']=='ERROR_DIAGNOSE' for x in results):sys.exit(1)


if __name__=='__main__':main()
