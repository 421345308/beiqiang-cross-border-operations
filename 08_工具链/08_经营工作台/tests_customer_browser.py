"""Optional real Chrome + HTTP acceptance using isolated synthetic customer data.

Enable with BEIQIANG_RUN_BROWSER_TEST=1; optionally set BEIQIANG_TEST_CHROME.
No real customer files, mail accounts, or external sends are used.
"""
import html
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import urlsplit
import server
import tests_desk_http

# The shared fixture mocks subprocess.Popen for agent jobs; retain the real launcher.
REAL_POPEN = subprocess.Popen
desk = Path(__file__).resolve().parent

DRIVER = r'''(() => {
  const out = document.createElement('pre'); out.id = 'revision-acceptance';
  out.dataset.state = 'running'; document.body.append(out);
  const check = (test, message) => { if (!test) throw new Error(message); };
  const nativeFetch = window.fetch.bind(window), calls = [];
  window.fetch = async (path, options = {}) => {
    const response = await nativeFetch(path, options);
    if (options.method === 'POST') calls.push({path, status:response.status});
    return response;
  };
  const pause = () => new Promise(r => setTimeout(r, 50));
  const until = async (fn, message) => { for(let i=0;i<300;i++){const value=fn();if(value)return value;await pause();}throw new Error(message); };
  const button = label => [...document.querySelectorAll('button')].find(x => x.textContent.trim()===label);
  const read = async path => { const response=await fetch(path,{cache:'no-store'});check(response.ok,'GET '+path+' '+response.status);return response.json(); };
  const post = async (path, data, token) => { const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Token':token},body:JSON.stringify(data)});check(response.ok,'POST '+path+' '+response.status);return response.json(); };
  (async () => {
    const oid='customer:website-BQ-REAL', encoded=encodeURIComponent(oid);
    const token=(await read('/api/desk/bootstrap')).csrf_token;
    const profileUrl='/api/desk/customer-profile?object_id='+encoded;
    const workflowUrl='/api/desk/customer-workflow?object_id='+encoded;
    await until(()=>button('编辑解读与分析'),'profile editor not rendered');
    button('编辑解读与分析').click();
    const translation=await until(()=>document.querySelector('textarea[aria-label="中文译文 / 解读"]'),'translation input missing');
    translation.value='Browser unsaved translation';translation.dispatchEvent(new Event('input',{bubbles:true}));
    const original=await read(profileUrl);
    await post('/api/desk/customer-profile',{object_id:oid,revision:original.revision,source_hash:original.source_hash,translation_zh:'Independent latest translation'},token);
    const profileStart=calls.length;
    button('保存中文解读与分析').click();
    await until(()=>[...document.querySelectorAll('.agent-feedback')].some(x=>x.textContent.includes('已变化')),'profile conflict not shown');
    await new Promise(r=>setTimeout(r,4500));
    check(translation.isConnected,'profile input disappeared');
    check(calls.slice(profileStart).filter(x=>x.path==='/api/desk/customer-profile').length===1,'profile automatically retried');
    check(calls.slice(profileStart).find(x=>x.path==='/api/desk/customer-profile')?.status===409,'profile did not return HTTP 409');
    check(translation.value==='Browser unsaved translation','profile input not preserved');
    check((await read(profileUrl)).translation_zh==='Independent latest translation','profile overwritten');
    check(document.body.textContent.includes('请先复制需要保留的内容'),'profile copy guidance missing');
    button('放弃本次修改并重新读取').click();
    await until(()=>!translation.isConnected && button('编辑解读与分析'),'profile discard did not finish');
    check(document.body.textContent.includes('Independent latest translation'),'latest profile not displayed');
    button('编辑解读与分析').click();
    const reopenedTranslation=await until(()=>document.querySelector('textarea[aria-label="中文译文 / 解读"]'),'profile did not reopen');
    check(reopenedTranslation.value==='Independent latest translation','reopened profile stale');
    reopenedTranslation.value='Reviewed latest translation';reopenedTranslation.dispatchEvent(new Event('input',{bubbles:true}));
    button('保存中文解读与分析').click();
    await until(()=>!reopenedTranslation.isConnected,'fresh profile save not completed');
    check((await read(profileUrl)).translation_zh==='Reviewed latest translation','fresh profile save failed');
    const workflow=await until(()=>document.querySelector('.workflow-editor textarea[aria-label="下一动作"]'),'workflow input missing');
    workflow.value='Browser unsaved next action';workflow.dispatchEvent(new Event('input',{bubbles:true}));
    const flow=await read(workflowUrl);
    await post('/api/desk/customer-workflow',{object_id:oid,revision:flow.revision,next_action:'Independent latest action'},token);
    const workflowStart=calls.length;
    button('保存推进安排').click();
    await until(()=>document.querySelector('.workflow-editor .agent-feedback')?.textContent.includes('已变化'),'workflow conflict not shown');
    await new Promise(r=>setTimeout(r,4500));
    check(calls.slice(workflowStart).filter(x=>x.path==='/api/desk/customer-workflow').length===1,'workflow automatically retried');
    check(calls.slice(workflowStart).find(x=>x.path==='/api/desk/customer-workflow')?.status===409,'workflow did not return HTTP 409');
    check(calls.slice(profileStart).filter(x=>x.path==='/api/desk/customer-profile').length===2,'profile automatically retried later');
    check(workflow.isConnected,'workflow input disappeared');
    check((await read(profileUrl)).translation_zh==='Reviewed latest translation','profile overwritten later');
    check(workflow.value==='Browser unsaved next action','workflow input not preserved');
    check((await read(workflowUrl)).next_action==='Independent latest action','workflow overwritten');
    check(document.body.textContent.includes('请先复制需要保留的内容'),'workflow copy guidance missing');
    button('放弃本次修改并重新读取').click();
    await until(()=>!workflow.isConnected,'workflow discard did not finish');
    const reopenedWorkflow=await until(()=>document.querySelector('.workflow-editor textarea[aria-label="下一动作"]'),'workflow did not reopen');
    check(reopenedWorkflow.value==='Independent latest action','latest workflow not displayed');
    reopenedWorkflow.value='Reviewed latest action';reopenedWorkflow.dispatchEvent(new Event('input',{bubbles:true}));
    button('保存推进安排').click();
    await until(()=>!reopenedWorkflow.isConnected,'fresh workflow save not completed');
    check((await read(workflowUrl)).next_action==='Reviewed latest action','fresh workflow save failed');
    out.dataset.state='pass';out.textContent='profile=409/input-preserved/latest-preserved; workflow=409/input-preserved/latest-preserved';
  })().catch(error=>{out.dataset.state='fail';out.textContent=String(error.stack||error);});
})();'''


class InjectedHandler(server.Handler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path not in ('/', '/revision-driver.js'):
            return super().do_GET()
        self.check_host()
        if path=='/':
            source=(desk/'web'/'index.html').read_text(encoding='utf8')
            source=source.replace('</body>', '<script src="/revision-driver.js" defer></script></body>')
            mime='text/html; charset=utf-8'
        else:source=DRIVER;mime='text/javascript; charset=utf-8'
        payload=source.encode('utf8')
        self.send_response(200);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)


@unittest.skipUnless(os.environ.get('BEIQIANG_RUN_BROWSER_TEST') == '1',
                     'optional real-browser test: set BEIQIANG_RUN_BROWSER_TEST=1')
class CustomerBrowserTests(unittest.TestCase):
    def test_stale_forms_return_409_and_preserve_input_and_latest_values(self):
        configured = os.environ.get('BEIQIANG_TEST_CHROME')
        candidates = [Path(configured)] if configured else []
        for base in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
            if os.environ.get(base):
                candidates.append(Path(os.environ[base])/'Google/Chrome/Application/chrome.exe')
        candidates.extend(Path(path) for path in (
            '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium', '/usr/bin/chromium-browser',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))
        if configured and not Path(configured).is_file():
            self.fail('BEIQIANG_TEST_CHROME does not point to a browser executable')
        chrome = next((path for path in candidates if path.is_file()), None)
        if chrome is None:
            self.fail('Browser test explicitly enabled but Chrome was not found; set BEIQIANG_TEST_CHROME')
        fixture = tests_desk_http.DeskHTTPTests(methodName='runTest')
        fixture.setUp()
        process = None
        profile = None
        try:
            fixture.http.RequestHandlerClass = InjectedHandler
            fixture_root = fixture.root.resolve()
            profile = Path(tempfile.mkdtemp(prefix='browser-profile-', dir=fixture_root))
            if not profile.resolve().is_relative_to(fixture_root):
                raise RuntimeError('Browser profile escaped fixture root')
            url = 'http://127.0.0.1:%d/#/object/customer%%3Awebsite-BQ-REAL' % fixture.http.server_port
            process = REAL_POPEN([str(chrome), '--headless=new', '--disable-gpu',
                '--no-first-run', '--no-default-browser-check', '--user-data-dir='+str(profile),
                '--virtual-time-budget=25000', '--dump-dom', url],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=55)
            document = stdout.decode('utf8', errors='replace')
            match = re.search(r'<pre id="revision-acceptance" data-state="([^"]+)">(.*?)</pre>', document, re.S)
            detail = html.unescape(match.group(2)) if match else 'browser result marker absent'
            self.assertEqual(process.returncode, 0, stderr.decode('utf8', errors='replace')[-1500:])
            self.assertIsNotNone(match, detail)
            self.assertEqual(match.group(1), 'pass', detail)
        finally:
            try:
                if process is not None and process.poll() is None:
                    # Only this isolated browser process tree is targeted.
                    if os.name == 'nt':
                        cleanup = REAL_POPEN(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        cleanup.communicate(timeout=10)
                    else:
                        process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate(timeout=5)
            finally:
                try:
                    if profile is not None:
                        resolved = profile.resolve()
                        if resolved == fixture.root.resolve() or not resolved.is_relative_to(fixture.root.resolve()):
                            raise RuntimeError('Refusing cleanup outside isolated fixture root')
                        shutil.rmtree(resolved)
                finally:
                    fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
