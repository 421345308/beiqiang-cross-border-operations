import json,csv,pathlib,re
out=pathlib.Path(__file__).parent
bank=json.loads((pathlib.Path(r'C:\Users\spq\Desktop\贝强\02_Alibaba运营\06_图片与检查记录\API全量图片审计_2026-09-03\video_bank.json').read_text(encoding='utf-8')))
videos=bank.get('result',{}).get('model',{}).get('list',[])
rows=json.loads((out/'full_product_audit.json').read_text(encoding='utf-8'))
for r in rows:
    m=(r.get('modelNumber') or '')
    code=(re.search(r'BQ\d+',m,re.I) or [None])[0]
    hits=[v for v in videos if code and code.upper() in (v.get('title') or '').upper()]
    r['videoBankCandidateCount']=len(hits)
    r['videoBankCandidates']=' | '.join(v.get('title','') for v in hits)
    r['videoBindingStatus']='not verified by product.get; candidate only' if hits else 'no model-matched bank video found'
(out/'full_product_audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'full_product_audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print({'rows':len(rows)})
