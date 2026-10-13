"""Analyze dated public Alibaba card captures without imputing sales or product facts."""
import argparse
import collections
import csv
import html
import json
import re
import statistics
from pathlib import Path


def classify(title):
    t = title.lower()
    if re.search(r'\b(kids?|children|baby|toddler|infant|boys|girls)\b', t):
        return '童鞋（不直接对标）'
    if re.search(r'\b(shoe outsoles?|shoe soles?|foam soles?|foam insoles?|comfort insoles?|sports insoles?|shoe midsoles?)\b', t) or ('insole' in t and not re.search(r'\b(shoes|sneakers|boots)\b', t)):
        return '鞋底鞋垫部件'
    if re.search(r'\b(water|aqua|swimming|wading)\b', t):
        return '水鞋（不直接对标）'
    if re.search(r'\b(clogs?|slippers?|mules?)\b', t):
        return '拖鞋穆勒鞋'
    if re.search(r'\b(formal|dress|oxfords?|wedding|pointed)\b', t):
        return '正装鞋（不直接对标）'
    if re.search(r'\b(badminton|pickleball|tennis|volleyball|basketball|football|soccer)\b', t):
        return '球类运动鞋'
    if re.search(r'\b(barefoot|minimalist|zero[ -]drop)\b', t):
        return '赤足及极简概念鞋'
    if re.search(r'\b(knit|knitted|knitting|woven|weaving|slip[ -]?on|sock|loafers?)\b', t):
        return '针织套脚及乐福鞋'
    if re.search(r'\b(hiking|trekking|boots?)\b', t):
        return '户外鞋靴'
    if re.search(r'\b(running|marathon|racing)\b', t):
        return '跑步运动鞋'
    return '休闲及其他成鞋'


def prepare(raw, page, observed_at):
    title = raw.get('title') or ''
    text = raw.get('text') or ''
    sold = re.search(r'([\d,]+)\s+sold\b', text)
    moq = re.search(r'Min\.\s*[Oo]rder:?\s*([\d,]+)\s*([A-Za-z]+)', text)
    price = re.search(r'\$([\d.]+)(?:-([\d.]+))?', raw.get('price_text') or text)
    pid = re.search(r'_(\d+)\.html', raw['url'])
    return dict(product_id=pid.group(1) if pid else raw['url'], page=page,
                title=title, title_characters=len(title), category=classify(title),
                sold_display=int(sold.group(1).replace(',', '')) if sold else None,
                sold_scope='公开显示数量；单位/周期/退货及变体范围未明',
                moq_quantity=int(moq.group(1).replace(',', '')) if moq else None,
                moq_unit=moq.group(2) if moq else None,
                price_min_display=float(price.group(1)) if price else None,
                price_max_display=float(price.group(2) or price.group(1)) if price else None,
                price_currency='USD', price_unit='卡片未留存计价单位，详情待核',
                observed_at=observed_at, url=raw['url'], image_url=raw.get('image'),
                image_visual_review='待逐图实看', source_text=text)


def analyze(source, out):
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    by_id = {}
    appearances = []
    for page in data['pages']:
        for card in page['cards']:
            row = prepare(card, page['page'], page['observed_at'])
            appearances.append(row['product_id'])
            by_id.setdefault(row['product_id'], row)
    rows = list(by_id.values())
    review_file = out.parent / '视觉证据' / '主图实看.json'
    if review_file.exists():
        reviews = {r['product_id']: r for r in json.loads(review_file.read_text(encoding='utf-8'))['items']}
        for row in rows:
            if row['product_id'] in reviews:
                row['image_visual_review'] = '已实看：' + reviews[row['product_id']]['visible']
    rows.sort(key=lambda r: (r['sold_display'] is None, -(r['sold_display'] or 0), r['product_id']))
    categories = collections.Counter(r['category'] for r in rows)
    terms = {'OEM/ODM':r'\b(oem|odm)\b', '定制':r'\b(custom\w*|customiz\w*|customis\w*)\b',
             '透气':r'\bbreathable\b', '步行':r'\bwalking\b', '套脚':r'\bslip[ -]?on\b',
             '针织':r'\b(knit|knitted|knitting|woven|weaving)\b', '舒适':r'\b(comfort\w*|soft)\b',
             '轻量':r'\b(lightweight|light[ -]weight|ultra[ -]light)\b', '宽头':r'\bwide\b',
             '赤足':r'\b(barefoot|zero[ -]drop)\b'}
    term_counts = {k:sum(bool(re.search(v,r['title'],re.I)) for r in rows) for k,v in terms.items()}
    excluded = ['童鞋（不直接对标）','水鞋（不直接对标）','鞋底鞋垫部件','拖鞋穆勒鞋','球类运动鞋','正装鞋（不直接对标）']
    focus = [r for r in rows if r['category'] not in excluded and re.search(r'\b(knit|knitted|knitting|woven|weaving|slip[ -]?on|sock|loafers?)\b',r['title'],re.I)]
    summary = dict(observed_date=data['observed_date'], status=data['status'],
        completed_pages=len(data['pages']), expected_pages=data['expected_pages'],
        page_coverage=len(data['pages'])/data['expected_pages'], raw_cards=len(appearances),
        unique_products=len(rows), duplicate_appearances=len(appearances)-len(rows),
        visible_sold_products=sum(r['sold_display'] is not None for r in rows),
        missing_sold_products=sum(r['sold_display'] is None for r in rows),
        missing_sales_is_zero=False, title_length_median=statistics.median(r['title_characters'] for r in rows),
        titles_over_120=sum(r['title_characters']>120 for r in rows),
        categories=dict(categories), title_term_counts=term_counts,
        moq_counts=dict(collections.Counter((str(r['moq_quantity'])+' '+str(r['moq_unit'])) for r in rows)),
        repeated_sold_counts=collections.Counter(r['sold_display'] for r in rows if r['sold_display'] is not None).most_common(8),
        focus_count=len(focus), focus_visible_sold=sum(r['sold_display'] is not None for r in focus),
        top_focus=focus[:12], top_catalog=rows[:12],
        ranking_status='未获得行业店铺销量榜；不能称凯顺行业销量第一或前列',
        sales_causality='未取得竞品曝光、点击、流量来源、广告、历史版本或询盘转化，不能推断标题/图片因果',
        missing_pages=data['missing_pages'])
    out.mkdir(parents=True, exist_ok=True)
    for name, obj in [('kaisuntd-clean.json',rows),('analysis-summary.json',summary)]:
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'kaisuntd-products.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    chosen=[]
    for group in [focus[:10],rows[:6],list(reversed(focus))[:4]]:
        for row in group:
            if row not in chosen:chosen.append(row)
    cards=''.join('<article><img src="'+html.escape(r['image_url'] or '')+'"><div class="tag">'+html.escape(r['category'])+'</div><h3>'+html.escape(r['title'])+'</h3><p>显示成交 '+('未显示' if r['sold_display'] is None else str(r['sold_display']))+' · '+html.escape(r['source_text'].split('$')[-1].split('\n')[0])+'</p><p>MOQ '+str(r['moq_quantity'])+' '+str(r['moq_unit'])+'</p><a href="'+html.escape(r['url'])+'">原商品 '+r['product_id']+'</a></article>' for r in chosen)
    gallery='<!doctype html><meta charset="utf-8"><title>凯顺主图对照册</title><style>body{font:15px Arial;background:#f3f4f6;color:#172033;margin:30px}header{max-width:1150px}main{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}article{background:white;padding:14px;border-radius:12px}img{width:100%;height:220px;object-fit:contain}h3{font-size:13px;line-height:1.5}.tag{font-size:12px;color:#697586}a{color:#315f9b}</style><header><h1>凯顺主图对照册</h1><p>2026-10-11；已采集34/55页。主图原件来自公开商品卡片，未修改鞋型。显示成交数量不等于已核周期销量；缺失不等于零。此册为代表样本视觉分析，尚未覆盖全店图库。</p></header><main>'+cards+'</main>'
    manifest_file = out.parent / '视觉证据' / 'representative-assets-manifest.json'
    if manifest_file.exists():
        for asset in json.loads(manifest_file.read_text(encoding='utf-8'))['assets']:
            if (out.parent / asset['path']).is_file():
                gallery = gallery.replace(html.escape(asset['url']), html.escape(asset['path']))
    (out.parent/'主图对照册.html').write_text(gallery,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['top_focus','top_catalog']},ensure_ascii=True,indent=2))
    print('FOCUS TOP:',json.dumps([{'id':r['product_id'],'title':r['title'],'sold':r['sold_display'],'moq':str(r['moq_quantity'])+' '+str(r['moq_unit'])} for r in focus[:8]],ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('out',type=Path);args=parser.parse_args();analyze(args.source,args.out)
