"""Opt-in Chrome/HTTP batch acceptance with synthetic objects and local-only drafts.

Run BEIQIANG_RUN_BROWSER_TEST=1; optional BEIQIANG_TEST_CHROME executable.
No real customer records, CRM, mail credentials or outbound transport are used.
"""
import copy
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

import server
import tests_desk_http
from tests_customer_browser import REAL_POPEN

DESK = Path(__file__).resolve().parent
DRIVER = r'''(() => {
 const out=document.createElement('pre');out.id='batch-browser-acceptance';out.dataset.state='running';document.body.append(out);
 const nativeFetch=window.fetch.bind(window);let sends=0;
 window.fetch=(path,options={})=>{if(options.method==='POST' && /\/(send|research|revise)$/.test(String(path))){sends++;throw Error('Forbidden external operation in browser fixture');}return nativeFetch(path,options);};
 const check=(value,message)=>{if(!value)throw Error(message);};
 const pause=()=>new Promise(resolve=>setTimeout(resolve,50));
 const until=async(fn,message)=>{for(let i=0;i<250;i++){const value=fn();if(value)return value;await pause();}throw Error(message);};
 const button=(root,label)=>[...root.querySelectorAll('button')].find(node=>node.textContent.trim()===label);
 const read=async path=>{const response=await fetch(path,{cache:'no-store'});check(response.ok,'GET failed '+path);return response.json();};
 const row=name=>[...document.querySelectorAll('.batch-row')].find(node=>node.querySelector('h3')?.textContent===name);
 const input=label=>document.querySelector('[aria-label="'+label+'"]');
 (async()=>{
  await until(()=>row('Synthetic Alpha Buyer') && row('Synthetic Beta Buyer'),'two synthetic customers not rendered');
  check(row('Synthetic Alpha Buyer').getBoundingClientRect().width>0,'Alpha not visible');
  check(row('Synthetic Beta Buyer').getBoundingClientRect().width>0,'Beta not visible');
  const batch=(await read('/api/customer-batches')).items[0];const url='/api/customer-batches/'+encodeURIComponent(batch.id);
  const before=await read(url), betaBefore=before.items.find(item=>item.object_id==='customer:browser-beta');
  const groups=document.querySelector('.batch-research-groups');
  await until(()=>groups?.textContent.includes('Synthetic Beta Buyer · 尚未启动'),'persisted research group not displayed');
  check(groups.textContent.includes('Synthetic Alpha Buyer · 已形成成果'),'completed child not displayed');
  button(groups,'继续尚未启动的客户研究').click();
  await until(()=>!groups.textContent.includes('Synthetic Beta Buyer · 尚未启动'),'planned child did not continue');
  input('搜索批次内客户').value='Synthetic';input('搜索批次内客户').dispatchEvent(new Event('input',{bubbles:true}));
  button(row('Synthetic Alpha Buyer'),'审阅这位客户').click();
  await until(()=>input('英文正文（发送给客户）')?.value==='Alpha original proposal','Alpha draft missing');
  check(document.querySelector('.batch-detail').textContent.includes('Alpha source evidence'),'Alpha source not displayed');
  check(input('收件人').value==='alpha@example.test','Alpha recipient wrong');
  input('仅此客户的修改要求').value='Only Alpha: explain its casual footwear assortment.';
  button(document.querySelector('.batch-detail'),'保存修改要求').click();
  await until(()=>document.querySelector('.batch-detail').textContent.includes('已保存此客户的修改要求'),'Alpha change request not saved');
  const after=await read(url), alphaAfter=after.items.find(item=>item.object_id==='customer:browser-alpha'), betaAfter=after.items.find(item=>item.object_id==='customer:browser-beta');
  check(alphaAfter.change_request==='Only Alpha: explain its casual footwear assortment.','Alpha request not persisted');
  check(alphaAfter.review_state==='changes_requested','Alpha review state wrong');
  check(betaAfter.item_revision===betaBefore.item_revision,'Alpha save changed Beta revision');
  check(betaAfter.change_request===betaBefore.change_request,'Alpha save changed Beta request');
  check(betaAfter.draft.version===betaBefore.draft.version,'Alpha save changed Beta draft');
  button(row('Synthetic Beta Buyer'),'审阅这位客户').click();
  await until(()=>input('英文正文（发送给客户）')?.value==='Beta original proposal','Beta draft missing after switching');
  check(document.querySelector('.batch-detail').textContent.includes('Beta source evidence'),'Beta source missing');
  check(input('收件人').value==='beta@example.test','Beta recipient wrong');
  check(input('仅此客户的修改要求').value==='','Alpha request leaked into Beta');
  button(row('Synthetic Alpha Buyer'),'审阅这位客户').click();
  await until(()=>input('英文正文（发送给客户）')?.value==='Alpha original proposal','Alpha draft not reopened');
  check(input('仅此客户的修改要求').value===alphaAfter.change_request,'Alpha request not reopened');
  check(input('搜索批次内客户').value==='Synthetic','batch filter lost');
  check((await read(url)).items.length===2,'original batch no longer readable');
  check(sends===0,'outbound operation attempted');
  out.dataset.state='pass';out.textContent='customers=2; sources=Alpha/Beta; drafts=distinct; Alpha=request-saved; Beta=unchanged; batch=reopened; research=planned-child-resumed; sends=0';
 })().catch(error=>{out.dataset.state='fail';out.textContent=String(error.stack||error)+' PAGE: '+document.body.innerText.slice(-5000);});
})();'''


class BatchHandler(server.Handler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path not in ('/','/batch-browser-driver.js'):
            return super().do_GET()
        self.check_host()
        source=(DESK/'web/index.html').read_text(encoding='utf8').replace('</body>','<script src="/batch-browser-driver.js" defer></script></body>') if path=='/' else DRIVER
        payload=source.encode('utf8')
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8' if path=='/' else 'text/javascript; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)


@unittest.skipUnless(os.environ.get('BEIQIANG_RUN_BROWSER_TEST')=='1','optional real Chrome test: BEIQIANG_RUN_BROWSER_TEST=1')
class CustomerBatchBrowserTests(unittest.TestCase):
    def test_two_customers_switch_and_isolated_change_request(self):
        configured=os.environ.get('BEIQIANG_TEST_CHROME')
        candidates=[Path(configured)] if configured else []
        for key in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
            if os.environ.get(key):candidates.append(Path(os.environ[key])/'Google/Chrome/Application/chrome.exe')
        candidates.extend(Path(p) for p in ('/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))
        chrome=next((p for p in candidates if p.is_file()),None)
        self.assertIsNotNone(chrome,'Explicit browser test requires Chrome; set BEIQIANG_TEST_CHROME')
        fixture=tests_desk_http.DeskHTTPTests(methodName='runTest');fixture.setUp()
        process=None;profile=None
        try:
            objects={}
            for key,label in (('alpha','Alpha'),('beta','Beta')):
                oid='customer:browser-'+key
                objects[oid]={'id':oid,'kind':'customer','title':'Synthetic '+label+' Buyer','source_type':'manual_import','source':'Synthetic '+label+' source','summary':label+' synthetic footwear buyer','subtitle':'Synthetic isolated customer','assets':[],'related':[],'links':[{'label':label+' source evidence','url':'https://'+key+'.example.test/about'}],'facts':[{'label':'采购方向','value':label+' casual shoes'}],'content':json.dumps({'email':key+'@example.test','country':'US','original_text':label+' source evidence','company':'Synthetic '+label+' Buyer','contact_verification':'verified','suppression_state':'clear'})}
            original_get=fixture.app.business.get_object;original_list=fixture.app.business.list_objects
            fixture.app.business.get_object=lambda oid:copy.deepcopy(objects[oid]) if oid in objects else original_get(oid)
            fixture.app.business.list_objects=lambda kind='',q='':original_list(kind,q)+[copy.deepcopy(obj) for obj in objects.values() if (not kind or kind==obj['kind']) and (not q or q.casefold() in json.dumps(obj).casefold())]
            empty={'status':{'state':'not_connected','account_email':'fixture@example.test','revision':0},'messages':[],'reply_pending':False}
            fixture.app.gmail=SimpleNamespace(revision=0,status=lambda:copy.deepcopy(empty['status']),peek=lambda oid:copy.deepcopy(empty),customer=lambda oid,*a,**kw:copy.deepcopy(empty))
            fixture.app.outreach_checks=SimpleNamespace(inspect=lambda oid,draft,**kw:{'object_id':oid,'draft_version':draft.get('version'),'status':'unknown','reasons':[{'code':'fixture_only','message':'Synthetic fixture: no mailbox connected','status':'unknown'}],'duplicates':[]})
            fixture.app.gmail_drafts.grant_reader=lambda account:{}
            def forbidden(*args,**kwargs):raise AssertionError('No external sending allowed in this fixture')
            fixture.app.gmail_drafts.sender=forbidden
            fixture.app.gmail_drafts.send=forbidden
            for key,label in (('alpha','Alpha'),('beta','Beta')):
                fixture.app.gmail_drafts._put({'object_id':'customer:browser-'+key,'version':'fixture-'+key,'status':'draft','account':'fixture@example.test','to':key+'@example.test','subject':label+' synthetic proposal','body_en':label+' original proposal','body_zh':label+' 中文草稿','attachments':[],'updated_at':'2026-11-06T00:00:00Z'})
            batch=fixture.app.customer_batches.create({'title':'Synthetic browser batch','object_ids':list(objects)})
            spec={'type':'customer_batch_research','object_ids':list(objects),'instruction':'Synthetic research',
                  'revision':batch['revision'],'request_id':'a'*32}
            group=fixture.app.agent_jobs.create_group('customer:browser-alpha','Synthetic group',batch_id=batch['id'],context=spec)
            alpha=fixture.app.agent_jobs.start('customer:browser-alpha','Synthetic research',mode='outreach_research',
                batch_id=batch['id'],parent_job_id=group['id'],idempotency_key=fixture.app.batch_research._child_key('a'*32,'customer:browser-alpha'))
            fixture.app.agent_jobs.start('customer:browser-beta','Synthetic research',mode='outreach_research',
                batch_id=batch['id'],parent_job_id=group['id'],idempotency_key=fixture.app.batch_research._child_key('a'*32,'customer:browser-beta'))
            with fixture.app.agent_jobs._write():
                alpha.update(status='completed',attempt=1,worker_finished=True)
                fixture.app.agent_jobs._save(alpha)
            fixture.http.RequestHandlerClass=BatchHandler
            root=fixture.root.resolve();profile=Path(tempfile.mkdtemp(prefix='batch-browser-profile-',dir=root))
            self.assertTrue(profile.resolve().is_relative_to(root))
            url='http://127.0.0.1:%s/#/customers?view=batches'%fixture.http.server_port
            process=REAL_POPEN([str(chrome),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--user-data-dir='+str(profile),'--virtual-time-budget=20000','--dump-dom',url],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            stdout,stderr=process.communicate(timeout=50)
            document=stdout.decode('utf8',errors='replace')
            match=re.search(r'<pre id="batch-browser-acceptance" data-state="([^"]+)">(.*?)</pre>',document,re.S)
            detail=html.unescape(match.group(2)) if match else 'browser result marker absent'
            self.assertEqual(process.returncode,0,stderr.decode('utf8',errors='replace')[-1500:])
            self.assertIsNotNone(match,detail);self.assertEqual(match.group(1),'pass',detail)
            readback=fixture.app.customer_batches.get(batch['id'])
            self.assertEqual(len(readback['items']),2)
            self.assertEqual(next(row for row in readback['items'] if row['object_id']=='customer:browser-beta')['change_request'],'')
            print('Real Chrome batch acceptance: '+detail)
        finally:
            try:
                if process is not None and process.poll() is None:
                    if os.name=='nt':
                        cleanup=REAL_POPEN(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.PIPE,stderr=subprocess.PIPE);cleanup.communicate(timeout=10)
                    else:process.terminate()
                    try:process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=5)
            finally:
                try:
                    if profile is not None:
                        resolved=profile.resolve();root=fixture.root.resolve()
                        if resolved==root or not resolved.is_relative_to(root):raise RuntimeError('Refusing cleanup outside isolated fixture root')
                        shutil.rmtree(resolved)
                finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
