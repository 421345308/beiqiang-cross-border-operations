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
if(!document.getElementById('page').textContent.includes('Fixture buyer'))throw Error('website inquiry missing from business inbox');
button('查看客户').click();await until(()=>location.hash.includes('/object/customer%3Awebsite-BQ-REAL') && document.querySelector('.workflow-editor'),'inbox did not open the original customer');
location.hash='/tasks';await until(()=>document.querySelector('[aria-label="任务要求"]'),'task return failed');
const instruction=document.querySelector('[aria-label="任务要求"]');instruction.value='BQ009 整理真实商品资料';button('查找接续任务').click();
await until(()=>button('准备新任务（不启动）'),'command did not resolve BQ009 to create');
button('准备新任务（不启动）').click();await until(()=>button('确认启动此任务'),'draft task detail not opened');
const taskHash=location.hash;if(!taskHash.includes('/task/local%3A'))throw Error('not actual task route');
const packet=document.querySelector('[aria-label="可恢复任务上下文"]');if(!packet || !packet.value.includes('BQ009'))throw Error('context omitted product');
if(!document.getElementById('page').textContent.includes('尚未执行'))throw Error('draft not clearly unstarted');
const read=async path=>{const response=await fetch(path,{cache:'no-store'});if(!response.ok)throw Error('GET '+path+' '+response.status);return response.json();};
const original=JSON.parse(packet.value),token=(await read('/api/desk/bootstrap')).csrf_token;
if(original.job.status!=='planned' || original.goal!=='BQ009 整理真实商品资料')throw Error('initial synthetic plan incorrect');
const adjust=async body=>fetch('/api/desk/job/adjust',{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Token':token},body:JSON.stringify(body)});
const change={id:original.job.id,expected_version:original.job.version,current_goal:'先核对合成商品的当前供货目标',
  effective_decisions:[{text:'先检查来源记录，不承诺供货',source:'隔离测试中的负责人决定'}],
  intent_source:'隔离测试中的工作记录',intent_reason:'业务目标已调整',next_action:'读取合成来源并准备核对结果'};
const saved=await adjust(change);if(!saved.ok)throw Error('intent save failed '+saved.status);const updated=await saved.json();
if(updated.intent.version!==1 || updated.status!=='planned')throw Error('intent version or planned state incorrect');
const stale=await adjust({...change,current_goal:'陈旧目标不能覆盖',effective_decisions:[{text:'陈旧决定',source:'旧记录'}],next_action:'陈旧下一步'});
if(stale.status!==409)throw Error('stale intent write did not return 409');
const latest=await read('/api/desk/task-context?id='+encodeURIComponent(original.job.id));
if(latest.goal!==change.current_goal || latest.next_action!==change.next_action || latest.intent_version!==1 ||
   latest.effective_decisions[0]?.text!==change.effective_decisions[0].text || latest.effective_decisions[0]?.source!==change.effective_decisions[0].source)
  throw Error('stale intent write changed current context');
if(!latest.job.intent.history.some(item=>item.goal===original.goal && item.status==='superseded'))throw Error('superseded goal history missing');
const verifyDetail=async()=>{
  await until(()=>{const page=document.getElementById('page').textContent;return page.includes('目标：'+change.current_goal) &&
    page.includes(change.effective_decisions[0].text+' · 来源：'+change.effective_decisions[0].source) && page.includes('下一步：'+change.next_action);},'current intent detail not rendered');
  const page=document.getElementById('page').textContent,copy=document.querySelector('[aria-label="可恢复任务上下文"]');
  if(page.includes('目标：'+original.goal) || page.includes('陈旧目标不能覆盖') || page.includes('陈旧下一步'))throw Error('old intent shown as current');
  const context=JSON.parse(copy.value);if(context.goal!==change.current_goal || context.next_action!==change.next_action ||
    context.intent_version!==1 || context.effective_decisions[0]?.source!==change.effective_decisions[0].source)throw Error('updated task packet not preserved');
};
location.hash='/tasks';await until(()=>document.querySelector('[aria-label="任务要求"]'),'list return failed');
location.hash=taskHash;await until(()=>button('确认启动此任务'),'task re-entry failed');
await verifyDetail();
document.getElementById('reload').click();await until(()=>!document.getElementById('reload').disabled && button('确认启动此任务'),'task refresh failed');
await verifyDetail();
const response=await fetch('/api/desk/task-overview');const overview=await response.json();if(!overview.tasks.some(t=>t.origin==='local' && t.status==='planned'))throw Error('planned task not persisted');
out.dataset.state='pass';out.textContent='Real Chrome verified the synthetic planned task, intent/decision update, stale 409, re-entry and refresh';
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
