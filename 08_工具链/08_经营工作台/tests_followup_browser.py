"""Real Chrome acceptance of a synthetic completion/review/continuation loop.

Enable with BEIQIANG_RUN_BROWSER_TEST=1. The server, project and model process
are isolated fixtures; no production service, customer or external send is used.
"""
import time
import unittest
from unittest.mock import patch

import tests_customer_browser as browser
from batch_sending import BatchSending
from gmail_drafts import GmailDrafts
from single_send_guard import SingleSendGuard


DRIVER = r'''(() => {
const out=document.createElement('pre');out.id='revision-acceptance';out.dataset.state='running';document.body.append(out);
const pause=()=>new Promise(r=>setTimeout(r,50));
const until=async(fn,message)=>{for(let i=0;i<300;i++){const value=await fn();if(value)return value;await pause();}throw Error(message);};
const read=async path=>{const response=await fetch(path,{cache:'no-store'});if(!response.ok)throw Error('GET '+path+' '+response.status);return response.json();};
const btn=(root,label)=>[...root.querySelectorAll('button')].find(x=>x.textContent.trim()===label);
const input=(root,label,value)=>{const node=root.querySelector(`[aria-label="${label}"]`);if(!node)throw Error('input missing '+label);node.value=value;node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));};
const jobId='__SYNTHETIC_JOB_ID__',taskId='local:'+jobId,writes=[];
const originalFetch=window.fetch.bind(window);
window.fetch=(path,options={})=>{if((options.method||'GET').toUpperCase()==='POST')writes.push(new URL(path,location.href).pathname);return originalFetch(path,options);};
(async()=>{
  location.hash='/tasks';
  await until(()=>document.getElementById('page')?.textContent.includes('经营 Inbox'),'Inbox missing');
  const first=await read('/api/desk/task-overview');
  const notice=first.inbox.find(x=>x.kind==='completion_review' && x.task_id===taskId && x.state==='awaiting_review');
  if(!notice)throw Error('finished synthetic run missing from Inbox');
  if(!document.getElementById('page').textContent.includes('外部会话事件桥：未接通') ||
     !document.getElementById('page').textContent.includes('主动通知：未接通'))throw Error('connection boundary not shown');
  if(!document.getElementById('page').textContent.includes('主动提醒未接通'))throw Error('notification boundary not shown');
  const card=await until(()=>[...document.querySelectorAll('#page article.card')].find(x=>
    x.textContent.includes('回合已结束，仍需对照目标和证据验收') && btn(x,'打开任务')),'completion Inbox card missing');
  btn(card,'打开任务').click();
  const event=await until(()=>[...document.querySelectorAll('details.completion-event')].find(x=>
    x.querySelector('summary')?.textContent.includes('回合 1 · 待验收')),'first run review missing');
  event.open=true;
  input(event,'验收结论','continue');input(event,'目标验收状态','not_met');input(event,'能力验收状态','not_met');
  input(event,'成果位置','合成结果');input(event,'欠交付','仍需核对合成产品资料');input(event,'验收下一动作','只读核对合成产品的下一步');
  input(event,'验收证据来源','隔离测试记录');input(event,'验收证据时间',new Date().toISOString());input(event,'验收证据说明','第一轮合成结果已生成，目标尚未完成');
  const save=btn(event,'登记本轮验收');if(!save)throw Error('review submit button missing');save.click();
  const second=await until(async()=>{const job=await read('/api/desk/job?id='+encodeURIComponent(jobId));
    return job.attempt===2 && job.worker_finished===true ? job : null;},'second synthetic attempt not finished');
  if(second.id!==jobId || second.mode!=='mail_draft')throw Error('continuation left original task or mode');
  if((second.runs||[]).length!==2 || second.status!=='completed')throw Error('second run receipt incomplete');
  const context=await read('/api/desk/task-context?id='+encodeURIComponent(jobId));
  const events=context.completion_events||[],firstEvent=events.find(x=>x.attempt===1),secondEvent=events.find(x=>x.attempt===2);
  if(firstEvent?.assessment?.disposition!=='continue' || firstEvent.assessment.goal_status!=='not_met' ||
     firstEvent.dispatch?.target_job_id!==jobId || firstEvent.dispatch?.target_attempt!==2 || firstEvent.dispatch?.state!=='completed')
    throw Error('original review or continuation receipt missing');
  if(secondEvent?.state!=='awaiting_review')throw Error('second run did not remain pending acceptance');
  document.getElementById('reload').click();
  await until(()=>[...document.querySelectorAll('details.completion-event summary')].some(x=>x.textContent.includes('回合 1 · 接续回合已结束，待验收')) &&
    [...document.querySelectorAll('details.completion-event summary')].some(x=>x.textContent.includes('回合 2 · 待验收')),
    'refreshed run receipts missing from task detail');
  if(writes.filter(path=>path==='/api/desk/job/assess-completion').length!==1 ||
     writes.some(path=>/send|continue-followup/.test(path)))throw Error('unexpected or repeated mutation');
  location.hash='/tasks';
  await until(()=>document.getElementById('page')?.textContent.includes('经营 Inbox'),'Inbox did not reopen');
  const refresh=await until(()=>btn(document.getElementById('page'),'刷新已接入工作'),'Inbox refresh missing');refresh.click();
  const after=await read('/api/desk/task-overview');
  if(!after.inbox.some(x=>x.kind==='completion_review' && x.task_id===taskId && x.event_id===secondEvent.event_id && x.state==='awaiting_review'))
    throw Error('second run review missing after refresh');
  if(after.inbox.some(x=>x.kind==='completion_review' && x.task_id===taskId && x.event_id===firstEvent.event_id))
    throw Error('completed continuation left duplicate first-run Inbox item');
  if(!document.getElementById('page').textContent.includes('主动提醒未接通'))throw Error('notification boundary disappeared');
  out.dataset.state='pass';out.textContent='Synthetic run reached Inbox; review started one same-task attempt; new run remained pending; no send.';
})().catch(error=>{out.dataset.state='fail';out.textContent=String(error.stack||error);});
})();'''


class FollowupBrowserTests(browser.CustomerBrowserTests):
    def test_stale_forms_return_409_and_preserve_input_and_latest_values(self):
        previous_driver=browser.DRIVER
        fixture_class=browser.tests_desk_http.DeskHTTPTests
        original_setup=fixture_class.setUp
        created=[]

        def setup_followup(fixture):
            original_setup(fixture)
            try:
                if fixture.http.server_port == 8766:
                    raise AssertionError('isolated test must not use the production workbench port')
                job=fixture.app.agent_jobs.start('product:BQ009','合成商品目标，仍需后续核对',mode='mail_draft')
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    current=fixture.app.agent_jobs.get_job(job['id'])
                    if current.get('worker_finished') is True and current.get('status')=='completed':
                        break
                    time.sleep(.01)
                else:
                    raise AssertionError('first synthetic run did not finish')
                if not current.get('completion_events',{}).get('1'):
                    raise AssertionError('first completion event was not registered')
                created.append(fixture)
                browser.DRIVER=DRIVER.replace('__SYNTHETIC_JOB_ID__',job['id'])
            except BaseException:
                fixture.tearDown()
                raise

        try:
            with patch.object(fixture_class,'setUp',setup_followup), \
                 patch.object(GmailDrafts,'send',side_effect=AssertionError('synthetic test must not send mail')) as gmail, \
                 patch.object(SingleSendGuard,'send',side_effect=AssertionError('synthetic test must not send mail')) as single, \
                 patch.object(BatchSending,'send',side_effect=AssertionError('synthetic test must not send mail')) as batch:
                super().test_stale_forms_return_409_and_preserve_input_and_latest_values()
                self.assertEqual(len(created),1)
                self.assertEqual(len(created[0].processes),2)
                self.assertIn('只读核对合成产品的下一步',created[0].processes[1].stdin.value)
                gmail.assert_not_called();single.assert_not_called();batch.assert_not_called()
        finally:
            browser.DRIVER=previous_driver


if __name__=='__main__':
    unittest.main()
