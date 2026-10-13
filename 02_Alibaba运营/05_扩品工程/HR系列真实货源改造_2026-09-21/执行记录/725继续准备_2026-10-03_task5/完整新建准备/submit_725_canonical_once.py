from pathlib import Path
from types import SimpleNamespace
import importlib.util,json,sys
R=Path(r'C:\Users\spq\Desktop\贝强');O=Path(__file__).parent/'725_next_preparation_20261003'
manifest=O/'publish_manifest_complete.json';m=json.loads(manifest.read_text(encoding='utf-8'))
assert m['ready_for_submission'] and not m['placeholder_urls_present']
ledger=json.loads((O/'upload_once_ledger.json').read_text());assert len(ledger['uploads'])==16 and all(a['status']=='UPLOADED_BUSINESS_VERIFIED' for a in ledger['uploads'])
receipt=O/'create_once_receipt.json';assert not receipt.exists(),'Existing write reservation: reconcile; never repeat create'
sys.path.insert(0,str(R/'08_工具链/01_业务脚本/国际站扩品'));import publish_hot_rank_hr_a_batch as pub
spec=importlib.util.spec_from_file_location('sdk',R/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');sdk=importlib.util.module_from_spec(spec);spec.loader.exec_module(sdk)
sdk.http_json=lambda req,timeout=60:sdk.native_http_json(req,timeout=60)
pub.load_client=lambda:sdk
raise SystemExit(pub.run_scoped_cli(SimpleNamespace(mode='publish',input_manifest=str(manifest),receipt=str(receipt),product_id=None)))
