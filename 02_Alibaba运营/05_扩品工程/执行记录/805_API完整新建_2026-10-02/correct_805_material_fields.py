from pathlib import Path
import xml.etree.ElementTree as E
W=Path(__file__).parent;p=W/'prepare_805.py';t=p.read_text(encoding='utf-8')
t=t.replace("prop('p-20700','Rubber',next(q.get('value') for q in props['p-20700'].findall('./options/option') if q.get('displayName','').lower()=='rubber'))","prop('p-20700','Not specified',-2)")
t=t.replace("prop('p-191290426','Not specified',-2)","prop('p-191290426','Rubber',next(q.get('value') for q in props['p-191290426'].findall('./options/option') if q.get('displayName','').lower()=='rubber'))")
p.write_text(t,encoding='utf-8');r=E.parse(W/'805_execution/schema.xml').getroot()
for k in ['p-20700','p-191290426','p-191290428','p-191290430']:
 d=next(x for x in r.iter('field') if x.get('id')==k);print(k,d.get('name'),[(x.get('displayName'),x.get('value')) for x in d.findall('./options/option') if x.get('displayName')=='Rubber'],flush=True)
