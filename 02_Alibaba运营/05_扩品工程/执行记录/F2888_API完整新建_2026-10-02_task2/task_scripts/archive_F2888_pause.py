from pathlib import Path
import json,shutil,hashlib
W=Path(__file__).resolve().parent;O=W/'F2888_execution';D=Path.home()/'Desktop'/'贝强/02_Alibaba运营/05_扩品工程/执行记录/F2888_API完整新建_2026-10-02_task2'
assert json.loads((O/'PAUSED_USER_2026-10-02.json').read_text(encoding='utf-8'))['paused']
D.mkdir(parents=True,exist_ok=True);copied=[]
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);a=hashlib.sha256(src.read_bytes()).hexdigest();assert hashlib.sha256(dst.read_bytes()).hexdigest()==a;copied.append({'relative_path':str(dst.relative_to(D)),'sha256':a})
for p in O.rglob('*'):
 if p.is_file():copy(p,D/p.relative_to(O))
for p in (W/'shangchao_2357652').iterdir():
 if p.is_file():copy(p,D/'supplier_originals'/p.name)
for name in ['setup_F2888.py','api_F2888.py','stage_F2888.py','prepare_F2888.py','export_F2888_buyer_images.py','finalize_F2888_assets.py','check_F2888_cdn.py','pause_F2888.py','archive_F2888_pause.py']:
 copy(W/name,D/'task_scripts'/name)
receipt={'path':str(D),'copied_count':len(copied),'files':copied,'status':'SAVED_PAUSED_NO_AUTOMATIC_RESUME'}
(D/'archive_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');(O/'archive_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(str(D));print('Copied and hash verified',len(copied),'files; no external calls or shared-table writes.')
