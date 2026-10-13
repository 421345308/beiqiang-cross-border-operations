from pathlib import Path
import sys,json,importlib.util,xml.etree.ElementTree as E
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'3522_execution';D=O/'keyword_protocol';D.mkdir(exist_ok=True);P=Path(r'C:\Users\spq\Desktop\贝强')
s=importlib.util.spec_from_file_location('sdk_keyword_probe',P/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(s);s.loader.exec_module(sdk);c=sdk.load_config(Path.home()/'.config/beiqiang/alibaba-openapi.json')
sys.path.insert(0,str(W.parent/'task-8'));from sdk_runtime_5998 import load
sdk.http_json=load().http_json
# Existing meaningful catalog keyword is a format reference only, not a source of this shoe's facts.
pid=1601943650718
j=sdk.top_call(c,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':pid,'language':'en_US'}});(D/'HR044A_reference_render.response.json').write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8');d=j.get('alibaba_icbu_product_schema_render_response',j);r=E.fromstring(d['data']);n=r.find("./field[@id='productKeywords']");(D/'HR044A_keywords.xml').write_text(E.tostring(n,encoding='unicode'),encoding='utf-8');print(E.tostring(n,encoding='unicode'),flush=True)
