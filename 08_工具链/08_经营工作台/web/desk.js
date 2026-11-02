'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => { const value = document.createElement(tag); if (text !== undefined) value.textContent = text; if (cls) value.className = cls; return value; };
  // Only the retired port is special; future launch ports keep their own origin.
  if (location.port === '8765') {
    const destination = new URL(location.href);
    destination.port = '8766';
    const panel = el('section', undefined, 'empty');
    const status = el('p', '正在检查当前入口，连通后会自动前往。');
    const entrance = el('a', '打开当前工作台入口 →');
    entrance.href = destination.href;
    panel.append(el('h1', '这是旧工作台入口（8765）'), status, entrance);
    document.body.replaceChildren(panel);
    document.title = '旧入口 · 贝强工作台';
    const probe = new URL('/desk.js', destination);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    // Static asset only: never send cookies or read business data across ports.
    fetch(probe.href, { method: 'HEAD', mode: 'no-cors', credentials: 'omit', cache: 'no-store', signal: controller.signal })
      .then(() => { location.replace(destination.href); })
      .catch(() => { status.textContent = '工作台尚未连接，请双击“启动工作台”后重试。'; })
      .finally(() => clearTimeout(timeout));
    return;
  }
  const S = { token: '', objects: [], jobs: [], artifacts: [], goals: {}, route: '', page: 'overview', object: null, detail: null, edits: new Map(), pending: false, loadSerial: 0, pollBusy: false, websiteStatus: {}, alibabaStatus: {}, gmailRevision: 0, listRefresh: null, lastBootstrapPoll: 0, instructions: new Map(), selectedArtifacts: new Map() };
  const statusNames = { queued: '等待开始', running: '正在处理', completed: '已形成成果', needs_input: '待补充依据', failed: '未能完成', cancelled: '已停止' };
  const text = value => value === null || value === undefined ? '' : typeof value === 'object' ? Array.isArray(value) ? value.map(text).join(' · ') : Object.values(value).map(text).filter(Boolean).join(' · ') : String(value);
  const valueLabels = { new: '待处理', unknown: '尚待核对', unverified: '待核实', not_checked: '尚未核对', RAW_PACKAGE: '已有原始资料', ADOPTED: '已采纳来源', HOLD_SOURCE: '来源待核实', external: '外采', factory: '工厂供货', reference_only: '仅作参考' };
  const displayText = value => valueLabels[text(value)] || text(value).replace(/网站询盘/g, '网站记录');
  function assetLabel(asset) { return text(asset.label || asset.path || '关联素材').split(/\s*\/\s*/).map(value => {
    const map = { 'Douyin color_files': '抖店颜色图', 'Douyin detail_files': '抖店详情图', 'Douyin main_files': '抖店主图', 'Website collar': '网站鞋口图', 'Website colour': '网站配色图', 'Website heel': '网站后跟图', 'Website on-foot': '网站上脚图', 'Website outsole': '网站鞋底图', 'Website overview': '网站概览图', 'Website pair': '网站双鞋图', 'Website side': '网站侧面图', 'Website top': '网站俯视图', 'Website upper': '网站鞋面图' };
    if (map[value]) return map[value]; if (/^Alibaba main (\d+)$/.test(value)) return value.replace(/^Alibaba main (\d+)$/, '国际站主图 $1'); if (/^Reviewed M(\d+)$/.test(value)) return value.replace(/^Reviewed M(\d+)$/, '整理主图 $1'); if (/^Reviewed D(\d+)$/.test(value)) return value.replace(/^Reviewed D(\d+)$/, '整理详情图 $1'); if (value.startsWith('Reviewed SKU_')) return '整理配色图'; return value;
  }).join(' · '); }
  const isWebsite = object => text(object.source).startsWith('website:') || /网站(?:询盘|记录)/.test(text(object.subtitle));
  const time = value => { if (!value) return '时间未提供'; const stamp = new Date(value); return Number.isNaN(stamp.getTime()) ? text(value) : stamp.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }); };
  const button = (label, action, cls) => { const item = el('button', label, cls); item.type = 'button'; item.addEventListener('click', () => Promise.resolve(action()).catch(error => message(error.message))); return item; };
  const link = (label, url) => { const href = safeUrl(url); if (!href) return null; const item = el('a', label); item.href = href; item.target = '_blank'; item.rel = 'noopener noreferrer'; return item; };
  function safeUrl(value) { if (typeof value !== 'string' || !value.trim()) return null; try { const url = new URL(value, location.origin); return url.protocol === 'https:' || (url.origin === location.origin && url.protocol === 'http:') ? url.href : null; } catch { return null; } }
  const imageAsset = item => item?.kind === 'image' || [item?.path, item?.url].some(value => typeof value === 'string' && /\.(?:jpe?g|png|webp|gif|avif|bmp)(?:$|[?#])/i.test(value));
  const firstImage = object => (object.assets || []).find(asset => imageAsset(asset) && safeUrl(asset.url));
  const isActive = job => ['queued', 'running'].includes(job.status);
  const objectKind = object => object.kind === 'product' ? '商品' : object.kind === 'creation' ? '创作项目' : object.kind === 'prospect' ? '开发研究' : '客户';
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
  function renderTitleReview(host,change,reason) {
    let attempted=change.submission?.state!=='not-submitted';
    const status=el('p'), feedback=el('p'), actions=el('div');
    host.replaceChildren(el('h3','标题修改草稿'),el('p',`平台商品：${change.productId || ''}`),el('p',`修改前：${change.diff?.before || ''}`),el('p',`拟修改：${change.diff?.after || ''}`),el('p',`修改理由：${change.rationale || reason || ''}`),el('p',`草稿编号：${change.id || ''}`),status,actions,feedback);
    const labels={'withdrawn':'已撤回','not-submitted':'尚未提交','outcome-unknown':'结果未知，请读回核对','submitted':'已提交','pending':'审核中','verified':'正式回读通过','synced':'已同步','not-synced':'未同步','not-verified':'未验收','conflict':'同步冲突'};
    const show=v=>labels[v] || v || '待核实';
    const update=()=>{status.textContent=`提交：${show(change.submission?.state)} · 正式审核：${show(change.formal?.state)} · 本地：${show(change.localSync?.state)} · 公开页面：${show(change.publicVerification?.state)}`;submit.disabled=attempted || !change.version || !change.id;read.disabled=!attempted || change.submission?.state==='withdrawn' || change.state==='withdrawn';submit.hidden=read.hidden=change.submission?.state==='withdrawn' || change.state==='withdrawn';};
    const submit=button('审核通过，提交此标题',async()=>{
      if(attempted)return;attempted=true;update();feedback.textContent='正在提交，请勿重复操作。';
      try {const value=await api(`/api/product-changes/${encodeURIComponent(change.id)}/apply`,{confirmed:true,expected_version:change.version});if(value.change)change=value.change;feedback.textContent=value.ok ? '已返回提交结果，请读回核对。' : '未确认提交结果，请读回核对，勿重复提交。';}
      catch {feedback.textContent='提交结果未知，请读回核对，勿重复提交。';}update();
    },'primary');
    const read=button('读回审核与同步状态',async()=>{read.disabled=true;try{const value=await api(`/api/product-changes/${encodeURIComponent(change.id)}/reconcile`,{});if(value.change)change=value.change;feedback.textContent=value.ok ? '已读取正式审核及本地同步结果。' : '暂未完成核对，请稍后再次读回。';}catch{feedback.textContent='读取失败，请稍后再次读回。';}update();},'quiet');
    actions.append(submit,read);update();
  }
  function titleDraftForm(box,object,select) {
    let paths=[]; try { const content=JSON.parse(object.content || '{}'); paths=Array.isArray(content.selected_evidence_paths) ? content.selected_evidence_paths : []; } catch {}
    paths=[...new Set(paths.filter(p=>typeof p==='string' && p && !p.includes('\\') && !p.startsWith('/') && !/^[A-Za-z]:/.test(p) && !p.split('/').some(x=>x==='..' || x.startsWith('.'))))];
    const form=el('section',undefined,'title-draft-form'), title=el('input'), reason=el('textarea'), evidence=el('div',undefined,'evidence-choices'), result=el('div',undefined,'title-review'), choices=[];
    title.setAttribute('aria-label','拟修改英文标题');title.placeholder='拟修改英文标题';reason.setAttribute('aria-label','修改理由');reason.placeholder='根据已核事实说明修改理由';
    form.append(el('h3','准备标题修改草稿'),el('p','仅准备可审阅草稿；平台与正式本地档案不会在此修改。'),title,reason,el('p','选择本商品已有证据：'),evidence);
    for(const path of paths) { const label=el('label'), check=el('input');check.type='checkbox';const name=path.split('/').slice(-2).join(' / ');check.setAttribute('aria-label',name);choices.push({check,path});label.append(check,el('span',name));evidence.append(label); }
    if(!paths.length)evidence.append(el('p','本商品尚无可选证据，请先补齐原档。'));
    const prepare=button('准备修改草稿',async()=>{
      const selected=choices.filter(x=>x.check.checked).map(x=>x.path);
      if(!title.value?.trim() || !reason.value?.trim() || !selected.length){result.replaceChildren(el('p','请填写英文标题、修改理由并选择已有证据。'));return;}
      if(!/^[\x20-\x7E]+$/.test(title.value.trim())){result.replaceChildren(el('p','请使用英文标题。'));return;}
      prepare.disabled=true;const pid=select.value;
      try { const value=await api('/api/product-changes/prepare',{product_id:pid,proposed_title:title.value.trim(),rationale:reason.value.trim(),evidence:selected});if(!value.ok)throw new Error('草稿未能准备，请核实证据、平台状态及标题。');const d=value.change;
        renderTitleReview(result,d,reason.value.trim());
      } catch(error){result.replaceChildren(el('p',error.message));} finally {prepare.disabled=false;}
    },'quiet');prepare.disabled=!paths.length;const saved=el('div'); const read=button('查看已有草稿',async()=>{try{const data=await api('/api/product-changes');const rows=(data.changes || []).filter(x=>String(x.productId)===String(select.value));saved.replaceChildren();for(const draft of rows) { const row=el('div'); row.append(el('p',`${draft.diff?.after || '标题草稿'} · ${draft.state === 'prepared' ? '待审核' : draft.state}`),button('打开审核',()=>renderTitleReview(result,draft,''),'quiet')); saved.append(row); }if(!rows.length)empty(saved,'此商品还没有标题草稿。');}catch(error){saved.replaceChildren(el('p',error.message));}},'quiet'); form.insertBefore(read,title);form.insertBefore(saved,title);form.insertBefore(result,title);form.append(prepare);box.append(form);
  }
  function sectionHeading(title, note) { const row = el('div', undefined, 'section-title'); row.append(el('h2', title)); if (note) row.append(el('span', note)); return row; }
  function heading(eyebrow, title, description) { const wrap = el('div', undefined, 'page-heading'), content = el('div'); content.append(el('span', eyebrow, 'eyebrow'), el('h1', title)); if (description) content.append(el('p', description)); wrap.append(content); return wrap; }
  function empty(root, description) { root.append(el('div', description, 'empty')); }
  function goObject(id, artifactId = '') {
    const value = String(id);
    let route = value.startsWith('creation:') ? `/creation?item=${encodeURIComponent(value)}` :
      value.startsWith('prospect:') ? `/customers?view=development&item=${encodeURIComponent(value.slice('prospect:'.length))}` : `/object/${encodeURIComponent(value)}`;
    if (artifactId) route += `${route.includes('?') ? '&' : '?'}artifact=${encodeURIComponent(artifactId)}`;
    location.hash = route;
  }
  function remember(id) { try { const prior = JSON.parse(localStorage.getItem('bq-desk-recent') || '[]').map(value => typeof value === 'string' ? { id: value, at: null } : value); localStorage.setItem('bq-desk-recent', JSON.stringify([{ id, at: new Date().toISOString() }, ...prior.filter(value => value.id !== id)].slice(0, 12))); } catch { /* Recent links are optional. */ } }
  function recentObjects() {
    let ids = []; try { ids = JSON.parse(localStorage.getItem('bq-desk-recent') || '[]').map(value => typeof value === 'string' ? value : value.id); } catch { /* Use only actual jobs if local history is unavailable. */ }
    const jobs = [...S.jobs].sort((a, b) => String(b.updated_at || b.created_at || '').localeCompare(String(a.updated_at || a.created_at || ''))); const seen = new Set();
    return [...ids, ...jobs.map(job => job.object_id)].map(objectById).filter(object => { if (!object || seen.has(object.id)) return false; seen.add(object.id); return true; }).slice(0, 6);
  }
  function businessEntrances() {
    const grid = el('div', undefined, 'business-entrances'), products = S.objects.filter(item => item.kind === 'product' && !/^HR[-_]?\d+$/i.test(item.title || '')).length;
    const website = typeof S.websiteStatus.total === 'number' ? S.websiteStatus.total : S.objects.filter(item => item.source_type === 'website' || String(item.id).startsWith('customer:website-')).length;
    for (const [title, note, hash] of [['商品', `已接入 ${products} 款商品 · 查资料、选素材、整理选款`, '/products'], ['客户', '查看客户需求、往来与开发进展', '/customers'], ['网站询盘', S.websiteStatus.observed_at ? `已读取 ${website} 条询盘 · 查看客户需求` : '询盘正在读取', '/customers?view=inquiries&q=%E7%BD%91%E7%AB%99']]) { const card = el('article', undefined, 'card business-entry'); card.append(el('h2', title), el('p', note), button('打开 →', () => { location.hash = hash; }, 'quiet')); grid.append(card); }
    return grid;
  }
  function image(asset, cls) { const src = safeUrl(asset?.url); if (!src) return null; const img = el('img', undefined, cls); img.src = src; img.alt = assetLabel(asset); img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.addEventListener('error', () => img.remove()); return img; }
  function productDescription(object) { const f=(object.facts || []).find(x => text(x.label).startsWith('用途候选')); return text(f?.value).split('·').map(v => v.replace(/需求/g, '').replace(/待分类/g, '').trim()).filter(Boolean).join(' · ') || '商品类型尚未整理'; }
  function creativeSummary(content) { return text(content).split('\n').map(line=>line.trim().replace(/\*\*/g,'').replace(/^[-*]\s*/,'').replace(/^(?:更新|更新时间)：\d{4}-\d{2}-\d{2}[。\s]*/,'')) .filter(line=>line && !/^(#|\||---|项目名称：)/.test(line) && !/本档案仅按既有本地文件/i.test(line) && /[\u3400-\u9fff]/.test(line)).map(line=>line.split(/；(?:本次未|未新增|未生成|用户再次明确授权删除|自动审批)/)[0])[0] || ''; }
  function appendSupply(host, object) { const supply=object.supply || {};
    if(supply.kind==='own') host.append(el('p','自有工厂'));
    else if(supply.kind==='external') { const row=el('p'); if(supply.model)row.append(el('span',text(supply.model)+' ')); const a=link('查看供货商品',supply.url); if(a)row.append(a); if(row.children.length)host.append(row); }
  }
  function appendProductLinks(host, object) {
    const supply = object.supply || {}, listings = (object.links || []).filter(item => /^Alibaba \d+$/.test(item.label || ''));
    if (supply.kind !== 'own' && !safeUrl(supply.url) && !listings.length) return;
    const section = el('div', undefined, 'product-links'), links = el('div', undefined, 'related-links');
    section.append(el('h3', '供货与国际站链接'));
    if (supply.kind === 'own') links.append(el('span', '自有工厂'));
    else if (supply.kind === 'external') { const source = link(supply.model ? `供货商品 ${supply.model} ↗` : '供货商品 ↗', supply.url); if (source) links.append(source); }
    for (const item of listings) { const a = link(`国际站商品 ${item.label.split(' ')[1]} ↗`, item.url); if (a) links.append(a); }
    section.append(links); host.append(section);
  }
  function productCategory(object) { const d=object.category && object.category !== '其他' ? object.category : productDescription(object); return /靴/.test(d) ? 'boot' : /洞洞/.test(d) ? 'clog' : /凉鞋|拖鞋|半拖/.test(d) ? 'sandal' : /乐福|豆豆/.test(d) ? 'loafer' : /套脚|袜套|一脚蹬/.test(d) ? 'slip' : /系带/.test(d) ? 'lace' : 'other'; }
  function tile(object) {
    const card = el('article', undefined, 'card object-tile'), asset = firstImage(object);
    // 2026-11-01：无图商品原来没有图片区，卡片比同排矮一截，网格参差。补等高占位，
    // 同时明确写出"无登记图片"——这正是缺口本身，不该用空白糊过去。
    if (asset) card.append(image(asset, 'tile-image'));
    else if (object.kind === 'product') card.append(el('div', '无登记图片', 'tile-image tile-placeholder'));
    card.append(el('span', objectKind(object), 'object-type'), el('h3', text(object.title), 'object-title'), el('p', object.kind === 'product' ? productDescription(object) : displayText(object.subtitle || object.summary)), button(object.kind === 'product' ? '查看商品 →' : '继续处理 →', () => goObject(object.id), 'quiet open-object')); if(object.kind==='product')appendSupply(card,object); return card;
  }
  function workRow(job) {
    const row = el('article', undefined, 'card work-row'), info = el('div'), object = objectById(job.object_id); info.append(el('h3', text(job.title || object?.title || '一项工作')), el('p', `${object?.title || '关联资料'} · ${time(job.updated_at || job.created_at)}`));
    const right = el('div'); right.append(badge(job.status), button('打开', () => goObject(job.object_id), 'quiet')); row.append(info, right); return row;
  }
  function artifactRow(artifact) {
    const row = el('article', undefined, 'card work-row'), info = el('div'); info.append(el('h3', text(artifact.title || '工作成果')), el('p', `${objectById(artifact.object_id)?.title || '关联资料'} · ${time(artifact.updated_at)}`)); row.append(info, button('查看成果 →', () => goObject(artifact.object_id, artifact.id), 'quiet')); return row;
  }
  function websiteText() {
    const value = S.websiteStatus || {}, stamp = value.observed_at ? ` · 上次读取 ${time(value.observed_at)}` : '';
    if (['loading', 'refreshing', 'pending'].includes(value.state)) return `网站记录正在读取，完成后会自动出现${stamp}`;
    if (['error', 'failed', 'stale'].includes(value.state)) return `网站记录暂未更新，保留已取得资料${stamp}`;
    if (value.observed_at) return `网站记录已读取${stamp}`;
    return '网站记录尚未完成读取，不代表没有新需求。';
  }
  function alibabaText() { const status = S.alibabaStatus || {}; if (['loading', 'refreshing', 'pending'].includes(status.state)) return '正在读取国际站订单买家；不会混入询盘数量。'; if (status.observed_at) return `订单买家来源：仅已读取的第 ${status.pagination?.page || 1} 页订单 · ${time(status.observed_at)}，不代表全量客户或新询盘。`; return '国际站订单买家尚未完成读取；订单买家与询盘分开显示。'; }
  function websiteLabel() { return el('p', websiteText(), 'website-status'); }
  function updateWebsiteLabels() { document.querySelectorAll('.website-status').forEach(item => { item.textContent = item.className.includes('alibaba-source-status') ? alibabaText() : websiteText(); }); }
  function todayAction(action) {
    if (!action) return null;
    const go = hash => button(action.label || '打开', () => { location.hash = hash; }, 'quiet');
    if (action.type === 'agent') return button(action.label || '交给 Sol', async () => {
      try { await api('/api/desk/jobs', { object_id: action.object_id, instruction: action.instruction, mode: 'draft' }); toast('已交给 Sol；完成后成果会回到该客户下。'); }
      catch (error) { message(error.message); }
    }, 'primary');
    if (action.type === 'open_object' && action.object_id) return button(action.label || '打开', () => goObject(action.object_id), 'quiet');
    if (action.type === 'open_job') { const job = S.jobs.find(item => item.id === action.job_id); return job?.object_id ? button(action.label || '查看', () => goObject(job.object_id), 'quiet') : null; }
    if (action.type === 'refresh_channel') return button(action.label || '重新采集', async () => {
      try { await api('/api/desk/refresh', {}); await api('/api/desk/alibaba/refresh', { page: 1 }); toast('已触发重新采集，稍后回来核对结果。'); }
      catch (error) { message(error.message); }
    }, 'quiet');
    if (action.type === 'open_products') return go('/products?view=gaps');
    if (action.type === 'open_catalog') return go('/products');
    if (action.type === 'open_development') return go('/customers?view=development');
    if (action.type === 'open_channels') return go('/channels');
    return go('/customers?view=inquiries');
  }
  async function renderToday(host) {
    let data;
    try { data = await api('/api/desk/today'); } catch { host.replaceChildren(el('p', '待办暂时无法读取，请稍后重试。', 'inline-error')); return; }
    const detached = host.isConnected === false || (host.isConnected === undefined && !(host.parentNode || host.parent));
    if (S.page !== 'overview' || detached) return;
    const groups = data.groups || {}, labels = data.labels || {}, counts = data.counts || {};
    const summary = ['decide', 'act', 'watch'].filter(key => counts[key]).map(key => `${labels[key] || key} ${counts[key]}`).join(' · ');
    host.replaceChildren(sectionHeading('今天', summary || '暂时没有待处理事项'));
    const unavailable = Object.entries(data.sources || {}).filter(([, value]) => value?.state === 'unavailable');
    if (unavailable.length) host.append(el('p', '部分信息暂时无法读取，请检查对应连接。', 'inline-error'));
    const grid = el('div', undefined, 'today-groups');
    for (const key of ['decide', 'act', 'watch']) {
      const items = groups[key] || [];
      if (!items.length) continue;
      const card = el('section', undefined, `card today-group ${key}`);
      card.append(el('h3', `${labels[key] || key}　${items.length}`));
      for (const item of items) {
        const row = el('article', undefined, `today-row ${item.severity || 'normal'}`), info = el('div');
        info.append(el('h4', text(item.title)));
        if (text(item.judgment)) info.append(el('p', text(item.judgment)));
        const evidence = (item.evidence || []).filter(entry => text(entry.value));
        if (evidence.length) {
          // 依据与来源默认折叠：免责说明、来源路径属于脚注，不该占据首屏。
          const details = el('details', undefined, 'today-evidence');
          details.append(el('summary', '依据与来源'));
          for (const entry of evidence) details.append(el('p', `${entry.label}：${entry.value}`, 'muted'));
          info.append(details);
        }
        row.append(info);
        const action = todayAction(item.action);
        if (action) row.append(action);
        card.append(row);
      }
      grid.append(card);
    }
    if (!grid.children.length) empty(grid, '今天没有需要你处理的事。客户回复、平台草稿、渠道数据变化后会自动出现在这里。');
    host.append(grid);
  }
  function renderOverview() {
    const page = $('page'), goalsOpen = page.querySelector('.goals')?.open; page.replaceChildren(heading('我的工作台', '今天，从这里继续', '找到正在推进的事，把下一步交给 Sol，成果留在原处。'));
    page.append(websiteLabel());
    const today = el('section', undefined, 'overview-today'); page.append(today); renderToday(today);
    const goals = Object.entries(S.goals || {}).filter(([, value]) => text(value)); if (goals.length) { const details = el('details', undefined, 'card goals'); details.open = !!goalsOpen; details.append(el('summary', '当前方向与重点')); for (const [key, value] of goals) details.append(el('div', `${({ long_term: '长期方向', phase: '当前阶段', focus: '当前重点', priorities: '优先事项', notes: '补充要求' }[key] || '当前要求')}：${text(value)}`)); page.append(details); }
    page.append(sectionHeading('从业务开始', '进入真实对象，而非工具菜单'), businessEntrances()); const recentRows = recentObjects(); if (recentRows.length) { page.append(sectionHeading('继续工作', '近期打开或实际处理过的对象')); const recent = el('div', undefined, 'continue-grid'); recentRows.forEach(object => recent.append(tile(object))); page.append(recent); }
    const artifacts = el('section'); artifacts.append(sectionHeading('最近成果', '打开后可继续编辑')); const list = el('div', undefined, 'row-list'); [...S.artifacts].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''))).slice(0, 5).forEach(item => list.append(artifactRow(item))); if (!list.children.length) empty(list, '新的选款资料、回复草稿会保存在这里，并关联原商品或客户。'); artifacts.append(list); page.append(artifacts);
  }
  function parseRoute() { const raw = location.hash.replace(/^#\/?/, '') || 'overview', split = raw.indexOf('?'); return { parts: (split < 0 ? raw : raw.slice(0, split)).split('/'), query: new URLSearchParams(split < 0 ? '' : raw.slice(split + 1)) }; }
  function setNav(page) { const name = ({ overview: '总览', products: '商品', customers: '客户', channels: '渠道', creation: '创作', library: '客户资料包' })[page] || '详情'; $('page-name').textContent = name; document.querySelectorAll('[data-nav]').forEach(item => item.classList.toggle('active', item.dataset.nav === page)); }
  async function renderRoute() {
    const serial = ++S.loadSerial, route = parseRoute(), requestedHash = location.hash; const routeIsCurrent = () => serial === S.loadSerial && location.hash === requestedHash; message(); S.route = location.hash; S.detail = null; S.object = null; S.listRefresh = null; const kind = route.parts[0];
    if (kind === 'object') {
      S.page = 'object'; setNav('overview'); $('page').replaceChildren(el('div', '正在打开这份资料…', 'loading-state'));
      try { const id = decodeURIComponent(route.parts.slice(1).join('/')), object = objectResult(await api(`/api/desk/object?id=${encodeURIComponent(id)}`)); if (!routeIsCurrent()) return; if (!object || String(object.id) !== String(id) || (id.startsWith('product:') && object.kind !== 'product') || (id.startsWith('customer:') && object.kind !== 'customer')) throw new Error('返回资料与所选对象不一致，未打开。请重新选择。'); S.object = object; remember(object.id); const index = S.objects.findIndex(item => item.id === object.id); if (index < 0) S.objects.push(object); else S.objects[index] = object; setNav(object.kind === 'product' ? 'products' : 'customers'); $('page-name').textContent = object.title; renderObject(object, route.query.get('artifact')); }
      catch (error) { if (routeIsCurrent()) { $('page').replaceChildren(el('div', error.message, 'empty')); message(error.message); } }
      return;
    }
    S.page = ['products', 'customers', 'library', 'channels', 'creation'].includes(kind) ? kind : 'overview'; setNav(S.page); if (S.page === 'overview') renderOverview(); else if (S.page === 'library') await window.renderCustomerLibrary(); else if (S.page === 'channels') await renderChannels(); else if (S.page === 'creation') await renderCreation(route.query.get('item')); else renderSearchPage(S.page, route.query.get('q') || '');
  }
  async function renderChannels() {
    const page = $('page'); page.replaceChildren(heading('渠道', '从渠道继续经营', '查看已有数据和可以直接进入的工作。'));
    try { const data=await api('/api/desk/channels'); if (S.page !== 'channels') return; const grid=el('div',undefined,'overview-grid');
      for (const item of data.channels || []) { if (item.connection?.state === 'not_integrated') continue; const card=el('section',undefined,'card'); card.append(el('h2',item.title));
        if (item.id === 'website') { card.append(el('p',websiteText()),el('p',item.connection?.total == null ? '询盘数量暂不可用' : `现有网站询盘：${item.connection.total} 条`),button('查看网站询盘',()=>{location.hash='/customers?view=inquiries';},'quiet')); }
        else if (item.id === 'alibaba') { const stamp=item.connection?.last_success_at; card.append(el('p',stamp ? `最近成功读取：${time(stamp)}` : '尚无可展示的近期读取记录。')); if(item.data?.ok && item.data.metrics) { const metrics=item.data.metrics; const labels={search_impressions:'搜索曝光',search_clicks:'搜索点击',visitors:'访客',inquiries:'询盘',tm_buyers:'TM买家',marketing_clicks:'营销点击'}; card.append(el('p',`历史数据 ${item.data.period || ''} · ${item.data.timezone || ''}`)); const line=Object.entries(labels).filter(([k])=>metrics[k] != null).map(([k,v])=>`${v} ${metrics[k]}`).join(' · '); if(line)card.append(el('p',line)); card.append(el('p','商品口径汇总，人数未去重；不用于计算转化率。','muted')); } card.append(button('查看商品',()=>{location.hash='/products';},'quiet'),button('查看订单买家',()=>{location.hash='/customers?view=inquiries&source=orders';},'quiet')); }
        else {
          const detail = item.data || {};
          card.append(el('p', detail.available === false ? '当前未取到该渠道数据。' : (text(detail.scope) || '暂无可展示的指标。')));
          if (detail.observed_at) card.append(el('p', `上次观测：${time(detail.observed_at)}`, 'muted'));
          for (const action of item.actions || []) if (text(action)) card.append(el('p', text(action), 'muted'));
        }
        const gaps=(item.gaps || []).filter(gap=>!gap.includes('妙手尚未接工作台调用'));
        if (gaps.length) {
          const box=el('details',undefined,'channel-gaps');
          box.append(el('summary',`未接通的能力 ${gaps.length} 项`));
          for (const gap of gaps) box.append(el('p',gap,'muted'));
          card.append(box);
        }
        grid.append(card);
      } page.append(grid);
    } catch(error) { message(error.message); }
  }
  function libtvPanel() {
    const panel=el('section',undefined,'card'), list=el('div'), message=el('p','','agent-feedback'); panel.append(el('h2','LibTV 画布'),el('p','读取和整理已有画布，也可以新建画布、添加文字节点。'));
    async function load() { list.replaceChildren(el('p','正在读取画布…')); try { const value=await api('/api/desk/creation/libtv'); if(!value.ok)throw new Error(value.error?.message || '读取失败'); list.replaceChildren(); const rows=value.data?.projects?.items || []; for(const canvas of rows) { const row=el('article',undefined,'card'), detail=el('div'); row.append(el('h3',canvas.name || '未命名画布'),button('查看节点',async()=>{ detail.replaceChildren(el('p','正在读取…')); try {const result=await api(`/api/desk/creation/libtv/nodes?project_id=${encodeURIComponent(canvas.id)}`); if(!result.ok)throw new Error(result.error?.message || '读取失败'); detail.replaceChildren(); for(const node of result.data?.nodes?.items || [])detail.append(el('p',[node.title,node.content].filter(Boolean).join('：'))); if(!detail.children.length)detail.append(el('p','暂无节点'));}catch(error){detail.replaceChildren(el('p',error.message,'inline-error'));}},'quiet'));
        const editor=el('details'), form=el('div',undefined,'profile-form'), title=addField(form,'节点标题'), content=addField(form,'文字内容','',true), feedback=el('p','','agent-feedback'); editor.append(el('summary','添加文字到这个画布'),form,feedback,button('添加文字节点',async()=>{if(!title.value.trim()||!content.value.trim()){feedback.textContent='请填写标题和内容。';return;}try{const result=await api('/api/desk/creation/libtv/text',{project_id:canvas.id,title:title.value.trim(),content:content.value.trim()});if(!result.ok)throw new Error(result.error?.message || '添加失败');feedback.textContent='已添加到 LibTV 画布。';title.value='';content.value='';}catch(error){feedback.textContent=error.message;}},'primary')); row.append(detail,editor);list.append(row); } if(!rows.length)empty(list,'当前没有画布。'); }catch(error){list.replaceChildren(el('p',error.message,'inline-error'));} }
    const create=el('details'), form=el('div',undefined,'profile-form'), name=addField(form,'新画布名称'); create.append(el('summary','新建 LibTV 画布'),form,button('创建画布',async()=>{if(!name.value.trim()){message.textContent='请填写画布名称。';return;}try{const result=await api('/api/desk/creation/libtv/create',{name:name.value.trim(),workspace_id:'0'});if(!result.ok)throw new Error(result.error?.message || '创建失败');message.textContent='画布已创建。';name.value='';await load();}catch(error){message.textContent=error.message;}},'primary'),message);
    panel.append(button('读取我的画布',load,'quiet'),create,list);return panel;
  }
  async function renderCreation(selected) {
    const requestedHash=location.hash, current=()=>S.page==='creation' && location.hash===requestedHash; const page=$('page'); page.replaceChildren(heading('创作','继续现有创作','从原项目记录和已关联素材继续，不重复建项目。'));
    try { if (selected) { const item=await api(`/api/desk/creation/item?id=${encodeURIComponent(selected)}`); if(!current())return;
        page.append(button('← 返回创作项目',()=>{location.hash='/creation';},'quiet')); const card=el('section',undefined,'card'); card.append(el('h2',item.title));
        const canvasCard=el('section',undefined,'card'); canvasCard.append(el('h2','项目画布'),el('p','围绕本项目的资料与素材整理镜头和想法。')); const canvasHost=el('div'); canvasCard.append(button('打开画布',()=>{ const frame=el('iframe'); frame.src=`/creation-canvas/index.html?object_id=${encodeURIComponent(selected)}`; frame.title='项目创作画布'; frame.style.width='100%'; frame.style.height='760px'; frame.style.border='0'; canvasHost.replaceChildren(frame); },'primary'),link('全屏打开画布 ↗', `/creation-canvas/index.html?object_id=${encodeURIComponent(selected)}`),canvasHost); page.append(canvasCard);
        const summary=creativeSummary(item.summary); if(summary)card.append(el('p',summary));
        for (const [key, label] of [['progress','当前进展'],['next_actions','下一步']]) { const section=(item.project_context?.[key] || []).find(entry => text(entry.content).trim()); if(section) { const excerpt=text(section.content).replace(/\*\*/g,'').trim(); card.append(el('h3',label),el('p',excerpt.length>500 ? `${excerpt.slice(0,500)}…` : excerpt)); } }
        const original=el('details'); original.append(el('summary','项目记录'),el('pre',item.content,'plain-reading')); card.append(original);
        if ((item.assets || []).length) { card.append(el('h3','项目引用的素材')); for(const asset of item.assets) { if(asset.type==='html') continue; const data={kind:['png','jpg','jpeg'].includes(asset.type)?'image':asset.type==='mp3'||asset.type==='wav'?'audio':'video',url:`/api/media/file?path=${encodeURIComponent(asset.path)}`,label:asset.name}; card.append(button(asset.name,()=>previewAsset(data),'quiet')); } }
        for(const url of item.links || []) { const a=link('打开 LibTV 项目 ↗',url); if(a)card.append(a); } page.append(card);
        try {
          const result=await api(`/api/desk/object?id=${encodeURIComponent(selected)}`); if(!current())return; const object=result.object || result;
          const layout=el('div',undefined,'object-layout'), right=el('aside',undefined,'card object-agent'), outcomes=el('section',undefined,'card'); outcomes.append(el('h2','创作成果'),el('p','继续原项目，整理脚本、分镜与修改方案；成果可编辑并保存在原项目。','artifact-note'));
          const tabs=el('div',undefined,'artifact-tabs'), editor=el('div'); outcomes.append(tabs,editor); const ctx={object,right,tabs,editor,artifacts:[],selectedId:null,currentEdit:null,requestedArtifact:parseRoute().query.get('artifact')}; S.detail=ctx; buildAgent(ctx);
          ctx.right.querySelector('h2').textContent='交给 Sol 继续创作'; ctx.right.querySelector('.agent-copy').textContent='依据原项目记录与关联素材继续，明确需要的创作成果。'; ctx.instruction.placeholder='例如：按原项目风格完善这一段分镜，并说明素材缺口';
          ctx.right.querySelector('.agent-shortcuts').replaceChildren(button('整理下一步创作方案',()=>{ctx.instruction.value='先读取原项目与关联素材，说明当前成果、待解决问题，并给出可执行的创作方案。付费AI视频生成须有负责人当次明确确认。';ctx.instruction.focus();}));
          layout.append(outcomes,right);page.append(layout);await refreshArtifacts(ctx,true);
        } catch(error) { if(current())page.append(el('p',`创作助手暂不可用：${error.message}`,'inline-error')); }
        return; }
      page.append(libtvPanel(),sectionHeading('本地创作项目','项目原文与关联素材'));
      const result=await api('/api/desk/creation'); if(S.page!=='creation')return; const list=el('div',undefined,'row-list');
      const input=el('input',undefined,'search-input'); input.type='search'; input.placeholder='搜索项目名称或内容'; input.setAttribute('aria-label','搜索创作项目'); page.append(input,list);
      function showProjects() { list.replaceChildren(); const query=input.value.trim().toLowerCase(); for(const item of result.projects || []) { if(query && !`${item.title} ${item.summary}`.toLowerCase().includes(query))continue; const card=el('article',undefined,'card work-row'),info=el('div'); const summary=creativeSummary(item.summary); info.append(el('h3',item.title)); if(summary)info.append(el('p',summary.slice(0,160))); info.append(el('small',`项目记录更新：${time(item.updated_at*1000)}`)); card.append(info,button('打开项目 →',()=>{location.hash=`/creation?item=${encodeURIComponent(item.id)}`;},'quiet'));list.append(card); } if(!list.children.length)empty(list,'没有找到匹配项目。'); } input.addEventListener('input',showProjects); showProjects();
    } catch(error) { message(error.message); }
  }
  function renderSearchPage(kind, query) {
    if (kind === 'customers' && parseRoute().query.get('view') === 'competitors') { renderCompetitors(); return; }
    if (kind === 'customers' && parseRoute().query.get('view') !== 'inquiries') { renderDevelopment(); return; }
    if (kind === 'customers' && parseRoute().query.get('source') !== 'orders') { renderInquiryQueue(query); return; }
    const listRouteSerial = S.loadSerial; const listIsCurrent = () => listRouteSerial === S.loadSerial && parseRoute().parts[0] === kind;
    const gapView = kind === 'products' && parseRoute().query.get('view') === 'gaps';
    const page = $('page'), labels = { products: ['商品资料', '商品', '从真实产品、规格与素材出发，整理可以直接使用的选款资料。'], customers: ['客户与需求', '客户', '需求、来源与准备中的回复，放在同一处继续。'], library: ['查找资料', '资料', '跨商品与客户查找原文、图片和已有资料，不搬动原文件。'] };
    page.replaceChildren(heading(...labels[kind])); if (kind === 'customers') page.append(customerTabs('inquiries')); if (kind === 'customers' || kind === 'library') page.append(websiteLabel()); if (gapView) { const bar = el('div', undefined, 'gap-view-bar'); bar.append(el('p', '查看尚未关联的商品图片、供货链接和国际站链接。', 'muted'), button('查看全部商品 →', () => { location.hash = '/products'; }, 'quiet')); page.append(bar); } const input = el('input', undefined, 'search-input'); input.type = 'search'; input.value = query; input.placeholder = kind === 'products' ? '搜索款号、名称或商品信息' : kind === 'customers' ? '搜索客户、需求或来源' : '搜索商品、客户与关联资料'; input.setAttribute('aria-label', '搜索资料'); const sourceSelect = kind === 'customers' ? el('select', undefined, 'source-filter') : null; if (sourceSelect) { for (const [value, label] of [['records', '需求与客户记录'], ['orders', '国际站订单买家（非询盘）'], ['all', '全部来源（分类型）']]) { const option = el('option', label); option.value = value; sourceSelect.append(option); } sourceSelect.value = parseRoute().query.get('source') || 'records'; sourceSelect.setAttribute('aria-label', '客户来源类型'); } const category = el('select'); category.setAttribute('aria-label', '商品分类'); for (const [v,l] of [['','全部分类'],['lace','系带鞋'],['slip','套脚鞋'],['boot','靴'],['sandal','凉鞋与拖鞋'],['clog','洞洞鞋'],['loafer','乐福与豆豆鞋'],['other','其他与待分类']]) { const o=el('option',l); o.value=v; category.append(o); } const count = el('span', '', 'search-count'), list = el('div', undefined, kind === 'products' ? 'product-grid' : kind === 'library' ? 'library-grid' : 'row-list'); const search = el('div', undefined, 'search-bar'); search.append(input); if (kind === 'products') { search.append(category); category.addEventListener('change', () => find(input.value)); } if (sourceSelect) search.append(sourceSelect); search.append(count); page.append(search); if (kind === 'customers') { const orderStatus = el('p', '', 'alibaba-source-status website-status'); orderStatus.textContent = alibabaText(); page.append(orderStatus, button('更新订单买家（第 1 页）', async () => { try { const result = await api('/api/desk/alibaba/refresh', { page: 1 }); S.alibabaStatus = result.status || result; orderStatus.textContent = alibabaText(); } catch (error) { message(error.message); } }, 'quiet order-refresh')); } page.append(list); let timer, searchSerial = 0;
    async function find(value) { const sequence = ++searchSerial; count.textContent = '正在查找…'; try { const endpointKind = kind === 'products' ? 'product' : kind === 'customers' ? 'customer' : ''; const result = await api(`/api/desk/objects?q=${encodeURIComponent(value)}&kind=${endpointKind}`); if (sequence !== searchSerial || S.page !== kind || !listIsCurrent()) return; let rows = array(result, 'objects').filter(object => !sourceSelect || sourceSelect.value === 'all' || (sourceSelect.value === 'orders' ? object.source_type === 'alibaba_order_buyer' : object.source_type !== 'alibaba_order_buyer')); if (kind === 'products') { rows = rows.filter(object => !/^HR[-_]?\d+$/i.test(object.title)); if (category.value) rows = rows.filter(object => productCategory(object) === category.value); rows.sort((a,b) => productCategory(a).localeCompare(productCategory(b), 'zh-CN') || text(a.title).localeCompare(text(b.title), 'zh-CN', {numeric:true})); } list.replaceChildren(); count.textContent = kind === 'customers' ? `${sourceSelect.value === 'orders' ? '订单买家' : '来源记录'} ${rows.length} 份` : `${rows.length} 项结果`;
        if (kind === 'products') {
          if (gapView) {
            const limit = Math.max(1, S.objects.filter(object => object.kind === 'product').length);
            const gaps = await api(`/api/desk/product-gaps?limit=${limit}`), byId = new Map((gaps.items || []).map((row, index) => [String(row.object_id), { row, index }]));
            if (sequence !== searchSerial || S.page !== kind || !listIsCurrent()) return;
            rows = rows.filter(object => byId.has(String(object.id)));
            rows.sort((a, b) => byId.get(String(a.id)).index - byId.get(String(b.id)).index);
            count.textContent = `${rows.length} 款待补充资料`;
          }
          let shown = 0; const more = button('显示更多商品', () => showMore(), 'quiet');
          function showMore() { more.remove(); const end = Math.min(shown + 36, rows.length); while (shown < end) list.append(tile(rows[shown++])); if (shown < rows.length) list.append(more); }
          showMore();
        } else for (const object of rows) {
          if (kind === 'customers') { const row = el('article', undefined, 'card customer-row'), content = el('div'); content.append(el('h3', text(object.title), 'object-title'), el('p', displayText(object.subtitle || object.summary)), el('div', text(object.source), 'source-label')); row.append(el('div', text(object.title).slice(0, 1) || '客', 'customer-avatar'), content, button('打开客户 →', () => goObject(object.id), 'quiet')); list.append(row); }
          else { const row = el('article', undefined, 'card library-row'); row.append(el('span', objectKind(object), 'eyebrow'), el('h3', text(object.title), 'object-title'), el('p', text(object.summary || object.subtitle)), el('p', text(object.source)), button('打开关联资料 →', () => goObject(object.id), 'quiet')); const names = (object.assets || []).map(asset => asset.label || asset.path).filter(Boolean); if (names.length) row.append(el('p', `关联素材：${names.slice(0, 4).join(' · ')}`)); list.append(row); }
        }
        if (!rows.length) empty(list, value ? '没有找到匹配资料。换个名称、款号或需求关键词再试。' : kind === 'customers' && !S.websiteStatus?.observed_at ? websiteText() : '当前没有可展示的这类资料。');
      } catch (error) { if (sequence === searchSerial && listIsCurrent()) { count.textContent = ''; list.replaceChildren(el('div', error.message, 'empty')); } }
    }
    if (sourceSelect) sourceSelect.addEventListener('change', () => { if (!listIsCurrent()) return; history.replaceState(null, '', `#/customers?view=inquiries&source=${sourceSelect.value}${input.value ? `&q=${encodeURIComponent(input.value)}` : ''}`); find(input.value); });
    input.addEventListener('input', () => { if (!listIsCurrent()) return; clearTimeout(timer); const value = input.value; history.replaceState(null, '', `#/${kind}?${kind === 'customers' ? `view=inquiries&source=${sourceSelect.value}&` : ''}${value ? `q=${encodeURIComponent(value)}` : ''}`); timer = setTimeout(() => find(value), 250); }); S.listRefresh = () => find(input.value); find(query);
  }
  const workflowStates = { new: '待处理', preparing: '准备回复', waiting_customer: '等客户', internal_review: '内部评估', quoting: '报价沟通', sampling: '样品推进', won: '已成交', lost: '不再推进', archived: '归档' };
  const priorityNames = { urgent: '紧急', high: '优先', normal: '正常', low: '稍后' };
  function selectField(root, label, values, selected) { const wrap = el('label', undefined, 'desk-field'), input = el('select'); input.setAttribute('aria-label', label); for (const [value, title] of values) { const option = el('option', title); option.value = value; input.append(option); } input.value = selected || ''; wrap.append(el('span', label), input); root.append(wrap); return input; }
  function renderInquiryQueue(query) {
    const serial = S.loadSerial, page = $('page'), bucket = parseRoute().query.get('bucket') || 'active';
    const current = () => serial === S.loadSerial && parseRoute().parts[0] === 'customers' && parseRoute().query.get('view') === 'inquiries';
    page.replaceChildren(heading('询盘处理', '先处理眼前的一步', '按经营状态推进，历史复盘与订单买家分开查看。'), customerTabs('inquiries'));
    const tabs = el('div', undefined, 'customer-tabs inquiry-buckets'); for (const [id, label] of [['active', '待办'], ['history', '历史复盘'], ['archive', '已结束']]) tabs.append(button(label, () => { location.hash = `/customers?view=inquiries&bucket=${id}`; }, bucket === id ? 'active' : ''));
    tabs.append(button('订单买家', () => { location.hash = '/customers?view=inquiries&source=orders'; }, 'quiet')); page.append(tabs, websiteLabel());
    const filters = el('div', undefined, 'search-bar'), search = addField(filters, '搜索客户与需求', query), state = selectField(filters, '推进状态', [['', '全部状态'], ...Object.entries(workflowStates)], parseRoute().query.get('state')), priority = selectField(filters, '优先级', [['', '全部优先级'], ...Object.entries(priorityNames)], ''), sort = selectField(filters, '排序', [['urgency', '优先级与截止时间'], ['recent', '最近收到']], 'urgency');
    const count = el('p', '', 'search-count'), list = el('div', undefined, 'row-list inquiry-list'); page.append(filters, count, list); let sequence = 0, rows = [], timer;
    function paint() { list.replaceChildren(); let visible = rows.filter(row => !priority.value || row.workflow?.priority === priority.value); const ranks = {urgent:0,high:1,normal:2,low:3}; visible = [...visible].sort((a,b) => sort.value === 'recent' ? String(b.received_at || '').localeCompare(String(a.received_at || '')) : (ranks[a.workflow?.priority] ?? 2) - (ranks[b.workflow?.priority] ?? 2) || String(a.workflow?.due_at || '9999').localeCompare(String(b.workflow?.due_at || '9999'))); count.textContent = `${visible.length} 条${bucket === 'history' ? '历史复盘' : bucket === 'archive' ? '已结束记录' : '待办'}`;
      for (const row of visible) { const card = el('article', undefined, 'card inquiry-row'), w = row.workflow || {}, a = row.analysis || {}, brief = row.business_summary || {}, head = el('div', undefined, 'inquiry-row-head'); head.append(el('h2', row.title || '客户记录'), el('span', `${w.state_label || workflowStates[w.state] || '待处理'} · ${w.priority_label || priorityNames[w.priority] || '正常'}`, `workflow-badge priority-${w.priority || 'normal'}`)); card.append(head); if(replyNotice(w))card.append(el('p',replyNotice(w),'mail-attention')); if (bucket === 'history') card.append(el('span', '历史复盘 · 不属于当前新询盘', 'eyebrow')); card.append(el('p', brief.core_need || brief.headline || a.core_need || a.brief || '打开原文，确认本次实际需求。', 'inquiry-need'), el('p', `下一步：${(w.gmail_reply_pending && w.gmail_next_action) || brief.next_action || w.next_action || (bucket === 'archive' ? '已结束' : a.next_action || '先阅读需求并确定处理动作')}`, 'next-action')); if (w.due_at) card.append(el('p', `客户时限：${w.due_at}`, 'muted')); card.append(button('打开客户', () => goObject(row.object_id), 'quiet')); list.append(card); }
      if (!visible.length) list.append(el('p', bucket === 'active' ? '当前没有符合条件的待办。网站读取状态见上方。' : '这个分组暂无符合条件的记录。', 'empty-state'));
    }
    async function read() { const seq = ++sequence; try { const result = await api(`/api/desk/inquiry-queue?bucket=${bucket}&state=${encodeURIComponent(state.value)}&q=${encodeURIComponent(search.value)}`); if (!current() || seq !== sequence) return; rows = result.items || result.rows || []; paint(); } catch (error) { if (current()) list.replaceChildren(el('p', error.message, 'inline-error')); } }
    search.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(read, 220); }); state.addEventListener('change', read); priority.addEventListener('change', paint); sort.addEventListener('change', paint); S.listRefresh = read; read();
  }
  function workflowEditor(ctx, host) {
    const w = ctx.profile.workflow; if (!w) return; const box = el('details', undefined, 'workflow-editor'), summary = el('summary', `${w.state_label || workflowStates[w.state] || '待处理'} · ${w.priority_label || priorityNames[w.priority] || '正常'} · 调整推进安排`); box.append(summary);
    const form = el('div', undefined, 'profile-form'), transitions = (w.allowed_transitions || []).map(item => typeof item === 'string' ? [item, workflowStates[item] || item] : [item.state, item.label]); if (!transitions.some(item => item[0] === w.state)) transitions.unshift([w.state, w.state_label || workflowStates[w.state] || w.state]); const state = selectField(form, '经营状态', transitions, w.state), priority = selectField(form, '处理优先级', Object.entries(priorityNames), w.priority || 'normal'), bucket = selectField(form, '记录分组', [['active','当前待办'],['history','历史复盘'],['archive','已结束']], w.bucket || 'active'), next = addField(form, '下一动作', w.next_action || ctx.profile.analysis?.next_action, true), due = addField(form, '客户明确截止时间（没有则留空）', w.due_at), note = addField(form, '处理备注', w.note, true), feedback = el('p', '', 'agent-feedback');
    for (const input of [state, priority, bucket, next, due, note]) { input.addEventListener('input', () => { ctx.workflowEditing = true; }); input.addEventListener('change', () => { ctx.workflowEditing = true; }); } form.append(feedback, button('保存推进安排', async () => { try { await api('/api/desk/customer-workflow', {object_id:ctx.object.id,state:state.value,priority:priority.value,...(bucket.value !== (w.bucket || 'active') ? {bucket:bucket.value} : {}),next_action:next.value,due_at:due.value,note:note.value}); ctx.workflowEditing = false; await loadProfile(ctx); toast('推进安排已保存。'); } catch(error) { feedback.textContent = error.message; } }, 'primary')); box.append(form); host.append(box);
  }
  function customerTabs(current) {
    const tabs = el('div', undefined, 'customer-tabs'); for (const [id, label] of [['development', '客户开发'], ['competitors', '同行找客户'], ['inquiries', '询盘处理']]) tabs.append(button(label, () => { location.hash = `/customers?view=${id}`; }, current === id ? 'active' : '')); return tabs;
  }
  async function renderCompetitors() {
    const page = $('page'), serial = S.loadSerial;
    const current = () => S.page === 'customers' && serial === S.loadSerial && parseRoute().query.get('view') === 'competitors';
    page.replaceChildren(heading('客户开发', '同行找客户', '从国际站同行入手，找到买家后直接在这里登记、继续研究。'), customerTabs('competitors'));
    const explanation = el('p', '查海关时结合地址、货描和日期核对出口方。批量复制优先中文名，未找到中文名的使用英文。', 'competitor-intro');
    const search = el('input', undefined, 'search-input'); search.type = 'search'; search.placeholder = '搜索公司名、信用代码或鞋类'; search.setAttribute('aria-label', '搜索同行');
    const count = el('span', '', 'search-count'), bar = el('div', undefined, 'search-bar competitor-search-bar'), list = el('div', undefined, 'row-list competitor-list');
    bar.append(search, count); page.append(explanation, bar, list);
    let data;
    try { data = await api('/api/desk/competitors'); } catch (error) { if (current()) message(error.message); return; }
    if (!current()) return;
    const copyAll = button('一键复制全部公司名', async () => {
      const names = (data.items || []).map(item => text(item.identity?.name).trim() || text(item.company).trim()).filter(Boolean);
      if (!names.length) { toast('当前没有可复制的公司名称。'); return; }
      if (!navigator.clipboard?.writeText) { toast('当前页面无法使用剪贴板。'); return; }
      try { await navigator.clipboard.writeText(names.join('\n')); toast(`已复制 ${names.length} 家公司名称，每家一行。`); }
      catch { toast('复制未成功，请检查浏览器剪贴板权限。'); }
    }, 'primary competitor-copy-all');
    bar.append(copyAll);
    function openBuyer(id) { location.hash = `/customers?view=development&item=${encodeURIComponent(id)}`; }
    function addBuyer(company) {
      const dialog = el('dialog', undefined, 'intake-dialog competitor-dialog'), form = el('div', undefined, 'competitor-form');
      dialog.append(el('h2', `登记 ${company.company} 的买家线索`), el('p', '填入查询到的公司，保存后可继续研究其业务与联系方式。', 'muted'));
      const name = addField(form, '买家公司名称', '', false, '例如：ABC Footwear Inc.'), country = addField(form, '国家或市场（选填）'), note = addField(form, '线索说明（选填）', '', true, '可填写查询来源、货描、日期等');
      const feedback = el('div', undefined, 'inline-error');
      const save = button('保存并查看客户', async () => {
        const companyName = name.value.trim(); feedback.replaceChildren();
        if (!companyName) { feedback.textContent = '请填写买家公司名称。'; return; }
        const same = (data.existing_buyers || []).find(row => row.company.trim().toLocaleLowerCase() === companyName.toLocaleLowerCase());
        if (same) { feedback.append(el('p', '该公司已在客户列表中，请先查看已有记录。'), button('打开已有客户', () => { dialog.close(); openBuyer(same.id); }, 'quiet')); return; }
        save.disabled = true;
        try {
          const description = note.value.trim();
          const created = await api('/api/desk/discovery', { kind: 'candidate', company: companyName, country: country.value.trim(),
            target: `从同行 ${company.company} 研究中登记的买家线索。`,
            evidence: description ? [{text: description, url: '', observed_at: ''}] : [],
            next_action: '核对具体来源及买家公司业务、采购入口。', related_competitors: [company.id] });
          const item = created.item || created;
          data.existing_buyers.push({id: item.id, company: companyName}); dialog.close(); openBuyer(item.id);
        } catch (error) { feedback.textContent = error.message; save.disabled = false; }
      }, 'primary');
      dialog.append(form, feedback, save, button('取消', () => dialog.close(), 'quiet'));
      dialog.addEventListener('close', () => dialog.remove()); document.body.append(dialog); dialog.showModal(); name.focus();
    }
    function buyerLinks(host, buyers) {
      if (!buyers?.length) return;
      const row = el('div', undefined, 'competitor-buyers'); row.append(el('span', '相关买家线索：'));
      buyers.forEach(buyer => row.append(button(buyer.company, () => openBuyer(buyer.id), 'quiet'))); host.append(row);
    }
    function paint() {
      list.replaceChildren(); const query = search.value.trim().toLocaleLowerCase();
      const rows = (data.items || []).filter(item => `${item.company} ${item.direction} ${item.identity?.name || ''} ${item.identity?.credit_code || ''}`.toLocaleLowerCase().includes(query));
      count.textContent = `${rows.length} 家同行`;
      for (const item of rows) {
        const card = el('article', undefined, 'card competitor-row'), info = el('div', undefined, 'competitor-main'), actions = el('div', undefined, 'competitor-actions');
        info.append(el('h3', item.company), el('p', item.direction));
        if (item.identity) { const identity = el('p', `中文检索名：${item.identity.name}${item.identity.credit_code ? ` · 信用代码：${item.identity.credit_code}` : ''}`, 'competitor-identity'); const source = link('来源 ↗', item.identity.source_url); if (source) identity.append(el('span', ' '), source); info.append(identity); }
        if (item.sales) { const sold = el('p', item.sales.note, 'competitor-sales'); const source = link('销量依据 ↗', item.sales.source_url); if (source) sold.append(el('span', ' '), source); info.append(sold); }
        buyerLinks(info, item.buyers); const shop = link('查看国际站店铺 ↗', item.store_url); if (shop) actions.append(shop);
        if (item.identity) actions.append(button('复制中文名', async () => { if (!navigator.clipboard?.writeText) { toast('请选择中文公司名称后复制。'); return; } await navigator.clipboard.writeText(item.identity.name); toast('中文公司名已复制。'); }, 'quiet'));
        actions.append(button('复制公司名', async () => { if (!navigator.clipboard?.writeText) { toast('请选择公司名称后复制。'); return; } await navigator.clipboard.writeText(item.company); toast('公司名已复制。'); }, 'quiet'), button('登记买家', () => addBuyer(item), 'primary'));
        card.append(info, actions); list.append(card);
      }
      if (!rows.length) empty(list, '没有找到匹配的同行。');
    }
    search.addEventListener('input', paint); paint();
  }
  function addField(root, label, value = '', multiline = false, placeholder = '') { const wrap = el('label', undefined, 'desk-field'), input = el(multiline ? 'textarea' : 'input'); input.value = text(value); input.placeholder = placeholder; input.setAttribute('aria-label', label); wrap.append(el('span', label), input); root.append(wrap); return input; }
  function listText(root, title, values) { const section = el('div', undefined, 'analysis-block'); section.append(el('h3', title)); const items = Array.isArray(values) ? values : values ? [values] : []; if (items.length) { const list = el('ul'); items.forEach(item => list.append(el('li', displayText(item)))); section.append(list); } else section.append(el('p', '尚未取得依据', 'muted')); root.append(section); }
  function replyNotice(workflow = {}) {
    return [workflow.gmail_reply_pending ? 'Gmail 客户有新回复' : '', workflow.customer_reply_pending ? '网站站内消息有新回复' : ''].filter(Boolean).join(' · ');
  }
  function mountGmail(ctx, main) {
    const host = el('section', undefined, 'card gmail-conversation'); ctx.gmailHost = host; main.append(host);
    ctx.gmailMessages = el('div'); ctx.composerHost = el('div', undefined, 'gmail-composer-host'); host.append(ctx.gmailMessages, ctx.composerHost);
    ctx.candidateNext = main.querySelector('.candidate-next-action');
    ctx.candidateNextDefault = ctx.candidateNext?.textContent || '';
    ctx.gmailMessages.append(el('h2', 'Gmail 邮件往来'), el('p', '正在读取邮件连接状态…'));
    loadGmail(ctx);
  }
  async function loadGmail(ctx, sync = false) {
    if (ctx.gmailBusy) return; ctx.gmailBusy = true; ctx.lastGmailRefresh = Date.now();
    try {
      const data = await api(sync ? '/api/desk/gmail/sync' : `/api/desk/gmail/customer?object_id=${encodeURIComponent(ctx.object.id)}`, sync ? {object_id:ctx.object.id} : undefined);
      if (S.detail !== ctx) return;
      if (ctx.candidateNext) ctx.candidateNext.textContent = data.reply_pending ? '下一步：阅读客户新邮件，准备后续沟通' : ctx.candidateNextDefault;
      const stamp = JSON.stringify(data); if (stamp === ctx.gmailStamp) return; ctx.gmailStamp = stamp;
      const host = ctx.gmailMessages, status = data.status || {}, connected = status.state === 'connected', noContact = status.state === 'no_contact_email'; host.replaceChildren(el('h2', 'Gmail 邮件往来'));
      host.append(el('p', connected ? `已连接${status.account_email ? ` · ${status.account_email}` : ''}${status.last_success_at ? ` · 最近读取 ${time(status.last_success_at)}` : ''}` : noContact ? '这位客户尚未填写联系邮箱。' : status.state === 'error' ? '邮件读取暂未完成，请稍后重试。' : '尚未连接 Gmail，当前没有自动收信。', connected ? 'gmail-status' : 'artifact-note'));
      if (connected) host.append(el('p', '工作台运行时约每 2 分钟检查一次；可手动更新。回复在本页审核后发送。', 'gmail-sync-note'));
      if(status.authorization_expires_at)host.append(el('p',`Google 测试授权预计 ${time(status.authorization_expires_at)} 到期，到期后重新授权即可。`,'artifact-note'));
      if (status.error) host.append(el('p', text(status.error), 'inline-error'));
      if (status.history_note) host.append(el('p', text(status.history_note), 'artifact-note'));
      if (!connected && !noContact) {
        const setup = el('details', undefined, 'gmail-connect'); setup.append(el('summary', '连接我的 Gmail'));
        setup.append(el('h3', '使用 Google 账号授权'), el('p', '工作台只读邮件。首次连接需要创建 Google 桌面应用并启用 Gmail API，再选择下载的客户端文件；已经连接过的账号重新授权时无需再次选择文件。'));
        const steps = el('details'); steps.append(el('summary','首次设置步骤'));
        steps.append(el('p','1. 打开 Google Cloud，新建或选择一个项目，启用 Gmail API。'));
        const library=link('打开 Gmail API 设置 ↗','https://console.cloud.google.com/apis/library/gmail.googleapis.com'); if(library)steps.append(library);
        steps.append(el('p','2. 设置 Google 身份验证平台：应用名称可填“贝强经营工作台”，支持和联系邮箱填自己的 Gmail，个人账号选择“外部”。'));
        const branding=link('打开 Google 授权设置 ↗','https://console.cloud.google.com/auth/branding'); if(branding)steps.append(branding);
        steps.append(el('p','3. 如果项目处于测试模式，在“受众”添加自己的 Gmail 为测试用户。测试模式的授权会在 7 天后到期。'));
        const audience=link('打开受众与测试用户 ↗','https://console.cloud.google.com/auth/audience'); if(audience)steps.append(audience);
        steps.append(el('p','4. 在“数据访问”添加并保存下面的 Gmail 只读权限：'));
        steps.append(el('code','https://www.googleapis.com/auth/gmail.readonly'));
        const scopes=link('打开数据访问设置 ↗','https://console.cloud.google.com/auth/scopes'); if(scopes)steps.append(scopes);
        steps.append(el('p','5. 创建“桌面应用”类型的 OAuth 客户端，下载 JSON 文件，在下方选择。'));
        const clients=link('创建桌面应用客户端 ↗','https://console.cloud.google.com/auth/clients/create'); if(clients)steps.append(clients);
        setup.append(steps);
        const config=addField(setup,'Google 桌面应用客户端文件');config.type='file';config.accept='.json,application/json';
        const oauthFeedback=el('p','','agent-feedback'), oauthLink=el('div');
        const oauthButton=button('准备 Google 授权',async()=>{
          oauthButton.disabled=true;oauthFeedback.textContent='正在准备 Google 登录…';oauthLink.replaceChildren();
          try {
            let clientConfig=null;
            if(config.files?.[0]) { try { clientConfig=JSON.parse(await config.files[0].text()); } catch { throw new Error('客户端文件不是有效的 JSON，请重新选择。'); } }
            const result=await api('/api/desk/gmail/oauth/start',{client_config:clientConfig});
            const authorize=link('继续 Google 登录并授权 ↗',result.authorization_url);
            if(!authorize)throw new Error('未能准备 Google 登录，请重试。');
            oauthLink.append(authorize);oauthFeedback.textContent='请点击下方链接，在 Google 页面完成登录和只读授权。';
          } catch(error) { oauthFeedback.textContent=error.message; }
          finally { oauthButton.disabled=false; }
        },'primary');
        setup.append(oauthButton,oauthFeedback,oauthLink);
        const passwordSetup=el('details');passwordSetup.append(el('summary','其他方式：应用专用密码'));
        passwordSetup.append(el('p', '需要账号支持两步验证及应用专用密码。此密码允许访问邮箱，工作台只读取邮件。请只在本地页面填写，不要发到聊天中。'));
        const help = link('在 Google 创建应用专用密码 ↗', 'https://myaccount.google.com/apppasswords'); if (help) passwordSetup.append(help);
        const account = addField(passwordSetup, 'Gmail 邮箱', status.account_email || ''), password = addField(passwordSetup, 'Google 应用专用密码'); account.type = 'email'; password.type = 'password'; password.autocomplete = 'new-password';
        const feedback = el('p', '', 'agent-feedback'), connect = button('连接邮箱', async () => {
          const secret = password.value; password.value = '';
          if (!account.value.trim() || !secret.trim()) { feedback.textContent = '请填写邮箱和 Google 提供的应用专用密码。'; return; }
          connect.disabled = true; feedback.textContent = '正在连接邮箱…';
          try { await api('/api/desk/gmail/connect', {account_email:account.value.trim(),app_password:secret}); if(S.detail !== ctx)return; ctx.gmailStamp = null; await loadGmail(ctx); }
          catch { if(S.detail === ctx)feedback.textContent = '连接未完成，请检查邮箱、两步验证和应用专用密码后重试。'; }
          finally { password.value = ''; connect.disabled = false; }
        }, 'primary'); passwordSetup.append(feedback, connect); setup.append(passwordSetup); host.append(setup);
      }
      if (data.reply_pending) host.append(el('p', '客户有新邮件，请先阅读，再准备下一步。', 'mail-attention'));
      if (data.reply_pending) host.append(button('标记邮件已处理',async()=>{try{await api('/api/desk/gmail/ack',{object_id:ctx.object.id});ctx.gmailStamp=null;await loadGmail(ctx);if(ctx.profileHost)await loadProfile(ctx);toast('已标记处理。');}catch(error){toast(error.message);}},'quiet'));
      if (data.callback_error) host.append(el('p', text(data.callback_error), 'inline-error'));
      if (data.next_action) host.append(el('p', `下一步：${data.next_action}`, 'next-action'));
      const mailActions = el('div', undefined, 'gmail-actions');
      mailActions.append(button('写邮件 / 继续草稿', () => openGmailComposer(ctx), 'primary'));
      mailActions.append(button('更新邮件往来', () => loadGmail(ctx, true), 'quiet'), button('根据邮件准备回复', () => { ctx.instruction.value = (ctx.instruction.value.trim() ? ctx.instruction.value + '\n\n' : '') + '请先读取这位客户最新 Gmail 往来，用中文说明客户回复的重点、当前需要处理的事项和建议下一步，再准备英文回复草稿并附中文对照。保留原有承诺与上下文，不发送邮件。'; S.instructions.set(String(ctx.object.id), ctx.instruction.value); ctx.instruction.focus(); }, 'quiet'));
      const messages = Array.isArray(data.messages) ? [...data.messages].sort((a,b) => text(b.sent_at).localeCompare(text(a.sent_at))) : [];
      const latestThread = messages.find(mail => mail.url)?.url;
      if (latestThread) { const replyLink = link('在 Gmail 查看并回复 ↗', latestThread); if (replyLink) { replyLink.className = 'gmail-reply-link'; mailActions.append(replyLink); } }
      host.append(mailActions);
      if (!messages.length) host.append(el('p', connected ? '暂未找到与这位客户关联的邮件。' : '连接完成后，客户邮件会在这里显示。', 'muted'));
      for (const mail of messages) {
        const entry = el('article', undefined, 'gmail-message'); entry.append(el('h3', `${mail.direction === 'outbound' ? '我方发出' : mail.mail_kind === 'automatic' ? '自动回复' : '客户来信'} · ${time(mail.sent_at)}`));
        if (mail.subject_zh) entry.append(el('p', text(mail.subject_zh), 'mail-subject'));
        if (mail.translation_zh) entry.append(el('p', text(mail.translation_zh), 'plain-reading'));
        else if (mail.translation_state === 'ready') entry.append(el('p', '邮件没有可显示的文字正文。', 'muted'));
        else if (mail.translation_state === 'translating') entry.append(el('p', '正在翻译成中文…', 'muted'));
        else entry.append(el('p', '中文翻译暂未完成。', 'inline-error'), button('重试翻译', () => loadGmail(ctx, true), 'quiet'));
        if (mail.from) entry.append(el('p', `发件人：${text(mail.from)}`, 'artifact-note'));
        if (mail.attachments?.length) entry.append(el('p', `附件：${mail.attachments.map(a=>text(a.filename)).join('、')}`, 'artifact-note'));
        const source = link('在 Gmail 查看原文 ↗', mail.url); if (source) entry.append(source); host.append(entry);
        if (mail.body_truncated) entry.append(el('p','邮件内容较长，可在 Gmail 查看完整原文和附件。','artifact-note'));
      }
    } catch (error) { if (S.detail === ctx) ctx.gmailMessages.replaceChildren(el('h2', 'Gmail 邮件往来'), el('p', `邮件暂不可读取：${error.message}`, 'artifact-note'), button('重试读取邮件', () => loadGmail(ctx), 'quiet')); }
    finally { ctx.gmailBusy = false; }
  }
  async function openGmailComposer(ctx, source = null) {
    if (ctx.composer) {
      if (source) ctx.composer.useSource(source);
      ctx.composerHost.scrollIntoView?.({behavior:'smooth',block:'start'}); return;
    }
    const host = ctx.composerHost; host.replaceChildren(el('p', '正在打开邮件草稿…', 'muted'));
    try {
      const initial = await api(`/api/desk/gmail/draft?object_id=${encodeURIComponent(ctx.object.id)}`);
      if (S.detail !== ctx) return;
      const state = {draft:initial, dirty:false, editSeq:0, saving:Promise.resolve(), timer:null};
      const editState = {dirty:false}; S.edits.set(`gmail:${ctx.object.id}`, editState);
      const body = el('div', undefined, 'mail-composer'), editor = el('div', undefined, 'mail-editor'), preview = el('div', undefined, 'mail-review');
      const feedback = el('p', '', 'mail-compose-feedback'), head = el('div', undefined, 'mail-compose-head');
      head.append(el('div', '给客户写邮件', 'mail-compose-title'), el('span', '草稿保存在本机 · 发送前由你审核', 'mail-compose-caption'));
      body.append(head, editor, preview, feedback); host.replaceChildren(body);
      function fields(draft) {
        editor.replaceChildren(); preview.replaceChildren(); preview.hidden=true;
        editor.append(el('p', `发件邮箱：${draft.account || '尚未连接 Gmail'}`, 'mail-from'));
        const to = addField(editor, '收件人', draft.to), subject = addField(editor, '邮件主题', draft.subject);
        if(draft.thread_id) editor.append(el('p','沿原邮件线程回复；如果修改主题，会作为新邮件发送。','artifact-note'));
        to.type='email';
        const en = addField(editor, '英文正文（发送给客户）', draft.body_en, true, '在这里撰写或从工作成果中采用英文回复');
        const zh = addField(editor, '中文对照（仅供自己审核）', draft.body_zh, true, '填写中文对照，方便审核');
        en.className='mail-body-input'; zh.className='mail-body-input chinese';
        const attachments = el('div', undefined, 'mail-attachments'); editor.append(attachments);
        const grant=el('details',undefined,'mail-grant'),grantBody=el('div'),grantNote=el('p','账号授权失效时，可在这里重新授权发信。邮件仍须在本页审核后手动发送。','artifact-note');
        grant.append(el('summary','Gmail 发信授权'),grantNote,grantBody);
        grantBody.append(button('准备重新授权',async()=>{
          grantBody.replaceChildren(el('p','正在准备 Google 授权…','muted'));
          try{const result=await api('/api/desk/gmail/send-oauth/start',{}),authorize=link('继续 Google 登录并授权 ↗',result.authorization_url);if(!authorize)throw new Error('无法打开 Google 授权。');grantBody.replaceChildren(authorize,el('p','授权完成后返回并刷新工作台。','artifact-note'));}
          catch(error){grantBody.replaceChildren(el('p',error.message,'inline-error'));}
        },'quiet'));editor.append(grant);
        const row = el('div', undefined, 'mail-compose-actions'), saveButton = button('保存草稿', async()=>{await save();feedback.textContent='草稿已保存。';}, 'quiet');
        const reviewButton = button('查看并审核', async()=>{
          reviewButton.disabled=true;
          try {
            await save(); const d=state.draft;
            if (!d.to.trim() || !d.subject.trim() || !d.body_en.trim()) throw new Error('请先填写收件人、主题和英文正文。');
            review(d); editor.hidden=true; preview.hidden=false; feedback.textContent='请检查完整内容和附件，确认后才会发送。';
          } catch(error) { feedback.textContent=error.message; } finally { reviewButton.disabled=false; }
        }, 'primary');
        row.append(saveButton,reviewButton); editor.append(row);
        for (const input of [to,subject,en,zh]) input.addEventListener('input',()=>{
          state.dirty=true; editState.dirty=true; state.editSeq++; feedback.textContent='正在保存草稿…';
          clearTimeout(state.timer); state.timer=setTimeout(()=>save().catch(error=>{feedback.textContent=error.message;}),900);
        });
        async function save() {
          clearTimeout(state.timer);
          state.saving = state.saving.catch(()=>{}).then(async()=>{
            while(state.dirty) {
              const seq=state.editSeq, snapshot={to:to.value.trim(),subject:subject.value.trim(),body_en:en.value,body_zh:zh.value};
              const saved=await api('/api/desk/gmail/draft',{object_id:ctx.object.id,version:state.draft.version,fields:snapshot});
              state.draft={...state.draft,...saved}; if(seq===state.editSeq){state.dirty=false;editState.dirty=false;feedback.textContent='草稿已保存';}
            }
          });
          return state.saving;
        }
        function attachmentLinks(box, draft, removable) {
          if (!draft.attachments?.length) {box.append(el('p','尚未添加附件','muted'));return;}
          for(const item of draft.attachments) {
            const line=el('div',undefined,'mail-attachment');
            const href=`/api/desk/gmail/attachment?object_id=${encodeURIComponent(ctx.object.id)}&id=${encodeURIComponent(item.id)}`;
            const view=link(`${item.name} · ${(item.size/1024/1024).toFixed(2)} MB ↗`,href); if(view)line.append(view);
            if(removable)line.append(button('移除',async()=>{try{await save();state.draft={...state.draft,...await api('/api/desk/gmail/attachment/remove',{object_id:ctx.object.id,version:state.draft.version,attachment_id:item.id})};drawAttachments();}catch(error){feedback.textContent=error.message;}},'quiet'));
            box.append(line);
          }
        }
        function drawAttachments() {
          attachments.replaceChildren(el('h3','附件')); attachmentLinks(attachments,state.draft,true);
          const controls=el('div',undefined,'mail-attachment-controls');
          const uploadLabel=el('label','添加本地文件','mail-upload'), upload=el('input'); upload.type='file'; upload.multiple=true; upload.setAttribute('aria-label','添加本地附件'); uploadLabel.append(upload); controls.append(uploadLabel);
          upload.addEventListener('change',async()=>{
            try {
              await save(); const selected=Array.from(upload.files || []);
              for(const file of selected) {
                if(file.size>18*1024*1024)throw new Error('附件合计请控制在 18 MB 以内。');
                const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('附件读取失败。'));reader.readAsDataURL(file);});
                state.draft={...state.draft,...await api('/api/desk/gmail/attachment',{object_id:ctx.object.id,version:state.draft.version,filename:file.name,data})};
              }
              feedback.textContent='附件已添加，请在审核时打开检查。';drawAttachments();
            } catch(error) {feedback.textContent=error.message;} finally {upload.value='';}
          });
          const materials=el('details',undefined,'mail-material-picker'); materials.append(el('summary','从资料包选择'));
          const materialList=el('div'); materials.append(materialList);
          materials.addEventListener('toggle',async()=>{
            if(!materials.open || materials.loaded)return; materials.loaded=true; materialList.replaceChildren(el('p','正在读取资料…','muted'));
            try {
              const result=await api('/api/library'); materialList.replaceChildren();
              const search=el('input');search.placeholder='搜索资料名称';search.setAttribute('aria-label','搜索附件资料');materialList.append(search);
              const list=el('div',undefined,'mail-material-list');materialList.append(list);
              function draw(){list.replaceChildren();const items=(result.items || []).filter(item=>`${item.title} ${item.path}`.toLowerCase().includes(search.value.toLowerCase()));
                if(!items.length)list.append(el('p','没有匹配资料','muted'));
                for(const item of items)list.append(button(`＋ ${item.title}`,async()=>{try{await save();state.draft={...state.draft,...await api('/api/desk/gmail/attachment',{object_id:ctx.object.id,version:state.draft.version,resource_id:item.id})};feedback.textContent='资料已添加，请在审核时打开检查。';drawAttachments();}catch(error){feedback.textContent=error.message;}},'quiet'));
              } search.addEventListener('input',draw);draw();
            } catch(error){materialList.replaceChildren(el('p',error.message,'inline-error'));}
          });
          controls.append(materials);attachments.append(controls);
        }
        function review(d) {
          preview.replaceChildren(el('h3','请审核这封邮件'),el('p',`发件人：${d.account || '未连接'}`),el('p',`收件人：${d.to}`),el('p',`主题：${d.subject}`));
          preview.append(el('h4','中文对照（不会发送）'),el('pre',d.body_zh || '尚未填写中文对照','mail-review-text'),el('h4','英文正文（发送内容）'),el('pre',d.body_en,'mail-review-text'));
          const files=el('div',undefined,'mail-review-files');files.append(el('h4','实际附件'));attachmentLinks(files,d,false);preview.append(files);
          if(!d.can_send)preview.append(el('p','当前邮箱尚未具备可用的发送授权，请返回修改并打开“Gmail 发信授权”。','inline-error'));
          const actions=el('div',undefined,'mail-compose-actions');
          actions.append(button('返回修改',()=>{preview.hidden=true;editor.hidden=false;feedback.textContent='可继续修改草稿。';},'quiet'));
          const sendButton=button('确认发送这封邮件',async()=>{
            sendButton.disabled=true;feedback.textContent='正在发送，请稍候…';
            try {state.draft={...state.draft,...await api('/api/desk/gmail/send',{object_id:ctx.object.id,version:state.draft.version})};drawResult();ctx.gmailStamp=null;await loadGmail(ctx);}
            catch(error){
              try{const latest=await api(`/api/desk/gmail/draft?object_id=${encodeURIComponent(ctx.object.id)}`);if(latest.status!=='draft'){state.draft={...state.draft,...latest};drawResult();return;}}catch{}
              feedback.textContent=error.message;sendButton.disabled=false;
            }
          },'primary'); sendButton.disabled=!d.can_send;actions.append(sendButton);preview.append(actions);
        }
        ctx.composer.useSource=source=>{
          if(en.value.trim() || zh.value.trim()){feedback.textContent='草稿已有正文，请先处理现有内容，再采用其他成果。';return;}
          en.value=source.en || '';zh.value=source.zh || '';if(source.subject && !subject.value.trim())subject.value=source.subject;
          state.dirty=true;editState.dirty=true;state.editSeq++;feedback.textContent='已带入成果，请检查并保存。';en.focus();
        };
        drawAttachments();
      }
      function drawResult() {
        const d=state.draft; editor.hidden=true;preview.hidden=false;preview.replaceChildren();
        if(d.status==='sent') {
          preview.append(el('h3','邮件已由 Gmail 接收'),el('p',`收件人：${d.to} · ${time(d.sent_at)}`),el('p',`主题：${d.subject}`));
          if(d.sync_note)preview.append(el('p',d.sync_note,'inline-error'));
          const original=link('在 Gmail 查看已发送邮件 ↗',d.gmail_url);if(original)preview.append(original);
          preview.append(button('写下一封',async()=>{try{state.draft={...state.draft,...await api('/api/desk/gmail/draft/new',{object_id:ctx.object.id})};editor.hidden=false;fields(state.draft);feedback.textContent='';}catch(error){feedback.textContent=error.message;}},'primary'));
          feedback.textContent='发送结果已记录，客户后续回复会继续同步。';
        } else {
          preview.append(el('h3','发送结果尚未确认'),el('p',d.error || '请先核对 Gmail 已发送邮件。','inline-error'));
          preview.append(button('核对发送结果',async()=>{try{state.draft={...state.draft,...await api('/api/desk/gmail/reconcile',{object_id:ctx.object.id})};drawResult();if(state.draft.status==='sent'){ctx.gmailStamp=null;await loadGmail(ctx);}}catch(error){feedback.textContent=error.message;}},'primary'));
          const sent=link('打开 Gmail 已发送邮件 ↗',`https://mail.google.com/mail/u/?authuser=${encodeURIComponent(d.account || '')}#sent`);if(sent)preview.append(sent);
          if(d.status==='unknown')preview.append(button('我已确认未发送，恢复草稿',async()=>{try{state.draft={...state.draft,...await api('/api/desk/gmail/resume-unsent',{object_id:ctx.object.id,confirmed_not_sent:true})};editor.hidden=false;fields(state.draft);feedback.textContent='草稿已恢复，请重新审核。';}catch(error){feedback.textContent=error.message;}},'quiet'));
          feedback.textContent='核对结果前不能重复发送。';
        }
      }
      ctx.composer={useSource:()=>{}};
      if(initial.status==='draft'){fields(initial);if(source)ctx.composer.useSource(source);}else drawResult();
      host.scrollIntoView?.({behavior:'smooth',block:'start'});
    } catch(error){host.replaceChildren(el('p',`草稿暂时打不开：${error.message}`,'inline-error'));}
  }
  function renderConversation(ctx) {
    if (!ctx.conversationMessages) return;
    const rows = Array.isArray(ctx.profile?.conversation) ? ctx.profile.conversation : ctx.object.conversation || [];
    ctx.conversationMessages.replaceChildren();
    for (const message of rows) {
      const entry = el('article');
      entry.append(el('h3', `${['buyer','customer','visitor'].includes(message.sender) ? '客户' : ['sales','seller','admin','staff','assistant','us'].includes(message.sender) ? '我方' : text(message.sender) || '来源未标明'} · ${text(message.sent_at)}`));
      if (message.translation_zh) entry.append(el('h4', '中文译文'), el('pre', text(message.translation_zh), 'plain-reading'));
      else entry.append(el('p', message.translation_stale ? '原文已变化，请使用“翻译并分析原文”更新中文对照。' : '尚无中文对照，请使用需求解读中的翻译分析按钮。', 'artifact-note'));
      entry.append(el('h4', '原文'), el('pre', text(message.body), 'source-body'));
      ctx.conversationMessages.append(entry);
    }
  }
  async function loadProfile(ctx) {
    try { const value = await api(`/api/desk/customer-profile?object_id=${encodeURIComponent(ctx.object.id)}`); if (S.detail !== ctx || ctx.profileEditing || ctx.workflowEditing) return; ctx.profile = value.profile || value; ctx.lastProfileRefresh=Date.now(); if (ctx.summaryParagraph) ctx.summaryParagraph.textContent = ctx.profile.cleaned?.need || '原始需求在下方，可生成中文解读。'; renderProfile(ctx); renderConversation(ctx); }
    catch (error) { if (S.detail === ctx) ctx.profileHost.replaceChildren(el('h2', '需求解读与处理'), el('p', error.message, 'inline-error')); }
  }
  function renderProfile(ctx) {
    const profile = ctx.profile, host = ctx.profileHost; host.replaceChildren(el('h2', '询盘简报')); const provenance = profile.provenance || {}, analysis = profile.analysis || {}, cleaned = profile.cleaned || {};
    if (profile.workflow?.bucket === 'history') host.append(el('p', '历史复盘 · 保留原始记录，不视为当前新询盘', 'eyebrow'));
    if (replyNotice(profile.workflow)) host.append(el('p', `${replyNotice(profile.workflow)}，请查看下方往来。`, 'mail-attention'));
    const waitingForCustomer = profile.workflow?.state === 'waiting_customer';
    const brief = el('section', undefined, 'inquiry-brief'); brief.append(el('p', analysis.brief || analysis.intent && analysis.intent !== 'unknown' && analysis.intent || '先读清客户本次需求，再确定回复与推进动作。', 'brief-judgment'), el('h3', '核心需求'), el('p', analysis.core_need || cleaned.need || '尚未整理，可读取下方原文或生成解读。'));
    if (analysis.fit && analysis.fit !== 'unknown') brief.append(el('h3', '我们怎么承接'), el('p', text(analysis.fit), 'brief-fit'));
    const questions = analysis.questions_now || []; if (!waitingForCustomer && !profile.workflow?.gmail_reply_pending && questions.length) listText(brief, '现在需要问清', questions.slice(0,3));
    brief.append(el('p', `下一步：${profile.workflow?.next_action || analysis.next_action || '阅读原文并确定本次动作'}`, 'next-action'));
    if (!waitingForCustomer && !profile.workflow?.gmail_reply_pending && analysis.recommended_reply) { const value = text(analysis.recommended_reply), reply = el('section', undefined, 'brief-reply'); reply.append(el('h3', '建议回复'), el('p', value.length > 260 ? `${value.slice(0,260)}…` : value)); if (value.length > 260) { const full = el('details'); full.append(el('summary', '查看完整建议回复'), el('pre', value, 'plain-reading')); reply.append(full); } brief.append(reply); }
    if (profile.operator_context) { const context = el('details', undefined, 'operator-context'); context.append(el('summary', '业务补充说明'), el('p', text(profile.operator_context))); brief.append(context); } host.append(brief); workflowEditor(ctx, host);
    const actions = el('div', undefined, 'profile-actions'), analyse = button('翻译并分析原始需求', async () => {
      analyse.disabled = true;
      try { const job = jobResult(await api('/api/desk/jobs', { object_id: ctx.object.id, mode: 'customer_analysis', instruction: '保留原始需求，用中文逐段翻译并提取公司、国家、数量、具体需求；给出秘书式一句业务判断、核心需求、次要或后续事项、冲突字段取舍、建议回复、最多三个当前关键问题与下一步。严格区分工厂已知能力和本次具体开发参数，不把后续泛化需求当本次前置条件，不将表单必填数量自动视为确认订单量；订单买家记录不能当成新询盘。不推测客户价值分数，不编造或发送消息。' })); upsertJob(job); renderJob(ctx); toast('已交给 Sol 翻译并分析，完成后解读回到此处。'); }
      catch (error) { toast(error.message); } finally { analyse.disabled = jobsFor(ctx.object.id).some(isActive); }
    }, 'primary'); analyse.disabled = jobsFor(ctx.object.id).some(isActive); actions.append(analyse, button('编辑解读与分析', () => editProfile(ctx)), button('重读解读', () => loadProfile(ctx), 'quiet')); host.append(actions); const sourceNotes = [...new Set([provenance.evidence_notes, provenance.source_verification?.note].filter(Boolean).map(text))]; if (sourceNotes.length || provenance.source) { const source = el('details', undefined, 'source-note'); source.append(el('summary', '来源记录')); if (provenance.source) source.append(el('p', text(provenance.source), 'object-source')); sourceNotes.forEach(note => source.append(el('p', note, 'artifact-note'))); host.append(source); }
    const comparison = el('div', undefined, 'bilingual-grid'), zh = el('section'), original = el('details'); zh.append(el('h3', '中文译文 / 解读'), el('pre', profile.translation_zh || '尚未生成中文解读。可以翻译分析原文，也可以按已知事实手工补充。', 'plain-reading')); original.append(el('summary', '原始需求 · 保留原稿'), el('pre', profile.original_text || '原记录未提供正文', 'plain-reading')); comparison.append(zh, original); host.append(comparison);
    const requirements = el('dl', undefined, 'object-facts'); for (const [key, label] of [['company', '公司 / 对象'], ['contact_name', '联系人'], ['email', '邮箱'], ['country', '国家 / 市场'], ['quantity', '数量']]) if (cleaned[key]) requirements.append(el('dt', label), el('dd', displayText(cleaned[key]))); if (requirements.children.length) host.append(requirements);
    const grid = el('div', undefined, 'analysis-grid'); listText(grid, '需求与意向', analysis.intent === 'unknown' ? [] : analysis.intent); listText(grid, '产品适配', analysis.fit === 'unknown' ? [] : analysis.fit); if (!analysis.brief && !analysis.core_need) host.append(grid);
    const recommendations = analysis.recommendations || [], recommendationBox = el('div', undefined, 'recommendations'); let expanded = false;
    function renderRecommendations() { recommendationBox.replaceChildren(); listText(recommendationBox, '建议行动', recommendations.slice(0, expanded ? recommendations.length : 3)); if (recommendations.length > 3) recommendationBox.append(button(expanded ? '收起建议' : `展开全部 ${recommendations.length} 条建议`, () => { expanded = !expanded; renderRecommendations(); }, 'quiet')); }
    if (recommendations.length) { renderRecommendations(); host.append(recommendationBox); }
    const folders = el('div', undefined, 'analysis-folders'); for (const [label, values] of [['适配依据', analysis.basis], ['信息缺口', analysis.missing], ['已知事实', analysis.facts], ['待核推断', analysis.inferences], ['后续事项', analysis.secondary_requests], ['冲突字段与取舍', analysis.conflicts]].filter(([, values], index) => ((!analysis.brief && !analysis.core_need) && index < 4) || values?.length)) { const detail = el('details'); detail.append(el('summary', `${label}${values?.length ? ` · ${values.length} 条` : ''}`)); if (values?.length) { const list = el('ul'); values.forEach(value => list.append(el('li', displayText(value)))); detail.append(list); } else detail.append(el('p', '尚未取得依据', 'muted')); folders.append(detail); } host.append(folders, button('把缺口或下一步转为研究任务', () => analysisToResearch(ctx), 'quiet'));

  }
  function analysisToResearch(ctx) {
    const profile = ctx.profile, analysis = profile.analysis || {}, dialog = el('dialog', undefined, 'desk-modal intake-dialog'); dialog.append(el('h2', '将分析接到一项研究工作'), el('p', '关联当前来源与分析，补齐需要的证据；不自动外发或认定客户意向。', 'agent-copy')); const form = el('div', undefined, 'profile-form'), title = addField(form, '研究任务名称', `为${ctx.object.title}补充需求与适配依据`), target = addField(form, '需要研究的问题', [analysis.next_action, ...(analysis.missing || [])].filter(Boolean).join('\n'), true), feedback = el('p', '', 'agent-feedback'); const save = button('保存研究任务并打开', async () => {
      if (!title.value.trim() || !target.value.trim()) { feedback.textContent = '请写清研究名称和这次需要补齐的问题。'; return; } save.disabled = true;
      try { const inherited = Array.isArray(profile.provenance?.evidence) ? profile.provenance.evidence : []; const evidence = inherited.length ? inherited : [{ text: `源于当前对象 ${ctx.object.id} 的原文与分析；来源尚需核实。`, ...(profile.provenance?.observed_at ? { observed_at: profile.provenance.observed_at } : {}) }]; const result = await api('/api/desk/discovery', { kind: 'research_task', title: title.value, target: target.value, next_action: analysis.next_action || '', origin_object_id: ctx.object.id, evidence, status: '研究准备' }); const item = result.item || result; dialog.close(); location.hash = `/customers?view=development&item=${encodeURIComponent(item.id)}`; }
      catch (error) { feedback.textContent = error.message; save.disabled = false; }
    }, 'primary'); dialog.append(form, feedback, save, button('取消', () => dialog.close(), 'quiet')); document.body.append(dialog); dialog.addEventListener('close', () => dialog.remove()); dialog.showModal();
  }
  function editProfile(ctx) {
    ctx.profileEditing = true; const p = ctx.profile, host = ctx.profileHost, form = el('div', undefined, 'profile-form'); host.replaceChildren(el('h2', '编辑中文解读与处理依据')); const translation = addField(form, '中文译文 / 解读', p.translation_zh, true), company = addField(form, '公司 / 对象', p.cleaned?.company), country = addField(form, '国家 / 市场', p.cleaned?.country), quantity = addField(form, '数量', p.cleaned?.quantity), need = addField(form, '具体需求', p.cleaned?.need, true), fit = addField(form, '产品适配（只写有依据的判断）', p.analysis?.fit === 'unknown' ? '' : p.analysis?.fit, true), basis = addField(form, '适配依据（每行一条）', (p.analysis?.basis || []).join('\n'), true), missing = addField(form, '信息缺口（每行一条）', (p.analysis?.missing || []).join('\n'), true), next = addField(form, '下一步', p.analysis?.next_action, true), sourceNote = addField(form, '来源核验备注', p.provenance?.evidence_notes, true); const message = el('p', '', 'agent-feedback');
    const lines = input => input.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
    form.append(message, button('保存中文解读与分析', async () => { try { await api('/api/desk/customer-profile', { object_id: ctx.object.id, source_hash: p.source_hash || p.provenance?.source_hash, translation_zh: translation.value, original_language: p.original_language || 'unknown', cleaned: { ...p.cleaned, company: company.value, country: country.value, quantity: quantity.value, need: need.value }, analysis: { ...p.analysis, fit: fit.value || 'unknown', basis: lines(basis), missing: lines(missing), next_action: next.value }, source_note: sourceNote.value }); ctx.profileEditing = false; await loadProfile(ctx); toast('中文解读与分析已保存，原始需求未改动。'); } catch (error) { message.textContent = error.message; } }, 'primary'), button('返回阅读（不保存本次编辑）', () => { ctx.profileEditing = false; renderProfile(ctx); }, 'quiet')); host.append(form);
  }
  function customerStage(item, activity) {
    const flow = item.workflow || {}, state = text(flow.state), status = text(item.contact_status_label);
    if (flow.gmail_reply_pending || flow.customer_reply_pending || item.gmail_reply_pending) return 'action';
    if (['won', 'lost', 'archived'].includes(state) || /已结束|不再推进|停止联系/.test(status)) return 'ended';
    if (activity?.group === 'act' || activity?.group === 'decide') return 'action';
    if (state === 'waiting_customer' || activity?.kind === 'customer_waiting') return 'waiting';
    if ((flow.configured || item.kind === 'inquiry') && state && state !== 'waiting_customer') return 'action';
    if (/待审核|待回复|收到.*回复|客户.*新.*(?:信|回复)|准备回复/.test(status)) return 'action';
    if (/等待|等客户|已联系|已发|已回复/.test(status) || /等待.*回复|等客户/.test(text(item.next_action))) return 'waiting';
    return 'prospect';
  }
  function customerStageLabel(stage, item) {
    if (item.gmail_reply_pending || item.workflow?.gmail_reply_pending || item.workflow?.customer_reply_pending) return '有新回复';
    return ({action:'待我处理', waiting:'等待客户', prospect:'待开发', ended:'已结束'})[stage] || '待开发';
  }
  function customerInquiry(row) {
    const summary = row.business_summary || {}, flow = row.workflow || {};
    return {id:row.object_id, object_id:row.object_id, kind:'inquiry', title:row.title,
      business_category:row.source_type === 'website' ? '网站询盘' : '客户询盘', business_summary:summary.core_need || summary.headline || row.analysis?.core_need || '',
      contact_status_label:flow.state_label || '', next_action:summary.next_action || flow.next_action || '',
      workflow:flow, updated_at:flow.updated_at || row.received_at, source_type:row.source_type};
  }
  async function renderDevelopment() {
    const page = $('page'), routeSerial = S.loadSerial; const current = () => S.page === 'customers' && routeSerial === S.loadSerial && parseRoute().query.get('view') !== 'inquiries'; page.replaceChildren(heading('客户工作台', '客户与机会', '先看需要处理的事，再继续开发目标客群。'), customerTabs('development')); const target = el('details', undefined, 'card discovery-target'); target.append(el('summary', '新建买家研究任务')); const form = el('div', undefined, 'discovery-target-form'), title = addField(form, '研究任务名称', '', false, '例如：为一组产品寻找匹配的买家'), audience = addField(form, '目标客群与研究要求', '', true, '说明市场、买家业务、产品适配与需要核查的证据'); const feedback = el('p', '', 'agent-feedback'), inbox = el('section'), tasks = el('section'), candidates = el('section'), detail = el('section'), sync = el('div', undefined, 'customer-sync'); target.append(form, feedback, button('保存研究任务', async () => { if (!title.value.trim() || !audience.value.trim()) { feedback.textContent = '请先写清任务名称和目标客群。'; return; } try { const result = await api('/api/desk/discovery', { kind: 'research_task', title: title.value, target: audience.value, status: '研究准备' }); await read(); await openItem((result.item || result).id); } catch (error) { feedback.textContent = error.message; } }, 'primary')); page.append(sync, inbox, candidates, tasks, target, detail);
    async function openItem(id) {
      const result = await api(`/api/desk/discovery/item?id=${encodeURIComponent(id)}`); if (!current()) return; const item = result.item || result; const route = parseRoute(), artifact = route.query.get('item') === String(item.id) ? route.query.get('artifact') : null; history.replaceState(null, '', `#/customers?view=development&item=${encodeURIComponent(item.id)}${artifact ? `&artifact=${encodeURIComponent(artifact)}` : ''}`); target.hidden = true; inbox.hidden = true; tasks.hidden = true; candidates.hidden = true; searchPanel.hidden = true; sync.hidden = true; detail.replaceChildren(button('← 返回客户开发列表', () => { location.hash = '/customers?view=development'; }, 'quiet back-development'));
      const layout = el('div', undefined, 'object-layout discovery-detail'), main = el('div', undefined, 'card'), right = el('aside', undefined, 'card object-agent'); main.append(el('h2', item.title || item.company || '研究记录'), el('p', item.kind === 'research_task' ? '研究任务' : item.business_category || '待确认业务类型', 'provenance-note'));
      if (item.kind === 'candidate') {
        const prior = item.source_record?.analysis || {}, summary = el('section', undefined, 'candidate-summary');
        summary.append(el('h3', '买家摘要'), el('p', item.business_summary || '尚无可展示的业务摘要。'));
        summary.append(el('p', `联系状态：${item.contact_status_label || '尚未核实联系状态'}`), el('p', `下一步：${item.next_action || '补充推进安排'}`, 'candidate-next-action'));
        main.append(summary);
        const contacts = item.source_record?.contacts || [], site = link('访问公司网站 ↗', item.website); if (contacts.length || site || item.contact_name || item.email || item.phone) { const contactBox = el('section', undefined, 'candidate-contacts'); contactBox.append(el('h3', '联系方式')); if (site) contactBox.append(site); for (const [label,value] of [['联系人',item.contact_name],['邮箱',item.email],['电话',item.phone]]) if(value)contactBox.append(el('p',`${label}：${text(value)}`)); for (const contact of contacts) { const value = typeof contact === 'string' ? contact : contact.value; if (!value) continue; const kind = typeof contact === 'object' ? text(contact.kind).toLowerCase() : ''; const label = ({email:'邮箱',phone:'电话',telephone:'电话',whatsapp:'WhatsApp',wechat:'微信'})[kind] || '联系'; contactBox.append(el('p', `${label}：${text(value)}`)); } main.append(contactBox); }
      }
      const edit = el('div', undefined, 'profile-form'), company = addField(edit, '公司', item.company), website = item.kind === 'candidate' ? addField(edit, '公司网站', item.website) : null, country = item.kind === 'candidate' ? addField(edit, '国家或市场', item.country || item.market_hint) : null, contactName = item.kind === 'candidate' ? addField(edit, '联系人', item.contact_name) : null, email = item.kind === 'candidate' ? addField(edit, '邮箱', item.email) : null, phone = item.kind === 'candidate' ? addField(edit, '电话', item.phone) : null, businessSummary = item.kind === 'candidate' ? addField(edit, '业务摘要', item.business_summary, true) : null, category = item.kind === 'candidate' ? addField(edit, '买家类型', item.business_category) : null, contactStatus = item.kind === 'candidate' ? addField(edit, '联系状态', item.contact_status_label) : null, priority = item.kind === 'candidate' ? selectField(edit, '开发优先级', [['high','优先'],['normal','正常'],['low','稍后']], item.priority || 'normal') : null, aim = addField(edit, item.kind === 'candidate' ? '研究问题' : '目标客群 / 适配问题', item.target, true), notes = addField(edit, '研究记录', item.notes, true), next = addField(edit, '下一步', item.next_action, true), evidence = addField(edit, '新增来源网址（每行一条）', '', true), evidenceText = addField(edit, '新增证据说明', '', true); const editDetails=el('details'); editDetails.append(el('summary','编辑客户资料'),edit); main.append(editDetails);
      const proof = el('div', undefined, 'candidate-evidence'); proof.append(el('h3', '已有候选证据')); for (const value of item.evidence || []) { const row = el('div'); row.append(el('p', value.text || '来源说明未提供')); const a = link('查看来源', value.url); if (a) row.append(a); if (value.observed_at) row.append(el('small', `记录时间 ${time(value.observed_at)}`)); proof.append(row); } if (!(item.evidence || []).length) proof.append(el('p', '尚未登记可核来源，不把研究结论当作已证实事实。', 'muted')); const proofDetails=el('details'); proofDetails.append(el('summary','参考资料'),proof); main.append(proofDetails);
      async function save(promote = false, selectedEvidence = []) { const additions = evidence.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean).map(url => ({ url, text: evidenceText.value, observed_at: new Date().toISOString() })); const value = await api('/api/desk/discovery/update', { id: item.id, company: company.value, ...(item.kind === 'candidate' ? {title:company.value,website:website.value,country:country.value,contact_name:contactName.value,email:email.value,phone:phone.value,business_summary:businessSummary.value,business_category:category.value,contact_status_label:contactStatus.value,priority:priority.value} : {}), target: aim.value, notes: notes.value, next_action: next.value, evidence: [...(item.evidence || []), ...additions, ...selectedEvidence], ...(promote ? { status: '推进准备', ready_for_customer: true } : {}) }); toast(promote ? '已标记推进准备。' : '客户资料已保存。'); await read(); await openItem((value.item || value).id || item.id); }
      edit.append(button(item.kind === 'candidate' ? '保存客户资料' : '保存研究任务', () => save(), 'primary')); if (item.kind === 'candidate') main.append(button('标记进入推进准备', () => save(true)));
      if (item.kind === 'candidate') {
        const lookup=el('section',undefined,'candidate-lookup'), results=el('div'), status=el('p','','agent-feedback');
        const findSite=button('查找公司官网',async()=>{
          findSite.disabled=true; status.textContent='正在查找公开来源…'; results.replaceChildren();
          try {
            const found=await api('/api/desk/company-lookup',{object_id:item.object_id || `prospect:${item.id}`});
            if(!current() || S.detail?.object?.id !== (item.object_id || `prospect:${item.id}`))return;
            if(!found.candidates?.length) {
              const problem=(found.attempts || []).find(x=>x.error)?.error;
              status.textContent=found.status==='not_found' ? '暂未找到公司官网，可通过搜索继续查找。' : `官网查询暂未完成${problem ? '：'+problem : '。'}`;
              const manual=link('打开公开搜索 ↗',found.manual_search_url); if(manual)results.append(manual); return;
            }
            status.textContent='找到以下网址，请根据公司业务选择。';
            for(const candidate of found.candidates) {
              const row=el('article',undefined,'card'), site=link(candidate.website,candidate.website), source=link('查看资料来源 ↗',candidate.source_url);
              if(site)row.append(site); if(source)row.append(source);
              const choose=button('使用这个官网',async()=>{
                choose.disabled=true; website.value=candidate.website;
                try { const evidenceRow=candidate.source_url ? [{url:candidate.source_url,text:`官网发现来源：${text(candidate.source_title || '')} ${text(candidate.evidence || '')}`.trim(),observed_at:found.checked_at || new Date().toISOString()}] : []; await save(false,evidenceRow); }
                catch(error) {status.textContent=error.message;choose.disabled=false;}
              },'quiet'); row.append(choose); results.append(row);
            }
          } catch(error) {status.textContent=error.message;} finally {findSite.disabled=false;}
        },'quiet');
        lookup.append(el('h3','公司官网'),el('p','按公司名称查找公开网址，结果可用于后续买家研究。每次查询使用现有搜索额度。'),findSite,status,results); main.append(lookup);
      }
      const object = { id: item.object_id || `prospect:${item.id}`, kind: 'prospect', title: item.title || item.company, source: item.source, assets: [] }, artifactSection = el('section', undefined, 'card'); artifactSection.append(el('h2', '研究成果')); const tabs = el('div', undefined, 'artifact-tabs'), editor = el('div'); artifactSection.append(tabs, editor); const ctx = { object, right, tabs, editor, artifacts: [], selectedId: null, requestedArtifact: parseRoute().query.get('artifact') }; S.detail = ctx; buildAgent(ctx); ctx.instruction.placeholder = '说明希望核查哪些候选、哪类来源、哪些适配问题。'; ctx.right.querySelector('h2').textContent = '交给 Sol 研究'; ctx.right.querySelector('.agent-copy').textContent = '围绕当前客户，整理资料、分析需求和准备回复。'; ctx.instruction.value = item.kind === 'candidate' ? '请先读取当前候选的既有初筛、来源证据和原CRM关联，核对已发送、退信及停止联系状态，避免重复开发；再根据明确缺口调用业务工具 research_company 读取候选公司官网；用中文整理业务类型、产品与采购适配依据、来源网址、待核信息及下一步。工具无法读取的来源明确列为缺口，不编造联系方式、采购意向或已联系记录，不发送消息。' : `请执行当前研究任务：${item.title || ''}。\n研究目标：${item.target || '请按记录中的明确目标推进'}。\n${item.origin_object_id ? `先读取关联来源对象 ${item.origin_object_id} 的原文及已有资料，再处理本研究目标。` : '先读取当前研究记录与证据，不要把任务强行改成公司官网研究。'}\n用中文完成有依据的分析与可执行改进方案，区分已知事实、推断、缺口和下一步；需要时调用对应业务工具，不自动外发。`; const shortcutBox = ctx.right.querySelector('.agent-shortcuts'); const defaultInstruction = ctx.instruction.value; shortcutBox.replaceChildren(button(item.kind === 'candidate' ? '核对官网与候选证据' : '按当前目标执行研究', () => { ctx.instruction.value = defaultInstruction; ctx.instruction.focus(); }), button(item.kind === 'candidate' ? '整理适配与下一步' : '核对原文与问题依据', () => { ctx.instruction.value = item.kind === 'candidate' ? '请根据当前目标和已有证据，用中文整理供货适配、证据缺口和可执行下一步。需要公司官网证据时调用 research_company，不虚构采购意向。' : `请围绕“${item.target || item.title}”核对关联来源${item.origin_object_id ? `对象 ${item.origin_object_id}` : '记录'}中的原文、事实依据与未解决问题，明确改进方向，不把网站承接或询盘处理任务变成找公司官网。`; ctx.instruction.focus(); })); if(item.kind==='candidate'){mountGmail(ctx,main);main.insertBefore(ctx.gmailHost,editDetails);} layout.append(main, right); detail.append(layout, artifactSection); refreshArtifacts(ctx, true); detail.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
      if (item.kind === 'candidate') {
        ctx.instruction.value = S.instructions.get(String(ctx.object.id)) || '';
        ctx.instruction.placeholder = '例如：看看客户最新回复，准备一份中英对照的邮件草稿。';
        const shortcuts = el('div', undefined, 'candidate-quick-actions');
        shortcuts.append(button('查看资料与回复', () => artifactSection.scrollIntoView?.({behavior:'smooth',block:'start'}), 'quiet'), button('编辑客户资料', () => { editDetails.open = true; editDetails.scrollIntoView?.({behavior:'smooth',block:'start'}); }, 'quiet'));
        main.querySelector('.candidate-summary')?.append(shortcuts);
      }
    }
    function addCandidate() {
      const dialog=el('dialog',undefined,'desk-modal intake-dialog'), form=el('div',undefined,'profile-form'); dialog.append(el('h2','新增目标客户'));
      const company=addField(form,'公司名称'),website=addField(form,'公司网站'),country=addField(form,'国家或市场'),contactName=addField(form,'联系人'),email=addField(form,'邮箱'),phone=addField(form,'电话'),summary=addField(form,'业务摘要','',true),category=addField(form,'买家类型','','','例如：鞋类进口与批发'),status=addField(form,'联系状态','','','例如：未联系'),next=addField(form,'下一步','',true),priority=selectField(form,'开发优先级',[['high','优先'],['normal','正常'],['low','稍后']],'normal'),feedback=el('p','','agent-feedback');
      const save=button('保存客户',async()=>{if(!company.value.trim()){feedback.textContent='请填写公司名称。';return;}save.disabled=true;try{const result=await api('/api/desk/discovery',{kind:'candidate',company:company.value.trim(),website:website.value.trim(),country:country.value.trim(),contact_name:contactName.value.trim(),email:email.value.trim(),phone:phone.value.trim(),market_hint:country.value.trim(),business_summary:summary.value.trim(),business_category:category.value.trim(),contact_status_label:status.value.trim(),next_action:next.value.trim(),priority:priority.value});dialog.close();await read();await openItem((result.item||result).id);}catch(error){feedback.textContent=error.message;save.disabled=false;}},'primary');
      dialog.append(form,feedback,save,button('取消',()=>dialog.close(),'quiet'));document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
    }
    const searchPanel=el('details',undefined,'card customer-search-tool'), searchForm=el('div',undefined,'profile-form'), buyerKeyword=addField(searchForm,'买家搜索关键词','footwear importer'), searchResults=el('div'), searchFeedback=el('p','','agent-feedback');
    searchPanel.append(el('summary','搜索公开买家线索'),el('p','输入鞋类、买家类型或目标市场，选择有价值的公司继续研究。搜索使用现有 Firecrawl 额度。'),searchForm);
    const searchButton=button('搜索买家',async()=>{
      searchButton.disabled=true;searchFeedback.textContent='正在搜索…';searchResults.replaceChildren();
      try {
        const result=await api(`/api/desk/buyer-search?q=${encodeURIComponent(buyerKeyword.value.trim() || 'footwear importer')}`);
        if(['failed','timeout','unavailable'].includes(result.status)) {
          searchFeedback.textContent=result.error || '搜索暂不可用'; const manual=link('打开公开搜索 ↗',result.manual_search_url); if(manual)searchResults.append(manual); return;
        }
        const currentData=await api('/api/desk/discovery');
        searchFeedback.textContent=result.records.length ? `找到 ${result.records.length} 条公开线索，请核对公司名称后添加。` : '没有找到合适结果，可以换一组关键词。';
        for(const buyer of result.records) {
          const row=el('article',undefined,'card work-row'), content=el('div');content.append(el('h3',text(buyer.source_title || buyer.company)),el('p','公开搜索线索，可查看来源并核对公司名称。'));
          const source=link('查看来源 ↗',buyer.source_url);if(source)content.append(source);
          const name=addField(content,'公司名称',buyer.company || '');
          const action=button('加入目标客户',async()=>{
            const selected=name.value.trim();if(!selected){searchFeedback.textContent='请填写公司名称。';return;}
            const prior=(currentData.candidates || []).find(item=>text(item.company).trim().toLowerCase()===selected.toLowerCase());
            if(prior){await openItem(prior.id);return;}action.disabled=true;
            try { const value=await api('/api/desk/discovery',{kind:'candidate',company:selected,business_category:'公开搜索线索',business_summary:'来自公开搜索，下一步了解主营鞋品、销售市场和采购方式。',next_action:'了解主营产品、官网和采购入口。',evidence:buyer.source_url?[{url:buyer.source_url,text:text(buyer.excerpt || '公开搜索结果'),observed_at:new Date().toISOString()}]:[]});await read();await openItem((value.item || value).id); }
            catch(error){action.disabled=false;searchFeedback.textContent=error.message;}
          },'quiet');row.append(content,action);searchResults.append(row);
        }
      }catch(error){searchFeedback.textContent=error.message;}finally{searchButton.disabled=false;}
    },'primary');searchPanel.append(searchButton,searchFeedback,searchResults);page.insertBefore(searchPanel,candidates);
    let candidateQuery = '', candidateCategory = '', candidateStatus = 'active';
    async function read() {
      try { const data = await api('/api/desk/discovery'); if (!current()) return;
        const extra = await Promise.allSettled([api('/api/desk/today'), api('/api/desk/inquiry-queue?bucket=active')]); if (!current()) return;
        const today = extra[0].status === 'fulfilled' ? extra[0].value : {}, queue = extra[1].status === 'fulfilled' ? extra[1].value : {};
        const activities = new Map(); for (const group of ['watch','act','decide']) for (const item of today.groups?.[group] || []) if (item.object_id) activities.set(item.object_id, {...item,group});
        const allCustomers = [...(data.candidates || []), ...(queue.items || []).map(customerInquiry)];
        tasks.replaceChildren(); candidates.replaceChildren();
        if (extra[1].status !== 'fulfilled') candidates.append(el('p','网站询盘暂未读取，以下先显示已有目标客户。','inline-error'));
        if (extra[0].status !== 'fulfilled') candidates.append(el('p','部分待办状态暂未读取，请稍后刷新。','inline-error'));
        api('/api/desk/gmail/candidates').then(mail=>{
          if(!current())return;
          const gmailStatus = mail.status || {}, lastMail = gmailStatus.last_success_at ? ` · 最近检查 ${time(gmailStatus.last_success_at)}` : '';
          const source = el('div', undefined, 'sync-status-line');
          source.append(el('span', '', `sync-indicator ${gmailStatus.state === 'ready' ? 'online' : ''}`), el('span', gmailStatus.state === 'ready' ? `Gmail 已连接 · 运行时约每 2 分钟检查${lastMail}` : gmailStatus.state === 'loading' ? 'Gmail 正在检查来信' : gmailStatus.state === 'error' ? 'Gmail 暂未同步，请检查连接' : 'Gmail 尚未连接'));
          const website = S.websiteStatus || {}; const webText = website.observed_at ? `网站询盘 · 页面打开时约 2 分钟刷新 · 最近读取 ${time(website.observed_at)}` : '网站询盘 · 正在读取';
          sync.replaceChildren(source,el('span',webText,'sync-website'),el('span','邮件发送前在 Gmail 审核','sync-review'));
          const known=new Set((data.candidates||[]).flatMap(item=>[item.email,...(item.source_record?.contacts||[]).filter(c=>c?.kind==='email').map(c=>c.value)]).filter(Boolean).map(v=>text(v).trim().toLowerCase()));
          const rows=(mail.items||[]).filter(item=>!known.has(text(item.email).trim().toLowerCase()));inbox.replaceChildren();
          if(mail.status?.state==='error'){inbox.append(el('p','Gmail 新买家邮件筛选暂未完成，请检查邮箱连接。','inline-error'));return;}
          if(mail.status?.state==='loading'){inbox.append(el('p','正在筛选 Gmail 来信，请稍候。','muted'));return;}
          if(!rows.length)return;
          const active=rows.filter(item=>item.is_new!==false && item.answered!==true),historical=rows.filter(item=>item.is_new===false || item.answered===true);
          if(active.length)inbox.append(sectionHeading('Gmail 潜在买家来信','筛选出的鞋类采购咨询，加入客户后可继续分析'));
          if(mail.status?.history_limited)inbox.append(el('p','当前检查最近 30 封鞋类关键词邮件，可在 Gmail 查看更早邮件。','artifact-note'));
          const history=el('details',undefined,'card');if(historical.length)history.append(el('summary',`历史买家邮件 · ${historical.length} 封`));
          for(const item of [...active,...historical]){
            const card=el('article',undefined,'card work-row'),content=el('div');
            content.append(el('h3',text(item.title)),el('p',text(item.summary)),el('p',`来信邮箱：${text(item.email)} · ${time(item.sent_at)}`));
            if(item.answered===true)content.append(el('p','已在原邮件线程回复。','muted'));
            else if(item.is_new===false)content.append(el('p',item.answered===false?'历史来信，原线程未发现我方回复。':'历史来信，可查看原线程进展。','muted'));
            const original=link('在 Gmail 查看原文 ↗',item.url);if(original)content.append(original);
            const name=addField(content,'公司或联系人',item.title),action=button('加入客户并处理',async()=>{
              if(!name.value.trim())return;action.disabled=true;
              try{const value=await api('/api/desk/discovery',{kind:'candidate',company:name.value.trim(),contact_name:text(item.contact_name),email:text(item.email),business_category:'邮件咨询',business_summary:text(item.summary),contact_status_label:item.is_new===false?'历史来信':'收到邮件',next_action:item.is_new===false?'查看邮件往来与当前进展。':'阅读客户邮件并准备回复。',evidence:item.url?[{url:item.url,text:'Gmail 来信',observed_at:item.sent_at || ''}]:[]});await read();await openItem((value.item||value).id);}
              catch(error){action.disabled=false;toast(error.message);}
            },'primary');const actions=el('div');actions.append(action,button('忽略这封',async()=>{
              try{await api('/api/desk/gmail/candidates/dismiss',{message_id:item.id});await read();}catch(error){toast(error.message);}
            },'quiet'));card.append(content,actions);(historical.includes(item)?history:inbox).append(card);
          }
          if(historical.length)inbox.append(history);
        }).catch(()=>{if(current())sync.replaceChildren(el('span','Gmail 状态暂不可读取。','inline-error'));});
        const taskRows = data.tasks || []; if (taskRows.length) { const box=el('details',undefined,'customer-research'); box.append(el('summary',`研究任务 · ${taskRows.length}`)); for(const item of taskRows){const row=el('article',undefined,'research-row'), copy=el('div');copy.append(el('h3',item.title || '研究任务'),el('p',item.target || ''));row.append(copy,button('打开研究 →',()=>openItem(item.id),'quiet'));box.append(row);} tasks.append(box); }
        const header = el('div',undefined,'customer-list-heading'), headingText=el('div'); headingText.append(el('h2','目标客户与询盘'),el('p','按当前进展排列，先处理有回复和待办的客户。')); header.append(headingText,button('新增客户',addCandidate,'primary')); candidates.append(header);
        const stats=el('div',undefined,'customer-stats'), bar=el('div',undefined,'customer-filter-bar'), input=el('input',undefined,'search-input'), categories=el('select'), statuses=el('select'), count=el('span','','search-count'), list=el('div',undefined,'customer-list');
        input.type='search';input.placeholder='搜索公司、需求或市场';input.setAttribute('aria-label','搜索目标客户');input.value=candidateQuery;
        categories.setAttribute('aria-label','买家类型');for(const value of ['',...new Set(allCustomers.map(item=>item.business_category || '其他'))]){const option=el('option',value || '全部买家类型');option.value=value;categories.append(option);}categories.value=candidateCategory;
        statuses.setAttribute('aria-label','联系状态');for(const [value,label] of [['active','全部进行中'],['action','待我处理'],['waiting','等待客户'],['prospect','待开发'],['ended','已结束跟进'],['all','全部状态']]){const option=el('option',label);option.value=value;statuses.append(option);}statuses.value=candidateStatus;
        bar.append(input,categories,statuses,count);candidates.append(stats,bar,list);
        function draw() {
          stats.replaceChildren();list.replaceChildren();
          const countStage=stage=>allCustomers.filter(item=>customerStage(item,activities.get(item.object_id))===stage).length;
          for(const [stage,label,caption] of [['action','待我处理','新回复与待办'],['waiting','等待客户','已联系或已报价'],['prospect','待开发','待研究和联系']]){
            const tile=button('',()=>{candidateStatus=stage;statuses.value=stage;draw();},`customer-stat ${stage}${candidateStatus===stage?' active':''}`);
            tile.append(el('span',label,'stat-label'),el('strong',String(countStage(stage))),el('span',caption,'stat-caption'));stats.append(tile);
          }
          const rows=allCustomers.filter(item=>{const stage=customerStage(item,activities.get(item.object_id));return (!candidateCategory || (item.business_category || '其他')===candidateCategory) && (candidateStatus==='all' || (candidateStatus==='active'?stage!=='ended':candidateStatus===stage)) && [item.title,item.company,item.business_summary,item.country,item.market_hint,item.next_action].some(value=>text(value).toLowerCase().includes(candidateQuery.trim().toLowerCase()));});
          const stageRank={action:0,waiting:1,prospect:2,ended:3},priorityRank={high:0,normal:1,low:2};rows.sort((a,b)=>stageRank[customerStage(a,activities.get(a.object_id))]-stageRank[customerStage(b,activities.get(b.object_id))] || (priorityRank[a.priority]??1)-(priorityRank[b.priority]??1) || text(b.updated_at || b.created_at).localeCompare(text(a.updated_at || a.created_at)));
          count.textContent=`${rows.length} 位客户`;
          if(rows.length){const columns=el('div',undefined,'customer-columns');for(const label of ['客户','客户情况','下一步','进展'])columns.append(el('span',label));list.append(columns);}
          for(const item of rows){
            const activity=activities.get(item.object_id),stage=customerStage(item,activity),row=el('article',undefined,`customer-list-row stage-${stage}`),identity=el('div',undefined,'customer-identity'),name=el('div');
            const avatar=el('span',text(item.title || item.company || '客').slice(0,1).toUpperCase(),'customer-monogram');name.append(el('h3',item.title || item.company || '客户'),el('p',[item.country || item.market_hint,item.business_category].filter(Boolean).map(text).join(' · ') || '目标客户'));identity.append(avatar,name);
            const brief=el('div',undefined,'customer-brief');if(item.contact_status_label && item.kind!=='inquiry')brief.append(el('strong',text(item.contact_status_label),'customer-progress'));brief.append(el('p',item.business_summary || '打开客户查看业务情况。'));const dateValue=text(item.updated_at || item.created_at || item.discovered_at).slice(0,10);if(/^\d{4}-\d{2}-\d{2}$/.test(dateValue))brief.append(el('small',`${item.updated_at?'更新':'发现'} ${dateValue}`));
            const next=el('div',undefined,'customer-action-cell'), action=item.gmail_reply_pending ? (item.gmail_next_action || '阅读客户新邮件，准备后续沟通') : item.next_action || activity?.judgment || (stage==='waiting'?'等待客户回复':'了解业务与采购入口');next.append(el('p',text(action)));
            const meta=el('div',undefined,'customer-row-actions');meta.append(el('span',customerStageLabel(stage,item),`customer-stage ${stage}`),button('打开客户 →',()=>item.kind==='inquiry'?goObject(item.object_id):openItem(item.id),'quiet'));row.append(identity,brief,next,meta);list.append(row);
          }
          if(!rows.length)empty(list,candidateStatus==='action'?'目前没有需要你处理的客户。':'没有找到符合条件的客户。');
        }
        input.addEventListener('input',()=>{candidateQuery=input.value;draw();});categories.addEventListener('change',()=>{candidateCategory=categories.value;draw();});statuses.addEventListener('change',()=>{candidateStatus=statuses.value;draw();});draw();
      } catch (error) { feedback.textContent = error.message; }
    }
    S.listRefresh = read; await read(); const selected = parseRoute().query.get('item'); if (selected && current()) { try { await openItem(selected); } catch (error) { feedback.textContent = error.message; } }
  }
  function summaryFacts(object) {
    const all = object.facts || []; if (object.kind !== 'product') return { shown: all.slice(0, 6), more: all.slice(6) };
    const hide = /来源|供应商|原款|共用.*ID|别名|原始资料包|原包路径|供货模式|已采纳供应来源|历史参考来源|Alibaba|渠道|平台|src[_-]/i;
    const priorities = [/^产品(?:名称|类型)?$/, /来源状态/, /^供应商$/, /供应商原款|原款/, /用途/, /参考价/, /原档已有规格|供货模式/]; const candidates = all.filter(item => !hide.test(text(item.label)));
    const shown = [];
    for (const rule of priorities) for (const item of candidates) if (rule.test(text(item.label)) && !shown.includes(item) && shown.length < 6) shown.push(item);
    for (const item of candidates) if (!shown.includes(item) && shown.length < 6) shown.push(item);
    return { shown, more: all.filter(item => !shown.includes(item)) };
  }
  function renderObject(object, requestedArtifact) {
    const page = $('page'), top = el('div', undefined, 'detail-top'), info = el('div'); info.append(el('span', objectKind(object), 'eyebrow'), el('h1', text(object.title))); if (object.subtitle && object.kind !== 'customer') info.append(el('p', object.kind === 'product' && /[A-Za-z]/.test(text(object.subtitle)) ? `平台原文：${text(object.subtitle)}` : displayText(object.subtitle))); if (object.kind === 'product') info.append(el('p', '集中查看产品事实、来源依据和素材，继续整理可用的选款资料。'));  top.append(info, button('返回列表', () => { location.hash = object.kind === 'product' ? '/products' : object.kind === 'prospect' ? '/customers?view=development' : '/customers?view=inquiries'; }, 'quiet')); page.replaceChildren(top);
    const layout = el('div', undefined, 'object-layout'), main = el('div', undefined, 'object-main'), right = el('aside', undefined, 'card object-agent'); const hero = el('section', undefined, 'card detail-hero'), asset = firstImage(object), facts = el('div'); if (asset) hero.append(image(asset, 'hero-image')); else hero.style.gridTemplateColumns = '1fr'; facts.append(el('h2', object.kind === 'product' ? '商品资料' : '需求与背景')); const summaryParagraph = el('p', object.kind === 'customer' ? '原始需求在下方，可生成中文解读。' : text(object.summary), object.kind === 'customer' ? 'agent-copy customer-need' : 'agent-copy'); if (object.kind === 'customer') facts.append(summaryParagraph); if(object.kind==='product')appendProductLinks(facts,object); const dl = el('dl', undefined, 'object-facts'); const factGroups = summaryFacts(object); for (const item of factGroups.shown) dl.append(el('dt', text(item.label)), el('dd', displayText(item.value) || '资料未提供')); facts.append(dl); if (object.kind !== 'product' && (factGroups.more.length || object.source)) { const details = el('details', undefined, 'extra-facts'); details.append(el('summary', '更多档案与渠道信息')); const more = el('dl', undefined, 'object-facts'); for (const item of factGroups.more) more.append(el('dt', text(item.label)), el('dd', displayText(item.value) || '资料未提供')); details.append(more, el('div', `来源：${text(object.source) || '来源未提供'}`, 'object-source')); facts.append(details); } hero.append(facts); if (object.kind !== 'customer') main.append(hero);
    if ((object.assets || []).length) {
      const materials = el('section', undefined, 'card'); materials.append(el('h2', object.kind === 'product' ? '图片与素材' : '需求资料')); const grid = el('div', undefined, 'asset-grid'); let expanded = false;
      function renderAssets() { grid.replaceChildren(); for (const item of object.assets.slice(0, expanded ? object.assets.length : 6)) { const row = el('div', undefined, 'asset-item'), src = safeUrl(item.url); if (imageAsset(item) && src) row.append(image(item, '')); row.append(el('div', assetLabel(item), 'asset-label')); if (src) row.append(button('预览', () => previewAsset(item), 'quiet')); grid.append(row); } }
      materials.append(grid); if (object.assets.length > 6) { const toggle = button(`展开全部 ${object.assets.length} 份素材`, () => { expanded = !expanded; toggle.textContent = expanded ? '收起素材' : `展开全部 ${object.assets.length} 份素材`; renderAssets(); }, 'quiet asset-toggle'); materials.append(toggle); } renderAssets(); main.append(materials);
    }
    if (object.content && object.kind !== 'customer' && object.kind !== 'product') { const source = el('details', undefined, 'card object-source-details'); source.append(el('summary', object.kind === 'product' ? '查看原始资料' : '查看来源正文与完整需求'), el('pre', text(object.content), 'source-body')); main.append(source); }
    if ((object.kind !== 'product' && (object.links || []).length) || (object.related || []).length) { const related = el('section', undefined, 'card'); related.append(el('h2', '关联与出处')); const links = el('div', undefined, 'related-links'); if (object.kind !== 'product') for (const item of object.links || []) { const a = link(item.label || '打开来源', item.url); if (a) links.append(a); } for (const item of object.related || []) { const id = typeof item === 'string' ? item : item.id || item.object_id; if (id) links.append(button(typeof item === 'string' ? objectById(id)?.title || '关联资料' : item.title || item.label || '关联资料', () => goObject(id))); } related.append(links); main.append(related); }
    let conversationMessages, replyArea;
    if (object.kind === 'customer' && Array.isArray(object.conversation)) {
      const conversation = el('section', undefined, 'card customer-conversation'); conversation.append(el('h2', '网站站内消息'));
      conversationMessages = el('div'); conversation.append(conversationMessages);
      const reply = el('textarea'), result = el('p', '', 'agent-feedback'); replyArea=reply; reply.placeholder = '英文回复原文'; reply.setAttribute('aria-label', '网站私信回复');
      const send = button('发送网站私信', async () => { if (!reply.value.trim()) { result.textContent = '请先填写回复原文。'; return; } send.disabled = true; try { const value = await api('/api/desk/website-reply', {object_id:object.id,message:reply.value}); result.textContent = value.saved ? `网站私信已保存并发送；${value.notification_sent ? '邮件提醒已发送' : '邮件提醒未发送，请查看网站往来记录'}。` : '未确认发送成功，请核对往来记录。'; if (value.saved) { reply.value = ''; const refreshed = objectResult(await api(`/api/desk/object?id=${encodeURIComponent(object.id)}`)); object.conversation = refreshed.conversation || []; const entry = el('article'); entry.append(el('h3', '我方 · 刚刚'), el('p', '消息已保存，重新打开可查看完整往来。')); conversation.insertBefore(entry, reply); } } catch (error) { result.textContent = error.message; } finally { send.disabled = false; } }, 'primary');
      conversation.append(el('p', '点击后将给买家发送网站私信，并尝试邮件提醒。'), reply, send, result); main.append(conversation);
    }
    if (object.kind === 'product') loadProductGaps(object, main);
    if (object.kind === 'product') { const listings=(object.links || []).filter(x=>/^Alibaba \d+$/.test(x.label || '')); if(listings.length) { const box=el('section',undefined,'card'), select=el('select'), output=el('div'); box.append(el('h2','国际站商品标题'),el('p','选择对应平台商品，读取当前正式标题。')); select.setAttribute('aria-label','国际站商品'); for(const entry of listings) { const option=el('option',`平台商品 ${entry.label.split(' ')[1]}`); option.value=entry.label.split(' ')[1]; select.append(option); } box.append(select,button('读取当前标题',async()=>{output.replaceChildren(el('p','正在读取…'));try{const value=await api(`/api/desk/title-diagnosis?product_id=${encodeURIComponent(select.value)}`);if(!value.ok)throw new Error('当前商品暂不可读取，请检查国际站连接。');const d=value.change;output.replaceChildren(el('p',`平台标题：${d.platform?.title || '未返回'}`),el('p',`本地记录：${d.localTitle || '未记录'}`),el('p',d.platform?.title===d.localTitle ? '平台和本地标题一致。' : '平台和本地标题不同，请先检查。'));}catch(error){output.replaceChildren(el('p',error.message));}},'quiet'),output);titleDraftForm(box,object,select);main.append(box); } }
    const artifactSection = el(object.kind === 'customer' ? 'details' : 'section', undefined, 'card'); if(object.kind==='customer' && isWebsite(object))artifactSection.open=true; artifactSection.append(el(object.kind === 'customer' ? 'summary' : 'h2', object.kind === 'customer' ? '回复草稿与工作成果' : '工作成果')); const tabs = el('div', undefined, 'artifact-tabs'), editor = el('div'); artifactSection.append(el('p', '整理出的选款资料、回复草稿和补充内容都保存在这里，可继续编辑。', 'artifact-note'), tabs, editor); main.insertBefore(artifactSection, main.children[1] || null);
    const ctx = { object, right, tabs, editor, summaryParagraph, conversationMessages, replyArea, artifacts: [], selectedId: null, requestedArtifact, currentEdit: null }; S.detail = ctx; buildAgent(ctx); if (object.kind === 'customer') { ctx.profileHost = el('section', undefined, 'card customer-analysis'); main.insertBefore(ctx.profileHost, main.children[0] || null); main.insertBefore(button('客户资料包 · 选择与组合材料',()=>{location.hash='/library?customer='+encodeURIComponent(object.id);},'quiet'),ctx.profileHost); loadProfile(ctx); } if(object.kind==='customer')mountGmail(ctx,main); layout.append(main, right); page.append(layout); refreshArtifacts(ctx, true);
  }
  async function loadProductGaps(object, host) {
    const card = el('section', undefined, 'card product-gaps');
    card.append(el('h2', '资料缺口'), el('p', '正在核对已登记字段…', 'muted'));
    host.append(card);
    try {
      const data = await api(`/api/desk/product-gaps?product_id=${encodeURIComponent(String(object.id).replace(/^product:/, ''))}`);
      const gaps = data.gaps || [];
      if (!gaps.length) { card.remove(); return; }
      card.replaceChildren(el('h2', '待补充资料'));
      for (const gap of gaps) card.append(el('p', `${gap.label}：${gap.reason}`, gap.severity === 'high' ? 'gap-blocking' : 'muted'));
    } catch { card.remove(); }
  }
  function previewAsset(asset) {
    const src = safeUrl(asset.url); if (!src) return; const dialog = el('dialog', undefined, 'desk-modal'), header = el('div', undefined, 'modal-head'); header.append(el('h2', assetLabel(asset)), button('关闭', () => dialog.close(), 'quiet')); dialog.append(header); const wrap = el('div', undefined, 'modal-media'); let media;
    const path = asset.path || asset.url; if (imageAsset(asset)) { media = el('img'); media.alt = assetLabel(asset); }
    else if (/\.(?:mp4|mov|webm|m4v)(?:$|[?#])/i.test(path)) { media = el('video'); media.controls = true; media.playsInline = true; }
    else if (/\.(?:mp3|wav|ogg|flac|aac|m4a)(?:$|[?#])/i.test(path)) { media = el('audio'); media.controls = true; }
    if (media) { media.src = src; if (media.tagName !== 'IMG') media.preload = 'metadata'; media.addEventListener('error', () => { wrap.replaceChildren(el('p', '这份素材暂时无法预览，可重新读取后再试。')); }); wrap.append(media); } else { const a = link('在新窗口打开这份资料 ↗', src); if (a) wrap.append(a); }
    dialog.append(wrap); dialog.addEventListener('close', () => { if (media && typeof media.pause === 'function') { media.pause(); media.removeAttribute('src'); media.load(); } dialog.remove(); }); document.body.append(dialog); dialog.showModal();
  }
  function buildAgent(ctx) {
    const title = el('div', undefined, 'agent-heading'); title.append(el('h2', '一起推进'), el('span', 'Sol', 'agent-mark')); ctx.right.append(title, el('p', `已带入${ctx.object.kind === 'product' ? '这款商品' : ctx.object.kind === 'prospect' ? '当前研究对象' : '这位客户'}的资料。说明你需要的结果，成果会回到当前页面。`, 'agent-copy'));
    const shortcuts = el('div', undefined, 'agent-shortcuts'), instruction = el('textarea', undefined, 'agent-instruction'); instruction.placeholder = ctx.object.kind === 'product' ? '例如：整理一份适合发给买家的选款资料，指出还缺哪些依据。' : '例如：根据客户原需求准备回复草稿，把需要确认的问题写清楚。'; instruction.setAttribute('aria-label', '交给 Sol 的要求'); instruction.value = S.instructions.get(String(ctx.object.id)) || ''; instruction.addEventListener('input', () => S.instructions.set(String(ctx.object.id), instruction.value));
    const choices = ctx.object.kind === 'product' ? [['整理选款资料', '请根据当前商品资料与素材，先用中文整理产品事实、适配依据与待确认项，形成可编辑选款资料。英文来源须保留原文并附中文释义；如需英文买家版本，先给中文说明再给英文原稿。不新增未证实的材料、性能或商业承诺。'], ['找出资料缺口', '请检查当前商品资料，指出影响买家选款与报价的缺口，按重要性给出可以执行的下一步。']] : [['准备回复草稿', '请根据当前客户原文和已有资料，先给中文需求解读、回复要点与待确认问题，再提供可编辑的英文回复原稿并配中文译文。不编造价格、供货能力或已执行动作，不发送消息。'], ['梳理下一步', '请梳理当前客户的明确需求、尚缺信息及下一步动作，形成可以继续编辑使用的工作记录。']]; for (const [label, value] of choices) shortcuts.append(button(label, () => { instruction.value = value; S.instructions.set(String(ctx.object.id), value); instruction.focus(); }));
    const feedback = el('div', '', 'agent-feedback'), submit = button('交给 Sol 处理', async () => {
      const value = instruction.value.trim(); if (!value) { feedback.textContent = '先写下这次希望得到什么结果。'; instruction.focus(); return; } submit.disabled = true; feedback.textContent = '正在启动这次工作…';
      try { const job = jobResult(await api('/api/desk/jobs', { object_id: ctx.object.id, instruction: `${value}\n\n界面使用中文：分析、依据、缺口、下一步均先用中文；引用英文或外发英文草稿须保留原文并附中文释义，不擅自发送。` })); upsertJob(job); feedback.textContent = '工作已开始，结果会保存在当前对象下。你可以继续查看资料。'; renderJob(ctx); }
      catch (error) { feedback.textContent = error.message; feedback.classList.add('inline-error'); }
      finally { submit.disabled = jobsFor(ctx.object.id).some(isActive); }
    }, 'primary agent-submit'); const jobs = el('div'); ctx.right.append(shortcuts, instruction, submit, feedback, jobs); Object.assign(ctx, { instruction, feedback, submit, jobBox: jobs }); renderJob(ctx);
  }
  function upsertJob(job) { const index = S.jobs.findIndex(item => item.id === job.id); if (index < 0) S.jobs.unshift(job); else S.jobs[index] = job; }
  function renderJob(ctx) {
    const job = jobsFor(ctx.object.id)[0], logOpen = ctx.jobBox.querySelector('.job-events')?.open; ctx.submit.disabled = jobsFor(ctx.object.id).some(isActive); ctx.jobBox.replaceChildren(); if (!job) return; const panel = el('div', undefined, 'job-detail'); panel.append(el('h3', '这次工作'), el('p', text(job.title || '工作记录'))); const actions = el('div', undefined, 'job-actions'); actions.append(badge(job.status)); if (isActive(job)) actions.append(button('停止', async () => { upsertJob(jobResult(await api('/api/desk/job/cancel', { id: job.id }))); renderJob(ctx); })); panel.append(actions); if(job.instruction) { const request=el('details'); request.append(el('summary','查看工作要求'),el('p',text(job.instruction))); panel.append(request); } if (job.summary) panel.append(el('p', text(job.summary))); if (job.error) panel.append(el('p', text(job.error).slice(0, 400), 'inline-error')); if (job.artifact_id) panel.append(button('查看这次成果 →', () => selectArtifact(ctx, job.artifact_id), 'quiet'));
    if ((job.events || []).length) { const detail = el('details', undefined, 'job-events'); detail.open = !!logOpen; detail.append(el('summary', '查看处理记录')); const lines = (job.events || []).slice(-30).map(item => typeof item === 'string' ? item : ({ 'thread.started': '已建立执行会话', 'turn.started': '正在处理资料', 'turn.completed': '本轮处理结束', 'turn.failed': '本轮处理未完成' }[item.type] || item.text || item.message || '执行记录已更新')); detail.append(el('pre', lines.map(text).join('\n'))); panel.append(detail); } ctx.jobBox.append(panel);
  }
  function editKey(ctx, id) { return `${ctx.object.id}:${id || 'new'}`; }
  function englishReplyDraft(content) { const match=text(content).match(/^##\s*(?:英文正文|英文回复草稿)(?:[^\n]*)\n([\s\S]*?)(?=^##\s|(?![\s\S]))/m); return match ? match[1].replace(/^\s*(?:\*\*)?Subject:(?:\*\*)?[^\n]*\n/im,'').trim() : ''; }
  function chineseReplyDraft(content) { const match=text(content).match(/^##\s*(?:完整中文对照|中文正文|中文对照|中文回复|中文译文|中文翻译)(?:[^\n]*)\n([\s\S]*?)(?=^##\s|(?![\s\S]))/m); return match ? match[1].trim() : ''; }
  function plainEmailDraft(value) { return text(value).replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,'$1: $2').replace(/^\s*\|?\s*:?-{3,}[^\n]*$/gm,'').replace(/^\s*\|(.+)\|\s*$/gm,(_,row)=>row.split('|').map(cell=>cell.trim()).join('  |  ')).replace(/\*\*([^*]+)\*\*/g,'$1').replace(/\n{3,}/g,'\n\n').trim(); }
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
    modes.append(read, write); const footer = el('div', undefined, 'artifact-footer'); footer.append(caption, save); if(ctx.replyArea && englishReplyDraft(content.value))footer.append(button('采用英文正文到回复框',()=>{const value=englishReplyDraft(content.value); if(!value){toast('请先在成果中写明英文正文。');return;} if(ctx.replyArea.value.trim()){toast('回复框已有内容，请先处理后再采用。');return;}ctx.replyArea.value=value;ctx.replyArea.focus();ctx.replyArea.scrollIntoView?.({behavior:'smooth',block:'center'});toast('已放入回复框，请检查后发送。');},'quiet')); if(ctx.gmailHost && englishReplyDraft(content.value) && !/已发送/.test(text(artifact?.title))){footer.append(button('采用到邮件草稿',()=>openGmailComposer(ctx,{en:plainEmailDraft(englishReplyDraft(content.value)),zh:plainEmailDraft(chineseReplyDraft(content.value))}),'quiet'));footer.append(button('复制英文回复',async()=>{const value=plainEmailDraft(englishReplyDraft(content.value));if(!value){toast('请先准备英文回复。');return;}try{await navigator.clipboard.writeText(value);toast('英文回复已复制，可在 Gmail 中审核并回复。');}catch{toast('复制未成功，请从编辑区复制英文正文。');}},'quiet'));} ctx.editor.append(modes, preview, title, content, footer, el('p', '保存的是这份工作成果；不会自动发送给客户或修改平台商品。', 'artifact-note')); setMode(artifact && !edit.dirty ? 'preview' : 'edit'); renderArtifactTabs(ctx);
  }
  function renderArtifactTabs(ctx) { ctx.tabs.replaceChildren(); for (const artifact of ctx.artifacts) ctx.tabs.append(button(text(artifact.title || '工作成果'), () => selectArtifact(ctx, artifact.id), ctx.selectedId === artifact.id ? 'active' : '')); ctx.tabs.append(button('＋ 新建笔记', () => { ctx.userPickedNew = true; showArtifactEditor(ctx, null); }, ctx.selectedId === null ? 'active' : '')); }
  function selectArtifact(ctx, id) { const artifact = ctx.artifacts.find(item => String(item.id) === String(id)); if (artifact) { showArtifactEditor(ctx, artifact); ctx.editor.scrollIntoView?.({ behavior: 'smooth', block: 'start' }); } else refreshArtifacts(ctx, true, id).then(() => ctx.editor.scrollIntoView?.({ behavior: 'smooth', block: 'start' })); }
  async function refreshArtifacts(ctx, initial = false, requested = null) {
    try { const result = await api(`/api/desk/artifacts?object_id=${encodeURIComponent(ctx.object.id)}`); if (S.detail !== ctx) return; ctx.artifacts = array(result, 'artifacts'); for (const artifact of ctx.artifacts) { const index = S.artifacts.findIndex(item => item.id === artifact.id); if (index < 0) S.artifacts.push(artifact); else S.artifacts[index] = artifact; }
      if (initial) {
        const explicit = requested || ctx.requestedArtifact, remembered = S.selectedArtifacts.get(String(ctx.object.id)), dirty = S.edits.get(editKey(ctx, remembered))?.dirty;
        const newestJob = jobsFor(ctx.object.id).find(job => job.artifact_id && ctx.artifacts.some(item => String(item.id) === String(job.artifact_id)));
        const latestSaved = isWebsite(ctx.object) ? [...ctx.artifacts].sort((a,b)=>String(b.updated_at || '').localeCompare(String(a.updated_at || '')))[0]?.id : newestJob?.artifact_id;
        const target = explicit || (dirty ? remembered : latestSaved);
        const artifact = !explicit && dirty && remembered === null ? null : ctx.artifacts.find(item => String(item.id) === String(target)) || ctx.artifacts[0] || null;
        showArtifactEditor(ctx, artifact);
      }
      else { renderArtifactTabs(ctx); if (!ctx.selectedId && !ctx.userPickedNew && !ctx.currentEdit?.dirty && ctx.artifacts.length) showArtifactEditor(ctx, ctx.artifacts[0]); }
    } catch (error) { if (S.detail === ctx) message(error.message); }
  }
  async function bootstrap() { $('reload').disabled = true; try { const value = await api('/api/desk/bootstrap'); S.token = value.csrf_token || ''; S.objects = value.objects || []; S.jobs = value.jobs || []; S.artifacts = value.artifacts || []; S.goals = value.goals || {}; S.websiteStatus = value.website_status || {}; S.alibabaStatus = value.alibaba_status || {}; S.gmailRevision = value.gmail_revision || 0; S.lastBootstrapPoll = Date.now(); $('connection').textContent = '本地工作台已连接'; await renderRoute(); } catch (error) { $('connection').textContent = '连接暂时中断'; message(error.message); if (!S.objects.length) $('page').replaceChildren(el('div', '还没有取得真实业务资料。请确认本地服务已启动，再点击重新读取。', 'empty')); } finally { $('reload').disabled = false; } }
  async function poll() {
    if (S.pollBusy || document.visibilityState === 'hidden' || !S.token) return; S.pollBusy = true;
    try {
      const value = await api('/api/desk/jobs'); const prior = JSON.stringify(S.jobs.map(job => [job.id, job.status, job.updated_at])); S.jobs = array(value, 'jobs'); const changed = JSON.stringify(S.jobs.map(job => [job.id, job.status, job.updated_at])) !== prior;
      let objectsChanged = false, dataChanged = false, websiteUpdated = false, gmailUpdated = false;
      if (Date.now() - S.lastBootstrapPoll >= 12000 || ['loading', 'refreshing', 'pending'].includes(S.websiteStatus.state) || ['loading', 'refreshing', 'pending'].includes(S.alibabaStatus.state)) {
        const result = await api('/api/desk/bootstrap'); S.lastBootstrapPoll = Date.now(); const old = JSON.stringify(S.objects); S.objects = result.objects || S.objects; objectsChanged = old !== JSON.stringify(S.objects); const priorArtifacts = JSON.stringify(S.artifacts.map(item => [item.id, item.updated_at])); S.artifacts = result.artifacts || S.artifacts; dataChanged = priorArtifacts !== JSON.stringify(S.artifacts.map(item => [item.id, item.updated_at])); websiteUpdated = !!result.website_status?.observed_at && result.website_status.observed_at !== S.websiteStatus.observed_at; gmailUpdated = (result.gmail_revision || 0) !== S.gmailRevision; S.gmailRevision = result.gmail_revision || 0; S.websiteStatus = result.website_status || S.websiteStatus; S.alibabaStatus = result.alibaba_status || S.alibabaStatus; if (result.csrf_token) S.token = result.csrf_token; updateWebsiteLabels();
      }
      if (S.detail) { const ctx = S.detail; if(ctx.gmailHost && (gmailUpdated || Date.now()-(ctx.lastGmailRefresh || 0)>=12000))loadGmail(ctx); if(ctx.profileHost && !ctx.profileEditing && !ctx.workflowEditing && (gmailUpdated || (isWebsite(ctx.object) && (websiteUpdated || Date.now()-(ctx.lastProfileRefresh || 0)>=120000)))) {ctx.lastProfileRefresh=Date.now();loadProfile(ctx);} if (changed) { renderJob(ctx); if (ctx.profileHost && !ctx.profileEditing) loadProfile(ctx); } if (changed || dataChanged || jobsFor(ctx.object.id).some(isActive)) await refreshArtifacts(ctx); }
      else if (S.page === 'overview' && (changed || objectsChanged || dataChanged || websiteUpdated || gmailUpdated)) renderOverview();
      else if ((objectsChanged || (S.page === 'customers' && (websiteUpdated || gmailUpdated))) && S.listRefresh) await S.listRefresh();
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
