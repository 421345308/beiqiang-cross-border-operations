"""Isolated real Chrome task-route smoke test. No production services or data."""
import unittest
import tests_customer_browser as browser

DRIVER = r'''(() => {
const out=document.createElement('pre');out.id='revision-acceptance';out.dataset.state='running';document.body.append(out);
const wait=()=>new Promise(r=>setTimeout(r,50));
(async()=>{location.hash='/tasks';for(let n=0;n<250;n++){if(document.querySelector('[aria-label="任务要求"]'))break;await wait();}
if(!document.querySelector('[aria-label="任务要求"]'))throw Error('task route missing');
if(!document.getElementById('page').textContent.includes('本地：'))throw Error('local source status absent');
if(!document.getElementById('page').textContent.includes('云端：'))throw Error('cloud source status absent');
if(!document.querySelector('a[data-nav="tasks"]'))throw Error('task navigation missing');
const until=async(fn,msg)=>{for(let n=0;n<250;n++){const value=fn();if(value)return value;await wait();}throw Error(msg);};
const button=label=>[...document.querySelectorAll('button')].find(x=>x.textContent===label);
const instruction=document.querySelector('[aria-label="任务要求"]');instruction.value='BQ009 整理真实商品资料';button('查找接续任务').click();
await until(()=>button('准备新任务（不启动）'),'command did not resolve BQ009 to create');
button('准备新任务（不启动）').click();await until(()=>button('确认启动此任务'),'draft task detail not opened');
const taskHash=location.hash;if(!taskHash.includes('/task/local%3A'))throw Error('not actual task route');
const packet=document.querySelector('[aria-label="可恢复任务上下文"]');if(!packet || !packet.value.includes('BQ009'))throw Error('context omitted product');
if(!document.getElementById('page').textContent.includes('尚未执行'))throw Error('draft not clearly unstarted');
location.hash='/tasks';await until(()=>document.querySelector('[aria-label="任务要求"]'),'list return failed');
location.hash=taskHash;await until(()=>button('确认启动此任务'),'task re-entry failed');
document.getElementById('reload').click();await until(()=>!document.getElementById('reload').disabled && button('确认启动此任务'),'task refresh failed');
const response=await fetch('/api/desk/task-overview');const overview=await response.json();if(!overview.tasks.some(t=>t.origin==='local' && t.status==='planned'))throw Error('planned task not persisted');
out.dataset.state='pass';out.textContent='Real Chrome rendered unified task route with explicit source availability';
})().catch(e=>{out.dataset.state='fail';out.textContent=e.stack || String(e);});
})();'''

class TaskBrowserTests(browser.CustomerBrowserTests):
    def test_stale_forms_return_409_and_preserve_input_and_latest_values(self):
        previous=browser.DRIVER
        try:
            browser.DRIVER=DRIVER
            super().test_stale_forms_return_409_and_preserve_input_and_latest_values()
        finally:
            browser.DRIVER=previous

if __name__=='__main__': unittest.main()