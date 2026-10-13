from pathlib import Path
import json,datetime,hashlib
W=Path(__file__).parent;O=W/'805_execution';P=Path(r'C:\Users\spq\Desktop\贝强')
digest=hashlib.sha256((O/'intended_payload.xml').read_bytes()).hexdigest();assert digest=='6ea6bdd4fa7dd78b3df07b90714046221a09805c03f07e32cfddbbb0910a956f'
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
save('independent_payload_review.json',{'verdict':'PASS','reviewer':'review_9968','xml_sha256':digest,'actual_review':'Current schema material names and IDs,21SKU,omitted inventory/skuId,three prices,6M4D5company6FAQ; prior outsole/midsole reversal corrected before any product mutation','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
save('official_cdn_visual_gate.json',{'verdict':'PASS','reviewer':'review_9968 + task7','actual_images':13,'dimensions':'All same as upload','pixel_difference':'Zero all13','actual_visual_review':'Same style/color, complete shoes and graphic copy; no redraw or wrong materials','evidence':['official_cdn_readback.json','official_cdn_contact.jpg']})
for p in [O/'ownership.json',P/'02_Alibaba运营/05_扩品工程/执行记录/805_待发布包_2026-10-02/ownership.json']:
 j=json.loads(p.read_text(encoding='utf-8'));assert j['owner']=='task-7';j.update(old_product_ids=['1601943738486'],old_model='HR065-A',old_action='NOT_SENT_PARENT_OFFOWNER_ONLY',status='READY_SINGLE_CREATE',preflight_xml_sha256=digest);p.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
q=P/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR持续替换目标与货源队列_2026-10-02.md';tag='805旧位确认：HR065-A / 1601943738486'
if tag not in q.read_text(encoding='utf-8'):
 with q.open('a',encoding='utf-8') as h:h.write('\n\n'+tag+'；父知识owner已配，task7确认本款占用。仅关联登记，旧品NOT_SENT；本款单次新建待回执，公开/真实5分验收前不报HR替换完成。\n')
t=(W/'pipeline_805.py').read_text(encoding='utf-8');needle="elif action=='publish':\n";replacement=needle+" for gate in ['independent_payload_review.json','official_cdn_visual_gate.json']:assert json.loads((O/gate).read_text(encoding='utf-8'))['verdict']=='PASS'\n assert hashlib.sha256((O/'intended_payload.xml').read_bytes()).hexdigest()==json.loads((O/'independent_payload_review.json').read_text(encoding='utf-8'))['xml_sha256']\n"
if "for gate in ['independent_payload_review.json'" not in t:t=t.replace(needle,replacement)
(W/'pipeline_805.py').write_text(t,encoding='utf-8')
print('805 exact XML independently approved; HR065-A mapped reference only; mutation remains one-shot ledger',flush=True)
