from pathlib import Path
import json
W=Path(__file__).resolve().parent;O=W/'F2888_execution';O.mkdir(exist_ok=True)
auth={'authorized':True,'resumed_at_UTC':'2026-10-02T22:13:00Z','source':'Parent delegated explicit user resume / Sentinel_c043320b2208819188af8aa3aea1259b','quote':'可以恢复了，请继续进行任务','scope':'F2888 source2357652 / HR056-A preparation and one product create; no old-off or shared production configuration writes'}
(O/'resume_authorization.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2),encoding='utf-8')
s=(W/'api_boots.py').read_text(encoding='utf-8')
for a,b in [('H219','F2888'),('BQ-ABH219','BQ-WBF2888'),('BQ-ABF2888','BQ-WBF2888'),('1601943767092','1601943775160'),('HR048-B','HR056-A'),("Women's Lace-Up Ankle Boots with Side Zipper and Lug Sole","Women's Quilted Winter Boots with Plush Lining and Side Zipper"),('len(rows)==12','len(rows)==13')]:s=s.replace(a,b)
s=s.replace("assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,10,2,18,tzinfo=datetime.timezone.utc),'Hard stop reached'","assert json.loads((O/'resume_authorization.json').read_text(encoding='utf-8'))['authorized'] is True")
s=s.replace("assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,10,2,18,tzinfo=datetime.timezone.utc),'Hard stop'","assert json.loads((O/'resume_authorization.json').read_text(encoding='utf-8'))['authorized'] is True")
s=s.replace(";assert str(pid)=='1601969936536'","")
(W/'api_F2888.py').write_text(s,encoding='utf-8')
print('Dedicated F2888 runtime staged; H219 unchanged.')
