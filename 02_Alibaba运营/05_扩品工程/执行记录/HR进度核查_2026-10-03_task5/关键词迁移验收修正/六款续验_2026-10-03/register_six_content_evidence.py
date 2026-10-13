from pathlib import Path
import json, hashlib, shutil, sys, xml.etree.ElementTree as E

BASE = Path(__file__).parent
ROOT = Path(r'C:\Users\spq\Desktop\贝强')
CODE = ROOT / '08_工具链/01_业务脚本/国际站扩品'
DEST = ROOT / '02_Alibaba运营/05_扩品工程/执行记录/HR进度核查_2026-10-03_task5/关键词迁移验收修正/六款续验_2026-10-03'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
registry_path = CODE / 'schema_capabilities.json'
before = registry_path.read_bytes()
registry = json.loads(before)
backup = BASE / 'six_version_acceptance_resume/schema_capabilities_before_append.json'
if not backup.exists():
    backup.write_bytes(before)
sys.path.insert(0, str(CODE))
import schema_publish_contract as contract

for name in sys.argv[1:]:
    src = BASE / 'six_version_acceptance_resume' / name
    proof = json.loads((src / 'prepared_evidence.json').read_text(encoding='utf8'))
    assert proof['content_ready'], (name, 'full content evidence incomplete')
    notice_source = BASE / proof['current_UI_notices'][0]['path']
    notice = json.loads(notice_source.read_text(encoding='utf-8-sig'))
    bound = [n for n in notice['notice'] if n['titleBound']]
    assert bound and len({n['text'] for n in bound}) == 1
    out = DEST / name
    out.mkdir(parents=True, exist_ok=True)
    sources = []
    def copy(source, filename, kind):
        source = Path(source)
        target = out / filename
        if target.exists():
            assert digest(target) == digest(source), ('evidence overwrite prohibited', str(target))
        else:
            shutil.copy2(source, target)
        sources.append({'path': target.relative_to(ROOT).as_posix(), 'kind': kind, 'sha256': digest(target)})
    copy(notice_source.with_suffix('.png'), 'notice.png', 'ui_notice')
    copy(notice_source, 'notice.json', 'ui_notice_metadata')
    copy(src / 'selling.png', 'selling.png', 'ui_selling_points')
    copy(src / 'selling.json', 'selling.json', 'ui_selling_points_metadata')
    copy(BASE / proof['formal_get_source'], 'formal_get.json', 'formal_get')
    copy(BASE / proof['render_source'], 'render.xml', 'render')
    public_source = BASE / proof['public_matches'][0]['path']
    copy(public_source, 'public_summary.json', 'public_summary')
    if public_source.with_suffix('.png').exists():
        copy(public_source.with_suffix('.png'), 'public_summary.png', 'public_summary_visual')
    if proof.get('fresh_formal_recheck'):
        copy(BASE / proof['fresh_formal_recheck']['source'], 'formal_scalar_recheck.json', 'formal_scalar_recheck')
    copy(src / 'prepared_evidence.json', 'prepared_evidence.json', 'comparison_metadata')
    row = {
        'product_id': proof['product_id'], 'encrypted_product_id': proof['encrypted_product_id'],
        'category_id': proof['category_id'], 'detail_type': '4',
        'editor_observation_id': name + '_normal_notice_sha256:' + digest(notice_source.with_suffix('.png')),
        'observed_at': notice['atUTC'], 'editor_url': 'https://' + notice['address'].removeprefix('https://'),
        'notice': bound[0]['text'], 'level': 'ui_schema_formal_public_verified',
        'content_status': 'CONTENT_COMPLETE', 'sources': sources,
        'ui_verified_summary_sha256': hashlib.sha256(proof['summary'].encode('utf8')).hexdigest(),
        'formal_get_observed_at': proof['formal_get_at_utc'],
        'fresh_formal_recheck': proof.get('fresh_formal_recheck'),
        'limits': 'Exact product/category and same-day normal-editor observation only. Actual cached full get dates remain explicit; current scalar recheck validates body/status, not legacy keywords. No platform build, keyword write, global category support or old-product retirement inferred.'
    }
    # Product description type is bound to actual get schema evidence, not inferred from prose.
    full_schema = BASE / 'hr_public_readonly_20261003' / (name + '_formal_schema.xml')
    if name == '2627BSK':
        full_schema = src / 'current_schema.xml'
    if full_schema.exists():
        observed_type = E.parse(full_schema).getroot().findtext("./field[@id='productDescType']/value")
        if observed_type is not None:
            assert observed_type == '4', (name, observed_type)
        else:
            row.pop('detail_type')
    else:
        row.pop('detail_type')
    existing = [r for r in registry['content_acceptance_evidence'] if r['editor_observation_id'] == row['editor_observation_id']]
    if existing:
        assert existing == [row], (name, 'existing observation differs')
    else:
        registry['content_acceptance_evidence'].append(row)
    ui = json.loads(public_source.read_text(encoding='utf-8-sig'))
    public_text = ' '.join(str(x.get('name', '')) for x in ui['rows'] if not x.get('offscreen'))
    result = contract.evaluate_versioned_content(
        E.fromstring(proof['schema_xml']), proof['product_get'], public_text,
        product_id=row['product_id'], category_id=row['category_id'],
        editor_observation_id=row['editor_observation_id'], observed_at=notice['atUTC'], registry=registry)
    assert result['status'] == 'product_summary_verified', (name, result)
    result['formal_get_observed_at'] = proof['formal_get_at_utc']
    result['legacy_keyword_observed_at'] = proof['formal_get_at_utc']
    result['fresh_formal_recheck'] = proof.get('fresh_formal_recheck')
    (out / 'actual_acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'candidate': name, 'product_id': row['product_id'], 'status': result['status'], 'summary_characters': result['summary_characters'], 'keyword_write_verified': False}, ensure_ascii=False))

assert registry_path.read_bytes() == before, 'Concurrent registry change: stop rather than overwrite'
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
