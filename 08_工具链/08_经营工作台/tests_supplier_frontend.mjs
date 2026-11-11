import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.value = ''; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(item => item.textContent).join(''); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = []; this._text = ''; this.append(...items); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(key, value) { this[key] = value; }
}
const walk = root => [root, ...root.children.flatMap(walk)];
const settle = async () => { for (let i=0; i<5; i++) await new Promise(resolve => setImmediate(resolve)); };

function setup({deferTimers=false}={}) {
  const page = new Element('main'), requests = [], opened = [], timers = new Map(); let nextTimer=0;
  const context = {
    window: {}, location: {hash: ''}, URLSearchParams,
    setTimeout: callback => { const id=++nextTimer; if(deferTimers)timers.set(id,callback);else callback(); return id; },
    clearTimeout: id => timers.delete(id),
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(new URL('./web/supplier-index.js', import.meta.url), 'utf8'), context);
  const el = (tag, text, cls) => { const item = new Element(tag); if (text !== undefined) item.textContent = text; if (cls) item.className = cls; return item; };
  const button = (label, action, cls) => { const item = el('button', label, cls); item.addEventListener('click', action); return item; };
  const link = (label, url) => { if (!url) return null; const item = el('a', label); item.href = url; return item; };
  const supplier = {id:'s1', names:['7号仓库'], shop_url:'https://shop.example/', has_profile:true,
    profile:{product_directions:[{name:'高尔夫鞋',scope:'来源款',evidence:[{kind:'SUPPLIER_PRODUCT_PAGE',url:'https://shop.example/1'}]}], process_directions:[],
      factory_identity:{status:'SELF_CLAIMED_FACTORY',summary:'身份未独立核验',evidence:[{kind:'SUPPLIER_SELF_CLAIM'}]},
      customization:{status:'OWNER_REPORTED_SINGLE_CASE',summary:'一项需求',evidence:[{kind:'OWNER_REPORTED'}]},
      location:{city:'泉州',type:'店铺所在地',evidence:[]}, owner_interactions:[],open_questions:['核实条件']},
    sources:[{model:'8805',url:'https://shop.example/1',products:[{id:'BQ-1',role:'candidate',category_clues:['运动鞋'],source_state:'HOLD_SOURCE'}]}]};
  const options = {cities:['泉州'],identities:['SELF_CLAIMED_FACTORY'],customization_evidence:['OWNER_REPORTED']};
  async function api(path) { requests.push(String(path)); return {suppliers:[supplier],unassociated_sources:[],options}; }
  let refresh,activeApi=api;
  const args = {page, current:()=>true, api:(...values)=>activeApi(...values), goObject:id=>opened.push(id), setRefresh:fn=>{refresh=fn;}, el, button, link,
    heading:(_eyebrow,title,description)=>{const x=el('header',title);x.append(el('p',description));return x;},
    empty:(root,message)=>root.append(el('div',message))};
  return {page,requests,opened,args,render:()=>context.window.renderSupplierIndex(args),refresh:()=>refresh,setApi:fn=>{activeApi=fn;},
    pendingTimers:()=>timers.size, flushTimers:()=>{const callbacks=[...timers.values()];timers.clear();for(const callback of callbacks)callback();}};
}

function deferred() { let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject}; }
const resultFor = name => ({suppliers:[{id:'fixture',names:[name],has_profile:false,profile:{},sources:[]}],unassociated_sources:[],options:{}});

test('matching page renders evidence, source links and truthful relationships', async () => {
  const h = setup(); await h.render();
  assert.match(h.page.textContent,/7号仓库/);
  assert.match(h.page.textContent,/供应商自述为工厂/);
  assert.match(h.page.textContent,/负责人曾就一例沟通/);
  assert.match(h.page.textContent,/店铺所在地/);
  assert.match(h.page.textContent,/候选来源/);
  assert.match(h.page.textContent,/不代表当前库存或可供条件/);
  assert.ok(walk(h.page).some(node=>node.tagName==='A' && node.href==='https://shop.example/1'));
  const direction = walk(h.page).find(node=>node.tagName==='P' && node.textContent.includes('高尔夫鞋'));
  assert.ok(direction.children.some(node=>node.tagName==='A' && node.href==='https://shop.example/1'));
  assert.ok(walk(h.page).some(node=>node.tagName==='SUMMARY' && node.textContent==='查看依据'));
  walk(h.page).find(node=>node.tagName==='BUTTON' && node.textContent==='BQ-1').listeners.click();
  assert.deepEqual(h.opened,['product:BQ-1']);
  assert.equal(typeof h.refresh(),'function');
});

test('search and evidence filter send the exact requested values', async () => {
  const h = setup(); await h.render();
  const search = walk(h.page).find(node=>node['aria-label']==='搜索厂家或型号');
  search.value='七号'; search.listeners.input(); await settle();
  assert.equal(new URL(h.requests.at(-1),'http://localhost').searchParams.get('q'),'七号');
  const custom = walk(h.page).find(node=>node['aria-label']==='筛选定制证据');
  custom.value='OWNER_REPORTED'; await custom.listeners.change();
  const query = new URL(h.requests.at(-1),'http://localhost').searchParams;
  assert.equal(query.get('q'),'七号');
  assert.equal(query.get('customization_evidence'),'OWNER_REPORTED');
});

test('a late response cannot paint over a different page', async () => {
  const h = setup(); let resolve;
  h.args.api=()=>new Promise(done=>{resolve=done;});
  let active=true; h.args.current=()=>active;
  const pending=h.render(); active=false; h.page.replaceChildren(new Element('section'));
  resolve({suppliers:[{names:['must not render']}],unassociated_sources:[],options:{}});
  await pending; assert.doesNotMatch(h.page.textContent,/must not render/);
});

test('a missing supplier endpoint explains the workbench needs an orderly restart', async () => {
  const h = setup();
  h.args.api=async()=>{const error=new Error('接口不存在');error.status=404;throw error;};
  await h.render();
  assert.match(h.page.textContent,/服务版本尚未更新/);
  assert.match(h.page.textContent,/等待当前工作结束后重启/);
  assert.doesNotMatch(h.page.textContent,/接口不存在/);
});

test('other supplier errors retain their actual cause', async () => {
  const h = setup();
  h.args.api=async()=>{const error=new Error('本地业务文件读取失败');error.status=500;throw error;};
  await h.render();
  assert.match(h.page.textContent,/本地业务文件读取失败/);
  assert.doesNotMatch(h.page.textContent,/服务版本尚未更新/);
});

test('editing immediately clears old results and invalidates an in-flight response before debounce',async()=>{
  const h=setup({deferTimers:true});await h.render();assert.match(h.page.textContent,/7号仓库/);
  const stale=deferred(),fresh=deferred(),calls=[];
  h.setApi(path=>{calls.push(String(path));return calls.length===1?stale.promise:fresh.promise;});
  const previous=h.refresh()();
  const input=walk(h.page).find(node=>node['aria-label']==='搜索厂家或型号');input.value='新型号';input.listeners.input();
  assert.doesNotMatch(h.page.textContent,/7号仓库/);assert.match(h.page.textContent,/正在查找/);assert.equal(h.pendingTimers(),1);
  stale.resolve(resultFor('旧查询响应'));await previous;assert.doesNotMatch(h.page.textContent,/旧查询响应/);assert.equal(calls.length,1);
  h.flushTimers();assert.equal(calls.length,2);assert.equal(new URL(calls[1],'http://localhost').searchParams.get('q'),'新型号');
  fresh.resolve(resultFor('新查询结果'));await settle();assert.match(h.page.textContent,/新查询结果/);assert.doesNotMatch(h.page.textContent,/旧查询响应/);
});

test('clearing text and changing a selector cancels the pending debounce and uses current fields',async()=>{
  const h=setup({deferTimers:true});await h.render();const next=deferred(),calls=[];h.setApi(path=>{calls.push(String(path));return next.promise;});
  const input=walk(h.page).find(node=>node['aria-label']==='搜索厂家或型号'),identity=walk(h.page).find(node=>node['aria-label']==='筛选厂家身份');
  input.value='8805';input.listeners.input();input.value='';input.listeners.input();assert.equal(h.pendingTimers(),1);assert.doesNotMatch(h.page.textContent,/7号仓库/);
  identity.value='SELF_CLAIMED_FACTORY';const request=identity.listeners.change();assert.equal(h.pendingTimers(),0);h.flushTimers();assert.equal(calls.length,1);
  const params=new URL(calls[0],'http://localhost').searchParams;assert.equal(params.has('q'),false);assert.equal(params.get('identity'),'SELF_CLAIMED_FACTORY');
  next.resolve(resultFor('清空后的结果'));await request;assert.match(h.page.textContent,/清空后的结果/);
});

test('a later query wins even if an older request fails after the new response',async()=>{
  const h=setup({deferTimers:true});await h.render();const older=deferred(),newer=deferred(),calls=[];
  h.setApi(path=>{calls.push(String(path));return calls.length===1?older.promise:newer.promise;});
  const input=walk(h.page).find(node=>node['aria-label']==='搜索厂家或型号');input.value='旧词';input.listeners.input();h.flushTimers();
  input.value='新词';input.listeners.input();assert.doesNotMatch(h.page.textContent,/7号仓库/);h.flushTimers();assert.equal(calls.length,2);
  newer.resolve(resultFor('新词命中'));await settle();older.reject(new Error('旧请求失败'));await settle();
  assert.match(h.page.textContent,/新词命中/);assert.doesNotMatch(h.page.textContent,/旧请求失败/);
});

test('explicit refresh cancels pending debounce and searches the newest input once',async()=>{
  const h=setup({deferTimers:true});await h.render();const pending=deferred(),calls=[];h.setApi(path=>{calls.push(String(path));return pending.promise;});
  const input=walk(h.page).find(node=>node['aria-label']==='搜索厂家或型号');input.value='8805';input.listeners.input();assert.equal(h.pendingTimers(),1);
  const request=h.refresh()();assert.equal(h.pendingTimers(),0);h.flushTimers();assert.equal(calls.length,1);assert.equal(new URL(calls[0],'http://localhost').searchParams.get('q'),'8805');
  pending.resolve(resultFor('刷新后结果'));await request;assert.match(h.page.textContent,/刷新后结果/);
});


test('leaving the page before a debounce fires does not issue a request',async()=>{
  const h=setup({deferTimers:true});let active=true;h.args.current=()=>active;await h.render();
  const input=walk(h.page).find(node=>node.tagName==='INPUT');input.value='8805';input.listeners.input();
  assert.equal(h.pendingTimers(),1);active=false;h.flushTimers();await settle();assert.equal(h.requests.length,1);
});
