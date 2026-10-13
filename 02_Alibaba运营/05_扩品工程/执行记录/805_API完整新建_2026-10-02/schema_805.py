from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
O=Path(__file__).parent/'805_execution';P=Path(r'C:\Users\spq\Desktop\贝强')
s=importlib.util.spec_from_file_location('approved_sdk_805',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);config=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
sys.path.insert(0,str(W if False else Path(r'C:\Users\spq\Documents\Codex\2026-10-02\task-8')));from sdk_runtime_5998 import load;sdk.http_json=load().http_json
for method,params,name in [('alibaba.icbu.category.get.new',{'cat_id':202240835},'category'),('alibaba.icbu.product.schema.get',{'param_product_top_publish_request':{'cat_id':202240835,'language':'en_US'}},'schema')]:
 (O/(name+'.params.json')).write_text(json.dumps(params),encoding='utf-8');j=sdk.top_call(config,method,params);(O/(name+'.response.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');keys=[k for k in j if k.endswith('_response') and k!='error_response'];d=j[keys[0]] if len(keys)==1 else j;assert not j.get('error_response'),j;(O/(name+'.flat.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 if name=='category':assert d['category']['leaf_category'] and d['category']['name']=='Loafers';print(json.dumps(d),flush=True)
 else:(O/'schema.xml').write_text(d['data'],encoding='utf-8');print('Fresh805 mens Loafers schema saved',flush=True)
