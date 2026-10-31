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
  const local = new Map(), location = { hash, origin: 'http://127.0.0.1:8765' };
  const context = { console, URL, URLSearchParams, Date, JSON, Math, Map, Set, location, localStorage: { getItem: key => local.get(key) || null, setItem: (key, value) => local.set(key, value) }, history: { replaceState: (_s, _t, next) => { location.hash = next; } }, setTimeout: () => 1, clearTimeout() {}, setInterval() {}, window: { addEventListener() {} }, document: { body, visibilityState: 'visible', createElement: tag => new Element(tag), getElementById: id => elements[id], querySelectorAll: selector => selector === '[data-nav]' ? nav : body.querySelectorAll(selector) } };
  context.fetch = async (path, options = {}) => {
    const url = new URL(path, location.origin), payload = options.body ? JSON.parse(options.body) : null; requests.push({ path, options, payload }); let value;
    if (url.pathname === '/api/desk/bootstrap') value = { csrf_token: 'fixture-token', objects, jobs, artifacts, website_status: web, goals: { phase: '当前经营阶段' } };
    else if (url.pathname === '/api/desk/inquiry-queue') value = {items:objects.filter(item => item.kind === 'customer' && item.source_type !== 'alibaba_order_buyer' && (item.bucket || 'active') === url.searchParams.get('bucket')).map(item => ({object_id:item.id,title:item.title,analysis:{core_need:item.summary},workflow:{state:'new',priority:item.priority || 'normal',...item.workflow}}))};
    else if (url.pathname === '/api/desk/customer-workflow') { Object.assign(profile.workflow, payload); value = profile.workflow; }
    else if (url.pathname === '/api/desk/objects') value = { objects: objects.filter(item => !url.searchParams.get('kind') || item.kind === url.searchParams.get('kind')) };
    else if (url.pathname === '/api/desk/object') value = objects.find(item => item.id === url.searchParams.get('id'));
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
    else if (url.pathname === '/api/desk/refresh') { web = { state: 'loading' }; value = { status: web }; }
    else throw new Error(`Unexpected API ${path}`);
    return { ok: true, json: async () => structuredClone(value) };
  };
  const source = fs.readFileSync(new URL('./web/desk.js', import.meta.url), 'utf8'); assert.doesNotMatch(source, /\.innerHTML\s*=/);
  vm.createContext(context); vm.runInContext(source.replace('bootstrap(); setInterval(poll, 4000);', 'window.__desk = { S, bootstrap, renderRoute, poll, refreshData, safeUrl, imageAsset };'), context);
  return { ui: context.window.__desk, elements, body, objects, artifacts, jobs, requests, location, profile, discovery, setWebsite: value => { web = value; }, originalFetch: context.fetch, interceptFetch: callback => { context.fetch = callback; } };
}

test('real data drives navigation and original content is collapsed; untrusted titles stay text', async () => {
  const h = harness('#/products'); await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('真实商品')); assert.equal(walk(h.body).some(item => item.tagName === 'SCRIPT'), false);
  h.location.hash = '#/object/product%3A1'; await h.ui.renderRoute(); await settle(); assert.equal(h.elements.page.querySelector('.object-source-details'), null); assert.equal(h.ui.safeUrl('javascript:alert(1)'), null); assert.equal(h.ui.imageAsset({ path: 'real.jpg', url: '/api/asset?id=1' }), true);
});

test('job carries current object/token, text events render, and polling preserves instruction and unsaved artifact', async () => {
  const h = harness('#/object/product%3A1'); await h.ui.bootstrap(); await settle(); const ctx = h.ui.S.detail;
  ctx.instruction.value = '根据真实材料整理选款'; ctx.instruction.listeners.input({}); await findButton(h.body, '交给 Sol 处理').click(); const call = h.requests.find(item => item.path === '/api/desk/jobs' && item.payload); assert.equal(call.payload.object_id, 'product:1'); assert.equal(call.options.headers['X-Workbench-Token'], 'fixture-token'); assert.ok(ctx.jobBox.textContent.includes('已取得资料'));
  const title = ctx.editor.querySelector('input'), editor = ctx.editor.querySelector('textarea'); title.value = '自己修改的标题'; title.listeners.input({}); editor.value = '自己未保存的正文'; editor.listeners.input({});
  h.jobs[0].status = 'completed'; h.jobs[0].updated_at = '2026-10-31T04:00:00Z'; h.artifacts.push({ id: 'new-result', object_id: 'product:1', title: '新成果', content: '模型新输出', updated_at: '2026-10-31T04:00:00Z' }); await h.ui.poll();
  assert.equal(ctx.editor.querySelector('textarea'), editor); assert.equal(editor.value, '自己未保存的正文'); assert.equal(ctx.instruction.value, '根据真实材料整理选款'); await findButton(ctx.editor, '保存成果').click(); const save = h.requests.find(item => item.path === '/api/desk/artifacts' && item.payload); assert.equal(save.payload.id, 'a1'); assert.equal(save.payload.content, '自己未保存的正文');
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

test('成果 sits before a large gallery and only six assets display until expanded', async () => {
  const h = harness('#/object/product%3A1'); h.objects[0].assets = Array.from({ length: 29 }, (_, i) => ({ path: `real-${i}.jpg`, label: `原素材 ${i}`, url: `/api/media/file?path=real-${i}.jpg` })); await h.ui.bootstrap(); await settle();
  const main = h.elements.page.querySelector('.object-main'); assert.ok(main.children[1].textContent.startsWith('工作成果')); const grid = main.querySelector('.asset-grid'); assert.equal(grid.children.length, 6); await findButton(main, '展开全部 29 份素材').click(); assert.equal(grid.children.length, 29); await findButton(main, '收起素材').click(); assert.equal(grid.children.length, 6);
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
  const hero = h.elements.page.querySelector('.detail-hero'), visible = hero.querySelector('.object-facts'), extra = hero.querySelector('.extra-facts'); assert.equal(visible.querySelectorAll('dt').length, 6); assert.equal(visible.textContent.includes('internal-id'), false); assert.equal(visible.textContent.includes('Long platform title'), false); assert.equal(extra, null);
});

test('default artifact follows latest actual job, explicit artifact wins, and saved work opens in read mode', async () => {
  const h = harness('#/object/product%3A1'); h.artifacts[0].updated_at = '2026-11-02T00:00:00Z'; h.artifacts.push({ id: 'latest-work', object_id: 'product:1', title: '最新真实成果', content: '最新工作正文', updated_at: '2026-10-31T02:00:00Z' });
  h.jobs.push({ id: 'old', object_id: 'product:1', status: 'needs_input', artifact_id: 'a1', created_at: '2026-10-30T00:00:00Z' }, { id: 'latest', object_id: 'product:1', status: 'completed', artifact_id: 'latest-work', created_at: '2026-10-31T00:00:00Z' });
  await h.ui.bootstrap(); await settle(); assert.equal(h.ui.S.detail.selectedId, 'latest-work'); assert.ok(h.ui.S.detail.editor.querySelector('.artifact-preview').textContent.includes('最新工作正文')); assert.equal(h.ui.S.detail.editor.querySelector('textarea').hidden, true); await findButton(h.ui.S.detail.editor, '编辑').click(); assert.equal(h.ui.S.detail.editor.querySelector('textarea').hidden, false);
  h.location.hash = '#/object/product%3A1?artifact=a1'; await h.ui.renderRoute(); await settle(); assert.equal(h.ui.S.detail.selectedId, 'a1');
});

test('customer analysis preserves original, displays Chinese profile, and submits structured analysis mode', async () => {
  const h = harness('#/object/customer%3Arecord'); h.objects.push({ id: 'customer:record', kind: 'customer', title: '来源记录', subtitle: '网站询盘', source: 'website:record', assets: [], content: 'Please send sample information.' }); await h.ui.bootstrap(); await settle(); const ctx = h.ui.S.detail;
  assert.ok(ctx.profileHost.textContent.includes('请提供样品信息')); assert.ok(ctx.profileHost.textContent.includes('Please send sample information.')); assert.ok(ctx.profileHost.textContent.includes('询盘简报')); assert.equal(ctx.profileHost.textContent.includes('真实询盘'), false);
  await findButton(ctx.profileHost, '翻译并分析原始需求').click(); const jobCall = h.requests.find(item => item.path === '/api/desk/jobs' && item.payload); assert.equal(jobCall.payload.mode, 'customer_analysis'); assert.equal(jobCall.payload.object_id, 'customer:record');
  h.profile.translation_zh = '新的完整中文译文'; h.jobs[0].status = 'completed'; h.jobs[0].updated_at = '2026-10-31T09:00:00Z'; h.jobs[0].profile_saved = true; h.jobs[0].artifact_id = null; await h.ui.poll(); await settle(); assert.ok(ctx.profileHost.textContent.includes('新的完整中文译文')); assert.equal(h.artifacts.length, 1);
  await findButton(ctx.profileHost, '编辑解读与分析').click(); const edit = ctx.profileHost.querySelector('textarea'); edit.value = '人工尚未保存的中文解释'; h.jobs[0].updated_at = '2026-10-31T10:00:00Z'; await h.ui.poll(); await settle(); assert.equal(ctx.profileHost.querySelector('textarea'), edit); assert.equal(edit.value, '人工尚未保存的中文解释');
  await findButton(ctx.profileHost, '保存中文解读与分析').click(); const save = h.requests.find(item => item.path === '/api/desk/customer-profile' && item.payload); assert.equal(save.payload.source_hash, 'hash-1'); assert.equal(save.payload.translation_zh, '人工尚未保存的中文解释'); assert.equal(Object.hasOwn(save.payload, 'original_text'), false);
});

test('analysis creates a linked research task with evidence and never sends outreach', async () => {
  const h = harness('#/object/customer%3Arecord'); h.objects.push({ id: 'customer:record', kind: 'customer', title: '当前需求', source: 'website:record', assets: [] }); await h.ui.bootstrap(); await settle(); await findButton(h.ui.S.detail.profileHost, '把缺口或下一步转为研究任务').click(); const dialog = walk(h.body).find(item => item.tagName === 'DIALOG'); await findButton(dialog, '保存研究任务并打开').click(); const created = h.requests.find(item => item.path === '/api/desk/discovery' && item.payload); assert.equal(created.payload.origin_object_id, 'customer:record'); assert.equal(created.payload.kind, 'research_task'); assert.ok(created.payload.evidence.length); assert.ok(h.location.hash.includes('view=development')); assert.equal(h.requests.some(item => /send|outreach/.test(item.path)), false);
});

test('development exposes real candidate evidence, research context, and a non-outreach preparation marker', async () => {
  const h = harness('#/customers?view=development'); h.discovery.candidates.push({ id: 'candidate:source', object_id: 'prospect:candidate:source', kind: 'candidate', title: '已有来源候选', company: '候选公司', target: '需要核实供货适配', evidence: [{ url: 'https://example.com/', text: '原候选公开来源' }] }); await h.ui.bootstrap(); await settle(); assert.ok(h.elements.page.textContent.includes('目标客群')); const row = walk(h.elements.page).find(item => item.tagName === 'ARTICLE' && item.textContent.includes('已有来源候选')); await findButton(row, '打开继续 →').click(); await settle(); assert.ok(h.elements.page.textContent.includes('原候选公开来源')); assert.ok(h.ui.S.detail.instruction.value.includes('research_company'));
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
  const h = harness('#/customers?view=development&item=research%3Alinked'); h.discovery.tasks.push({ id: 'research:linked', object_id: 'prospect:research:linked', kind: 'research_task', title: '改善承接', target: '优化定制开发询盘承接', origin_object_id: 'customer:record', evidence: [] }); await h.ui.bootstrap(); await settle(); assert.equal(h.elements.page.querySelector('.discovery-target').hidden, true); assert.ok(h.ui.S.detail.instruction.value.includes('优化定制开发询盘承接')); assert.ok(h.ui.S.detail.instruction.value.includes('customer:record')); assert.equal(h.ui.S.detail.instruction.value.includes('research_company'), false); assert.ok(findButton(h.elements.page, '← 返回客户开发列表'));
});


test('inquiry queue separates history, sorts priority, and shows workflow not raw archives', async () => {
 const h = harness('#/customers?view=inquiries'); h.objects.push({id:'customer:normal',kind:'customer',title:'普通待办',summary:'一双样品',priority:'normal'}, {id:'customer:high',kind:'customer',title:'优先待办',summary:'确认开发范围',priority:'high'}, {id:'customer:history',kind:'customer',title:'旧CRM复盘',bucket:'history'}); await h.ui.bootstrap(); await settle(); const rows = h.elements.page.querySelectorAll('.inquiry-row'); assert.equal(rows[0].textContent.includes('优先待办'),true); assert.equal(h.elements.page.textContent.includes('旧CRM复盘'),false); await findButton(h.elements.page,'历史复盘').click(); h.location.hash='#/customers?view=inquiries&bucket=history'; await h.ui.renderRoute(); await settle(); assert.ok(h.elements.page.textContent.includes('旧CRM复盘')); assert.equal(h.elements.page.textContent.includes('普通待办'),false);
});

test('customer detail prioritizes secretary brief, hides JSON and history, saves named workflow with token', async () => {
 const h = harness('#/object/customer%3Arecord'); h.objects.push({id:'customer:record',kind:'customer',title:'实际客户',content:'{"internal_schema":"never show"}',facts:[{label:'技术字段',value:'not in briefing'}],assets:[]}); Object.assign(h.profile.analysis,{brief:'先确认开发边界，再讨论样品',core_need:'开发专用鞋底',questions_now:['使用场景？','验收标准？','目标数量？','非当前问题'],recommended_reply:'先给现有能力及开发边界'}); h.profile.workflow={state:'preparing',priority:'high',next_action:'准备开发范围回复',allowed_transitions:[{state:'waiting_customer',label:'等客户'}]}; await h.ui.bootstrap(); await settle(); const page=h.elements.page,ctx=h.ui.S.detail; assert.ok(page.textContent.includes('先确认开发边界')); assert.equal(page.textContent.includes('internal_schema'),false); assert.equal(page.textContent.includes('非当前问题'),false); const history=walk(page).find(item=>item.tagName==='DETAILS'&&item.children[0]?.textContent==='历史草稿与处理记录'); assert.ok(history); assert.equal(Boolean(history.open),false); const editor=ctx.profileHost.querySelector('.workflow-editor'), next=walk(editor).find(item=>item['aria-label']==='下一动作'); next.value='等待客户补充使用场景'; await next.listeners.input(); await h.ui.poll(); await settle(); assert.equal(ctx.profileHost.querySelector('.workflow-editor'),editor); await findButton(editor,'保存推进安排').click(); const request=h.requests.find(item=>item.path==='/api/desk/customer-workflow'); assert.equal(request.payload.next_action,'等待客户补充使用场景'); assert.equal(request.options.headers['X-Workbench-Token'],'fixture-token');
});


test('brief keeps reception fit visible while context and source notes are folded', async () => {
 const h=harness('#/object/customer%3Arecord'); h.objects.push({id:'customer:record',kind:'customer',title:'客户',assets:[]}); Object.assign(h.profile.analysis,{brief:'先厘清开发边界',fit:'现有生产可承接，具体配方需按样品目标确认',recommended_reply:'可以先讨论样品目的与交付物。'}); h.profile.operator_context='数量来自表单必填，不代表确认订单'; h.profile.provenance.evidence_notes='来源说明'; h.profile.provenance.source_verification.note='来源说明'; await h.ui.bootstrap(); await settle(); const host=h.ui.S.detail.profileHost, brief=host.querySelector('.inquiry-brief'); assert.ok(brief.querySelector('.brief-fit').textContent.includes('现有生产可承接')); const context=brief.querySelector('.operator-context'); assert.equal(context.tagName,'DETAILS'); assert.equal(Boolean(context.open),false); const source=host.querySelector('.source-note'); assert.equal(source.tagName,'DETAILS'); assert.equal(Boolean(source.open),false); assert.equal(source.querySelectorAll('p').length,1); assert.ok(brief.querySelector('.brief-reply').textContent.includes('可以先讨论')); assert.equal(brief.querySelector('.brief-reply').tagName,'SECTION');
});
