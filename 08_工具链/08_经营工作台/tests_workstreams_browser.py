"""Real Chrome acceptance of workstream projections with synthetic records."""
from datetime import datetime,timedelta,timezone
import os
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
import unittest

import tests_customer_browser as browser


DRIVER = r'''(() => {
const result=document.createElement('pre');result.id='revision-acceptance';result.dataset.state='running';document.body.append(result);
const pause=()=>new Promise(resolve=>setTimeout(resolve,50));
const until=async(fn,message)=>{for(let n=0;n<300;n++){const value=fn();if(value)return value;await pause();}throw Error(message);};
(async()=>{
  location.hash='/tasks';
  await until(()=>document.querySelectorAll('.workstream-card').length===3,'three workstreams missing');
  const cards=[...document.querySelectorAll('.workstream-card')];
  for(const label of ['总控与工具','国际站运营','独立站增长']){
    const card=cards.find(x=>x.textContent.includes(label));if(!card)throw Error('workstream missing '+label);
    if(!card.textContent.includes('当前状态未知'))throw Error('stale status not unknown');
    if(!card.textContent.includes('未关联工作台任务'))throw Error('unlinked job not disclosed');
    if(!card.textContent.includes('下一步'))throw Error('next action missing');
    if(card.querySelectorAll('a[href^="codex://threads/"]').length!==1)throw Error('reference link missing');
    if([...card.querySelectorAll('button')].some(x=>/启动会话|发送消息|恢复会话/.test(x.textContent)))throw Error('reference presented as controllable');
  }
  if(!cards.find(x=>x.textContent.includes('国际站运营')).textContent.includes('SYNTHETIC_RESTRICTION'))throw Error('source blocker missing');
  result.dataset.state='pass';result.textContent='Three explicit workstreams, stale references, source excerpts and read-only links passed.';
})().catch(error=>{result.dataset.state='fail';result.textContent=String(error.stack||error);});
})();'''


class WorkstreamsBrowserTests(browser.CustomerBrowserTests):
    def test_stale_forms_return_409_and_preserve_input_and_latest_values(self):
        previous_driver=browser.DRIVER
        fixture_class=browser.tests_desk_http.DeskHTTPTests
        original_setup=fixture_class.setUp
        original_get=browser.InjectedHandler.do_GET
        staged=os.environ.get('BEIQIANG_TEST_DESK_JS')
        def serve_staged(handler):
            if staged and urlsplit(handler.path).path=='/desk.js':
                handler.check_host();payload=Path(staged).read_bytes()
                handler.send_response(200);handler.send_header('Content-Type','text/javascript; charset=utf-8')
                handler.send_header('Content-Length',str(len(payload)));handler.end_headers();handler.wfile.write(payload)
            else:original_get(handler)
        def setup_workstreams(fixture):
            original_setup(fixture)
            files={
                '08_工具链/08_经营工作台/README.md':'**总控当前工作：**合成工作。\n**总控已验证结果：**合成结果。\n**总控下一步：**合成下一步。\n**总控阻塞：**合成阻塞。\n',
                '02_Alibaba运营/01_店铺与全店诊断/店铺经营诊断.md':'本轮研究七号仓库；11月11日授权后 SYNTHETIC_RESTRICTION。\n负责人要求优先使用真实适配的现有鞋靴类目，继续核对。\n',
                '03_独立站/README.md':'**持续推进：国际站与独立站产品对齐（2026-11-11）。** 合成结果。继续逐款核对。\n'}
            for name,content in files.items():
                p=fixture.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf8')
            now=datetime.now(timezone.utc);old=(now-timedelta(minutes=20)).isoformat()
            ids=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333']
            rows=[{'id':i,'hostId':'durable','cwd':str(fixture.root),'status':'active','title':'Synthetic thread'} for i in ids]
            fixture.app.desktop_snapshot.import_snapshot({'observed_at':old,'status':'ok','truncated':False,'threads':rows})
            for line,thread in zip(('tools','alibaba','website'),ids):
                fixture.app.desktop_snapshot.link_workstream({'workstream':line,'host_id':'durable','thread_id':thread,'source_note':'synthetic explicit reference'})
            browser.DRIVER=DRIVER
        try:
            with patch.object(fixture_class,'setUp',setup_workstreams),patch.object(browser.InjectedHandler,'do_GET',serve_staged):
                super().test_stale_forms_return_409_and_preserve_input_and_latest_values()
        finally:
            browser.DRIVER=previous_driver


if __name__ == '__main__':
    unittest.main()
