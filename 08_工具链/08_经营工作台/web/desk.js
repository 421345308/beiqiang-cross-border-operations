'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => { const value = document.createElement(tag); if (text !== undefined) value.textContent = text; if (cls) value.className = cls; return value; };
  const S = { token: '', objects: [], jobs: [], artifacts: [], goals: {}, route: '', page: 'overview', object: null, detail: null, edits: new Map(), pending: false, loadSerial: 0, pollBusy: false, websiteStatus: {}, listRefresh: null, lastBootstrapPoll: 0, instructions: new Map(), selectedArtifacts: new Map() };
  const statusNames = { queued: '等待开始', running: '正在处理', completed: '已形成成果', needs_input: '待补充依据', failed: '未能完成', cancelled: '已停止' };
  const text = value => value === null || value === undefined ? '' : typeof value === 'object' ? Array.isArray(value) ? value.map(text).join(' · ') : Object.values(value).map(text).filter(Boolean).join(' · ') : String(value);
  const time = value => { if (!value) return '时间未提供'; const stamp = new Date(value); return Number.isNaN(stamp.getTime()) ? text(value) : stamp.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }); };
  const button = (label, action, cls) => { const item = el('button', label, cls); item.type = 'button'; item.addEventListener('click', () => Promise.resolve(action()).catch(error => message(error.message))); return item; };
  const link = (label, url) => { const href = safeUrl(url); if (!href) return null; const item = el('a', label); item.href = href; item.target = '_blank'; item.rel = 'noopener noreferrer'; return item; };
  function safeUrl(value) { if (typeof value !== 'string' || !value.trim()) return null; try { const url = new URL(value, location.origin); return url.protocol === 'https:' || (url.origin === location.origin && url.protocol === 'http:') ? url.href : null; } catch { return null; } }
  const imageAsset = item => item?.kind === 'image' || [item?.path, item?.url].some(value => typeof value === 'string' && /\.(?:jpe?g|png|webp|gif|avif|bmp)(?:$|[?#])/i.test(value));
  const firstImage = object => (object.assets || []).find(asset => imageAsset(asset) && safeUrl(asset.url));
  const isActive = job => ['queued', 'running'].includes(job.status);
  const objectKind = object => object.kind === 'product' ? '商品' : '客户';
  const objectById = id => S.objects.find(item => String(item.id) === String(id));
  const jobsFor = id => S.jobs.filter(job => String(job.object_id) === String(id)).sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  const badge = status => el('span', statusNames[status] || '状态待确认', `status ${status || ''}`);
  function message(value = '') { $('desk-notice').textContent = value; $('desk-notice').hidden = !value; }
  let toastTimer;
  function toast(value) { $('save-indicator').textContent = value; $('save-indicator').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('save-indicator').hidden = true; }, 4500); }
  async function api(path, body) {
    const response = await fetch(path, body === undefined ? { cache: 'no-store' } : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workbench-Token': S.token }, body: JSON.stringify(body) }); let value;
    try { value = await response.json(); } catch { throw new Error('暂时无法读取服务结果，请稍后重新读取。'); }
    if (!response.ok || value.ok === false) throw new Error(typeof value.error === 'string' ? value.error.slice(0, 400) : value.error?.message || '这次操作未完成，请稍后再试。');
    return value;
  }
  const array = (value, key) => Array.isArray(value) ? value : value?.[key] || [];
  const objectResult = value => value.object || value;
  const jobResult = value => value.job || value;
  const artifactResult = value => value.artifact || value;
  function sectionHeading(title, note) { const row = el('div', undefined, 'section-title'); row.append(el('h2', title)); if (note) row.append(el('span', note)); return row; }
  function heading(eyebrow, title, description) { const wrap = el('div', undefined, 'page-heading'), content = el('div'); content.append(el('span', eyebrow, 'eyebrow'), el('h1', title)); if (description) content.append(el('p', description)); wrap.append(content); return wrap; }
  function empty(root, description) { root.append(el('div', description, 'empty')); }
  function goObject(id) { location.hash = `/object/${encodeURIComponent(id)}`; }
  function remember(id) { try { const prior = JSON.parse(localStorage.getItem('bq-desk-recent') || '[]').map(value => typeof value === 'string' ? { id: value, at: null } : value); localStorage.setItem('bq-desk-recent', JSON.stringify([{ id, at: new Date().toISOString() }, ...prior.filter(value => value.id !== id)].slice(0, 12))); } catch { /* Recent links are optional. */ } }
  function recentObjects() {
    let ids = []; try { ids = JSON.parse(localStorage.getItem('bq-desk-recent') || '[]').map(value => typeof value === 'string' ? value : value.id); } catch { /* Use only actual jobs if local history is unavailable. */ }
    const jobs = [...S.jobs].sort((a, b) => String(b.updated_at || b.created_at || '').localeCompare(String(a.updated_at || a.created_at || ''))); const seen = new Set();
    return [...ids, ...jobs.map(job => job.object_id)].map(objectById).filter(object => { if (!object || seen.has(object.id)) return false; seen.add(object.id); return true; }).slice(0, 6);
  }
  function businessEntrances() {
    const grid = el('div', undefined, 'business-entrances'), products = S.objects.filter(item => item.kind === 'product').length, customers = S.objects.filter(item => item.kind === 'customer').length, website = S.objects.filter(item => item.kind === 'customer' && (text(item.source).startsWith('website:') || text(item.subtitle).includes('网站询盘'))).length;
    for (const [title, note, hash] of [['商品', `已接入 ${products} 份商品资料 · 查资料、选素材、整理选款`, '/products'], ['客户', `已关联 ${customers} 份客户与需求记录 · 看背景、准备下一步`, '/customers'], ['网站询盘', S.websiteStatus.observed_at ? `已取得 ${website} 条询盘 · 打开原需求继续处理` : '询盘仍在读取中，完成后自动出现', '/customers?q=%E7%BD%91%E7%AB%99%E8%AF%A2%E7%9B%98']]) { const card = el('article', undefined, 'card business-entry'); card.append(el('h2', title), el('p', note), button('打开 →', () => { location.hash = hash; }, 'quiet')); grid.append(card); }
    return grid;
  }
  function image(asset, cls) { const src = safeUrl(asset?.url); if (!src) return null; const img = el('img', undefined, cls); img.src = src; img.alt = text(asset.label || '实际商品图片'); img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.addEventListener('error', () => img.remove()); return img; }
  function tile(object) {
    const card = el('article', undefined, 'card object-tile'), asset = firstImage(object); if (asset) card.append(image(asset, 'tile-image'));
    card.append(el('span', objectKind(object), 'object-type'), el('h3', text(object.title), 'object-title'), el('p', object.kind === 'product' ? /[\u4e00-\u9fff]/.test(text(object.summary)) ? text(object.summary) : '查看商品资料、关联素材与选款成果' : text(object.subtitle || object.summary)), button(object.kind === 'product' ? '查看商品 →' : '继续处理 →', () => goObject(object.id), 'quiet open-object')); return card;
  }
  function workRow(job) {
    const row = el('article', undefined, 'card work-row'), info = el('div'), object = objectById(job.object_id); info.append(el('h3', text(job.title || object?.title || '一项工作')), el('p', `${object?.title || '关联资料'} · ${time(job.updated_at || job.created_at)}`));
    const right = el('div'); right.append(badge(job.status), button('打开', () => goObject(job.object_id), 'quiet')); row.append(info, right); return row;
  }
  function artifactRow(artifact) {
    const row = el('article', undefined, 'card work-row'), info = el('div'); info.append(el('h3', text(artifact.title || '工作成果')), el('p', `${objectById(artifact.object_id)?.title || '关联资料'} · ${time(artifact.updated_at)}`)); row.append(info, button('查看成果 →', () => { location.hash = `/object/${encodeURIComponent(artifact.object_id)}?artifact=${encodeURIComponent(artifact.id)}`; }, 'quiet')); return row;
  }
  function websiteText() {
    const value = S.websiteStatus || {}, stamp = value.observed_at ? ` · 上次读取 ${time(value.observed_at)}` : '';
    if (['loading', 'refreshing', 'pending'].includes(value.state)) return `网站询盘正在读取，完成后会自动出现${stamp}`;
    if (['error', 'failed', 'stale'].includes(value.state)) return `网站询盘暂未更新，保留已取得资料${stamp}`;
    if (value.observed_at) return `网站询盘已读取${stamp}`;
    return '网站询盘尚未完成读取，不代表没有新需求。';
  }
  function websiteLabel() { return el('p', websiteText(), 'website-status'); }
  function updateWebsiteLabels() { document.querySelectorAll('.website-status').forEach(item => { item.textContent = websiteText(); }); }
  function renderOverview() {
    const page = $('page'), goalsOpen = page.querySelector('.goals')?.open; page.replaceChildren(heading('YOUR WORKSPACE', '今天，从这里继续', '找到正在推进的事，把下一步交给 Sol，成果留在原处。'));
    page.append(websiteLabel());
    const goals = Object.entries(S.goals || {}).filter(([, value]) => text(value)); if (goals.length) { const details = el('details', undefined, 'card goals'); details.open = !!goalsOpen; details.append(el('summary', '当前方向与重点')); for (const [key, value] of goals) details.append(el('div', `${({ long_term: '长期方向', phase: '当前阶段', focus: '当前重点', priorities: '优先事项', notes: '补充要求' }[key] || '当前要求')}：${text(value)}`)); page.append(details); }
    page.append(sectionHeading('从业务开始', '进入真实对象，而非工具菜单'), businessEntrances()); const recentRows = recentObjects(); if (recentRows.length) { page.append(sectionHeading('继续工作', '近期打开或实际处理过的对象')); const recent = el('div', undefined, 'continue-grid'); recentRows.forEach(object => recent.append(tile(object))); page.append(recent); }
    const columns = el('div', undefined, 'overview-grid'), active = el('section'), artifacts = el('section'); active.append(sectionHeading('正在推进', '实际执行状态')); const jobs = el('div', undefined, 'row-list'); const running = S.jobs.filter(isActive); running.forEach(job => jobs.append(workRow(job))); if (!running.length) empty(jobs, '当前没有执行中的工作。打开一款商品或一位客户，说明这次需要什么。'); active.append(jobs); artifacts.append(sectionHeading('最近成果', '打开后可继续编辑')); const list = el('div', undefined, 'row-list'); [...S.artifacts].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''))).slice(0, 5).forEach(item => list.append(artifactRow(item))); if (!list.children.length) empty(list, '新的选款资料、回复草稿会保存在这里，并关联原商品或客户。'); artifacts.append(list); columns.append(active, artifacts); page.append(columns);
    const failed = S.jobs.filter(job => job.status === 'failed').slice(0, 3); if (failed.length) { page.append(sectionHeading('需要留意', '未完成的工作')); const rows = el('div', undefined, 'row-list'); failed.forEach(job => rows.append(workRow(job))); page.append(rows); }
  }
  function parseRoute() { const raw = location.hash.replace(/^#\/?/, '') || 'overview', split = raw.indexOf('?'); return { parts: (split < 0 ? raw : raw.slice(0, split)).split('/'), query: new URLSearchParams(split < 0 ? '' : raw.slice(split + 1)) }; }
  function setNav(page) { const name = ({ overview: '总览', products: '商品', customers: '客户', library: '资料' })[page] || '详情'; $('page-name').textContent = name; document.querySelectorAll('[data-nav]').forEach(item => item.classList.toggle('active', item.dataset.nav === page)); }
  async function renderRoute() {
    const serial = ++S.loadSerial, route = parseRoute(), requestedHash = location.hash; const routeIsCurrent = () => serial === S.loadSerial && location.hash === requestedHash; message(); S.route = location.hash; S.detail = null; S.object = null; S.listRefresh = null; const kind = route.parts[0];
    if (kind === 'object') {
      S.page = 'object'; setNav('overview'); $('page').replaceChildren(el('div', '正在打开这份资料…', 'loading-state'));
      try { const id = decodeURIComponent(route.parts.slice(1).join('/')), object = objectResult(await api(`/api/desk/object?id=${encodeURIComponent(id)}`)); if (!routeIsCurrent()) return; if (!object || String(object.id) !== String(id) || (id.startsWith('product:') && object.kind !== 'product') || (id.startsWith('customer:') && object.kind !== 'customer')) throw new Error('返回资料与所选对象不一致，未打开。请重新选择。'); S.object = object; remember(object.id); const index = S.objects.findIndex(item => item.id === object.id); if (index < 0) S.objects.push(object); else S.objects[index] = object; setNav(object.kind === 'product' ? 'products' : 'customers'); $('page-name').textContent = object.title; renderObject(object, route.query.get('artifact')); }
      catch (error) { if (routeIsCurrent()) { $('page').replaceChildren(el('div', error.message, 'empty')); message(error.message); } }
      return;
    }
    S.page = ['products', 'customers', 'library'].includes(kind) ? kind : 'overview'; setNav(S.page); if (S.page === 'overview') renderOverview(); else renderSearchPage(S.page, route.query.get('q') || '');
  }
  function renderSearchPage(kind, query) {
    const listRouteSerial = S.loadSerial; const listIsCurrent = () => listRouteSerial === S.loadSerial && parseRoute().parts[0] === kind;
    const page = $('page'), labels = { products: ['PRODUCTS', '商品', '从真实产品、规格与素材出发，整理可以直接使用的选款资料。'], customers: ['CUSTOMERS', '客户', '需求、来源与准备中的回复，放在同一处继续。'], library: ['FIND YOUR MATERIAL', '资料', '跨商品与客户查找原文、图片和已有资料，不搬动原文件。'] };
    page.replaceChildren(heading(...labels[kind])); if (kind === 'customers' || kind === 'library') page.append(websiteLabel()); const input = el('input', undefined, 'search-input'); input.type = 'search'; input.value = query; input.placeholder = kind === 'products' ? '搜索款号、名称或商品信息' : kind === 'customers' ? '搜索客户、需求或来源' : '搜索商品、客户与关联资料'; input.setAttribute('aria-label', '搜索资料'); const count = el('span', '', 'search-count'), list = el('div', undefined, kind === 'products' ? 'product-grid' : kind === 'library' ? 'library-grid' : 'row-list'); const search = el('div', undefined, 'search-bar'); search.append(input, count); page.append(search, list); let timer, searchSerial = 0;
    async function find(value) { const sequence = ++searchSerial; count.textContent = '正在查找…'; try { const endpointKind = kind === 'products' ? 'product' : kind === 'customers' ? 'customer' : ''; const result = await api(`/api/desk/objects?q=${encodeURIComponent(value)}&kind=${endpointKind}`); if (sequence !== searchSerial || S.page !== kind || !listIsCurrent()) return; const rows = array(result, 'objects'); list.replaceChildren(); count.textContent = `${rows.length} 项结果`;
        for (const object of rows) {
          if (kind === 'products') list.append(tile(object));
          else if (kind === 'customers') { const row = el('article', undefined, 'card customer-row'), content = el('div'); content.append(el('h3', text(object.title), 'object-title'), el('p', text(object.subtitle || object.summary)), el('div', text(object.source), 'source-label')); row.append(el('div', text(object.title).slice(0, 1) || '客', 'customer-avatar'), content, button('打开客户 →', () => goObject(object.id), 'quiet')); list.append(row); }
          else { const row = el('article', undefined, 'card library-row'); row.append(el('span', objectKind(object), 'eyebrow'), el('h3', text(object.title), 'object-title'), el('p', text(object.summary || object.subtitle)), el('p', text(object.source)), button('打开关联资料 →', () => goObject(object.id), 'quiet')); const names = (object.assets || []).map(asset => asset.label || asset.path).filter(Boolean); if (names.length) row.append(el('p', `关联素材：${names.slice(0, 4).join(' · ')}`)); list.append(row); }
        }
        if (!rows.length) empty(list, value ? '没有找到匹配资料。换个名称、款号或需求关键词再试。' : kind === 'customers' && !S.websiteStatus?.observed_at ? websiteText() : '当前没有可展示的这类资料。');
      } catch (error) { if (sequence === searchSerial && listIsCurrent()) { count.textContent = ''; list.replaceChildren(el('div', error.message, 'empty')); } }
    }
    input.addEventListener('input', () => { if (!listIsCurrent()) return; clearTimeout(timer); const value = input.value; history.replaceState(null, '', `#/${kind}${value ? `?q=${encodeURIComponent(value)}` : ''}`); timer = setTimeout(() => find(value), 250); }); S.listRefresh = () => find(input.value); find(query);
  }
  function summaryFacts(object) {
    const all = object.facts || []; if (object.kind !== 'product') return { shown: all.slice(0, 6), more: all.slice(6) };
    const hide = /共用.*ID|别名|原始资料包|原包路径|已采纳供应来源|历史参考来源|Alibaba|渠道|平台|src[_-]/i;
    const priorities = [/^产品(?:名称|类型)?$/, /来源状态/, /^供应商$/, /供应商原款|原款/, /用途/, /参考价/, /原档已有规格|供货模式/]; const candidates = all.filter(item => !hide.test(text(item.label)));
    const shown = [];
    for (const rule of priorities) for (const item of candidates) if (rule.test(text(item.label)) && !shown.includes(item) && shown.length < 6) shown.push(item);
    for (const item of candidates) if (!shown.includes(item) && shown.length < 6) shown.push(item);
    return { shown, more: all.filter(item => !shown.includes(item)) };
  }
  function renderObject(object, requestedArtifact) {
    const page = $('page'), top = el('div', undefined, 'detail-top'), info = el('div'); info.append(el('span', objectKind(object), 'eyebrow'), el('h1', text(object.title))); if (object.subtitle) info.append(el('p', text(object.subtitle))); top.append(info, button('返回列表', () => { location.hash = object.kind === 'product' ? '/products' : '/customers'; }, 'quiet')); page.replaceChildren(top);
    const layout = el('div', undefined, 'object-layout'), main = el('div', undefined, 'object-main'), right = el('aside', undefined, 'card object-agent'); const hero = el('section', undefined, 'card detail-hero'), asset = firstImage(object), facts = el('div'); if (asset) hero.append(image(asset, 'hero-image')); else hero.style.gridTemplateColumns = '1fr'; facts.append(el('h2', object.kind === 'product' ? '商品资料' : '需求与背景')); if (object.summary) facts.append(el('p', text(object.summary), 'agent-copy')); const dl = el('dl', undefined, 'object-facts'); const factGroups = summaryFacts(object); for (const item of factGroups.shown) dl.append(el('dt', text(item.label)), el('dd', text(item.value) || '资料未提供')); facts.append(dl); if (factGroups.more.length || object.source) { const details = el('details', undefined, 'extra-facts'); details.append(el('summary', '更多档案与渠道信息')); const more = el('dl', undefined, 'object-facts'); for (const item of factGroups.more) more.append(el('dt', text(item.label)), el('dd', text(item.value) || '资料未提供')); details.append(more, el('div', `来源：${text(object.source) || '来源未提供'}`, 'object-source')); facts.append(details); } hero.append(facts); main.append(hero);
    if ((object.assets || []).length) {
      const materials = el('section', undefined, 'card'); materials.append(el('h2', object.kind === 'product' ? '图片与素材' : '需求资料')); const grid = el('div', undefined, 'asset-grid'); let expanded = false;
      function renderAssets() { grid.replaceChildren(); for (const item of object.assets.slice(0, expanded ? object.assets.length : 6)) { const row = el('div', undefined, 'asset-item'), src = safeUrl(item.url); if (imageAsset(item) && src) row.append(image(item, '')); row.append(el('div', text(item.label || item.path || '关联资料'), 'asset-label')); if (src) row.append(button('预览', () => previewAsset(item), 'quiet')); grid.append(row); } }
      materials.append(grid); if (object.assets.length > 6) { const toggle = button(`展开全部 ${object.assets.length} 份素材`, () => { expanded = !expanded; toggle.textContent = expanded ? '收起素材' : `展开全部 ${object.assets.length} 份素材`; renderAssets(); }, 'quiet asset-toggle'); materials.append(toggle); } renderAssets(); main.append(materials);
    }
    if (object.content) { const source = el('details', undefined, 'card object-source-details'); source.append(el('summary', object.kind === 'product' ? '查看原始资料' : '查看来源正文与完整需求'), el('pre', text(object.content), 'source-body')); main.append(source); }
    if ((object.links || []).length || (object.related || []).length) { const related = el('section', undefined, 'card'); related.append(el('h2', '关联与出处')); const links = el('div', undefined, 'related-links'); for (const item of object.links || []) { const a = link(item.label || '打开来源', item.url); if (a) links.append(a); } for (const item of object.related || []) { const id = typeof item === 'string' ? item : item.id || item.object_id; if (id) links.append(button(typeof item === 'string' ? objectById(id)?.title || '关联资料' : item.title || item.label || '关联资料', () => goObject(id))); } related.append(links); main.append(related); }
    const artifactSection = el('section', undefined, 'card'); artifactSection.append(el('h2', '工作成果')); const tabs = el('div', undefined, 'artifact-tabs'), editor = el('div'); artifactSection.append(el('p', '整理出的选款资料、回复草稿和补充内容都保存在这里，可继续编辑。', 'artifact-note'), tabs, editor); main.insertBefore(artifactSection, main.children[1] || null);
    const ctx = { object, right, tabs, editor, artifacts: [], selectedId: null, requestedArtifact, currentEdit: null }; S.detail = ctx; buildAgent(ctx); layout.append(main, right); page.append(layout); refreshArtifacts(ctx, true);
  }
  function previewAsset(asset) {
    const src = safeUrl(asset.url); if (!src) return; const dialog = el('dialog', undefined, 'desk-modal'), header = el('div', undefined, 'modal-head'); header.append(el('h2', text(asset.label || '关联素材')), button('关闭', () => dialog.close(), 'quiet')); dialog.append(header); const wrap = el('div', undefined, 'modal-media'); let media;
    const path = asset.path || asset.url; if (imageAsset(asset)) { media = el('img'); media.alt = text(asset.label || '实际素材'); }
    else if (/\.(?:mp4|mov|webm|m4v)(?:$|[?#])/i.test(path)) { media = el('video'); media.controls = true; media.playsInline = true; }
    else if (/\.(?:mp3|wav|ogg|flac|aac|m4a)(?:$|[?#])/i.test(path)) { media = el('audio'); media.controls = true; }
    if (media) { media.src = src; if (media.tagName !== 'IMG') media.preload = 'metadata'; media.addEventListener('error', () => { wrap.replaceChildren(el('p', '这份素材暂时无法预览，可重新读取后再试。')); }); wrap.append(media); } else { const a = link('在新窗口打开这份资料 ↗', src); if (a) wrap.append(a); }
    dialog.append(wrap); dialog.addEventListener('close', () => { if (media && typeof media.pause === 'function') { media.pause(); media.removeAttribute('src'); media.load(); } dialog.remove(); }); document.body.append(dialog); dialog.showModal();
  }
  function buildAgent(ctx) {
    const title = el('div', undefined, 'agent-heading'); title.append(el('h2', '一起推进'), el('span', 'Sol', 'agent-mark')); ctx.right.append(title, el('p', `已带入这${ctx.object.kind === 'product' ? '款商品' : '位客户'}的资料。说明你需要的结果，成果会回到当前页面。`, 'agent-copy'));
    const shortcuts = el('div', undefined, 'agent-shortcuts'), instruction = el('textarea', undefined, 'agent-instruction'); instruction.placeholder = ctx.object.kind === 'product' ? '例如：整理一份适合发给买家的选款资料，指出还缺哪些依据。' : '例如：根据客户原需求准备回复草稿，把需要确认的问题写清楚。'; instruction.setAttribute('aria-label', '交给 Sol 的要求'); instruction.value = S.instructions.get(String(ctx.object.id)) || ''; instruction.addEventListener('input', () => S.instructions.set(String(ctx.object.id), instruction.value));
    const choices = ctx.object.kind === 'product' ? [['整理选款资料', '请根据当前商品的真实资料与素材，整理一份可编辑的买家选款资料。区分已经确认的事实与待确认项，不新增未证实的材料、性能或商业承诺。'], ['找出资料缺口', '请检查当前商品资料，指出影响买家选款与报价的缺口，按重要性给出可以执行的下一步。']] : [['准备回复草稿', '请根据当前客户的原始需求和已有资料，准备一份可编辑的回复草稿。区分已知事实与待确认问题，不编造价格、供货能力或已执行动作。'], ['梳理下一步', '请梳理当前客户的明确需求、尚缺信息及下一步动作，形成可以继续编辑使用的工作记录。']]; for (const [label, value] of choices) shortcuts.append(button(label, () => { instruction.value = value; S.instructions.set(String(ctx.object.id), value); instruction.focus(); }));
    const feedback = el('div', '', 'agent-feedback'), submit = button('交给 Sol 处理', async () => {
      const value = instruction.value.trim(); if (!value) { feedback.textContent = '先写下这次希望得到什么结果。'; instruction.focus(); return; } submit.disabled = true; feedback.textContent = '正在启动这次工作…';
      try { const job = jobResult(await api('/api/desk/jobs', { object_id: ctx.object.id, instruction: value })); upsertJob(job); feedback.textContent = '工作已开始，结果会保存在当前对象下。你可以继续查看资料。'; renderJob(ctx); }
      catch (error) { feedback.textContent = error.message; feedback.classList.add('inline-error'); }
      finally { submit.disabled = jobsFor(ctx.object.id).some(isActive); }
    }, 'primary agent-submit'); const jobs = el('div'); ctx.right.append(shortcuts, instruction, submit, feedback, jobs); Object.assign(ctx, { instruction, feedback, submit, jobBox: jobs }); renderJob(ctx);
  }
  function upsertJob(job) { const index = S.jobs.findIndex(item => item.id === job.id); if (index < 0) S.jobs.unshift(job); else S.jobs[index] = job; }
  function renderJob(ctx) {
    const job = jobsFor(ctx.object.id)[0], logOpen = ctx.jobBox.querySelector('.job-events')?.open; ctx.submit.disabled = jobsFor(ctx.object.id).some(isActive); ctx.jobBox.replaceChildren(); if (!job) return; const panel = el('div', undefined, 'job-detail'); panel.append(el('h3', '这次工作'), el('p', text(job.instruction || job.title))); const actions = el('div', undefined, 'job-actions'); actions.append(badge(job.status)); if (isActive(job)) actions.append(button('停止', async () => { upsertJob(jobResult(await api('/api/desk/job/cancel', { id: job.id }))); renderJob(ctx); })); panel.append(actions); if (job.summary) panel.append(el('p', text(job.summary))); if (job.error) panel.append(el('p', text(job.error).slice(0, 400), 'inline-error')); if (job.artifact_id) panel.append(button('查看这次成果 →', () => selectArtifact(ctx, job.artifact_id), 'quiet'));
    if ((job.events || []).length) { const detail = el('details', undefined, 'job-events'); detail.open = !!logOpen; detail.append(el('summary', '查看处理记录')); const lines = (job.events || []).slice(-30).map(item => typeof item === 'string' ? item : ({ 'thread.started': '已建立执行会话', 'turn.started': '正在处理资料', 'turn.completed': '本轮处理结束', 'turn.failed': '本轮处理未完成' }[item.type] || item.text || item.message || '执行记录已更新')); detail.append(el('pre', lines.map(text).join('\n'))); panel.append(detail); } ctx.jobBox.append(panel);
  }
  function editKey(ctx, id) { return `${ctx.object.id}:${id || 'new'}`; }
  function showArtifactEditor(ctx, artifact) {
    const id = artifact?.id || null, key = editKey(ctx, id); let edit = S.edits.get(key);
    if (edit && !edit.dirty && artifact && edit.baseline !== artifact.updated_at) edit = null;
    if (!edit) { edit = { title: artifact?.title || '', content: artifact?.content || '', dirty: false, baseline: artifact?.updated_at || null }; S.edits.set(key, edit); }
    ctx.selectedId = id; if (id) ctx.userPickedNew = false; S.selectedArtifacts.set(String(ctx.object.id), id); ctx.currentEdit = edit; ctx.editor.replaceChildren(); const title = el('input', undefined, 'artifact-title'); title.value = edit.title; title.placeholder = '成果标题'; title.setAttribute('aria-label', '成果标题'); const content = el('textarea', undefined, 'artifact-content'); content.value = edit.content; content.placeholder = 'Sol 的成果会出现在这里。你也可以直接整理和保存自己的内容。'; content.setAttribute('aria-label', '成果正文'); const caption = el('span', artifact ? `已保存 · ${time(artifact.updated_at)}` : '尚未保存', 'artifact-caption'), save = button('保存成果', async () => {
      if (!title.value.trim() && !content.value.trim()) { toast('先填写成果标题或正文。'); return; } save.disabled = true; const snapshot = { title: title.value, content: content.value };
      try { const saved = artifactResult(await api('/api/desk/artifacts', { object_id: ctx.object.id, title: title.value.trim() || '工作成果', content: content.value, ...(id ? { id } : {}) })); edit.baseline = saved.updated_at; if (edit.title === snapshot.title && edit.content === snapshot.content) edit.dirty = false; S.edits.set(editKey(ctx, saved.id), edit); ctx.selectedId = saved.id; if (!id) S.edits.delete(key); const index = ctx.artifacts.findIndex(item => item.id === saved.id); if (index < 0) ctx.artifacts.unshift(saved); else ctx.artifacts[index] = saved; const globalIndex = S.artifacts.findIndex(item => item.id === saved.id); if (globalIndex < 0) S.artifacts.unshift(saved); else S.artifacts[globalIndex] = saved; caption.textContent = edit.dirty ? '上一版已保存，新的编辑尚未保存' : `已保存到当前${ctx.object.kind === 'product' ? '商品' : '客户'} · ${time(saved.updated_at)}`; toast('成果已保存，可从原对象继续打开。'); renderArtifactTabs(ctx); if (!id) showArtifactEditor(ctx, saved); }
      catch (error) { toast(error.message); } finally { save.disabled = false; }
    }, 'primary');
    function update() { edit.title = title.value; edit.content = content.value; edit.dirty = true; caption.textContent = '有未保存的编辑'; } title.addEventListener('input', update); content.addEventListener('input', update);
    const modes = el('div', undefined, 'artifact-modes'), preview = el('div', undefined, 'artifact-preview'), read = button('阅读', () => setMode('preview')), write = button('编辑', () => setMode('edit'));
    function setMode(mode) { const reading = mode === 'preview'; title.hidden = reading; content.hidden = reading; save.hidden = reading; preview.hidden = !reading; read.classList.toggle('active', reading); write.classList.toggle('active', !reading); preview.replaceChildren(el('h3', title.value || '工作成果'), el('pre', content.value || '这份成果还没有正文。')); if (!reading) content.focus(); }
    modes.append(read, write); const footer = el('div', undefined, 'artifact-footer'); footer.append(caption, save); ctx.editor.append(modes, preview, title, content, footer, el('p', '保存的是这份工作成果；不会自动发送给客户或修改平台商品。', 'artifact-note')); setMode(artifact && !edit.dirty ? 'preview' : 'edit'); renderArtifactTabs(ctx);
  }
  function renderArtifactTabs(ctx) { ctx.tabs.replaceChildren(); for (const artifact of ctx.artifacts) ctx.tabs.append(button(text(artifact.title || '工作成果'), () => selectArtifact(ctx, artifact.id), ctx.selectedId === artifact.id ? 'active' : '')); ctx.tabs.append(button('＋ 新建笔记', () => { ctx.userPickedNew = true; showArtifactEditor(ctx, null); }, ctx.selectedId === null ? 'active' : '')); }
  function selectArtifact(ctx, id) { const artifact = ctx.artifacts.find(item => String(item.id) === String(id)); if (artifact) { showArtifactEditor(ctx, artifact); ctx.editor.scrollIntoView?.({ behavior: 'smooth', block: 'start' }); } else refreshArtifacts(ctx, true, id).then(() => ctx.editor.scrollIntoView?.({ behavior: 'smooth', block: 'start' })); }
  async function refreshArtifacts(ctx, initial = false, requested = null) {
    try { const result = await api(`/api/desk/artifacts?object_id=${encodeURIComponent(ctx.object.id)}`); if (S.detail !== ctx) return; ctx.artifacts = array(result, 'artifacts'); for (const artifact of ctx.artifacts) { const index = S.artifacts.findIndex(item => item.id === artifact.id); if (index < 0) S.artifacts.push(artifact); else S.artifacts[index] = artifact; }
      if (initial) {
        const explicit = requested || ctx.requestedArtifact, remembered = S.selectedArtifacts.get(String(ctx.object.id)), dirty = S.edits.get(editKey(ctx, remembered))?.dirty;
        const newestJob = jobsFor(ctx.object.id).find(job => job.artifact_id && ctx.artifacts.some(item => String(item.id) === String(job.artifact_id)));
        const target = explicit || (dirty ? remembered : newestJob?.artifact_id);
        const artifact = !explicit && dirty && remembered === null ? null : ctx.artifacts.find(item => String(item.id) === String(target)) || ctx.artifacts[0] || null;
        showArtifactEditor(ctx, artifact);
      }
      else { renderArtifactTabs(ctx); if (!ctx.selectedId && !ctx.userPickedNew && !ctx.currentEdit?.dirty && ctx.artifacts.length) showArtifactEditor(ctx, ctx.artifacts[0]); }
    } catch (error) { if (S.detail === ctx) message(error.message); }
  }
  async function bootstrap() { $('reload').disabled = true; try { const value = await api('/api/desk/bootstrap'); S.token = value.csrf_token || ''; S.objects = value.objects || []; S.jobs = value.jobs || []; S.artifacts = value.artifacts || []; S.goals = value.goals || {}; S.websiteStatus = value.website_status || {}; S.lastBootstrapPoll = Date.now(); $('connection').textContent = '本地工作台已连接'; await renderRoute(); } catch (error) { $('connection').textContent = '连接暂时中断'; message(error.message); if (!S.objects.length) $('page').replaceChildren(el('div', '还没有取得真实业务资料。请确认本地服务已启动，再点击重新读取。', 'empty')); } finally { $('reload').disabled = false; } }
  async function poll() {
    if (S.pollBusy || document.visibilityState === 'hidden' || !S.token) return; S.pollBusy = true;
    try {
      const value = await api('/api/desk/jobs'); const prior = JSON.stringify(S.jobs.map(job => [job.id, job.status, job.updated_at])); S.jobs = array(value, 'jobs'); const changed = JSON.stringify(S.jobs.map(job => [job.id, job.status, job.updated_at])) !== prior;
      let objectsChanged = false, dataChanged = false;
      if (Date.now() - S.lastBootstrapPoll >= 12000 || ['loading', 'refreshing', 'pending'].includes(S.websiteStatus.state)) {
        const result = await api('/api/desk/bootstrap'); S.lastBootstrapPoll = Date.now(); const old = JSON.stringify(S.objects); S.objects = result.objects || S.objects; objectsChanged = old !== JSON.stringify(S.objects); const priorArtifacts = JSON.stringify(S.artifacts.map(item => [item.id, item.updated_at])); S.artifacts = result.artifacts || S.artifacts; dataChanged = priorArtifacts !== JSON.stringify(S.artifacts.map(item => [item.id, item.updated_at])); S.websiteStatus = result.website_status || S.websiteStatus; if (result.csrf_token) S.token = result.csrf_token; updateWebsiteLabels();
      }
      if (S.detail) { const ctx = S.detail; if (changed) renderJob(ctx); if (changed || dataChanged || jobsFor(ctx.object.id).some(isActive)) await refreshArtifacts(ctx); }
      else if (S.page === 'overview' && (changed || objectsChanged || dataChanged)) renderOverview();
      else if (objectsChanged && S.listRefresh) await S.listRefresh();
      $('connection').textContent = '本地工作台已连接';
    } catch { $('connection').textContent = '连接中断 · 正在等待恢复'; } finally { S.pollBusy = false; }
  }
  async function refreshData() {
    $('reload').disabled = true;
    try { const result = await api('/api/desk/refresh', {}); S.websiteStatus = result.status || result.website_status || result; updateWebsiteLabels(); }
    catch (error) { message(error.message); }
    await bootstrap();
  }
  $('reload').addEventListener('click', refreshData); window.addEventListener('hashchange', renderRoute); window.addEventListener('beforeunload', event => { if ([...S.edits.values()].some(edit => edit.dirty)) { event.preventDefault(); event.returnValue = ''; } }); bootstrap(); setInterval(poll, 4000);
})();
