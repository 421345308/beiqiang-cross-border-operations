import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag = 'div') { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.dataset = {}; this.style = {}; this.value = ''; this._text = ''; this.className = ''; this.disabled = false; this.hidden = false; this.classList = { toggle: (name, on) => { const values = new Set(this.className.split(' ').filter(Boolean)); if (on) values.add(name); else values.delete(name); this.className = [...values].join(' '); }, add: name => { this.className += ` ${name}`; } }; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(item => item.textContent || '').join(''); }
  append(...items) { for (const item of items) { item.parent = this; this.children.push(item); } }
  insertBefore(item, before) { item.parent = this; const index = this.children.indexOf(before); if (index < 0) this.children.push(item); else this.children.splice(index, 0, item); }
  replaceChildren(...items) { this.children = []; this._text = ''; this.append(...items); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(key, value) { this[key] = value; }
  removeAttribute(key) { this[key] = ''; }
  querySelectorAll(selector) { return walk(this).slice(1).filter(item => selector.startsWith('.') ? item.className.split(' ').includes(selector.slice(1)) : item.tagName === selector.toUpperCase()); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  async click() { if (!this.disabled) return this.listeners.click?.({}); }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(item => item !== this); }
  showModal() { this.open = true; }
  close() { this.open = false; this.listeners.close?.({}); }
}
const walk = root => [root, ...root.children.flatMap(walk)];
const findButton = (root, label) => { const value = walk(root).find(item => item.tagName === 'BUTTON' && item.textContent === label); assert.ok(value, `Missing ${label}`); return value; };
const settle = async () => { for (let i = 0; i < 4; i++) await new Promise(resolve => setImmediate(resolve)); };
function harness(hash = '#/overview') {
  const body = new Element('body'), elements = {};
  for (const id of ['page', 'reload', 'desk-notice', 'save-indicator', 'connection', 'page-name', 'breadcrumb']) { elements[id] = new Element(id === 'reload' ? 'button' : 'div'); elements[id].id = id; body.append(elements[id]); }
  const nav = ['overview', 'products', 'customers', 'library'].map(name => { const item = new Element('a'); item.dataset.nav = name; body.append(item); return item; });
  const requests = [], objects = [{ id: 'product:1', kind: 'product', title: '<img src=x onerror=alert(1)>真实商品', subtitle: '实际款号', source: '商品原档案', facts: [{ label: '材料', value: '已核材料' }], assets: [{ path: '商品图.jpg', label: '真实主图', url: '/api/media/file?path=商品图.jpg' }], content: '很长的原文', related: [] }];
  const profile = { object_id: 'customer:record', source_type: 'website', source_hash: 'hash-1', provenance: { source_hash: 'hash-1', source_verification: { state: 'unverified', note: '来源待核' } }, original_text: 'Please send sample information.', translation_zh: '请提供样品信息。', cleaned: { company: '示例公司', quantity: '未提供' }, analysis: { intent: '尚待确认', fit: '尚待核对', basis: [], missing: ['采购数量'], next_action: '确认采购数量', facts: [], inferences: [], recommendations: ['核实来源'] } }; const discovery = { tasks: [], candidates: [] };
  const artifacts = [{ id: 'a1', object_id: 'product:1', title: '现有选款资料', content: '原成果', updated_at: '2026-10-31T01:00:00Z' }]; const jobs = []; let web = { state: 'loading' };
  // 「今天」与商品缺口为 2026-11-01 新增接口；默认空态，测试里按需替换。
  let today = { generated_at: '2026-11-01T00:00:00Z', groups: { decide: [], act: [], watch: [] }, counts: { decide: 0, act: 0, watch: 0 }, labels: { decide: '等你拍板', act: '今天能推', watch: '在跑，不用动手' }, sources: {} };
  let productGaps = { total: 1, with_gaps: 0, blocked: 0, counts: {}, items: [], checked: [], unavailable: {}, labels: {} };
  const local = new Map(), location = { hash, origin: 'http://127.0.0.1:8765' };
  const context = { console, URL, URLSearchParams, Date, JSON, Math, Map, Set, location, navigator: { clipboard: { writeText: async value => local.set('clipboard',value) } }, localStorage: { getItem: key => local.get(key) || null, setItem: (key, value) => local.set(key, value) }, history: { replaceState: (_s, _t, next) => { location.hash = next; } }, setTimeout: () => 1, clearTimeout() {}, setInterval() {}, window: { addEventListener() {} }, document: { body, visibilityState: 'visible', createElement: tag => new Element(tag), getElementById: id => elements[id], querySelectorAll: selector => selector === '[data-nav]' ? nav : body.querySelectorAll(selector) } };
  context.fetch = async (path, options = {}) => {
    const url = new URL(path, location.origin), payload = options.body ? JSON.parse(options.body) : null; requests.push({ path, options, payload }); let value;
    if (url.pathname === '/api/desk/bootstrap') value = { csrf_token: 'fixture-token', objects, jobs, artifacts, website_status: web, goals: { phase: '当前经营阶段' } };
    else if (url.pathname === '/api/desk/inquiry-queue') value = {items:objects.filter(item => item.kind === 'customer' && item.source_type !== 'alibaba_order_buyer' && (item.bucket || 'active') === url.searchParams.get('bucket')).map(item => ({object_id:item.id,title:item.title,analysis:{core_need:item.summary},workflow:{state:'new',priority:item.priority || 'normal',...item.workflow}}))};
    else if (url.pathname === '/api/desk/customer-workflow') { Object.assign(profile.workflow, payload); value = profile.workflow; }
    else if (url.pathname === '/api/desk/objects') value = { objects: objects.filter(item => !url.searchParams.get('kind') || item.kind === url.searchParams.get('kind')) };
    else if (url.pathname === '/api/desk/object') value = objects.find(item => item.id === url.searchParams.get('id'));
    else if (url.pathname === '/api/desk/product-review') {
      const object=objects.find(item=>item.id===url.searchParams.get('object_id'));const listings=(object?.links || []).filter(item=>/^Alibaba \d+$/.test(item.label || '')).map(item=>({id:item.label.split(' ')[1],url:item.url}));
      const selected=listings.find(item=>item.id===url.searchParams.get('listing_id')) || listings[0];
      value={listings,selected:selected ? {id:selected.id,state:'ready',local:{title:'Local'},platform:{title:'Live',main_images:[],detail_images:[],company_images:[],observed_at:'2026-11-02T00:00:00Z'},comparison:{title:'different',main_images:'not_recorded',detail_images:'not_recorded'}} : null};
    }
    else if (url.pathname === '/api/desk/customer-profile' && payload) { Object.assign(profile, payload); value = profile; }
    else if (url.pathname === '/api/desk/customer-profile') value = { ...profile, object_id: url.searchParams.get('object_id') };
    else if (url.pathname === '/api/desk/discovery' && payload) { value = { ...payload, id: 'research:new', object_id: 'prospect:research:new', evidence: payload.evidence || [] }; discovery.tasks.push(value); }
    else if (url.pathname === '/api/desk/discovery') value = discovery;
    else if (url.pathname === '/api/desk/discovery/item') value = [...discovery.tasks, ...discovery.candidates].find(item => item.id === url.searchParams.get('id'));
    else if (url.pathname === '/api/desk/discovery/update') { value = [...discovery.tasks, ...discovery.candidates].find(item => item.id === payload.id); Object.assign(value, payload); }
    else if (url.pathname === '/api/desk/jobs' && payload) { value = { id: 'j1', object_id: payload.object_id, instruction: payload.instruction, status: 'running', events: [{ type: 'progress', text: '已取得资料' }], updated_at: '2026-10-31T02:00:00Z' }; jobs.push(value); }
    else if (url.pathname === '/api/desk/jobs') value = { jobs };
    else if (url.pathname === '/api/desk/artifacts' && payload) { value = { ...payload, id: payload.id || 'a2', updated_at: '2026-10-31T03:00:00Z' }; const index = artifacts.findIndex(item => item.id === value.id); if (index >= 0) artifacts[index] = value; else artifacts.push(value); }
    else if (url.pathname === '/api/desk/artifacts') value = { artifacts: artifacts.filter(item => item.object_id === url.searchParams.get('object_id')) };
    else if (url.pathname === '/api/desk/today') value = today;
    else if (url.pathname === '/api/desk/product-gaps') value = productGaps;
    else if (url.pathname === '/api/desk/refresh') { web = { state: 'loading' }; value = { status: web }; }
    else throw new Error(`Unexpected API ${path}`);
    return { ok: true, json: async () => structuredClone(value) };
  };
  const source = fs.readFileSync(new URL('./web/desk.js', import.meta.url), 'utf8'); assert.doesNotMatch(source, /\.innerHTML\s*=/);
  vm.createContext(context); vm.runInContext(fs.readFileSync(new URL('./web/product-review.js', import.meta.url), 'utf8'),context); vm.runInContext(source.replace('bootstrap(); setInterval(poll, 4000);', 'window.__desk = { S, bootstrap, renderRoute, poll, refreshData, safeUrl, imageAsset };'), context);
  return { ui: context.window.__desk, elements, body, objects, artifacts, jobs, requests, location, profile, discovery, clipboard: () => local.get('clipboard'), setWebsite: value => { web = value; }, setToday: value => { today = value; }, setProductGaps: value => { productGaps = value; }, originalFetch: context.fetch, interceptFetch: callback => { context.fetch = callback; } };
}

test('业务对象可继续已保存的 Agent 会话，续接请求携带原工作编号', async () => {
  const h=harness('#/object/product%3A1'), original=h.originalFetch, calls=[];
  h.jobs.push({id:'saved-job',object_id:'product:1',instruction:'原研究',status:'completed',session_id:'saved-session',summary:'已有结果',updated_at:'2026-11-03T00:00:00Z'});
  h.interceptFetch(async(path,options={})=>{
    if(path==='/api/desk/job/resume') { const payload=JSON.parse(options.body); calls.push(payload); return {ok:true,json:async()=>({...h.jobs[0],status:'queued',instruction:payload.instruction})}; }
    return original(path,options);
  });
  await h.ui.bootstrap(); await settle();
  const entry=walk(h.elements.page).find(x=>x['aria-label']==='交给 Agent 的工作');
  entry.value='核对结果后继续'; await findButton(h.body,'继续这项工作').click(); await settle();
  assert.equal(calls.length,1); assert.equal(calls[0].id,'saved-job'); assert.equal(calls[0].instruction,'核对结果后继续');
  assert.equal(h.requests.some(x=>String(x.path).includes('/gmail/send')),false);
});

test('Gmail 默认显示中文，原文只通过 Gmail 链接查看，更新邮件保留未保存内容', async () => {
  const h=harness('#/object/customer%3A1'), original=h.originalFetch;
  h.objects.push({id:'customer:1',kind:'customer',title:'邮件客户',assets:[]});
  let mail={status:{state:'not_connected'},messages:[]};
  h.interceptFetch(async(path,options)=>String(path).startsWith('/api/desk/gmail/') ? {ok:true,json:async()=>structuredClone(mail)} : original(path,options));
  await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('尚未连接 Gmail')); assert.equal(h.elements.page.textContent.includes('已连接 ·'),false);
  mail={status:{state:'connected',account_email:'sales@example.org'},reply_pending:true,next_action:'准备样品资料',messages:[{id:'m1',direction:'inbound',sent_at:'2026-11-01T01:00:00Z',subject:'Sample request',subject_zh:'样品咨询',translation_zh:'请提供样品详情。',translation_state:'ready',body:'Buyer original text',from:'buyer@example.org',url:'https://mail.google.com/mail/u/0/#all/thread'}]};
  await findButton(h.body,'更新邮件往来').click(); await settle();
  const panel=h.elements.page.querySelector('.gmail-conversation'); assert.ok(panel.textContent.includes('客户有新邮件')); assert.ok(panel.textContent.includes('准备样品资料')); assert.ok(panel.textContent.includes('样品咨询')); assert.ok(panel.textContent.includes('请提供样品详情。')); assert.equal(panel.textContent.includes('Buyer original text'),false); assert.equal(panel.textContent.includes('Sample request'),false); assert.ok(walk(panel).some(x=>x.tagName==='A' && x.href==='https://mail.google.com/mail/u/0/#all/thread'));
  assert.equal(panel.textContent.includes('交给 Sol'),false); assert.equal(h.requests.some(x=>x.path.includes('send')),false);
});

test('客户邮件在本地保存、添加资料并审核后才发送，刷新邮件不丢草稿', async () => {
  const h=harness('#/object/customer%3Amail'),original=h.originalFetch,calls=[];
  h.objects.push({id:'customer:mail',kind:'customer',title:'测试客户',assets:[]});
  let draft={object_id:'customer:mail',account:'seller@example.test',to:'buyer@example.test',subject:'Re: Samples',body_en:'',body_zh:'',attachments:[],version:'v1',status:'draft',can_send:true};
  h.interceptFetch(async(path,options={})=>{
    const url=new URL(path,'http://127.0.0.1:8766'),payload=options.body ? JSON.parse(options.body) : null;calls.push({path:url.pathname,payload});
    if(url.pathname==='/api/desk/gmail/customer' || url.pathname==='/api/desk/gmail/sync')return {ok:true,json:async()=>({status:{state:'connected',account_email:'seller@example.test'},messages:[]})};
    if(url.pathname==='/api/desk/gmail/draft' && !payload)return {ok:true,json:async()=>structuredClone(draft)};
    if(url.pathname==='/api/desk/gmail/draft'){draft={...draft,...payload.fields,version:'v2'};return {ok:true,json:async()=>structuredClone(draft)};}
    if(url.pathname==='/api/library')return {ok:true,json:async()=>({items:[{id:'mat1',title:'产品目录',path:'catalog.pdf'}]})};
    if(url.pathname==='/api/desk/gmail/attachment'){draft={...draft,version:'v3',attachments:[{id:'a1',name:'catalog.pdf',size:1000}]};return {ok:true,json:async()=>structuredClone(draft)};}
    if(url.pathname==='/api/desk/gmail/send-oauth/start')return {ok:true,json:async()=>({authorization_url:'https://accounts.google.com/o/oauth2/v2/auth?state=fixture'})};
    if(url.pathname==='/api/desk/gmail/send'){draft={...draft,status:'sent',sent_at:'2026-11-02T00:00:00Z',gmail_url:'https://mail.google.com/mail/u/0/#all/20'};return {ok:true,json:async()=>structuredClone(draft)};}
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();
  const panel=h.elements.page.querySelector('.gmail-conversation');await findButton(panel,'写邮件 / 继续草稿').click();await settle();
  const composer=panel.querySelector('.mail-composer'), en=walk(composer).find(x=>x['aria-label']==='英文正文（发送给客户）'),zh=walk(composer).find(x=>x['aria-label']==='中文对照（仅供自己审核）');
  await findButton(composer,'准备重新授权').click();await settle();assert.ok(walk(composer).some(x=>x.tagName==='A' && x.textContent==='继续 Google 登录并授权 ↗'));
  en.value='Hello buyer, here are our shoes.';en.listeners.input();zh.value='您好，这是我们的鞋子。';zh.listeners.input();
  await findButton(panel,'更新邮件往来').click();await settle();assert.equal(en.value,'Hello buyer, here are our shoes.');
  const picker=walk(composer).find(x=>x.tagName==='DETAILS' && x.className==='mail-material-picker');picker.open=true;await picker.listeners.toggle();await settle();
  await findButton(composer,'＋ 产品目录').click();await settle();assert.ok(composer.textContent.includes('catalog.pdf'));
  await findButton(composer,'查看并审核').click();await settle();
  assert.ok(composer.textContent.includes('您好，这是我们的鞋子。'));assert.ok(composer.textContent.includes('Hello buyer, here are our shoes.'));
  assert.ok(composer.textContent.includes('收件人：buyer@example.test'));assert.ok(composer.textContent.includes('catalog.pdf'));
  assert.equal(calls.filter(x=>x.path==='/api/desk/gmail/send').length,0);
  await findButton(composer,'确认发送这封邮件').click();await settle();
  assert.equal(calls.filter(x=>x.path==='/api/desk/gmail/send').length,1);assert.ok(composer.textContent.includes('邮件已由 Gmail 接收'));
});

test('邮件翻译进行中及失败时显示状态，并可重试', async () => {
  const h=harness('#/object/customer%3A1'), original=h.originalFetch;
  h.objects.push({id:'customer:1',kind:'customer',title:'邮件客户',assets:[]});
  let state='translating'; const calls=[];
  h.interceptFetch(async(path,options)=>{ if(String(path).startsWith('/api/desk/gmail/')) { calls.push(path); return {ok:true,json:async()=>({status:{state:'connected'},messages:[{id:'m1',direction:'inbound',body:'secret original',translation_state:state,url:'https://mail.google.com/mail/u/0/#all/thread'}]})}; } return original(path,options); });
  await h.ui.bootstrap(); await settle(); const panel=h.elements.page.querySelector('.gmail-conversation');
  assert.ok(panel.textContent.includes('正在翻译成中文')); assert.equal(panel.textContent.includes('secret original'),false);
  state='error'; await findButton(panel,'更新邮件往来').click(); await settle();
  assert.ok(panel.textContent.includes('中文翻译暂未完成')); await findButton(panel,'重试翻译').click();
  assert.equal(calls.filter(x=>x==='/api/desk/gmail/sync').length,2);
});

test('Gmail 连接只在本地表单提交密码，成功刷新并清空密码', async () => {
  const h=harness('#/object/customer%3Amail'), original=h.originalFetch, calls=[];
  h.objects.push({id:'customer:mail',kind:'customer',title:'邮箱客户',assets:[]}); let connected=false;
  h.interceptFetch(async(path,options={})=>{ if(String(path)==='/api/desk/gmail/connect') {calls.push(JSON.parse(options.body)); connected=true; return {ok:true,json:async()=>({ok:true})};} if(String(path).startsWith('/api/desk/gmail/'))return {ok:true,json:async()=>({status:{state:connected?'connected':'not_connected',account_email:connected?'sales@example.org':''},messages:[]})}; return original(path,options); });
  await h.ui.bootstrap(); await settle();
  const panel=h.elements.page.querySelector('.gmail-conversation'), account=walk(panel).find(x=>x['aria-label']==='Gmail 邮箱'), password=walk(panel).find(x=>x['aria-label']==='Google 应用专用密码');
  assert.equal(password.type,'password'); assert.ok(panel.textContent.includes('不要发到聊天中')); assert.ok(walk(panel).some(x=>x.tagName==='A' && x.href==='https://myaccount.google.com/apppasswords'));
  account.value='sales@example.org'; password.value='fixture-app-secret'; await findButton(panel,'连接邮箱').click(); await settle();
  assert.equal(calls.length,1); assert.equal(calls[0].app_password,'fixture-app-secret'); assert.equal(password.value,''); assert.ok(panel.textContent.includes('已连接')); assert.equal(panel.textContent.includes('fixture-app-secret'),false);
});

test('Gmail 首选 Google 只读授权，客户端文件只提交给本机', async () => {
  const h=harness('#/object/customer%3Amail'),original=h.originalFetch,calls=[];
  h.objects.push({id:'customer:mail',kind:'customer',title:'邮箱客户',assets:[]});
  h.interceptFetch(async(path,options={})=>{
    if(path==='/api/desk/gmail/oauth/start'){calls.push(JSON.parse(options.body));return {ok:true,json:async()=>({authorization_url:'https://accounts.google.com/o/oauth2/v2/auth?state=fixture'})};}
    if(String(path).startsWith('/api/desk/gmail/'))return {ok:true,json:async()=>({status:{state:'not_connected'},messages:[]})};
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();const panel=h.elements.page.querySelector('.gmail-conversation');
  assert.ok(panel.textContent.includes('使用 Google 账号授权'));assert.ok(panel.textContent.includes('只读邮件'));
  const file=walk(panel).find(x=>x['aria-label']==='Google 桌面应用客户端文件');file.files=[{text:async()=>JSON.stringify({installed:{client_id:'fixture',client_secret:'local-secret'}})}];
  await findButton(panel,'准备 Google 授权').click();await settle();
  assert.equal(calls[0].client_config.installed.client_secret,'local-secret');
  assert.ok(walk(panel).some(x=>x.tagName==='A' && x.textContent==='继续 Google 登录并授权 ↗'));
  assert.equal(panel.textContent.includes('local-secret'),false);
});

test('Gmail 测试授权显示预计到期时间', async () => {
  const h=harness('#/object/customer%3Amail'),original=h.originalFetch;
  h.objects.push({id:'customer:mail',kind:'customer',title:'邮箱客户',assets:[]});
  h.interceptFetch(async(path,options)=>String(path).startsWith('/api/desk/gmail/')
    ? {ok:true,json:async()=>({status:{state:'connected',authorization_expires_at:'2026-11-08T08:17:00Z'},messages:[]})} : original(path,options));
  await h.ui.bootstrap();await settle();assert.ok(h.elements.page.textContent.includes('Google 测试授权预计'));assert.ok(h.elements.page.textContent.includes('重新授权即可'));
});

test('总览与询盘列表分别提醒 Gmail 和网站站内消息', async () => {
  const h=harness(); h.objects.push({id:'customer:mail',kind:'customer',title:'邮件回复买家',workflow:{gmail_reply_pending:true,customer_reply_pending:true,state:'preparing'}});
  h.setToday({groups:{decide:[],act:[{title:'邮件回复买家有新回复',judgment:'Gmail 客户有新回复 · 网站站内消息有新回复',action:{type:'open_object',object_id:'customer:mail'}}],watch:[]},counts:{decide:0,act:1,watch:0},labels:{act:'待处理'}});
  await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('Gmail 客户有新回复')); assert.ok(h.elements.page.textContent.includes('网站站内消息有新回复'));
  h.location.hash='#/customers?view=inquiries'; await h.ui.renderRoute(); await settle(); assert.ok(h.elements.page.textContent.includes('Gmail 客户有新回复'));
});

test('后台同步到新邮件后自动刷新总览', async () => {
  const h=harness(),original=h.originalFetch;let revision=0;
  h.setToday({groups:{decide:[],act:[],watch:[{title:'等待回复：邮件客户',judgment:'等待客户回复'}]},counts:{decide:0,act:0,watch:1},labels:{watch:'等待'}});
  h.interceptFetch(async(path,options)=>{
    const response=await original(path,options);
    if(path==='/api/desk/bootstrap'){const value=await response.json();value.gmail_revision=revision;return {ok:true,json:async()=>value};}
    return response;
  });
  await h.ui.bootstrap();await settle();assert.ok(h.elements.page.textContent.includes('等待回复：邮件客户'));
  revision=1;h.setToday({groups:{decide:[],act:[{title:'邮件客户有新回复',judgment:'Gmail 客户有新回复 · 阅读客户新邮件'}],watch:[]},counts:{decide:0,act:1,watch:0},labels:{act:'待处理'}});
  h.ui.S.lastBootstrapPoll=0;await h.ui.poll();await settle();
  assert.ok(h.elements.page.textContent.includes('Gmail 客户有新回复'));assert.ok(h.elements.page.textContent.includes('阅读客户新邮件'));
});

test('Gmail 新买家显示中文摘要并可加入原客户列表', async () => {
  const h=harness('#/customers?view=development'),original=h.originalFetch;
  h.interceptFetch(async(path,options)=>{
    if(path==='/api/desk/gmail/candidates')return {ok:true,json:async()=>({status:{state:'ready'},items:[{id:'m1',title:'Buyer Company',contact_name:'Buyer',email:'buyer@example.org',summary:'邮件提出鞋类采购或报价咨询',sent_at:'2026-11-01T01:00:00Z',url:'https://mail.google.com/mail/#all/abcd'}]})};
    if(String(path).startsWith('/api/desk/gmail/'))return {ok:true,json:async()=>({status:{state:'connected'},messages:[]})};
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();assert.ok(h.elements.page.textContent.includes('邮件提出鞋类采购或报价咨询'));
  await findButton(h.body,'加入客户并处理').click();await settle();
  const created=h.requests.find(x=>x.path==='/api/desk/discovery'&&x.payload?.kind==='candidate');
  assert.equal(created.payload.email,'buyer@example.org');assert.equal(created.payload.business_category,'邮件咨询');
});

test('Gmail 历史询盘单独折叠，不算当前新客户', async () => {
  const h=harness('#/customers?view=development'),original=h.originalFetch;
  h.interceptFetch(async(path,options)=>path==='/api/desk/gmail/candidates'
    ? {ok:true,json:async()=>({status:{state:'ready'},items:[{id:'old',title:'Old buyer',email:'old@example.org',summary:'邮件提出鞋类采购或报价咨询',is_new:false,answered:false}]})} : original(path,options));
  await h.ui.bootstrap();await settle();assert.ok(h.elements.page.textContent.includes('历史买家邮件 · 1 封'));
  assert.ok(h.elements.page.textContent.includes('原线程未发现我方回复'));assert.equal(h.elements.page.textContent.includes('Gmail 潜在买家来信'),false);
});

test('Gmail 首次筛选时给出可见的进度提示', async () => {
  const h=harness('#/customers?view=development'),original=h.originalFetch;
  h.interceptFetch(async(path,options)=>path==='/api/desk/gmail/candidates'
    ? {ok:true,json:async()=>({status:{state:'loading'},items:[]})} : original(path,options));
  await h.ui.bootstrap();await settle();assert.ok(h.elements.page.textContent.includes('正在筛选 Gmail 来信'));
});

test('real data drives navigation and original content is collapsed; untrusted titles stay text', async () => {
  const h = harness('#/products'); await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('真实商品')); assert.equal(walk(h.body).some(item => item.tagName === 'SCRIPT'), false);
  h.location.hash = '#/object/product%3A1'; await h.ui.renderRoute(); await settle(); assert.equal(h.elements.page.querySelector('.object-source-details'), null); assert.equal(h.ui.safeUrl('javascript:alert(1)'), null); assert.equal(h.ui.imageAsset({ path: 'real.jpg', url: '/api/asset?id=1' }), true);
});

test('商品分页并按实际鞋型筛选，不把冬鞋默认归为靴或把步行鞋归为系带', async () => {
  const h = harness('#/products'); h.objects.length = 0;
  for (let i = 0; i < 40; i++) h.objects.push({ id:`product:${i}`, kind:'product', title:`鞋${i}`, facts:[{label:'用途候选',value:i===0?'冬季套脚鞋':i===1?'步行休闲鞋':'系带鞋'}], assets:[] });
  await h.ui.bootstrap(); await settle();
  assert.equal(h.elements.page.querySelectorAll('.object-tile').length,36);
  await findButton(h.body,'显示更多商品').click(); assert.equal(h.elements.page.querySelectorAll('.object-tile').length,40);
  const category = walk(h.body).find(item=>item['aria-label']==='商品分类'); category.value='boot'; await category.listeners.change(); await settle();
  assert.equal(h.elements.page.querySelectorAll('.object-tile').length,0);
  category.value='slip'; await category.listeners.change(); await settle(); assert.ok(h.elements.page.textContent.includes('冬季套脚鞋'));
});

test('商品按真实供货方式筛选并显示外采链接', async () => {
  const h = harness('#/products'); h.objects.length = 0;
  h.objects.push({ id:'product:own', kind:'product', title:'BQ001', facts:[], assets:[], supply:{kind:'own'} });
  h.objects.push({ id:'product:sourced', kind:'product', title:'BQ-CS063C', facts:[], assets:[], supply:{kind:'external',model:'725',url:'https://supplier.example/725'} });
  h.objects.push({ id:'product:unknown', kind:'product', title:'BQ040', facts:[], assets:[], supply:{kind:'unconfirmed'} });
  await h.ui.bootstrap(); await settle();
  const sourced=walk(h.elements.page).find(item=>item.className.includes('object-tile') && item.textContent.includes('BQ-CS063C'));
  assert.ok(sourced.textContent.includes('外采供货'));assert.ok(sourced.textContent.includes('725'));assert.equal(sourced.querySelector('a').href,'https://supplier.example/725');
  const filter=walk(h.body).find(item=>item['aria-label']==='供货方式');
  filter.value='own';await filter.listeners.change();await settle();assert.ok(h.elements.page.textContent.includes('BQ001'));assert.equal(h.elements.page.textContent.includes('BQ-CS063C'),false);
  filter.value='external';await filter.listeners.change();await settle();assert.ok(h.elements.page.textContent.includes('BQ-CS063C'));assert.equal(h.elements.page.textContent.includes('BQ001'),false);
  filter.value='unconfirmed';await filter.listeners.change();await settle();assert.ok(h.elements.page.textContent.includes('BQ040'));assert.equal(h.elements.page.textContent.includes('BQ-CS063C'),false);
});

test('商品详情将供货链接与多个国际站商品链接集中展示', async () => {
  const h = harness('#/object/product%3A1');
  h.objects[0].supply = {kind:'external',model:'A502',url:'https://supplier.example/item'};
  h.objects[0].links = [{label:'Alibaba 123',url:'https://www.alibaba.com/product-detail/123.html'}, {label:'Alibaba 456',url:'https://www.alibaba.com/product-detail/456.html'}];
  await h.ui.bootstrap(); await settle(); const links = h.elements.page.querySelector('.product-links');
  assert.ok(links.textContent.includes('外采供货')); assert.ok(links.textContent.includes('供货商品 A502')); assert.ok(links.textContent.includes('国际站商品 123')); assert.ok(links.textContent.includes('国际站商品 456'));
  assert.equal(links.querySelectorAll('a').length,3);
});

test('客户开发可搜索分类，并把已结束跟进与当前客户分开', async () => {
  const h=harness('#/customers?view=development'); h.discovery.candidates.push(
    {id:'candidate:1',kind:'candidate',title:'英国批发公司',business_category:'批发商',business_summary:'经营休闲鞋',contact_status_label:'未联系'},
    {id:'candidate:2',kind:'candidate',title:'旧客户',business_category:'品牌',business_summary:'已有联系',contact_status_label:'已结束跟进'});
  await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('英国批发公司')); assert.equal(h.elements.page.textContent.includes('旧客户'),false);
  const input=walk(h.body).find(x=>x['aria-label']==='搜索目标客户'); input.value='不存在'; input.listeners.input(); assert.equal(h.elements.page.textContent.includes('英国批发公司'),false);
  input.value=''; input.listeners.input(); const status=walk(h.body).find(x=>x['aria-label']==='联系状态'); status.value='ended'; status.listeners.change(); assert.ok(h.elements.page.textContent.includes('旧客户')); assert.equal(h.elements.page.textContent.includes('英国批发公司'),false);
});

test('客户工作区把新回复置前，合并当前网站询盘并按下一步筛选', async () => {
  const h=harness('#/customers?view=development');
  h.discovery.candidates.push(
    {id:'candidate:waiting',object_id:'prospect:candidate:waiting',kind:'candidate',title:'等回复客户',contact_status_label:'已发送报价',business_summary:'做鞋类零售',next_action:'等待客户回复'},
    {id:'candidate:reply',object_id:'prospect:candidate:reply',kind:'candidate',title:'新回复客户',contact_status_label:'已发送报价',business_summary:'鞋类批发',next_action:'等待客户回复',gmail_reply_pending:true,gmail_next_action:'阅读客户新邮件'},
    {id:'candidate:new',object_id:'prospect:candidate:new',kind:'candidate',title:'待开发客户',contact_status_label:'未联系',business_summary:'进口休闲鞋'});
  h.objects.push({id:'customer:website-test',kind:'customer',title:'网站咨询客户',source_type:'website',summary:'寻求鞋类合作',workflow:{state:'waiting_customer',state_label:'等客户',next_action:'等待项目照片'}});
  await h.ui.bootstrap(); await settle();
  const rows=h.elements.page.querySelectorAll('.customer-list-row');
  assert.equal(rows[0].querySelector('h3').textContent,'新回复客户');
  assert.ok(rows[0].textContent.includes('有新回复')); assert.ok(rows[0].textContent.includes('阅读客户新邮件'));
  assert.ok(rows.some(row=>row.textContent.includes('网站咨询客户')));
  const actionable=walk(h.elements.page).find(item=>item.className.split(' ').includes('customer-stat') && item.className.split(' ').includes('action')); await actionable.click();
  assert.equal(h.elements.page.querySelectorAll('.customer-list-row').length,1);
  assert.ok(h.elements.page.textContent.includes('新回复客户')); assert.equal(h.elements.page.textContent.includes('待开发客户'),false);
});

test('客户详情直接展示公司网站和现有联系方式', async () => {
  const h=harness('#/customers?view=development&item=candidate%3A1'); h.discovery.candidates.push({id:'candidate:1',kind:'candidate',title:'买家公司',company:'买家公司',website:'https://example.org',business_category:'批发商',business_summary:'鞋类批发',source_record:{contacts:[{kind:'email',value:'buyer@example.org'}]}});
  await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('邮箱：buyer@example.org')); assert.ok(walk(h.body).some(x=>x.tagName==='A' && x.textContent==='访问公司网站 ↗'));
});

test('客户详情展示并保存发现路径和适配理由', async () => {
  const h=harness('#/customers?view=development&item=candidate%3A1');
  h.discovery.candidates.push({id:'candidate:1',kind:'candidate',title:'买家公司',company:'买家公司',discovery_reason:'公开搜索发现；官网主营休闲鞋。',evidence:[{url:'https://buyer.example/about',text:'官网业务'}]});
  await h.ui.bootstrap(); await settle();
  const summary=h.elements.page.querySelector('.candidate-summary');
  assert.ok(summary.textContent.includes('公开搜索发现；官网主营休闲鞋。'));
  assert.ok(h.elements.page.textContent.includes('交给 Agent 执行'));
  assert.ok(h.elements.page.textContent.includes('客户资料包 · 查看选款材料'));
  assert.ok(walk(summary).some(node=>node.tagName==='A' && node.href==='https://buyer.example/about'));
  const field=walk(h.elements.page).find(node=>node['aria-label']==='从哪里找到，为什么适合');
  field.value='公开目录发现；鞋类定位与本厂套脚鞋相邻。';
  await findButton(h.elements.page,'保存客户资料').click(); await settle();
  assert.equal(h.requests.find(item=>item.path==='/api/desk/discovery/update').payload.discovery_reason,field.value);
});

test('客户收到新邮件后，详情下一步不再显示等待回复', async () => {
  const h=harness('#/customers?view=development&item=candidate%3A1'), original=h.originalFetch;
  h.discovery.candidates.push({id:'candidate:1',object_id:'prospect:candidate:1',kind:'candidate',title:'买家公司',next_action:'等待客户回复'});
  h.interceptFetch(async(path,options)=>String(path).startsWith('/api/desk/gmail/') ? {ok:true,json:async()=>({status:{state:'connected'},reply_pending:true,messages:[]})} : original(path,options));
  await h.ui.bootstrap(); await settle();
  assert.ok(h.elements.page.textContent.includes('下一步：阅读客户新邮件，准备后续沟通'));
  assert.equal(h.elements.page.querySelector('.candidate-next-action').textContent.includes('等待客户回复'),false);
});

test('客户回复草稿可以复制英文到 Gmail，已发送内容不提供重复发送入口', async () => {
  const h=harness('#/customers?view=development&item=candidate%3A1'), original=h.originalFetch;
  h.discovery.candidates.push({id:'candidate:1',object_id:'prospect:candidate:1',kind:'candidate',title:'买家公司'});
  h.artifacts.push({id:'draft-1',object_id:'prospect:candidate:1',title:'回复草稿',content:'## 英文正文\nSubject: Quotation\n\nDear buyer,\n\n**Thank you.**\n\n## 中文对照\n谢谢。',updated_at:'2026-11-02'});
  h.interceptFetch(async(path,options)=>String(path).startsWith('/api/desk/gmail/') ? {ok:true,json:async()=>({status:{state:'connected'},messages:[]})} : original(path,options));
  await h.ui.bootstrap(); await settle(); await findButton(h.elements.page,'复制英文回复').click();
  assert.equal(h.clipboard(),'Dear buyer,\n\nThank you.'); assert.equal(h.requests.some(x=>/send|outreach/.test(x.path)),false);
  h.artifacts[1].title='回复（已发送）'; await h.ui.renderRoute(); await settle();
  assert.equal(walk(h.elements.page).some(item=>item.tagName==='BUTTON' && item.textContent==='复制英文回复'),false);
});

test('从客户开发新增公司，并保存业务信息', async () => {
  const h=harness('#/customers?view=development'); await h.ui.bootstrap(); await settle(); await findButton(h.body,'新增客户').click(); const dialog=walk(h.body).find(x=>x.tagName==='DIALOG');
  for (const [label,value] of [['公司名称','样例采购公司'],['公司网站','https://buyer.example'],['国家或市场','英国'],['业务摘要','鞋类批发'],['买家类型','批发商'],['联系状态','未联系'],['下一步','寻找采购联系人']]) { const field=walk(dialog).find(x=>x['aria-label']===label); field.value=value; }
  await findButton(dialog,'保存客户').click(); const request=h.requests.find(x=>x.path==='/api/desk/discovery'&&x.payload?.kind==='candidate'); assert.equal(request.payload.company,'样例采购公司'); assert.equal(request.payload.business_summary,'鞋类批发'); assert.equal(request.payload.next_action,'寻找采购联系人');
});

test('网站回复可采用成果中的英文正文，不带邮件主题或中文', async () => {
 const h=harness('#/object/customer%3Awebsite-x'); h.objects.push({id:'customer:website-x',kind:'customer',title:'买家',source:'website:x',conversation:[],assets:[]}); h.artifacts.push({id:'reply-1',object_id:'customer:website-x',title:'回复草稿',content:'# 回复\n## 英文正文\nSubject: inquiry\n\nDear buyer,\n\nThank you.\n\n## 完整中文对照\n亲爱的买家',updated_at:'2026-11-01'}); await h.ui.bootstrap(); await settle();
 await findButton(h.body,'采用英文正文到回复框').click(); const reply=walk(h.body).find(x=>x['aria-label']==='网站私信回复'); assert.equal(reply.value,'Dear buyer,\n\nThank you.'); assert.equal(h.requests.some(x=>x.path==='/api/desk/website-reply'),false);
});

test('网站客户优先打开最新保存的回复而非旧任务草稿', async () => {
 const h=harness('#/object/customer%3Awebsite-x'); h.objects.push({id:'customer:website-x',kind:'customer',title:'买家',source:'website:x',conversation:[],assets:[]});
 h.artifacts.push({id:'old',object_id:'customer:website-x',title:'旧草稿',content:'旧判断',updated_at:'2026-10-01'},{id:'new',object_id:'customer:website-x',title:'更新后的回复',content:'## 英文正文\nDear buyer',updated_at:'2026-11-01'}); h.jobs.push({id:'job',object_id:'customer:website-x',artifact_id:'old',status:'completed'});
 await h.ui.bootstrap();await settle();assert.ok(h.ui.S.detail.editor.textContent.includes('更新后的回复'));assert.equal(h.ui.S.detail.editor.textContent.includes('旧判断'),false);
});

test('买家搜索能查看真实来源并加入目标客户', async () => {
 const h=harness('#/customers?view=development'), original=h.originalFetch; h.interceptFetch(async (path,options) => { if(String(path).startsWith('/api/desk/buyer-search?'))return {ok:true,json:async()=>({status:'success',records:[{company:'Example Wholesale',source_title:'Example Wholesale',source_url:'https://example.test/about',excerpt:'Footwear wholesaler'}]})};return original(path,options); });
 await h.ui.bootstrap(); await settle(); await findButton(h.body,'搜索买家').click(); await settle(); assert.ok(h.elements.page.textContent.includes('Example Wholesale')); await findButton(h.body,'加入目标客户').click(); const created=h.requests.find(x=>x.payload?.company==='Example Wholesale'); assert.equal(created.payload.kind,'candidate'); assert.equal(created.payload.evidence[0].url,'https://example.test/about'); assert.equal(created.payload.country,undefined); assert.doesNotMatch(created.payload.business_summary,/进口记录/);
});

test('官网搜索可查看来源并保存所选网址到原客户', async () => {
 const h=harness('#/customers?view=development&item=candidate%3A1'), original=h.originalFetch;
 h.discovery.candidates.push({id:'candidate:1',object_id:'prospect:candidate:1',kind:'candidate',title:'Example Buyer',company:'Example Buyer',evidence:[]});
 h.interceptFetch(async(path,options)=>String(path)==='/api/desk/company-lookup' ? {ok:true,json:async()=>({status:'candidates',checked_at:'2026-11-01',candidates:[{website:'https://buyer.example',source_url:'https://source.example/buyer',evidence:'Website: buyer.example'}]})} : original(path,options));
 await h.ui.bootstrap(); await settle(); await findButton(h.body,'查找公司官网').click();
 assert.ok(h.elements.page.textContent.includes('https://buyer.example')); assert.ok(h.elements.page.textContent.includes('查看资料来源'));
 await findButton(h.body,'使用这个官网').click(); await settle();
 const saved=h.requests.find(x=>x.path==='/api/desk/discovery/update'); assert.equal(saved.payload.website,'https://buyer.example'); assert.equal(saved.payload.evidence.at(-1).url,'https://source.example/buyer');
});

test('LibTV 画布可读取节点并由用户添加文字', async () => {
 const h=harness('#/creation'), original=h.originalFetch, calls=[]; h.interceptFetch(async(path,options={})=>{ const url=new URL(path,'http://127.0.0.1:8766'); let value;
  if(url.pathname==='/api/desk/creation')value={projects:[]};
  else if(url.pathname==='/api/desk/creation/libtv')value={ok:true,data:{projects:{items:[{id:'canvas-1',name:'测试画布'}]}}};
  else if(url.pathname==='/api/desk/creation/libtv/nodes')value={ok:true,data:{nodes:{items:[{title:'参考',content:'鞋子画面'}]}}};
  else if(url.pathname==='/api/desk/creation/libtv/text'){calls.push(JSON.parse(options.body));value={ok:true,data:{node:{id:'node-1'}}};}
  else return original(path,options);return {ok:true,json:async()=>value}; });
 await h.ui.bootstrap(); await settle(); await findButton(h.body,'读取我的画布').click(); await findButton(h.body,'查看节点').click(); assert.ok(h.elements.page.textContent.includes('鞋子画面'));
 const title=walk(h.body).find(x=>x['aria-label']==='节点标题'),content=walk(h.body).find(x=>x['aria-label']==='文字内容');title.value='镜头想法';content.value='鞋子行走';await findButton(h.body,'添加文字节点').click();assert.equal(calls[0].project_id,'canvas-1');assert.equal(calls[0].content,'鞋子行走');
});

test('background updates do not expose a duplicate agent entry or overwrite unsaved work', async () => {
  const h = harness('#/object/product%3A1'); await h.ui.bootstrap(); await settle(); const ctx = h.ui.S.detail;
  assert.equal(h.elements.page.textContent.includes('交给 Sol'),false);h.jobs.push({id:'background',object_id:'product:1',status:'running',updated_at:'2026-10-31T02:00:00Z'});
  const title = ctx.editor.querySelector('input'), editor = ctx.editor.querySelector('textarea'); title.value = '自己修改的标题'; title.listeners.input({}); editor.value = '自己未保存的正文'; editor.listeners.input({});
  h.jobs[0].status = 'completed'; h.jobs[0].updated_at = '2026-10-31T04:00:00Z'; h.artifacts.push({ id: 'new-result', object_id: 'product:1', title: '新成果', content: '模型新输出', updated_at: '2026-10-31T04:00:00Z' }); await h.ui.poll();
  assert.equal(ctx.editor.querySelector('textarea'), editor); assert.equal(editor.value, '自己未保存的正文'); await findButton(ctx.editor, '保存成果').click(); const save = h.requests.find(item => item.path === '/api/desk/artifacts' && item.payload); assert.equal(save.payload.id, 'a1'); assert.equal(save.payload.content, '自己未保存的正文');
});

test('website loading is not an empty-inquiry claim and later real customer appears without replacing search', async () => {
  const h = harness('#/customers?view=inquiries'); await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('网站记录正在读取')); const search = h.elements.page.querySelector('input');
  h.objects.push({ id: 'customer:real', kind: 'customer', title: '真实需求', source: '网站询盘', assets: [], content: '客户原文' }); h.setWebsite({ state: 'ready', observed_at: '2026-10-31T05:00:00Z' }); await h.ui.poll(); await settle(); assert.equal(h.elements.page.querySelector('input'), search); assert.ok(h.elements.page.textContent.includes('真实需求')); await h.ui.refreshData(); assert.ok(h.requests.some(item => item.path === '/api/desk/refresh' && item.payload));
});

test('home never recommends arbitrary first products; recents require an actual open or job', async () => {
  const h = harness(); h.artifacts.length = 0; await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('从业务开始')); assert.ok(h.elements.page.textContent.includes('网站记录')); assert.equal(h.elements.page.textContent.includes('继续工作'), false); assert.equal(h.elements.page.textContent.includes('真实商品'), false);
  h.objects.push({ id: 'customer:worked', kind: 'customer', title: '实际处理过的客户', source: '本地客户记录', assets: [] }); h.jobs.push({ id: 'past-job', object_id: 'customer:worked', status: 'completed', updated_at: '2026-10-31T02:00:00Z' }); await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('实际处理过的客户')); assert.equal(h.elements.page.textContent.includes('真实商品'), false);
  h.location.hash = '#/object/product%3A1'; await h.ui.renderRoute(); await settle(); h.location.hash = '#/overview'; await h.ui.renderRoute(); assert.ok(h.elements.page.textContent.includes('真实商品')); assert.ok(h.elements.page.textContent.includes('继续工作'));
});

test('总览直接显示当前客户需求和下一动作', async () => {
  const h = harness(); h.setToday({groups:{decide:[],act:[{title:'当前买家',judgment:'需要采购休闲鞋 · 准备选款'}],watch:[]},counts:{decide:0,act:1,watch:0},labels:{act:'待处理'}});
  await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('当前买家')); assert.ok(h.elements.page.textContent.includes('需要采购休闲鞋')); assert.ok(h.elements.page.textContent.includes('准备选款'));
});

test('总览将待处理的新回复与等待客户的事项分开', async () => {
  const h = harness(); h.setToday({groups:{decide:[],act:[{title:'有新回复的买家',judgment:'网站站内消息有新回复'}],watch:[{title:'等待回复：等待中的买家',judgment:'等资料'}]},counts:{decide:0,act:1,watch:1},labels:{act:'待处理',watch:'等待'}});
  await h.ui.bootstrap(); await settle();
  const groups=h.elements.page.querySelectorAll('.today-group');
  const pending=groups.find(x=>x.className.split(' ').includes('act')), waiting=groups.find(x=>x.className.split(' ').includes('watch'));
  assert.ok(pending.textContent.includes('有新回复的买家')); assert.ok(pending.textContent.includes('网站站内消息有新回复'));
  assert.equal(pending.textContent.includes('等待中的买家'),false); assert.ok(waiting.textContent.includes('等待中的买家'));
});

test('网站往来更新后总览会刷新客户状态', async () => {
  const h=harness();
  h.setToday({groups:{decide:[],act:[],watch:[{title:'等待回复：客户甲',judgment:'等待客户'}]},counts:{decide:0,act:0,watch:1},labels:{watch:'等待'}});
  await h.ui.bootstrap();await settle();assert.ok(h.elements.page.textContent.includes('等待回复：客户甲'));
  h.setToday({groups:{decide:[],act:[{title:'客户甲有新回复',judgment:'网站站内消息有新回复 · 阅读新回复'}],watch:[]},counts:{decide:0,act:1,watch:0},labels:{act:'待处理'}});
  h.setWebsite({state:'ready',observed_at:'2026-11-01T03:00:00Z'});await h.ui.poll();await settle();
  assert.ok(h.elements.page.textContent.includes('网站站内消息有新回复'));assert.ok(h.elements.page.textContent.includes('阅读新回复'));
});

test('等待客户时隐藏过时的首封回复建议', async () => {
  const h=harness('#/object/customer%3Awebsite-x'); h.objects.push({id:'customer:website-x',kind:'customer',title:'买家',source:'website:x',conversation:[],assets:[]});
  h.profile.workflow={state:'waiting_customer',state_label:'等客户',bucket:'active',next_action:'等待照片',allowed_transitions:[]};
  h.profile.analysis.questions_now=['请发照片']; h.profile.analysis.recommended_reply='旧的首封回复';
  await h.ui.bootstrap(); await settle();
  assert.ok(h.ui.S.detail.profileHost.textContent.includes('等待照片')); assert.equal(h.ui.S.detail.profileHost.textContent.includes('旧的首封回复'),false);
});

test('商品平台检查优先，原有素材可展开', async () => {
  const h = harness('#/object/product%3A1'); h.objects[0].assets = Array.from({ length: 29 }, (_, i) => ({ path: `real-${i}.jpg`, label: `原素材 ${i}`, url: `/api/media/file?path=real-${i}.jpg` })); await h.ui.bootstrap(); await settle();
  const main = h.elements.page.querySelector('.object-main'); assert.ok(main.children[1].textContent.startsWith('国际站商品检查')); const grid = main.querySelector('.asset-grid'); assert.equal(grid.children.length, 6); await findButton(main, '展开全部 29 份素材').click(); assert.equal(grid.children.length, 29); await findButton(main, '收起素材').click(); assert.equal(grid.children.length, 6);
});


test('late product response cannot paint over a newer customer URL before hashchange is handled', async () => {
  const h = harness(); await h.ui.bootstrap(); await settle(); let finish;
  h.interceptFetch(async (path, options) => path.startsWith('/api/desk/object?') ? new Promise(resolve => { finish = () => resolve({ ok: true, json: async () => structuredClone(h.objects[0]) }); }) : h.originalFetch(path, options));
  h.location.hash = '#/object/product%3A1'; const opening = h.ui.renderRoute(); await settle();
  h.location.hash = '#/customers'; finish(); await opening; assert.equal(h.elements.page.textContent.includes('很长的原文'), false); assert.equal(h.ui.S.detail, null);
  await h.ui.renderRoute(); await settle(); assert.ok(h.elements.page.textContent.includes('客户')); assert.equal(h.ui.S.page, 'customers');
});

test('wrong object identity is never rendered or inserted as the selected customer', async () => {
  const h = harness(); await h.ui.bootstrap(); await settle(); h.interceptFetch(async (path, options) => path.startsWith('/api/desk/object?') ? { ok: true, json: async () => structuredClone(h.objects[0]) } : h.originalFetch(path, options));
  h.location.hash = '#/object/customer%3Afoot-levelers'; await h.ui.renderRoute(); await settle(); assert.ok(h.elements.page.textContent.includes('返回资料与所选对象不一致')); assert.equal(h.ui.S.object, null); assert.equal(h.ui.S.detail, null); assert.equal(h.ui.S.objects.some(item => item.id === 'customer:foot-levelers'), false);
});

test('detached customer search cannot rewrite the object hash while navigation is in progress', async () => {
  const h = harness('#/customers?view=inquiries'); await h.ui.bootstrap(); await settle(); const oldInput = h.elements.page.querySelector('input'); h.location.hash = '#/object/product%3A1'; oldInput.value = 'late event'; oldInput.listeners.input({}); assert.equal(h.location.hash, '#/object/product%3A1');
});

test('product summary keeps business facts compact and preserves long channel fields behind disclosure', async () => {
  const h = harness('#/object/product%3A1'); h.objects[0].facts = [{ label: '共用产品ID', value: 'internal-id' }, { label: '别名', value: 'extra aliases' }, { label: '来源状态', value: '已确认' }, { label: '供应商', value: '真实供应商' }, { label: '供应商原款', value: '原款008' }, { label: '用途候选', value: '候选方向' }, { label: '历史参考价', value: '仅作参考' }, { label: '原档已有规格', value: '原档规格' }, { label: 'Alibaba 123', value: 'Long platform title '.repeat(30) }, { label: '原始资料包', value: '原包路径' }]; await h.ui.bootstrap(); await settle();
  const hero = h.elements.page.querySelector('.detail-hero'), visible = hero.querySelector('.object-facts'), extra = hero.querySelector('.extra-facts'); assert.equal(visible.querySelectorAll('dt').length, 3); assert.equal(visible.textContent.includes('internal-id'), false); assert.equal(visible.textContent.includes('Long platform title'), false); assert.equal(extra, null);
});

test('default artifact follows latest actual job, explicit artifact wins, and saved work opens in read mode', async () => {
  const h = harness('#/object/product%3A1'); h.artifacts[0].updated_at = '2026-11-02T00:00:00Z'; h.artifacts.push({ id: 'latest-work', object_id: 'product:1', title: '最新真实成果', content: '最新工作正文', updated_at: '2026-10-31T02:00:00Z' });
  h.jobs.push({ id: 'old', object_id: 'product:1', status: 'needs_input', artifact_id: 'a1', created_at: '2026-10-30T00:00:00Z' }, { id: 'latest', object_id: 'product:1', status: 'completed', artifact_id: 'latest-work', created_at: '2026-10-31T00:00:00Z' });
  await h.ui.bootstrap(); await settle(); assert.equal(h.ui.S.detail.selectedId, 'latest-work'); assert.ok(h.ui.S.detail.editor.querySelector('.artifact-preview').textContent.includes('最新工作正文')); assert.equal(h.ui.S.detail.editor.querySelector('textarea').hidden, true); await findButton(h.ui.S.detail.editor, '编辑').click(); assert.equal(h.ui.S.detail.editor.querySelector('textarea').hidden, false);
  h.location.hash = '#/object/product%3A1?artifact=a1'; await h.ui.renderRoute(); await settle(); assert.equal(h.ui.S.detail.selectedId, 'a1');
});

test('客户成果链接打开所选草稿，而不是默认最新成果', async () => {
  const h=harness('#/customers?view=development&item=candidate%3A1&artifact=older');
  const oid='prospect:candidate:1';
  h.discovery.candidates.push({id:'candidate:1',object_id:oid,kind:'candidate',title:'买家公司'});
  h.artifacts.push({id:'newer',object_id:oid,title:'最新成果',content:'最新正文'},
                   {id:'older',object_id:oid,title:'指定草稿',content:'指定正文'});
  await h.ui.bootstrap(); await settle();
  assert.equal(h.ui.S.detail.selectedId,'older');
  assert.ok(h.ui.S.detail.editor.querySelector('.artifact-preview').textContent.includes('指定正文'));
});

test('customer analysis preserves original and background updates retain unsaved edits', async () => {
  const h = harness('#/object/customer%3Arecord'); h.objects.push({ id: 'customer:record', kind: 'customer', title: '来源记录', subtitle: '网站询盘', source: 'website:record', assets: [], content: 'Please send sample information.' }); await h.ui.bootstrap(); await settle(); const ctx = h.ui.S.detail;
  assert.ok(ctx.profileHost.textContent.includes('请提供样品信息')); assert.ok(ctx.profileHost.textContent.includes('Please send sample information.')); assert.ok(ctx.profileHost.textContent.includes('询盘简报')); assert.equal(ctx.profileHost.textContent.includes('真实询盘'), false);
  assert.equal(ctx.profileHost.textContent.includes('翻译并分析原始需求'),false);h.jobs.push({id:'background',object_id:'customer:record',status:'running',updated_at:'2026-10-31T08:00:00Z'});
  h.profile.translation_zh = '新的完整中文译文'; h.jobs[0].status = 'completed'; h.jobs[0].updated_at = '2026-10-31T09:00:00Z'; h.jobs[0].profile_saved = true; h.jobs[0].artifact_id = null; await h.ui.poll(); await settle(); assert.ok(ctx.profileHost.textContent.includes('新的完整中文译文')); assert.equal(h.artifacts.length, 1);
  await findButton(ctx.profileHost, '编辑解读与分析').click(); const edit = ctx.profileHost.querySelector('textarea'); edit.value = '人工尚未保存的中文解释'; h.jobs[0].updated_at = '2026-10-31T10:00:00Z'; await h.ui.poll(); await settle(); assert.equal(ctx.profileHost.querySelector('textarea'), edit); assert.equal(edit.value, '人工尚未保存的中文解释');
  await findButton(ctx.profileHost, '保存中文解读与分析').click(); const save = h.requests.find(item => item.path === '/api/desk/customer-profile' && item.payload); assert.equal(save.payload.source_hash, 'hash-1'); assert.equal(save.payload.translation_zh, '人工尚未保存的中文解释'); assert.equal(Object.hasOwn(save.payload, 'original_text'), false);
});

test('analysis creates a linked research task with evidence and never sends outreach', async () => {
  const h = harness('#/object/customer%3Arecord'); h.objects.push({ id: 'customer:record', kind: 'customer', title: '当前需求', source: 'website:record', assets: [] }); await h.ui.bootstrap(); await settle(); await findButton(h.ui.S.detail.profileHost, '把缺口或下一步转为研究任务').click(); const dialog = walk(h.body).find(item => item.tagName === 'DIALOG'); await findButton(dialog, '保存研究任务并打开').click(); const created = h.requests.find(item => item.path === '/api/desk/discovery' && item.payload); assert.equal(created.payload.origin_object_id, 'customer:record'); assert.equal(created.payload.kind, 'research_task'); assert.ok(created.payload.evidence.length); assert.ok(h.location.hash.includes('view=development')); assert.equal(h.requests.some(item => /send|outreach/.test(item.path)), false);
});

test('development exposes real candidate evidence, research context, and a non-outreach preparation marker', async () => {
  const h = harness('#/customers?view=development'); h.discovery.candidates.push({ id: 'candidate:source', object_id: 'prospect:candidate:source', kind: 'candidate', title: '已有来源候选', company: '候选公司', target: '需要核实供货适配', evidence: [{ url: 'https://example.com/', text: '原候选公开来源' }] }); await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('目标客群')); const row = walk(h.elements.page).find(item => item.tagName === 'ARTICLE' && item.textContent.includes('已有来源候选')); await findButton(row, '打开客户 →').click(); await settle(); assert.ok(h.elements.page.textContent.includes('原候选公开来源')); assert.equal(h.elements.page.textContent.includes('交给 Sol'),false); assert.equal(walk(h.elements.page).find(x=>x['aria-label']==='研究问题').value,'需要核实供货适配');
  await findButton(h.elements.page, '标记进入推进准备').click(); const changed = h.requests.find(item => item.path === '/api/desk/discovery/update'); assert.equal(changed.payload.ready_for_customer, true); assert.equal(changed.payload.status, '推进准备'); assert.equal(h.requests.some(item => /send|outreach/.test(item.path)), false);
});

test('order buyers stay a separate source filter instead of inflating inquiry counts', async () => {
  const h = harness('#/customers?view=inquiries'); h.objects.push({ id: 'customer:original', kind: 'customer', title: '原需求记录', assets: [] }, { id: 'customer:order', kind: 'customer', title: '订单来源买家', source_type: 'alibaba_order_buyer', assets: [] }); await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('原需求记录')); assert.equal(h.elements.page.textContent.includes('订单来源买家'), false); await findButton(h.elements.page, '订单买家').click(); h.location.hash = '#/customers?view=inquiries&source=orders'; await h.ui.renderRoute(); await settle(); assert.ok(h.elements.page.textContent.includes('订单来源买家')); assert.equal(h.elements.page.textContent.includes('原需求记录'), false);
});

test('customer reading keeps Chinese need first and supporting analysis folded with three recommendations', async () => {
  const h = harness('#/object/customer%3Arecord'); h.objects.push({ id: 'customer:record', kind: 'customer', title: '来源记录', summary: 'A long English original request.', source: 'website:record', assets: [] }); h.profile.cleaned.need = '中文提取的具体需求'; h.profile.cleaned.stage = 'new'; h.profile.provenance.evidence_notes = '网站来源尚待核实'; h.profile.analysis.recommendations = ['建议一', '建议二', '建议三', '建议四', '建议五']; await h.ui.bootstrap(); await settle(); const ctx = h.ui.S.detail;
  assert.equal(ctx.summaryParagraph.textContent, '中文提取的具体需求'); const folders = ctx.profileHost.querySelector('.analysis-folders'); assert.equal(folders.querySelectorAll('details').length, 4); assert.ok(folders.querySelectorAll('details').every(item => !item.open)); const rec = ctx.profileHost.querySelector('.recommendations'); assert.equal(rec.querySelectorAll('li').length, 3); await findButton(rec, '展开全部 5 条建议').click(); assert.equal(rec.querySelectorAll('li').length, 5); assert.ok(ctx.profileHost.textContent.includes('中文提取的具体需求'));
  const children = ctx.profileHost.children; assert.ok(children.indexOf(ctx.profileHost.querySelector('.source-note')) < children.indexOf(ctx.profileHost.querySelector('.bilingual-grid')));
});

test('selected research task hides the long candidate list and follows its actual goal and linked original', async () => {
  const h = harness('#/customers?view=development&item=research%3Alinked'); h.discovery.tasks.push({ id: 'research:linked', object_id: 'prospect:research:linked', kind: 'research_task', title: '改善承接', target: '优化定制开发询盘承接', origin_object_id: 'customer:record', evidence: [] }); await h.ui.bootstrap(); await settle(); assert.equal(h.elements.page.querySelector('.discovery-target').hidden, true); assert.equal(walk(h.elements.page).find(x=>x['aria-label']==='目标客群 / 适配问题').value,'优化定制开发询盘承接'); assert.equal(h.elements.page.textContent.includes('交给 Sol'),false); assert.ok(findButton(h.elements.page, '← 返回客户开发列表'));
});


test('inquiry queue separates history, sorts priority, and shows workflow not raw archives', async () => {
 const h = harness('#/customers?view=inquiries'); h.objects.push({id:'customer:normal',kind:'customer',title:'普通待办',summary:'一双样品',priority:'normal'}, {id:'customer:high',kind:'customer',title:'优先待办',summary:'确认开发范围',priority:'high'}, {id:'customer:history',kind:'customer',title:'旧CRM复盘',bucket:'history'}); await h.ui.bootstrap(); await settle(); const rows = h.elements.page.querySelectorAll('.inquiry-row'); assert.equal(rows[0].textContent.includes('优先待办'),true); assert.equal(h.elements.page.textContent.includes('旧CRM复盘'),false); await findButton(h.elements.page,'历史复盘').click(); h.location.hash='#/customers?view=inquiries&bucket=history'; await h.ui.renderRoute(); await settle(); assert.ok(h.elements.page.textContent.includes('旧CRM复盘')); assert.equal(h.elements.page.textContent.includes('普通待办'),false);
});

test('customer detail prioritizes secretary brief, hides JSON and history, saves named workflow with token', async () => {
 const h = harness('#/object/customer%3Arecord'); h.objects.push({id:'customer:record',kind:'customer',title:'实际客户',content:'{"internal_schema":"never show"}',facts:[{label:'技术字段',value:'not in briefing'}],assets:[]}); Object.assign(h.profile.analysis,{brief:'先确认开发边界，再讨论样品',core_need:'开发专用鞋底',questions_now:['使用场景？','验收标准？','目标数量？','非当前问题'],recommended_reply:'先给现有能力及开发边界'}); h.profile.workflow={state:'preparing',priority:'high',next_action:'准备开发范围回复',allowed_transitions:[{state:'waiting_customer',label:'等客户'}]}; await h.ui.bootstrap(); await settle(); const page=h.elements.page,ctx=h.ui.S.detail; assert.ok(page.textContent.includes('先确认开发边界')); assert.equal(page.textContent.includes('internal_schema'),false); assert.equal(page.textContent.includes('非当前问题'),false); const history=walk(page).find(item=>item.tagName==='DETAILS'&&item.children[0]?.textContent==='回复草稿与工作成果'); assert.ok(history); assert.equal(Boolean(history.open),false); const editor=ctx.profileHost.querySelector('.workflow-editor'), next=walk(editor).find(item=>item['aria-label']==='下一动作'); next.value='等待客户补充使用场景'; await next.listeners.input(); await h.ui.poll(); await settle(); assert.equal(ctx.profileHost.querySelector('.workflow-editor'),editor); await findButton(editor,'保存推进安排').click(); const request=h.requests.find(item=>item.path==='/api/desk/customer-workflow'); assert.equal(request.payload.next_action,'等待客户补充使用场景'); assert.equal(request.options.headers['X-Workbench-Token'],'fixture-token');
});


test('brief keeps reception fit visible while context and source notes are folded', async () => {
 const h=harness('#/object/customer%3Arecord'); h.objects.push({id:'customer:record',kind:'customer',title:'客户',assets:[]}); Object.assign(h.profile.analysis,{brief:'先厘清开发边界',fit:'现有生产可承接，具体配方需按样品目标确认',recommended_reply:'可以先讨论样品目的与交付物。'}); h.profile.operator_context='数量来自表单必填，不代表确认订单'; h.profile.provenance.evidence_notes='来源说明'; h.profile.provenance.source_verification.note='来源说明'; await h.ui.bootstrap(); await settle(); const host=h.ui.S.detail.profileHost, brief=host.querySelector('.inquiry-brief'); assert.ok(brief.querySelector('.brief-fit').textContent.includes('现有生产可承接')); const context=brief.querySelector('.operator-context'); assert.equal(context.tagName,'DETAILS'); assert.equal(Boolean(context.open),false); const source=host.querySelector('.source-note'); assert.equal(source.tagName,'DETAILS'); assert.equal(Boolean(source.open),false); assert.equal(source.querySelectorAll('p').length,1); assert.ok(brief.querySelector('.brief-reply').textContent.includes('可以先讨论')); assert.equal(brief.querySelector('.brief-reply').tagName,'SECTION');
});

test('creation project opens its exact object without a duplicate agent entry', async () => {
  const h = harness('#/creation?item=creation%3Aabc');
  const original = h.originalFetch;
  h.interceptFetch(async (path, options) => {
    const url = new URL(path, 'http://127.0.0.1:8765');
    let value;
    if (url.pathname === '/api/desk/creation/item') value = {id:'creation:abc',title:'视频项目',content:'原始项目记录',assets:[],links:[]};
    else if (url.pathname === '/api/desk/object' && url.searchParams.get('id') === 'creation:abc') value = {id:'creation:abc',kind:'creation',title:'视频项目',source:'05_内容与视频/项目/PROJECT.md',assets:[]};
    else return original(path, options);
    return {ok:true,json:async()=>value};
  });
  await h.ui.bootstrap(); await settle();
  assert.ok(h.elements.page.textContent.includes('原始项目记录'));
  assert.equal(h.elements.page.textContent.includes('交给 Sol'),false);
  assert.ok(h.elements.page.textContent.includes('创作成果'));
});

test('商品检查从经营分析打开精确链接，并支持切换与对照', async () => {
  const h = harness('#/object/product%3A1?listing=456');
  h.objects[0].links = [{label:'Alibaba 123',url:'https://example.com/product'},{label:'Alibaba 456',url:'https://example.com/product2'}];
  const original = h.originalFetch;
  h.interceptFetch(async (path, options) => {
    const u = new URL(path,'http://127.0.0.1:8765');
    if (u.pathname === '/api/desk/product-review') { const id=u.searchParams.get('listing_id') || '123';return {ok:true,json:async()=>({listings:[{id:'123',url:'https://example.com/product'},{id:'456',url:'https://example.com/product2'}],selected:{id,state:'ready',local:{title:'Local'},platform:{title:'Live '+id,title_zh:{state:'ready',text:'中文平台标题'},main_images:[{url:'https://example.com/main.jpg'}],detail_images:[{url:'https://example.com/detail.jpg'}],company_images:[],observed_at:'2026-11-02T00:00:00Z'},comparison:{title:'different',main_images:'same',detail_images:'not_recorded'}}})}; }
    return original(path, options);
  });
  await h.ui.bootstrap(); await settle();
  assert.ok(h.elements.page.textContent.includes('Live 456'));
  const select=walk(h.elements.page).find(x=>x['aria-label']==='选择国际站商品链接'); select.value='123';select.listeners.change();await settle();
  assert.ok(h.elements.page.textContent.includes('Live 123'));assert.ok(h.elements.page.textContent.includes('中文平台标题'));assert.ok(h.elements.page.textContent.includes('本地标题：Local'));
  assert.ok(h.elements.page.textContent.includes('平台主图 · 1 张'));assert.ok(h.elements.page.textContent.includes('平台详情图 · 1 张'));
});

test('商品主图调整先预览顺序，准备方案不自动提交', async () => {
  const h=harness('#/object/product%3A1'), original=h.originalFetch;
  h.objects[0].links=[{label:'Alibaba 123',url:'https://example.com/product'}];
  const urls=Array.from({length:6},(_,i)=>`https://sc04.alicdn.com/kf/${i}.jpg`);let prepared=null,submitted=false;
  h.interceptFetch(async(path,options={})=>{
    if(String(path).startsWith('/api/desk/product-review'))return {ok:true,json:async()=>({listings:[{id:'123'}],selected:{id:'123',state:'ready',local:{},platform:{title:'Live',main_images:urls.map(url=>({url})),detail_images:[],company_images:[]},comparison:{}}})};
    if(path==='/api/product-gallery-changes/prepare'){prepared=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,change:{id:'gallery1',version:'v1',diff:{before:urls,after:[urls[1],urls[0],...urls.slice(2)]},submission:{state:'not-submitted'}}})};}
    if(String(path).includes('/apply'))submitted=true;
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();
  const up=walk(h.elements.page).filter(node=>node.tagName==='BUTTON' && node.textContent==='前移');await up[1].click();
  await findButton(h.elements.page,'生成主图调整方案').click();await settle();
  assert.deepEqual(prepared,{product_id:'123',order:[2,1,3,4,5,6]});assert.match(h.elements.page.textContent,/主图调整方案/);assert.equal(submitted,false);
});

test('主图可选择本商品素材并生成替换方案',async()=>{
  const h=harness('#/object/product%3A1'),original=h.originalFetch;h.objects[0].links=[{label:'Alibaba 123',url:'https://example.com/product'}];
  const urls=Array.from({length:6},(_,i)=>`https://sc04.alicdn.com/kf/${i}.jpg`);let prepared;
  h.interceptFetch(async(path,options={})=>{
    if(String(path).startsWith('/api/desk/product-review'))return {ok:true,json:async()=>({listings:[{id:'123'}],selected:{id:'123',state:'ready',local:{},platform:{title:'Live',main_images:urls.map(url=>({url})),detail_images:[],company_images:[]},comparison:{}}})};
    if(path==='/api/product-gallery-plans/prepare'){prepared=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,change:{id:'p1',version:'v1',state:'prepared',before:urls,previews:[{previewRef:'商品图.jpg'},...urls.slice(1).map(url=>({url}))]}})};}
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();await walk(h.elements.page).find(node=>node.tagName==='BUTTON' && node.textContent==='替换图片').click();
  await walk(h.elements.page).find(node=>node.tagName==='BUTTON' && node.textContent==='真实主图').click();
  await findButton(h.elements.page,'生成主图调整方案').click();await settle();
  assert.deepEqual(prepared.slots,[{path:'商品图.jpg'},2,3,4,5,6]);assert.match(h.elements.page.textContent,/主图调整方案/);
});

test('详情图按平台图片组调整并准备方案',async()=>{
  const h=harness('#/object/product%3A1'),original=h.originalFetch;h.objects[0].links=[{label:'Alibaba 123',url:'https://example.com/product'}];let prepared;
  const rows=[{image_url:'https://example.com/a.jpg',image_set:{name:'Detail shot'}},{image_url:'https://example.com/b.jpg',image_set:{name:'Scene image'}}];
  h.interceptFetch(async(path,options={})=>{
    if(String(path).startsWith('/api/desk/product-review'))return {ok:true,json:async()=>({listings:[{id:'123'}],selected:{id:'123',state:'ready',local:{},platform:{title:'Live',main_images:[],detail_images:rows.map(row=>({url:row.image_url})),company_images:[]},comparison:{}}})};
    if(String(path).startsWith('/api/desk/product-details-diagnosis'))return {ok:true,json:async()=>({ok:true,change:{platform:{detail_images:rows},detailGroups:[{roleName:'Detail shot',slots:[1]},{roleName:'Scene image',slots:[2]}]}})};
    if(path==='/api/product-detail-changes/prepare'){prepared=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,change:{id:'d1',version:'v1',diff:{before:rows,after:[rows[1],rows[0]]},submission:{state:'not-submitted'}}})};}
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();await findButton(h.elements.page,'读取详情图分组').click();await settle();
  const move=walk(h.elements.page).filter(node=>node.tagName==='BUTTON' && node.textContent==='整组前移');await move[1].click();
  await findButton(h.elements.page,'生成详情图调整方案').click();await settle();
  assert.deepEqual(prepared,{product_id:'123',order:[2,1]});assert.match(h.elements.page.textContent,/详情图调整方案/);
});

test('详情图可选择商品素材准备替换，不自动提交',async()=>{
  const h=harness('#/object/product%3A1'),original=h.originalFetch;h.objects[0].links=[{label:'Alibaba 123',url:'https://example.com/product'}];let prepared;
  const rows=[{image_url:'https://example.com/a.jpg',image_set:{name:'Detail shot'}}];
  h.interceptFetch(async(path,options={})=>{
    if(String(path).startsWith('/api/desk/product-review'))return {ok:true,json:async()=>({listings:[{id:'123'}],selected:{id:'123',state:'ready',local:{},platform:{title:'Live',main_images:[],detail_images:rows.map(row=>({url:row.image_url})),company_images:[]},comparison:{}}})};
    if(String(path).startsWith('/api/desk/product-details-diagnosis'))return {ok:true,json:async()=>({ok:true,change:{platform:{detail_images:rows},detailGroups:[{roleName:'Detail shot',slots:[1]}]}})};
    if(path==='/api/product-detail-plans/prepare'){prepared=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,change:{id:'dp1',version:'v1',state:'prepared',before:rows,previews:[{previewRef:'商品图.jpg'}]}})};}
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();await findButton(h.elements.page,'读取可替换的详情图').click();await settle();
  await findButton(h.elements.page,'替换图片').click();await walk(h.elements.page).find(node=>node.tagName==='BUTTON' && node.textContent==='真实主图').click();
  await findButton(h.elements.page,'生成详情图替换方案').click();await settle();
  assert.deepEqual(prepared,{product_id:'123',slots:[{path:'商品图.jpg'}]});assert.match(h.elements.page.textContent,/详情图替换方案/);
});

for(const mode of ['gallery-order','gallery-replace','detail-order','detail-replace']) {
  for(const outcome of ['submitted','business_rejected','outcome_unknown',...(mode.endsWith('replace')?['uploaded_submission_blocked','uploaded_preparation_failed','upload_outcome_unknown']:[])]) {
    test(`${mode}提交反馈以平台实际结果为准：${outcome}`,async()=>{
      const h=harness('#/object/product%3A1'),original=h.originalFetch;
      h.objects[0].links=[{label:'Alibaba 123',url:'https://example.com/product'}];
      const urls=Array.from({length:6},(_,i)=>`https://sc04.alicdn.com/kf/${i}.jpg`);
      const rows=[{image_url:urls[0],image_set:{name:'Detail shot'}}];
      const local=mode.endsWith('replace'), detail=mode.startsWith('detail');
      const endpoint=detail?(local?'product-detail-plans':'product-detail-changes'):(local?'product-gallery-plans':'product-gallery-changes');
      let change=local?{id:'review1',version:'v1',productId:'123',createdAt:'2026-11-03',state:'prepared',before:detail?rows:urls,previews:[{previewRef:'商品图.jpg'}]}:{id:'review1',version:'v1',productId:'123',createdAt:'2026-11-03',state:'prepared',diff:{before:detail?rows:urls,after:detail?rows:urls},submission:{state:'not-submitted'}};
      let writes=0;
      h.interceptFetch(async(path,options={})=>{
        if(String(path).startsWith('/api/desk/product-review'))return {ok:true,json:async()=>({listings:[{id:'123'}],selected:{id:'123',state:'ready',local:{},platform:{title:'Live',main_images:urls.map(url=>({url})),detail_images:rows.map(row=>({url:row.image_url})),company_images:[]},comparison:{}}})};
        if(path===`/api/${endpoint}`)return {ok:true,json:async()=>({changes:[change]})};
        if(path==='/api/product-gallery-plans' || path==='/api/product-gallery-changes')return {ok:true,json:async()=>({changes:[]})};
        if(path===`/api/${endpoint}/review1/${local?'submit':'apply'}`){
          writes++;
          const submitted={state:outcome,submission:{state:outcome==='business_rejected'?'business-rejected':outcome==='outcome_unknown'?'outcome-unknown':'submitted'}};
          change={...change,state:outcome,version:'v2',...(local?{changeId:'formal1',submissionResult:outcome==='uploaded_submission_blocked'?{ok:false,error:{code:'PLATFORM_VERSION_CONFLICT'}}:{ok:true,change:submitted}}:{submission:submitted.submission})};
          return {ok:true,json:async()=>({ok:true,change})};
        }
        if(path===`/api/${endpoint}/review1/reconcile`){
          const formal={state:'formal_pending',submission:{state:'submitted'},formal:{state:'pending',status:'approved'},localSync:{state:'not-synced'}};
          change={...change,...(local?{state:'formal_pending',formalResult:{ok:true,change:formal}}:formal)};
          return {ok:true,json:async()=>({ok:true,change})};
        }
        return original(path,options);
      });
      await h.ui.bootstrap();await settle();
      await findButton(h.elements.page,detail?(local?'查看已有详情图替换方案':'查看已有详情图方案'):'查看已有主图方案').click();await settle();
      await walk(h.elements.page).find(node=>node.tagName==='BUTTON' && node.textContent.startsWith('查看 ') && node.textContent.endsWith(' 的方案')).click();
      await findButton(h.elements.page,detail?(local?'确认提交详情图替换':'确认提交详情图顺序'):'确认提交主图方案').click();await settle();
      assert.equal(writes,1);
      if(outcome==='submitted'){
        assert.match(h.elements.page.textContent,/已提交，请回读平台结果/);
        await findButton(h.elements.page,detail?(local?'回读详情图替换结果':'回读详情图结果'):'回读平台和本地结果').click();await settle();
        assert.match(h.elements.page.textContent,local?/正式结果尚未核对通过/:/平台：待核对/);
        assert.doesNotMatch(h.elements.page.textContent,/审核中|平台已回读并同步本地/);
      }
      else {
        assert.doesNotMatch(h.elements.page.textContent,/已提交，请回读平台结果/);
        const expected={business_rejected:/平台未受理商品修改/,outcome_unknown:/提交结果未知/,uploaded_submission_blocked:/商品提交未完成/,uploaded_preparation_failed:/商品方案未准备完成/,upload_outcome_unknown:/图片上传结果待核对/};
        assert.match(h.elements.page.textContent,expected[outcome]);
      }
    });
  }
}

test('客户商机可记录报价并保存下一步', async () => {
  const h=harness('#/object/customer%3Adeal'),original=h.originalFetch;
  h.objects.push({id:'customer:deal',kind:'customer',title:'测试客户',assets:[]});let saved;
  const commercial={object_id:'customer:deal',revision:'v1',records:[],owner:'',next_action:'',labels:{kinds:{quotation:'报价'},statuses:{draft:'内部准备'}}};
  h.interceptFetch(async(path,options={})=>{
    if(String(path).startsWith('/api/desk/customer-commercial')){if(options.body){saved=JSON.parse(options.body);commercial.records=[saved.record];commercial.next_action=saved.next_action;}return {ok:true,json:async()=>structuredClone(commercial)};}
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();await findButton(h.elements.page,'添加报价、样品或订单').click();
  const find=label=>walk(h.elements.page).find(node=>node['aria-label']===label);
  find('当前情况').value='客户需要确认混码报价';find('接下来做什么').value='确认颜色和尺码';
  await findButton(h.elements.page,'保存记录').click();await settle();
  assert.equal(saved.record.kind,'quotation');assert.equal(saved.record.summary,'客户需要确认混码报价');assert.equal(saved.next_action,'确认颜色和尺码');assert.match(h.elements.page.textContent,/客户需要确认混码报价/);
});

test('title draft selects only existing evidence and prepares without submission', async () => {
  const h=harness('#/object/product%3A1');
  h.objects[0].links=[{label:'Alibaba 123',url:'https://example.com/product'}];
  h.objects[0].content=JSON.stringify({selected_evidence_paths:['facts.md','../private.md','.local/secret.md',42]});
  const original=h.originalFetch;let prepared=0;
  h.interceptFetch(async(path,options)=>{
    if(String(path)==='/api/product-changes/prepare'){
      const body=JSON.parse(options.body);assert.deepEqual(body,{product_id:'123',proposed_title:'Verified Casual Shoes',rationale:'Verified source',evidence:['facts.md']});prepared++;
      return {ok:true,json:async()=>({ok:true,change:{id:'draft1',version:'version1',submission:{state:'not-submitted'},diff:{before:'Old title',after:body.proposed_title}}})};
    }
    if(String(path).endsWith('/draft1/apply')) {assert.deepEqual(JSON.parse(options.body),{confirmed:true,expected_version:'version1'});return {ok:true,json:async()=>({ok:false,error:{code:'CLIENT_OR_STORAGE_FAILURE'}})};}
    if(String(path).endsWith('/draft1/reconcile'))return {ok:true,json:async()=>({ok:true,change:{id:'draft1',version:'version2',submission:{state:'outcome-unknown'},formal:{state:'verified'},localSync:{state:'synced'},diff:{before:'Old title',after:'Verified Casual Shoes'}}})};
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();
  const nodes=walk(h.elements.page),byLabel=label=>nodes.find(x=>x['aria-label']===label);
  byLabel('选择国际站商品链接').value='123';byLabel('拟修改英文标题').value='Verified Casual Shoes';byLabel('修改理由').value='Verified source';
  assert.equal(byLabel('../private.md'),undefined);assert.equal(byLabel('.local/secret.md'),undefined);
  await findButton(h.elements.page,'准备修改草稿').click();assert.equal(prepared,0);
  byLabel('facts.md').checked=true;await findButton(h.elements.page,'准备修改草稿').click();await settle();
  assert.equal(prepared,1);assert.ok(h.elements.page.textContent.includes('修改前：Old title'));assert.ok(h.elements.page.textContent.includes('尚未提交'));
  await findButton(h.elements.page,'审核通过，提交此标题').click();await settle();
  assert.equal(findButton(h.elements.page,'审核通过，提交此标题').disabled,true);
  assert.ok(h.elements.page.textContent.includes('勿重复提交'));
  await findButton(h.elements.page,'读回审核与同步状态').click();await settle();
  assert.ok(h.elements.page.textContent.includes('已同步'));
  assert.equal(findButton(h.elements.page,'审核通过，提交此标题').disabled,true);
});
test('website conversation uses persisted Chinese and polling preserves unsent reply', async () => {
 const h=harness('#/object/customer%3Awebsite-test');
 h.objects.push({id:'customer:website-test',kind:'customer',title:'买家',assets:[],conversation:[{sender:'buyer',body:'Fallback original'}]});
 h.profile.conversation=[{message_id:'m1',sender:'buyer',body:'What is MOQ?',translation_zh:'起订量多少？'},{message_id:'m2',sender:'seller',body:'Choose a style.',translation_zh:''}];
 await h.ui.bootstrap();await settle();
 const page=h.elements.page;
 assert.ok(page.textContent.includes('起订量多少？'));assert.ok(page.textContent.includes('What is MOQ?'));assert.ok(page.textContent.includes('尚无中文对照'));
 assert.equal(page.textContent.includes('Fallback original'),false);
 const reply=walk(page).find(x=>x['aria-label']==='网站私信回复');reply.value='Unsent draft';
 await h.ui.poll();await settle();
 assert.equal(walk(page).find(x=>x['aria-label']==='网站私信回复'),reply);assert.equal(reply.value,'Unsent draft');
});

test('旧8765入口只检查静态资源并保留路径查询和路由，失败时保留明确链接', async () => {
  for (const available of [true, false]) {
    const body = new Element('body'), calls = [], redirects = [];
    const location = { port: '8765', href: 'http://127.0.0.1:8765/desk?view=work#/products?q=shoe', replace: url => redirects.push(url) };
    vm.runInNewContext(fs.readFileSync(new URL('./web/desk.js', import.meta.url), 'utf8'), {
      document: { body, createElement: tag => new Element(tag) }, location, URL, AbortController, setTimeout, clearTimeout,
      fetch: async (url, options) => { calls.push({ url, options }); if (!available) throw new Error('offline'); return {}; }
    });
    await settle();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, 'http://127.0.0.1:8766/desk.js');
    assert.equal(calls[0].options.method, 'HEAD');
    assert.equal(calls[0].options.credentials, 'omit');
    const target = 'http://127.0.0.1:8766/desk?view=work#/products?q=shoe';
    assert.equal(body.querySelector('a').href, target);
    assert.match(body.textContent, /旧工作台入口/);
    assert.deepEqual(redirects, available ? [target] : []);
    if (!available) assert.match(body.textContent, /双击“启动工作台”/);
  }
});

// 2026-11-01 新增：首页「今天」按"谁做主"分组渲染，判断一律来自后端，前端不自造结论。
test('首页今天区块按分组渲染后端给出的判断与动作', async () => {
  const h = harness();
  h.setToday({ groups: { decide: [{ id: 'd1', kind: 'customer_overdue', group: 'decide', title: 'HTV 已超期', judgment: '已超过自定时限，需要你决定继续还是改期。', action: { label: '打开并调整时限', type: 'open_object', object_id: 'customer:1' }, evidence: [{ label: '原定时限', value: '2026-10-01' }], severity: 'high' }], act: [{ id: 'a1', kind: 'customer_reply', group: 'act', title: '客户有新回复', judgment: '往来原文已在客户页。', action: { label: '让 Sol 起草', type: 'agent', object_id: 'customer:2', instruction: '读取最新往来并准备回复草稿；不自动发送。' }, evidence: [], severity: 'normal' }], watch: [] }, counts: { decide: 1, act: 1, watch: 0 }, labels: { decide: '等你拍板', act: '今天能推', watch: '在跑，不用动手' } });
  await h.ui.bootstrap(); await settle();
  const today = h.elements.page.querySelector('.overview-today');
  assert.ok(today, '今天区块应存在');
  assert.ok(today.textContent.includes('等你拍板'));
  assert.ok(today.textContent.includes('HTV 已超期'));
  assert.ok(today.textContent.includes('已超过自定时限'));
  // 依据默认折叠在 details 里，不应占据首屏文本主干之外
  assert.ok(today.querySelector('.today-evidence').textContent.includes('原定时限'));
  assert.ok(today.textContent.includes('今天能推'));
});

test('今天区块的旧 Agent 动作改为打开相关记录，不启动任务', async () => {
  const h = harness();
  h.setToday({ groups: { decide: [], act: [{ id: 'a1', kind: 'customer_reply', group: 'act', title: '客户有新回复', judgment: '判断', action: { label: '让 Sol 起草', type: 'agent', object_id: 'customer:2', instruction: '读取最新往来；不自动发送。' }, evidence: [] }], watch: [] }, counts: { decide: 0, act: 1, watch: 0 }, labels: { decide: '等你拍板', act: '今天能推', watch: '在跑' } });
  await h.ui.bootstrap(); await settle();
  const today = h.elements.page.querySelector('.overview-today');
  await findButton(today, '查看相关记录').click(); await settle();
  const started = h.requests.find(item => item.path === '/api/desk/jobs');
  assert.equal(started, undefined);assert.ok(h.location.hash.includes('customer%3A2'));
});

test('今天没有待办时给出明确空态，而不是空白', async () => {
  const h = harness(); await h.ui.bootstrap(); await settle();
  const today = h.elements.page.querySelector('.overview-today');
  assert.ok(today.textContent.includes('今天没有需要你处理的事'));
});

test('首页客户新来信直达该客户记录', async () => {
  const h = harness();
  h.setToday({groups:{decide:[],act:[{title:'买家有新来信',judgment:'发件人：buyer@example.org',action:{label:'查看客户',type:'open_object',object_id:'prospect:candidate:abc'}}],watch:[]},counts:{decide:0,act:1,watch:0},labels:{act:'待处理'}});
  await h.ui.bootstrap(); await settle();
  await findButton(h.elements.page.querySelector('.overview-today'),'查看客户').click();
  assert.equal(h.location.hash,'/customers?view=development&item=candidate%3Aabc');
});

test('首页网站询盘数量使用实际读取结果', async () => {
  const h = harness(); h.setWebsite({state:'ready',observed_at:'2026-11-02T01:00:00Z',total:1});
  h.objects.push({id:'customer:website-x',kind:'customer',source_type:'website',title:'买家'});
  await h.ui.bootstrap(); await settle();
  assert.ok(h.elements.page.textContent.includes('已读取 1 条询盘'));
});

test('商品页按资料缺口排序，并保留退回全部商品的出口', async () => {
  const h = harness('#/products?view=gaps');
  h.setProductGaps({ total: 2, with_gaps: 1, blocked: 1, counts: { no_source: 1 }, items: [{ object_id: 'product:1', title: '缺资料的款', gap_keys: ['no_source'], severity: 'high' }], checked: ['no_source'], unavailable: { no_price: '需打开单款' }, labels: {} });
  h.objects.push({ id: 'product:2', kind: 'product', title: '资料齐全的款', assets: [{}], supply: { kind: 'own', label: '自有工厂' }, source_role: 'adopted', links: [] });
  await h.ui.bootstrap(); await settle();
  assert.ok(h.elements.page.textContent.includes('1 款待补充资料'));
  assert.ok(findButton(h.elements.page, '查看全部商品 →'));
  // 缺口视图应只留缺资料的款；资料齐全的不该出现在这里。
  assert.equal(h.elements.page.textContent.includes('资料齐全的款'), false);
});

test('渠道页显示可用渠道，暂不接入的渠道不制造空入口', async () => {
  const h = harness('#/channels'); const original = h.originalFetch;
  h.interceptFetch(async (path, options) => String(path).startsWith('/api/desk/channels') ? { ok: true, json: async () => ({ channels: [{ id: 'alibaba', title: '国际站', data: {}, gaps: ['询盘与报价未验证接通'] }, { id: 'douyin', title: '抖店', connection: {state:'not_integrated'}, data: { available: false }, gaps: ['成交、流量和售后指标未接通'] }, { id: 'another', title: '其他已接入渠道', connection: {state:'ready'}, data:{scope:'经营数据'} }] }) } : original(path, options));
  await h.ui.bootstrap(); await settle();
  const text = h.elements.page.textContent;
  assert.ok(text.includes('国际站'));
  assert.equal(text.includes('抖店'), false);
  assert.ok(text.includes('其他已接入渠道'));
  assert.ok(text.includes('未接通的能力 1 项'));
  assert.ok(text.includes('询盘与报价未验证接通'));
});
test('独立站搜索数据连接入口及真实读取结果展示',async()=>{
  const h=harness('#/channels'),original=h.originalFetch;let state={state:'not_connected',available:false};
  h.interceptFetch(async(path,options={})=>{
    if(path==='/api/desk/channels')return {ok:true,json:async()=>({channels:[{id:'website',title:'独立站',connection:{total:0},data:{}}]})};
    if(path==='/api/desk/search-console')return {ok:true,json:async()=>structuredClone(state)};
    if(path==='/api/desk/search-console/oauth/start')return {ok:true,json:async()=>({authorization_url:'https://accounts.google.com/o/oauth2/v2/auth?state=test'})};
    if(path==='/api/desk/search-console/refresh')return {ok:true,json:async()=>({state:'ready',available:true,site_url:'https://www.beiqiang.online/',period:{start:'2026-10-01',end:'2026-10-28'},tables:{totals:[{impressions:100,clicks:5,ctr:0.05}],queries:[{keys:['walking shoes'],impressions:30,clicks:2}]}})};
    return original(path,options);
  });
  await h.ui.bootstrap();await settle();await findButton(h.elements.page,'连接 Google 搜索数据').click();
  assert.ok(walk(h.elements.page).some(node=>node.tagName==='A' && node.textContent.includes('继续 Google 登录并授权')));
  state={state:'ready',site_url:'https://www.beiqiang.online/',available:true,tables:{totals:[]},period:{}};await h.ui.renderRoute();await settle();
  await findButton(h.elements.page,'更新搜索数据').click();await settle();
  assert.match(h.elements.page.textContent,/展示 100 · 点击 5/);assert.match(h.elements.page.textContent,/walking shoes/);
});
test('渠道经营分析保留历史期和空数据，筛选重点行动并进入精确关联商品', async () => {
  const h=harness('#/channels');
  h.interceptFetch(async(path,options)=>path==='/api/desk/channels'?{ok:true,json:async()=>({channels:[{id:'alibaba',title:'国际站',data:{},product_analysis:{available:true,period:'2026-10-11~2026-10-17',notice:'历史统计，不代表当前表现',total:2,items:[
    {listing_id:'11',model:'BQ001',action:'已有咨询，改善有效采购承接',object_id:'product:BQ001',association:'matched',metrics:{inquiries:0}},
    {listing_id:'12',model:'BQ001',action:'换款与统计窗口重叠，先按新鞋核对',association:'unmatched',metrics:{}}
  ]}}]})}:h.originalFetch(path,options));
  await h.ui.bootstrap();await settle();
  assert.match(h.elements.page.textContent,/历史统计期：2026-10-11~2026-10-17/);
  assert.match(h.elements.page.textContent,/不代表当前表现/);
  assert.match(h.elements.page.textContent,/询盘 0/);
  assert.match(h.elements.page.textContent,/搜索曝光 无报表数据/);
  assert.match(h.elements.page.textContent,/此历史链接尚未关联当前商品/);
  const filter=h.elements.page.querySelector('select');filter.value='已有咨询，改善有效采购承接';filter.listeners.change();
  assert.doesNotMatch(h.elements.page.textContent,/链接 12/);
  await findButton(h.elements.page,'查看当前商品与平台链接').click();
  assert.equal(h.location.hash,'/object/product%3ABQ001?listing=11');
  assert.equal(h.requests.some(row=>row.payload),false);
});

test('同行清单展示真实店铺，登记买家进入原客户研究并保留关联', async () => {
  const h = harness('#/customers?view=competitors');
  h.interceptFetch(async (path, options) => path === '/api/desk/competitors' ? {ok:true,json:async()=>({items:[{id:'EX001',company:'Shoe Factory',direction:'休闲鞋',store_url:'https://shoe.en.alibaba.com/',identity:{name:'鞋业有限公司',credit_code:'123456789012345678',source_url:'https://example.com/company'},sales:{note:'单款 224 sold，周期不明',source_url:'https://www.alibaba.com/picks/shoes.html'},buyers:[{id:'candidate:old',company:'Known Buyer'}]}],excluded:[{company:'Old Shop',note:'店铺打开未确认',buyers:[]}],existing_buyers:[{id:'candidate:old',company:'Known Buyer'}]})} : h.originalFetch(path, options));
  await h.ui.bootstrap(); await settle();
  assert.match(h.elements.page.textContent,/鞋业有限公司/); assert.doesNotMatch(h.elements.page.textContent,/Old Shop|另外 1 家暂未列入/);
  assert.ok(walk(h.elements.page).some(node => node.tagName === 'A' && node.href === 'https://shoe.en.alibaba.com/'));
  assert.match(h.elements.page.textContent,/统一社会信用代码：123456789012345678/);
  assert.ok(walk(h.elements.page).some(node => node.tagName === 'A' && node.href === 'https://example.com/company'));
  const search=walk(h.elements.page).find(node=>node['aria-label']==='搜索同行');
  search.value='123456789012345678'; search.listeners.input(); assert.match(h.elements.page.textContent,/鞋业有限公司/);
  search.value='不存在的公司'; search.listeners.input(); assert.doesNotMatch(h.elements.page.textContent,/鞋业有限公司/);
  search.value=''; search.listeners.input();
  await findButton(h.elements.page,'复制公司名').click(); assert.equal(h.clipboard(),'鞋业有限公司');
  await findButton(h.elements.page,'复制信用代码').click(); assert.equal(h.clipboard(),'123456789012345678');
  await findButton(h.elements.page,'登记买家').click(); const dialog=walk(h.body).find(node=>node.tagName==='DIALOG');
  walk(dialog).find(node=>node['aria-label']==='买家公司名称').value='New Buyer';
  walk(dialog).find(node=>node['aria-label']==='国家或市场（选填）').value='US';
  walk(dialog).find(node=>node['aria-label']==='线索说明（选填）').value='数据库记录，鞋类';
  await findButton(dialog,'保存并查看客户').click();
  const created=h.requests.find(row=>row.path==='/api/desk/discovery' && row.payload);
  assert.equal(created.payload.company,'New Buyer'); assert.deepEqual(created.payload.related_competitors,['EX001']);
  assert.match(h.location.hash,/customers\?view=development&item=/); assert.equal(h.requests.some(row=>/send|outreach/.test(row.path)),false);
});

test('复制海关查询名单时包含公司全称及代码，不混入未查明的店铺名', async () => {
  const h = harness('#/customers?view=competitors');
  h.interceptFetch(async (path, options) => path === '/api/desk/competitors' ? {ok:true,json:async()=>({items:[
    {id:'EX001',company:'Shoe Factory',direction:'鞋',store_url:'https://shoe.en.alibaba.com/',identity:{name:'鞋业有限公司',credit_code:'91350200065858374U',source_url:'https://example.com/company'},buyers:[]},
    {id:'EX002',company:'Other Shoe Co., Ltd.',direction:'鞋',store_url:'https://other.en.alibaba.com/',buyers:[]},
    {id:'EX003',company:'Third Shoes',direction:'鞋',store_url:'https://third.en.alibaba.com/',identity:{name:'第三鞋业有限公司',source_url:'https://example.com/third'},buyers:[]}
  ],excluded:[{company:'Old Shop'}],existing_buyers:[]})} : h.originalFetch(path, options));
  await h.ui.bootstrap(); await settle();
  assert.match(h.elements.page.textContent,/2 家有公司全称 · 1 家未查到/);
  const copy = findButton(h.elements.page, '复制公司及信用代码');
  await copy.click(); assert.equal(h.clipboard(), '鞋业有限公司\t91350200065858374U\n第三鞋业有限公司\t信用代码未查到');
  await findButton(h.elements.page, '只复制公司名').click(); assert.equal(h.clipboard(), '鞋业有限公司\n第三鞋业有限公司');
  const search=walk(h.elements.page).find(node=>node['aria-label']==='搜索同行'); search.value='91350200065858374U'; search.listeners.input();
  await copy.click(); assert.equal(h.clipboard(), '鞋业有限公司\t91350200065858374U');
});

test('同行登记遇到已有公司时打开原客户，不重复建立', async () => {
  const h = harness('#/customers?view=competitors');
  h.interceptFetch(async (path, options) => path === '/api/desk/competitors' ? {ok:true,json:async()=>({items:[{id:'EX001',company:'Shoe Factory',direction:'鞋',store_url:'https://shoe.en.alibaba.com/',buyers:[]}],excluded:[],existing_buyers:[{id:'candidate:old',company:'Known Buyer'}]})} : h.originalFetch(path, options));
  await h.ui.bootstrap(); await settle(); await findButton(h.elements.page,'登记买家').click();
  const dialog=walk(h.body).find(node=>node.tagName==='DIALOG'); walk(dialog).find(node=>node['aria-label']==='买家公司名称').value=' known buyer ';
  await findButton(dialog,'保存并查看客户').click(); assert.equal(h.requests.some(row=>row.path==='/api/desk/discovery' && row.payload),false);
  await findButton(dialog,'打开已有客户').click(); assert.match(h.location.hash,/candidate%3Aold/);
});
