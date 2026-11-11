"""Real Chrome acceptance against isolated AgentJobs and an ephemeral server."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch
import unittest

import tests_customer_browser as browser


DRIVER = r'''(() => {
const result=document.createElement('pre');result.id='revision-acceptance';result.dataset.state='running';document.body.append(result);
const pause=()=>new Promise(resolve=>setTimeout(resolve,50));
const until=async(fn,message)=>{for(let n=0;n<300;n++){const value=fn();if(value)return value;await pause();}throw Error(message);};
const button=(label)=>[...document.querySelectorAll('button')].find(x=>x.textContent.trim()===label);
const read=async(path)=>{const r=await fetch(path);if(!r.ok)throw Error('read '+r.status);return r.json();};
const post=async(path,body,token)=>{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Token':token},body:JSON.stringify(body)});return {status:r.status,body:await r.json()};};
(async()=>{
  location.hash='/task/'+encodeURIComponent('local:__GROUP__');
  await until(()=>button('预览按优先级可执行的下一项'),'group preview missing');
  button('预览按优先级可执行的下一项').click();
  await until(()=>button('确认启动此候选'),'first candidate missing');
  if(!document.querySelector('.priority-next').textContent.includes('SYNTHETIC_HIGH'))throw Error('high priority was not previewed');
  const token=(await read('/api/desk/bootstrap')).csrf_token;
  const overview=await read('/api/desk/task-overview');
  const high=overview.tasks.find(t=>t.id==='local:__HIGH__');
  const changed=await post('/api/desk/job/adjust',{id:'__HIGH__',expected_version:high.version,priority:'low'},token);
  if(changed.status!==200)throw Error('independent synthetic change failed');
  button('确认启动此候选').click();
  await until(()=>document.querySelector('.priority-next .agent-feedback')?.textContent.includes('候选或版本已变化'),'stale preview did not conflict');
  let current=await read('/api/desk/task-overview');
  if(current.tasks.some(t=>['local:__HIGH__','local:__LOW__'].includes(t.id) && t.status!=='planned'))throw Error('stale preview started a task');
  button('预览按优先级可执行的下一项').click();
  await until(()=>document.querySelector('.priority-next')?.textContent.includes('SYNTHETIC_LOW'),'new candidate missing');
  button('确认启动此候选').click();
  for(let n=0;n<300;n++){
    current=await read('/api/desk/task-overview');
    if(current.tasks.find(t=>t.id==='local:__LOW__')?.status==='queued')break;
    await pause();
  }
  if(current.tasks.find(t=>t.id==='local:__LOW__')?.status!=='queued')throw Error('new candidate was not claimed');
  if(current.tasks.find(t=>t.id==='local:__HIGH__')?.status!=='planned')throw Error('other task changed');
  result.dataset.state='pass';result.textContent='Synthetic browser preview, stale conflict, reprioritization and explicit claim passed.';
})().catch(error=>{result.dataset.state='fail';result.textContent=String(error.stack||error);});
})();'''


class PriorityBrowserTests(browser.CustomerBrowserTests):
    def test_stale_forms_return_409_and_preserve_input_and_latest_values(self):
        previous_driver=browser.DRIVER
        fixture_class=browser.tests_desk_http.DeskHTTPTests
        original_setup=fixture_class.setUp
        def setup_with_group(fixture):
            original_setup(fixture)
            jobs=fixture.app.agent_jobs
            group=jobs.create_group('product:BQ009','Synthetic browser group')
            low=jobs.start('product:BQ009','Synthetic low plan',parent_job_id=group['id'],defer=True)
            high=jobs.start('product:BQ009','Synthetic high plan',parent_job_id=group['id'],defer=True)
            jobs.adjust(low['id'],expected_version=low['version'],next_action='SYNTHETIC_LOW')
            jobs.adjust(high['id'],expected_version=high['version'],priority='high',next_action='SYNTHETIC_HIGH')
            jobs._start_claimed_worker=lambda *_:None
            browser.DRIVER=(DRIVER.replace('__GROUP__',group['id']).replace('__HIGH__',high['id']).replace('__LOW__',low['id']))
        try:
            with patch.object(fixture_class,'setUp',setup_with_group):
                super().test_stale_forms_return_409_and_preserve_input_and_latest_values()
        finally:
            browser.DRIVER=previous_driver

    def test_standalone_priority_from_the_real_overview_page(self):
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
        def setup_standalone(fixture):
            original_setup(fixture)
            jobs=fixture.app.agent_jobs
            low=jobs.start('product:BQ009','Synthetic low plan',defer=True)
            high=jobs.start('product:BQ009','Synthetic high plan',defer=True)
            jobs.adjust(low['id'],expected_version=low['version'],next_action='SYNTHETIC_LOW')
            jobs.adjust(high['id'],expected_version=high['version'],priority='high',next_action='SYNTHETIC_HIGH')
            jobs._start_claimed_worker=lambda *_:None
            driver=DRIVER.replace("location.hash='/task/'+encodeURIComponent('local:__GROUP__');","location.hash='/tasks';")
            driver=driver.replace('预览按优先级可执行的下一项','预览独立计划优先项').replace('确认启动此候选','确认启动该独立计划').replace('.priority-next','.standalone-priority')
            browser.DRIVER=driver.replace('__HIGH__',high['id']).replace('__LOW__',low['id'])
        try:
            with patch.object(fixture_class,'setUp',setup_standalone), patch.object(browser.InjectedHandler,'do_GET',serve_staged):
                super().test_stale_forms_return_409_and_preserve_input_and_latest_values()
        finally:
            browser.DRIVER=previous_driver


if __name__ == '__main__':
    unittest.main()
