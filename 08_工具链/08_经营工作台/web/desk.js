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
  const S = { token: '', objects: [], jobs: [], artifacts: [], goals: {}, route: '', page: 'overview', object: null, detail: null, edits: new Map(), pending: false, loadSerial: 0, pollBusy: false, websiteStatus: {}, alibabaStatus: {}, gmailRevision: 0, listRefresh: null, lastBootstrapPoll: 0, selectedArtifacts: new Map(), cloudReview: {open:false,items:[],tasks:[],dispatches:[],taskId:'',instruction:'',model:'gpt-6-luna',preview:null,message:'',busy:false}, batchView: {id:'', selected:'', query:'', state:''} };
  const statusNames = { planned: '尚未启动', queued: '等待开始', running: '正在处理', completed: '已形成成果', needs_input: '待补充依据', failed: '未能完成', cancelled: '已停止' };
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
  const objectKind = object => object.kind === 'product' ? '商品' : object.kind === 'creation' ? '创作项目' : object.kind === 'prospect' ? '开发研究' : object.kind === 'channel' ? '渠道' : '客户';
  const objectById = id => S.objects.find(item => String(item.id) === String(id));
  const jobsFor = id => S.jobs.filter(job => job.task_kind !== 'group' && String(job.object_id) === String(id)).sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  const badge = status => el('span', statusNames[status] || '状态待确认', `status ${status || ''}`);
  function message(value = '') { $('desk-notice').textContent = value; $('desk-notice').hidden = !value; }
  let toastTimer;
  function toast(value) { $('save-indicator').textContent = value; $('save-indicator').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('save-indicator').hidden = true; }, 4500); }
  async function api(path, body) {
    const response = await fetch(path, body === undefined ? { cache: 'no-store' } : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workbench-Token': S.token }, body: JSON.stringify(body) }); let value;
    try { value = await response.json(); } catch { throw new Error('暂时无法读取服务结果，请稍后重新读取。'); }
    const errors={NO_CHANGE:'图片顺序没有变化，请先调整。',SIX_IMAGE_GALLERY_REQUIRED:'当前链接不是六张主图，暂不支持在此调整。',GALLERY_SCHEMA_UNVERIFIED:'平台未返回完整的主图编辑信息，请刷新后重试。',GALLERY_SCHEMA_MISMATCH:'平台主图刚发生变化，请刷新商品后重新调整。',GALLERY_IMAGE_UNAVAILABLE:'未能读取当前主图，请刷新后重试。',GALLERY_IMAGE_NOT_OFFICIAL:'当前主图无法匹配国际站图片银行。',IMAGE_BANK_UNAVAILABLE:'图片银行暂时无法读取，请稍后重试。',IMAGE_BANK_ASSET_NOT_FOUND:'图片银行未找到对应主图，请检查图片后再操作。',IMAGE_BANK_ASSET_AMBIGUOUS:'图片银行中有重复的对应图片，需要先确认。',LOCAL_IMAGE_FORMAT_UNSUPPORTED:'请选择 JPG 或 PNG 图片。',INVALID_LOCAL_IMAGE:'所选图片无法读取，或文件超过 5 MB。',DUPLICATE_GALLERY_IMAGE:'主图中有重复图片，请选择不同的图片。',DETAIL_TYPE_UNVERIFIED:'当前商品的详情类型暂不支持在此调整。',DETAIL_REORDER_WITHIN_GROUP_ONLY:'请保持每组图片连续，整组移动。',DETAIL_SCHEMA_MISMATCH:'平台详情图刚发生变化，请重新读取分组。',DETAIL_IMAGES_UNAVAILABLE:'平台未返回可调整的详情图。',PLATFORM_VERSION_CONFLICT:'平台商品已变化，请刷新后重新准备方案。',LOCAL_VERSION_CONFLICT:'本地商品记录已变化，请重新读取后准备方案。',PLATFORM_NOT_APPROVED:'商品仍在平台审核中，请审核完成后再调整。'};
    if (!response.ok || value.ok === false) { const error = new Error(typeof value.error === 'string' ? value.error.slice(0, 400) : value.error?.message || errors[value.error?.code] || '这次操作未完成，请稍后再试。'); error.status = response.status; throw error; }
    return value;
  }
  const array = (value, key) => Array.isArray(value) ? value : value?.[key] || [];
  const objectResult = value => value.object || value;
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
    for (const [title, note, hash] of [['外贸客户', '查看客户需求、往来与开发进展', '/customers'], ['国际站运营', '查看商品与已有经营记录', '/channels?view=alibaba'], ['抖店运营', '查看渠道状态并继续商品与内容工作', '/channels?view=douyin'], ['内容创作中心', '继续创作项目与画布', '/creation'], ['商品中心', `已接入 ${products} 款商品 · 查资料、选素材、整理选款`, '/products'], ['独立站运营', S.websiteStatus.observed_at ? `已读取 ${website} 条询盘 · 查看搜索与询盘` : '查看搜索连接与询盘状态', '/channels?view=website']]) { const card = el('article', undefined, 'card business-entry'); card.append(el('h2', title), el('p', note), button('打开 →', () => { location.hash = hash; }, 'quiet')); grid.append(card); }
    return grid;
  }
  function image(asset, cls) { const src = safeUrl(asset?.url); if (!src) return null; const img = el('img', undefined, cls); img.src = src; img.alt = assetLabel(asset); img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.addEventListener('error', () => img.remove()); return img; }
  function productDescription(object) { const f=(object.facts || []).find(x => text(x.label).startsWith('用途候选')); return text(f?.value).split('·').map(v => v.replace(/需求/g, '').replace(/待分类/g, '').trim()).filter(Boolean).join(' · ') || '商品类型尚未整理'; }
  function creativeSummary(content) { return text(content).split('\n').map(line=>line.trim().replace(/\*\*/g,'').replace(/^[-*]\s*/,'').replace(/^(?:更新|更新时间)：\d{4}-\d{2}-\d{2}[。\s]*/,'')) .filter(line=>line && !/^(#|\||---|项目名称：)/.test(line) && !/本档案仅按既有本地文件/i.test(line) && /[\u3400-\u9fff]/.test(line)).map(line=>line.split(/；(?:本次未|未新增|未生成|用户再次明确授权删除|自动审批)/)[0])[0] || ''; }
  function appendSupply(host, object) { const supply=object.supply || {};
    if(supply.kind==='own') host.append(el('p','自有工厂'));
    else if(supply.kind==='external') { const row=el('p','外采供货'); if(supply.model)row.append(el('span',' · '+text(supply.model))); const a=link('查看供货商品',supply.url); if(a)row.append(el('span',' · '),a); host.append(row); }
  }
  function appendProductLinks(host, object) {
    appendOtherChannels(host, object);
    const supply = object.supply || {}, listings = (object.links || []).filter(item => /^Alibaba \d+$/.test(item.label || ''));
    if (supply.kind !== 'own' && !safeUrl(supply.url) && !listings.length) return;
    const section = el('div', undefined, 'product-links'), links = el('div', undefined, 'related-links');
    section.append(el('h3', '供货与国际站链接'));
    if (supply.kind === 'own') links.append(el('span', '自有工厂'));
    else if (supply.kind === 'external') { links.append(el('span', '外采供货')); const source = link(supply.model ? `供货商品 ${supply.model} ↗` : '供货商品 ↗', supply.url); if (source) links.append(source); }
    for (const item of listings) { const a = link(`国际站商品 ${item.label.split(' ')[1]} ↗`, item.url); if (a) links.append(a); }
    section.append(links); host.append(section);
  }
  function appendOtherChannels(host, object) {
    const channels=object.other_channels; if (!channels) return;
    const section=el('div', undefined, 'product-links'); section.append(el('h3','抖店与独立站'));
    const douyin=channels.douyin || {}, rows=douyin.listings || [];
    if (!douyin.source_available) section.append(el('p','抖店对应资料暂不可读'));
    else if (!rows.length) section.append(el('p','抖店：未找到明确商品对应，不能据此判断是否上架'));
    else for (const row of rows) {
      const observed=row.observation || {};
      section.append(el('p', `抖店 · ${text(row.store)} · ${text(row.source_model)} · ${text(row.version)}${observed.record_updated_on ? ' · 原记录 '+text(observed.record_updated_on) : ''}（历史记录，非实时状态）`));
    }
    const website=channels.website || {};
    if (website.state==='matched') { const p=el('p','独立站：源码商品对应 · '), a=link('打开商品页 ↗',website.url); if(a)p.append(a); section.append(p,el('p','源码对应不代表当前线上已验收。','muted')); }
    else section.append(el('p', website.state==='ambiguous' ? '独立站：商品对应有歧义，暂不生成链接' : website.state==='source_unavailable' ? '独立站：商品对应资料暂不可读' : '独立站：已读目录未找到对应，不能据此判断线上状态'));
    host.append(section);
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
    if (action.type === 'agent') return action.object_id ? button('查看相关记录', () => goObject(action.object_id), 'quiet') : null;
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
    const page = $('page'), goalsOpen = page.querySelector('.goals')?.open; page.replaceChildren(heading('我的工作台', '今天，从这里继续', '查看客户、商品和正在推进的工作。'));
    page.append(websiteLabel());
    mountCloudReviews(page);
    const today = el('section', undefined, 'overview-today'); page.append(today); renderToday(today);
    const goals = Object.entries(S.goals || {}).filter(([, value]) => text(value)); if (goals.length) { const details = el('details', undefined, 'card goals'); details.open = !!goalsOpen; details.append(el('summary', '当前方向与重点')); for (const [key, value] of goals) details.append(el('div', `${({ long_term: '长期方向', phase: '当前阶段', focus: '当前重点', priorities: '优先事项', notes: '补充要求' }[key] || '当前要求')}：${text(value)}`)); page.append(details); }
    page.append(sectionHeading('从业务开始', '进入真实对象，而非工具菜单'), businessEntrances()); const recentRows = recentObjects(); if (recentRows.length) { page.append(sectionHeading('继续工作', '近期打开或实际处理过的对象')); const recent = el('div', undefined, 'continue-grid'); recentRows.forEach(object => recent.append(tile(object))); page.append(recent); }
    const artifacts = el('section'); artifacts.append(sectionHeading('最近成果', '打开后可继续编辑')); const list = el('div', undefined, 'row-list'); [...S.artifacts].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''))).slice(0, 5).forEach(item => list.append(artifactRow(item))); if (!list.children.length) empty(list, '新的选款资料、回复草稿会保存在这里，并关联原商品或客户。'); artifacts.append(list); page.append(artifacts);
  }
  function mountCloudReviews(page) {
    const state=S.cloudReview, box=el('details',undefined,'card cloud-reviews');box.open=state.open;
    box.addEventListener('toggle',()=>{if(box.isConnected)state.open=box.open;});
    box.append(el('summary','云端任务与成果'),el('p','将已有任务交给云端，电脑关闭后可继续处理已提交的云端资料任务；重新上线后在此预览成果。网站询盘仍在网站后台审阅。','muted'));
    const cloudEntry=link('打开云端工作台提交任务 ↗','https://www.beiqiang.online/admin/workbench/');if(cloudEntry)box.append(cloudEntry);
    const redraw=()=>{if(S.page==='overview')renderOverview();};
    const loadTasks=button('读取可交给云端的任务',async()=>{if(state.busy)return;state.busy=true;state.message='正在读取云端任务…';redraw();try{const [tasks,dispatches]=await Promise.all([api('/api/desk/cloud-review',{action:'tasks'}),api('/api/desk/cloud-review',{action:'dispatches'})]);state.tasks=tasks.tasks || [];state.dispatches=dispatches.dispatches || [];if(!state.tasks.some(item=>item.id===state.taskId))state.taskId=state.tasks[0]?.id || '';state.message=state.tasks.length?'请选择任务并填写要求。':'云端暂无可接续任务。';}catch(error){state.message=error.message;}finally{state.busy=false;redraw();}},'quiet');loadTasks.disabled=state.busy;box.append(loadTasks);
    if(state.tasks.length){const form=el('div',undefined,'profile-form'),select=el('select'),instruction=el('textarea'),model=el('select');select.setAttribute('aria-label','选择云端任务');for(const item of state.tasks){const option=el('option',text(item.title));option.value=item.id;select.append(option);}select.value=state.taskId;select.addEventListener('change',()=>{state.taskId=select.value;});instruction.setAttribute('aria-label','云端任务要求');instruction.placeholder='说明这次需要云端完成什么';instruction.value=state.instruction;instruction.addEventListener('input',()=>{state.instruction=instruction.value;});model.setAttribute('aria-label','云端任务模型');for(const [value,label] of [['gpt-6-luna','Luna · 轻量任务'],['gpt-6.1-sol','Sol · 复杂任务']]){const option=el('option',label);option.value=value;model.append(option);}model.value=state.model;model.addEventListener('change',()=>{state.model=model.value;});
      const submit=button('提交到云端',async()=>{const task=state.tasks.find(item=>item.id===state.taskId);if(!task || !state.instruction.trim()){state.message='请先选择任务并填写要求。';redraw();return;}if(state.busy)return;state.busy=true;state.message='正在提交云端任务…';redraw();try{const result=await api('/api/desk/cloud-review',{action:'enqueue',task_id:task.id,task_version:task.version,source_version:task.source_version,instruction:state.instruction.trim(),model:state.model});state.message=`云端已确认任务，当前状态：${result.status==='queued'?'排队中':result.status || '已提交'}。`;state.instruction='';}catch(error){state.message=error.message;}finally{try{state.dispatches=(await api('/api/desk/cloud-review',{action:'dispatches'})).dispatches || [];}catch{}state.busy=false;redraw();}},'primary');submit.disabled=state.busy;form.append(el('p','选择已有任务，系统将携带对应的本地资料快照。','muted'),select,instruction,model,submit);box.append(form);}
    for(const item of state.dispatches.filter(item=>item.status==='pending')){const row=el('div',undefined,'agent-job');row.append(el('p',`${text(item.title || '云端任务')} · 提交结果待核对`));const check=button('核对提交状态',async()=>{if(state.busy)return;state.busy=true;state.message='正在核对…';redraw();try{const result=await api('/api/desk/cloud-review',{action:'reconcile',request_id:item.request_id});state.message=result.status==='confirmed'?'云端已确认该任务。':result.message;state.dispatches=(await api('/api/desk/cloud-review',{action:'dispatches'})).dispatches || [];}catch(error){state.message=error.message;}finally{state.busy=false;redraw();}},'quiet');check.disabled=state.busy;row.append(check);box.append(row);}
    const load=button('读取云端待审成果',async()=>{if(state.busy)return;state.busy=true;state.message='正在读取云端成果…';redraw();try{const data=await api('/api/desk/cloud-review',{action:'list'});state.items=data.runs || [];state.preview=null;state.message=state.items.length?'请选择一项成果预览。':'云端暂无待审项目成果。';}catch(error){state.message=error.message;}finally{state.busy=false;redraw();}},'quiet');load.disabled=state.busy;box.append(load);
    for(const item of state.items){const row=el('article',undefined,'agent-job');row.append(el('h3',text(item.title || '云端成果')),el('p',text(item.summary || '待查看')),el('p',`更新时间：${time(item.updated_at)}`,'muted'));const preview=button('预览成果',async()=>{if(state.busy)return;state.busy=true;state.message='正在核对原资料版本…';redraw();try{state.preview=await api('/api/desk/cloud-review',{action:'preview',run_id:item.id});state.message=state.preview.conflict?state.preview.message:'已读取，可核对内容。';}catch(error){state.preview=null;state.message=error.message;}finally{state.busy=false;redraw();}},'quiet');preview.disabled=state.busy;row.append(preview);box.append(row);}
    const p=state.preview;if(p){const detail=el('section',undefined,'analysis-block');detail.append(el('h3','成果预览'),el('p',text(p.summary)));for(const next of p.next_steps || [])detail.append(el('p',text(next)));if(p.diff)detail.append(el('pre',p.diff,'source-body'));if(p.changes && p.proposal_hash && !p.conflict){const apply=button('确认写回本地原资料',async()=>{if(state.busy)return;state.busy=true;state.message='正在核对并写回…';redraw();try{const result=await api('/api/desk/cloud-review',{action:'apply',run_id:p.run_id,proposal_hash:p.proposal_hash});state.message=result.message;state.preview=null;}catch(error){state.message=error.message;}finally{state.busy=false;redraw();}},'primary');apply.disabled=state.busy;detail.append(apply);}else if(!p.conflict)detail.append(el('p','此成果没有原资料修改，可在云端继续审阅。','muted'));box.append(detail);}
    box.append(el('p',state.message,'agent-feedback'));page.append(box);
  }
  function parseRoute() { const raw = location.hash.replace(/^#\/?/, '') || 'overview', split = raw.indexOf('?'); return { parts: (split < 0 ? raw : raw.slice(0, split)).split('/'), query: new URLSearchParams(split < 0 ? '' : raw.slice(split + 1)) }; }
  function setNav(page) { const name = ({ overview: '总览', products: '商品', customers: '客户', channels: '渠道', creation: '创作', library: '客户资料包' })[page] || '详情'; $('page-name').textContent = name; document.querySelectorAll('[data-nav]').forEach(item => item.classList.toggle('active', item.dataset.nav === page)); }
  async function renderRoute() {
    const serial = ++S.loadSerial, route = parseRoute(), requestedHash = location.hash; const routeIsCurrent = () => serial === S.loadSerial && location.hash === requestedHash; message(); S.route = location.hash; S.detail = null; S.object = null; S.listRefresh = null; const kind = route.parts[0];
    if (kind === 'object') {
      S.page = 'object'; setNav('overview'); $('page').replaceChildren(el('div', '正在打开这份资料…', 'loading-state'));
      try { const id = decodeURIComponent(route.parts.slice(1).join('/')), object = objectResult(await api(`/api/desk/object?id=${encodeURIComponent(id)}`)); if (!routeIsCurrent()) return; if (!object || String(object.id) !== String(id) || (id.startsWith('product:') && object.kind !== 'product') || (id.startsWith('customer:') && object.kind !== 'customer') || (id.startsWith('channel:') && object.kind !== 'channel')) throw new Error('返回资料与所选对象不一致，未打开。请重新选择。'); S.object = object; remember(object.id); const index = S.objects.findIndex(item => item.id === object.id); if (index < 0) S.objects.push(object); else S.objects[index] = object; setNav(object.kind === 'product' ? 'products' : object.kind === 'channel' ? 'channels' : 'customers'); $('page-name').textContent = object.title; renderObject(object, route.query.get('artifact')); }
      catch (error) { if (routeIsCurrent()) { $('page').replaceChildren(el('div', error.message, 'empty')); message(error.message); } }
      return;
    }
    S.page = ['products', 'customers', 'library', 'channels', 'creation'].includes(kind) ? kind : 'overview'; setNav(S.page); if (S.page === 'overview') renderOverview(); else if (S.page === 'library') await window.renderCustomerLibrary(); else if (S.page === 'channels') await renderChannels(); else if (S.page === 'creation') await renderCreation(route.query.get('item')); else renderSearchPage(S.page, route.query.get('q') || '');
  }
  function mountSearchConsole(card) {
    const section=el('section',undefined,'search-console-panel'), content=el('div');section.append(el('h3','Google 搜索表现'),content);card.append(section);
    async function load(){try{draw(await api('/api/desk/search-console'));}catch(error){content.replaceChildren(el('p',error.message,'muted'));}}
    function draw(data){
      content.replaceChildren();
      if(data.available && data.tables){
        const total=data.tables.totals?.[0] || {};content.append(el('p',`${data.period?.start || ''} 至 ${data.period?.end || ''} · 展示 ${total.impressions ?? 0} · 点击 ${total.clicks ?? 0} · 点击率 ${((total.ctr || 0)*100).toFixed(1)}%`),el('p',`上次更新：${time(data.last_success_at)}`,'muted'));
        for(const [name,title] of [['queries','买家搜索词'],['pages','网站页面'],['countries','国家']]){const rows=data.tables[name] || [];if(!rows.length)continue;const group=el('details');group.append(el('summary',title));for(const row of rows.slice(0,10))group.append(el('p',`${row.keys?.[0] || ''} · 展示 ${row.impressions ?? 0} · 点击 ${row.clicks ?? 0}`));content.append(group);}
      } else content.append(el('p',data.error || (data.state==='select_site'?'Google 已授权，请选择要分析的网站。':data.site_url?'已选网站，等待首次读取搜索数据。':'连接 Google 后查看本站搜索词与页面表现。'),'muted'));
      const feedback=el('p','','agent-feedback');
      if(data.state==='not_connected' || data.state==='error'){
        const options=el('details'), file=el('input');file.type='file';file.accept='.json,application/json';file.setAttribute('aria-label','Google 客户端 JSON');options.append(el('summary','如现有 Google 客户端不可用，选择客户端文件'),file);content.append(options);
        const connect=button('连接 Google 搜索数据',async()=>{connect.disabled=true;feedback.textContent='正在准备授权…';try{let config=null;if(file.files?.[0])config=JSON.parse(await file.files[0].text());const result=await api('/api/desk/search-console/oauth/start',{client_config:config});const a=link('继续 Google 登录并授权 ↗',result.authorization_url);if(!a)throw Error('未能准备授权链接');feedback.replaceChildren(a,el('span',' 完成授权后回到此页，点击重新读取。'));}catch(error){feedback.textContent=error.message;}finally{connect.disabled=false;}},'quiet');content.append(connect);
      }
      if(data.state==='select_site' || data.site_url){
        const choose=button('选择网站',async()=>{choose.disabled=true;feedback.textContent='正在读取可用网站…';try{const value=await api('/api/desk/search-console/sites');const select=el('select');select.setAttribute('aria-label','选择搜索网站');for(const row of value.items || []){const option=el('option',row.siteUrl);option.value=row.siteUrl;select.append(option);}if(!(value.items || []).length)throw Error('当前 Google 账号没有可读取的网站。');select.value=(value.items || []).find(row=>row.siteUrl==='https://www.beiqiang.online/')?.siteUrl || value.items[0].siteUrl;const save=button('使用这个网站',async()=>{try{await api('/api/desk/search-console/select',{site_url:select.value});feedback.textContent='已选择网站，正在后台更新搜索数据。';await load();}catch(error){feedback.textContent=error.message;}},'quiet');feedback.replaceChildren(select,save);}catch(error){feedback.textContent=error.message;}finally{choose.disabled=false;}},'quiet');content.append(choose);
      }
      if(data.site_url){const refresh=button('更新搜索数据',async()=>{refresh.disabled=true;feedback.textContent='正在读取 Google 搜索数据…';try{draw(await api('/api/desk/search-console/refresh',{}));}catch(error){feedback.textContent=error.message;refresh.disabled=false;}},'quiet');content.append(refresh);}
      content.append(feedback);
      if(data.state==='not_loaded')setTimeout(()=>{if(section.isConnected!==false)load();},4000);
    }
    load();
  }
  async function renderChannels() {
    const page = $('page'), serial = S.loadSerial, selected = parseRoute().query.get('view'); page.replaceChildren(heading('渠道', '从渠道继续经营', '查看已有数据和可以直接进入的工作。'));
    try { const data=await api('/api/desk/channels'); if (S.page !== 'channels' || serial !== S.loadSerial) return; const grid=el('div',undefined,'overview-grid');
      if (selected) page.append(button('查看全部渠道', () => { location.hash = '/channels'; }, 'quiet'));
      for (const item of data.channels || []) { if (selected && item.id !== selected) continue; const card=el('section',undefined,'card'); card.append(el('h2',item.title));
        if (item.id === 'website') { card.append(el('p',websiteText()),el('p',item.connection?.total == null ? '询盘数量暂不可用' : `现有网站询盘：${item.connection.total} 条`),button('查看网站询盘',()=>{location.hash='/customers?view=inquiries';},'quiet'));mountSearchConsole(card); }
        else if (item.id === 'alibaba') { const stamp=item.connection?.last_success_at; card.append(el('p',stamp ? `最近成功读取：${time(stamp)}` : '尚无可展示的近期读取记录。')); if(item.data?.ok && item.data.metrics) { const metrics=item.data.metrics; const labels={search_impressions:'搜索曝光',search_clicks:'搜索点击',visitors:'访客',inquiries:'询盘',tm_buyers:'TM买家',marketing_clicks:'营销点击'}; card.append(el('p',`历史数据 ${item.data.period || ''} · ${item.data.timezone || ''}`)); const line=Object.entries(labels).filter(([k])=>metrics[k] != null).map(([k,v])=>`${v} ${metrics[k]}`).join(' · '); if(line)card.append(el('p',line)); card.append(el('p','商品口径汇总，人数未去重；不用于计算转化率。','muted')); } card.append(button('查看商品',()=>{location.hash='/products';},'quiet'),button('查看订单买家',()=>{location.hash='/customers?view=inquiries&source=orders';},'quiet')); }
        else {
          const detail = item.data || {};
          card.append(el('p', detail.available === false ? '当前未取到该渠道数据。' : (text(detail.scope) || '暂无可展示的指标。')));
          if (detail.observed_at) card.append(el('p', `上次观测：${time(detail.observed_at)}`, 'muted'));
          if (item.id === 'douyin') {
            card.append(el('p', '成交、流量和售后指标尚未接入；可手动检查连接并读取各店在售商品首页。', 'muted'));
            const result=el('div'), check=button('检查两店连接',async()=>{
              check.disabled=true;result.replaceChildren(el('p','正在分别检查两家店…'));
              try{
                const data=await api('/api/desk/douyin?check_unbound=1');
                if(S.page!=='channels' || serial!==S.loadSerial)return;
                result.replaceChildren();
                for(const shop of data.shops || []){
                  const section=el('section',undefined,'artifact-row');section.append(el('h3',shop.title || '店铺'));
                  if(shop.ok){
                    const page=shop.pagination || {},items=shop.data?.items || [];
                    section.append(el('p',`读取成功 · ${shop.collectedAt ? time(shop.collectedAt) : '时间未提供'} · 本页 ${page.returned ?? items.length} 款 · 平台总数 ${page.total ?? '未提供'} 款`),el('p','仅在售商品第一页；平台填报库存不等于实物库存。','muted'));
                    if(items.length){const details=el('details');details.append(el('summary','查看本页商品'));for(const product of items)details.append(el('p',text(product.title || product.name || '未提供商品名称')));section.append(details);}
                  } else {
                    section.append(el('p',shop.error?.message || '店铺读取失败'));
                    if(shop.session?.message)section.append(el('p',shop.session.message));
                    if(shop.error?.code==='session_expired' || shop.session?.state==='expired')section.append(el('p','请正常续登并恢复该店本地连接；网页登录本身不一定更新工作台会话。','muted'));
                  }
                  result.append(section);
                }
                if(!(data.shops || []).length)result.append(el('p',data.error || '未取得店铺检查结果。'));
                if(data.notice)result.append(el('p',data.notice,'muted'));
              }catch(error){result.replaceChildren(el('p',error.message));}finally{check.disabled=false;}
            },'quiet');
            const snapshotResult=el('div'), snapshot=button('查看品牌店商品快照',async()=>{
              snapshot.disabled=true;snapshotResult.replaceChildren(el('p','正在读取本地快照…'));
              try {
                const data=await api('/api/desk/douyin?snapshot=1');
                if(S.page!=='channels' || serial!==S.loadSerial)return;
                snapshotResult.replaceChildren();
                if(!data.available){snapshotResult.append(el('p',data.message || '本地快照暂不可用。'));return;}
                const section=el('section',undefined,'artifact-row');section.append(el('h3',data.shop),el('p',`${data.source} · ${time(data.capturedAt)} · ${data.count} 条`),el('p',data.notice,'muted'));
                const details=el('details');details.append(el('summary','查看快照商品标题'));for(const product of data.items || [])details.append(el('p',text(product.title)));section.append(details);snapshotResult.append(section);
              } catch {snapshotResult.replaceChildren(el('p','本地快照暂不可读。'));} finally {snapshot.disabled=false;}
            },'quiet');
            const bridgeResult=el('div'), pair=button('连接品牌店实时数据',async()=>{
              pair.disabled=true;bridgeResult.replaceChildren(el('p','正在准备连接…'));
              try {
                const data=await api('/api/desk/miaoshou-bridge/issue',{});
                if(S.page!=='channels' || serial!==S.loadSerial)return;
                if(typeof data.code!=='string' || !Number.isFinite(data.expires_in))throw new Error('未取得有效连接码，请重试。');
                bridgeResult.replaceChildren(el('p','在已登录品牌店的妙手页面打开“贝强妙手只读连接”，填入以下一次性连接码。保持该页面打开，工作台和 Agent 才能读取实时商品。'),el('code',data.code),el('p',`连接码 ${Math.floor(data.expires_in/60)} 分钟内有效。`,'muted'));
                bridgeResult.append(button('复制连接码',async()=>{await navigator.clipboard.writeText(data.code);toast('连接码已复制');},'quiet'));
              } catch(error){bridgeResult.replaceChildren(el('p',error.message));} finally {pair.disabled=false;}
            },'quiet');
            const bridgeStatus=button('检查实时连接',async()=>{
              bridgeStatus.disabled=true;
              try {const data=await api('/api/desk/miaoshou-bridge/status',{});if(S.page==='channels' && serial===S.loadSerial)bridgeResult.replaceChildren(el('p',data.online?'连接在线；读取时会再次核验妙手登录及店铺。':data.paired?'已配对，但当前页面暂未在线。':'尚未配对实时连接。'));}
              catch(error){bridgeResult.replaceChildren(el('p',error.message));}finally{bridgeStatus.disabled=false;}
            },'quiet');
            const actions=el('div',undefined,'channel-actions');
            actions.append(pair,bridgeStatus,button('交给 Agent 经营抖店',()=>{location.hash='/object/channel%3Adouyin';},'quiet'),check,snapshot,button('查看商品中心', () => { location.hash = '/products'; }, 'quiet'),button('进入内容创作', () => { location.hash = '/creation'; }, 'quiet'));
            card.append(actions,result,snapshotResult,bridgeResult);
          }
          else for (const action of item.actions || []) if (text(action)) card.append(el('p', text(action), 'muted'));
        }
        if (item.id === 'alibaba' && item.quality) {
          const quality=item.quality, section=el('section',undefined,'channel-quality');
          section.append(el('h3','商品质量分'),el('p',quality.notice,'muted'));
          if(quality.available){
            section.append(el('p',`汇总完成：${time(quality.observed_at)} · 评分采集：${quality.score_observed_from ? time(quality.score_observed_from) : '未知'} 至 ${quality.score_observed_to ? time(quality.score_observed_to) : '未知'} · 目录 ${quality.catalog_total ?? '未知'} · 已检查 ${quality.selected ?? '未知'} · 有评分 ${quality.scored ?? '未知'} · 失败 ${quality.error_count} · 无评分 ${quality.missing_score_count} · ${quality.complete ? '全量检查完成' : '结果不完整'} · 采集时低于 5.0：${quality.below_5_count}`));
            if(quality.catalog_state_counts) section.append(el('p',`平台目录字段：${Object.entries(quality.catalog_state_counts).map(([state,count])=>`${state} ${count}`).join(' · ')}；字段状态不代表买家页验收。`,'muted'));
            for(const row of quality.below_5 || []){
              const entry=el('article',undefined,'artifact-row');entry.append(el('h4',`${row.model || '商品'} · 链接 ${row.id} · ${row.score} 分`));
              if(row.platform_reason)entry.append(el('p',`采集时平台提示：${row.platform_reason}`));
              if(row.problems?.length)entry.append(el('p',`采集时平台诊断代码：${row.problems.join('、')}`,'muted'));
              if(row.recorded_score?.scope)entry.append(el('p',`商品档案另有评分 ${row.recorded_score.score} · ${row.recorded_score.scope}`));
              const objectId=row.object_id || (item.product_analysis?.items || []).find(value=>String(value.listing_id)===String(row.id))?.object_id;
              if(objectId)entry.append(button('查看当前商品',()=>{location.hash=`/object/${encodeURIComponent(objectId)}?listing=${encodeURIComponent(row.id)}`;},'quiet'));
              section.append(entry);
            }
            const otherIssues=(quality.issues || []).filter(row=>!(typeof row.score==='number' && row.score<5));
            if(otherIssues.length){
              const details=el('details'), summary=el('summary',`其他有平台问题的商品：${otherIssues.length}`);details.append(summary);
              for(const row of otherIssues){const entry=el('article',undefined,'artifact-row');entry.append(el('h4',`${row.model || '商品'} · 链接 ${row.id} · ${row.score ?? '无评分'} 分`));if(row.platform_reason)entry.append(el('p',`采集时平台提示：${row.platform_reason}`));entry.append(el('p',`采集时平台诊断代码：${(row.problems || []).join('、')}`,'muted'));const objectId=row.object_id || (item.product_analysis?.items || []).find(value=>String(value.listing_id)===String(row.id))?.object_id;if(objectId)entry.append(button('查看当前商品',()=>{location.hash=`/object/${encodeURIComponent(objectId)}?listing=${encodeURIComponent(row.id)}`;},'quiet'));details.append(entry);}section.append(details);
            }
          }
          card.append(section);
        }
        if (item.id === 'alibaba' && item.product_analysis) {
          const analysis=item.product_analysis, section=el('section',undefined,'channel-product-analysis');
          section.append(el('h3','商品经营分析'),el('p',analysis.notice,'muted'));
          if(analysis.available) {
            section.append(el('p',`历史统计期：${analysis.period || '未提供'} · ${analysis.timezone || ''} · 观测：${time(analysis.observed_at)}`));
            const filter=el('select'), label=el('label','按重点行动筛选 '), list=el('div'), more=el('div');
            const counts=new Map();for(const row of analysis.items || [])counts.set(row.action,(counts.get(row.action)||0)+1);
            const all=el('option',`全部链接（${analysis.total}）`);all.value='';filter.append(all);
            for(const [action,count] of counts){const option=el('option',`${action}（${count}）`);option.value=action;filter.append(option);}
            label.append(filter);section.append(label,list,more);let limit=20;
            function draw(){
              const rows=(analysis.items || []).filter(row=>!filter.value || row.action===filter.value);list.replaceChildren();more.replaceChildren();
              for(const row of rows.slice(0,limit)){
                const entry=el('article',undefined,'artifact-row');entry.append(el('h4',`${row.model || '商品'} · 链接 ${row.listing_id}`),el('p',row.action));
                const labels={search_impressions:'搜索曝光',search_clicks:'搜索点击',visitors:'访客',inquiries:'询盘',tm_buyers:'TM买家'};
                entry.append(el('p',Object.entries(labels).map(([key,title])=>`${title} ${row.metrics?.[key] ?? '无报表数据'}`).join(' · ')));
                if(row.object_id)entry.append(button('查看当前商品与平台链接',()=>{location.hash=`/object/${encodeURIComponent(row.object_id)}?listing=${encodeURIComponent(row.listing_id)}`;},'quiet'));
                else entry.append(el('p',row.association==='ambiguous'?'此链接关联多个商品，先核商品对应。':'此历史链接尚未关联当前商品。','muted'));
                list.append(entry);
              }
              more.append(el('p',`显示 ${Math.min(limit,rows.length)} / ${rows.length} 条历史链接`,'muted'));
              if(rows.length>limit)more.append(button('再显示20条',()=>{limit+=20;draw();},'quiet'));
            }
            filter.addEventListener('change',()=>{limit=20;draw();});draw();
          }
          card.append(section);
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
          const outcomes=el('section',undefined,'card'); outcomes.append(el('h2','创作成果'),el('p','查看并编辑保存在原项目的成果。','artifact-note'));
          const tabs=el('div',undefined,'artifact-tabs'), editor=el('div'); outcomes.append(tabs,editor); const ctx={object,tabs,editor,artifacts:[],selectedId:null,currentEdit:null,requestedArtifact:parseRoute().query.get('artifact')}; S.detail=ctx;
          page.append(outcomes);await refreshArtifacts(ctx,true);
        } catch(error) { if(current())page.append(el('p',`创作助手暂不可用：${error.message}`,'inline-error')); }
        return; }
      page.append(libtvPanel(),sectionHeading('本地创作项目','项目原文与关联素材'));
      const result=await api('/api/desk/creation'); if(S.page!=='creation')return; const list=el('div',undefined,'row-list');
      const input=el('input',undefined,'search-input'); input.type='search'; input.placeholder='搜索项目名称或内容'; input.setAttribute('aria-label','搜索创作项目'); page.append(input,list);
      function showProjects() { list.replaceChildren(); const query=input.value.trim().toLowerCase(); for(const item of result.projects || []) { if(query && !`${item.title} ${item.summary}`.toLowerCase().includes(query))continue; const card=el('article',undefined,'card work-row'),info=el('div'); const summary=creativeSummary(item.summary); info.append(el('h3',item.title)); if(summary)info.append(el('p',summary.slice(0,160))); info.append(el('small',`项目记录更新：${time(item.updated_at*1000)}`)); card.append(info,button('打开项目 →',()=>{location.hash=`/creation?item=${encodeURIComponent(item.id)}`;},'quiet'));list.append(card); } if(!list.children.length)empty(list,'没有找到匹配项目。'); } input.addEventListener('input',showProjects); showProjects();
    } catch(error) { message(error.message); }
  }
  function renderSearchPage(kind, query) {
    if (kind === 'customers' && parseRoute().query.get('view') === 'batches') { renderCustomerBatches(); return; }
    if (kind === 'customers' && parseRoute().query.get('view') === 'competitors') { renderCompetitors(); return; }
    if (kind === 'customers' && parseRoute().query.get('view') !== 'inquiries') { renderDevelopment(); return; }
    if (kind === 'customers' && parseRoute().query.get('source') !== 'orders') { renderInquiryQueue(query); return; }
    const listRouteSerial = S.loadSerial; const listIsCurrent = () => listRouteSerial === S.loadSerial && parseRoute().parts[0] === kind;
    const gapView = kind === 'products' && parseRoute().query.get('view') === 'gaps';
    const page = $('page'), labels = { products: ['商品资料', '商品', '从真实产品、规格与素材出发，整理可以直接使用的选款资料。'], customers: ['客户与需求', '客户', '需求、来源与准备中的回复，放在同一处继续。'], library: ['查找资料', '资料', '跨商品与客户查找原文、图片和已有资料，不搬动原文件。'] };
    page.replaceChildren(heading(...labels[kind])); if (kind === 'customers') page.append(customerTabs('inquiries')); if (kind === 'customers' || kind === 'library') page.append(websiteLabel()); if (gapView) { const bar = el('div', undefined, 'gap-view-bar'); bar.append(el('p', '查看尚未关联的商品图片、供货链接和国际站链接。', 'muted'), button('查看全部商品 →', () => { location.hash = '/products'; }, 'quiet')); page.append(bar); } const input = el('input', undefined, 'search-input'); input.type = 'search'; input.value = query; input.placeholder = kind === 'products' ? '搜索款号、名称或商品信息' : kind === 'customers' ? '搜索客户、需求或来源' : '搜索商品、客户与关联资料'; input.setAttribute('aria-label', '搜索资料'); const sourceSelect = kind === 'customers' ? el('select', undefined, 'source-filter') : null; if (sourceSelect) { for (const [value, label] of [['records', '需求与客户记录'], ['orders', '国际站订单买家（非询盘）'], ['all', '全部来源（分类型）']]) { const option = el('option', label); option.value = value; sourceSelect.append(option); } sourceSelect.value = parseRoute().query.get('source') || 'records'; sourceSelect.setAttribute('aria-label', '客户来源类型'); } const category = el('select'); category.setAttribute('aria-label', '商品分类'); for (const [v,l] of [['','全部分类'],['lace','系带鞋'],['slip','套脚鞋'],['boot','靴'],['sandal','凉鞋与拖鞋'],['clog','洞洞鞋'],['loafer','乐福与豆豆鞋'],['other','其他与待分类']]) { const o=el('option',l); o.value=v; category.append(o); } const supplyFilter = el('select'); supplyFilter.setAttribute('aria-label', '供货方式'); for (const [v,l] of [['','全部供货方式'],['own','自有工厂'],['external','外采供货'],['unconfirmed','供货方式未录入']]) { const o=el('option',l); o.value=v; supplyFilter.append(o); } const count = el('span', '', 'search-count'), list = el('div', undefined, kind === 'products' ? 'product-grid' : kind === 'library' ? 'library-grid' : 'row-list'); const search = el('div', undefined, 'search-bar'); search.append(input); if (kind === 'products') { search.append(category,supplyFilter); category.addEventListener('change', () => find(input.value)); supplyFilter.addEventListener('change', () => find(input.value)); } if (sourceSelect) search.append(sourceSelect); search.append(count); page.append(search); if (kind === 'customers') { const orderStatus = el('p', '', 'alibaba-source-status website-status'); orderStatus.textContent = alibabaText(); page.append(orderStatus, button('更新订单买家（第 1 页）', async () => { try { const result = await api('/api/desk/alibaba/refresh', { page: 1 }); S.alibabaStatus = result.status || result; orderStatus.textContent = alibabaText(); } catch (error) { message(error.message); } }, 'quiet order-refresh')); } page.append(list); let timer, searchSerial = 0;
    async function find(value) { const sequence = ++searchSerial; count.textContent = '正在查找…'; try { const endpointKind = kind === 'products' ? 'product' : kind === 'customers' ? 'customer' : ''; const result = await api(`/api/desk/objects?q=${encodeURIComponent(value)}&kind=${endpointKind}`); if (sequence !== searchSerial || S.page !== kind || !listIsCurrent()) return; let rows = array(result, 'objects').filter(object => !sourceSelect || sourceSelect.value === 'all' || (sourceSelect.value === 'orders' ? object.source_type === 'alibaba_order_buyer' : object.source_type !== 'alibaba_order_buyer')); if (kind === 'products') { rows = rows.filter(object => !/^HR[-_]?\d+$/i.test(object.title)); if (category.value) rows = rows.filter(object => productCategory(object) === category.value); if (supplyFilter.value) rows = rows.filter(object => (object.supply?.kind || 'unconfirmed') === supplyFilter.value); rows.sort((a,b) => productCategory(a).localeCompare(productCategory(b), 'zh-CN') || text(a.title).localeCompare(text(b.title), 'zh-CN', {numeric:true})); } list.replaceChildren(); count.textContent = kind === 'customers' ? `${sourceSelect.value === 'orders' ? '订单买家' : '来源记录'} ${rows.length} 份` : `${rows.length} 项结果`;
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
  const batchReviewNames = {pending:'待审核',approved:'通过',changes_requested:'需修改',deferred:'暂缓',do_not_contact:'不联系'};
  async function renderCustomerBatches() {
    const page=$('page'), serial=S.loadSerial, view=S.batchView;
    const current=()=>serial===S.loadSerial && parseRoute().query.get('view')==='batches';
    page.replaceChildren(heading('客户开发','集中审阅开发批次','逐个看依据、草稿与历史；选中客户研究，或将已审核邮件送检后集中确认发送。'),customerTabs('batches'));
    const controls=el('div',undefined,'batch-controls'), feedback=el('p','','agent-feedback');
    const select=selectField(controls,'开发批次',[['','选择批次']],view.id), search=addField(controls,'搜索批次内客户',view.query), filter=selectField(controls,'审核状态',[['','全部状态'],...Object.entries(batchReviewNames)],view.state);
    const create=el('details',undefined,'card batch-create'), form=el('div',undefined,'profile-form');create.append(el('summary','新建开发批次'));
    const title=addField(form,'批次名称'), target=addField(form,'目标与范围','',true);
    form.append(button('创建批次',async()=>{if(!title.value.trim()){feedback.textContent='请填写批次名称。';return;}const data=await api('/api/customer-batches',{title:title.value.trim(),target:target.value});view.id=data.id;view.selected='';await loadBatches();await read();},'quiet'));create.append(form);
    const layout=el('div',undefined,'batch-layout'), queue=el('section',undefined,'batch-queue'), detail=el('section',undefined,'batch-detail'), count=el('p','','search-count');
    layout.append(queue,detail);page.append(controls,create,feedback,count,layout);let data=null,sequence=0,detailSequence=0;
    const dirty=()=>!!(S.detail?.batch && S.edits.get(`gmail:${S.detail.object.id}`)?.dirty);
    view.selections ||= new Map();
    const picks=()=>{if(!view.selections.has(view.id))view.selections.set(view.id,{research:new Set(),send:new Set()});return view.selections.get(view.id);};
    const actions=el('section',undefined,'card batch-actions'), actionResult=el('div',undefined,'batch-operation-results'), selectionCount=el('p','','muted'), instructions=addField(actions,'所选客户研究要求','',true,'说明本批次要研究的客户方向、证据及开发信重点');let operationBusy=false,selectionRevision=0;
    const reasonText=value=>Array.isArray(value)?value.map(item=>typeof item==='string'?item:item.message || item.reason || '').filter(Boolean).join('；'):text(value);
    const sendEligible=item=>item.review_state==='approved' && !item.review_stale && item.draft?.status==='draft';
    function invalidatePlan(){selectionRevision++;actionResult.replaceChildren();}
    function selectedRows(kind){return (data?.items || []).filter(row=>picks()[kind].has(row.object_id));}
    function selectionSummary(){selectionCount.textContent=`已选研究 ${picks().research.size} 位（每次 1–8 位） · 已选送检 ${picks().send.size} 封`;}
    function showSendResults(value){actionResult.replaceChildren(el('h3','逐封发送结果'));for(const row of value.items || value.results || []){const state=({sent:'已发送',not_sent:'未发送',unknown:'发送结果未知',sending:'发送结果未知',pending:'未发送'})[row.status] || '发送结果未知';actionResult.append(el('p',`${row.to || data?.items.find(item=>item.object_id===row.object_id)?.draft?.to || row.object_id} · ${state}${row.reason?' · '+reasonText(row.reason):''}`,row.status==='sent'?'':'inline-error'));}actionResult.append(el('p','结果未知或连接中断时先核对原邮件记录；此处不会自动重发。','muted'));}
    const newRequestId=()=>globalThis.crypto?.randomUUID?.().replaceAll('-','') || Array.from({length:32},()=>Math.floor(Math.random()*16).toString(16)).join('');
    function showResearchResults(value){actionResult.replaceChildren(el('h3','客户研究启动结果'));for(const row of value.results || []){const label=data?.items.find(item=>item.object_id===row.object_id)?.customer?.title || row.object_id;actionResult.append(el('p',`${label} · ${({started:'已开始',existing:'已有工作，请查看进度',blocked:'已阻止',not_started:'未开始'})[row.status] || '未确认启动'}${row.reason?' · '+reasonText(row.reason):''}`,['started','existing'].includes(row.status)?'':'inline-error'));if(row.job){const index=S.jobs.findIndex(job=>job.id===row.job.id);if(index<0)S.jobs.unshift(row.job);else S.jobs[index]=row.job;}}if(S.detail?.batch)renderAgentJobs(S.detail);}
    const research=button('研究所选客户',async()=>{if(operationBusy)return;const ids=selectedRows('research').map(row=>row.object_id);if(!data || ids.length<1 || ids.length>8){actionResult.replaceChildren(el('p','请选择 1–8 位客户研究。','inline-error'));return;}if(dirty()){actionResult.replaceChildren(el('p','请先保存当前客户邮件修改。','inline-error'));return;}const batchId=view.id;operationBusy=true;research.disabled=true;preflight.disabled=true;actionResult.replaceChildren(el('p','正在创建客户研究工作…'));try{const value=await api('/api/desk/customer-batches/research',{batch_id:batchId,revision:data.revision,object_ids:ids,instruction:instructions.value.trim() || '结合当前批次目标研究客户并准备个性化邮件。',request_id:newRequestId()});if(!current() || view.id!==batchId)return;showResearchResults(value);await loadResearchGroups();}catch(error){if(current() && view.id===batchId){actionResult.replaceChildren(el('p',`${error.message} 请先查看本批研究进度，核对已有工作后再继续。`,'inline-error'));await loadResearchGroups();}}finally{operationBusy=false;research.disabled=false;preflight.disabled=false;}},'quiet');
    const preflight=button('检查所选邮件并准备确认',async()=>{if(operationBusy)return;const rows=selectedRows('send');if(!data || !rows.length || rows.some(row=>!sendEligible(row))){actionResult.replaceChildren(el('p','请选择审核通过且未变化的邮件。','inline-error'));return;}if(dirty()){actionResult.replaceChildren(el('p','请先保存当前客户邮件修改并重新审核。','inline-error'));return;}const batchId=view.id,ids=rows.map(row=>row.object_id),checkedSelection=selectionRevision;operationBusy=true;research.disabled=true;preflight.disabled=true;actionResult.replaceChildren(el('p','正在检查当前草稿、客户历史及发送条件…'));try{const value=await api(`/api/customer-batches/${encodeURIComponent(batchId)}/preflight`,{revision:data.revision,object_ids:ids});if(!current() || view.id!==batchId || selectionRevision!==checkedSelection)return;actionResult.replaceChildren(el('h3',`发送前检查 · ${value.items?.length || 0} 封`));for(const row of value.items || []){const entry=el('article',undefined,'batch-send-entry');entry.append(el('p',`收件人：${row.to || '未提供'}`),el('p',`主题：${row.subject || '未提供'}`));const why=reasonText(row.reasons) || reasonText(row.checks?.reasons);if(why)entry.append(el('p',why,'inline-error'));actionResult.append(entry);}const allClear=value.can_confirm===true && !!value.plan_id && value.items?.length===ids.length && new Set(value.items.map(row=>row.object_id)).size===ids.length && value.items.every(row=>ids.includes(row.object_id) && !!row.to && !!row.subject && row.can_confirm===true && row.checks?.status==='clear' && !(row.reasons || []).length && !(row.checks?.reasons || []).length);if(!allClear){actionResult.append(el('p','本次存在未通过或未知项目，不能确认发送。请处理原因后重新检查。','inline-error'));return;}if(value.expires_at)actionResult.append(el('p',`本次确认有效至 ${time(value.expires_at)}`,'muted'));let consumed=false;const confirm=button(`确认发送以上 ${value.items.length} 封邮件`,async()=>{if(consumed)return;consumed=true;confirm.disabled=true;confirm.textContent='已提交，正在等待逐封结果…';try{const result=await api(`/api/customer-batches/${encodeURIComponent(batchId)}/send`,{plan_id:value.plan_id,confirmed:true});if(current() && view.id===batchId)showSendResults(result);}catch(error){if(current() && view.id===batchId)actionResult.replaceChildren(el('p',`发送结果未知：${error.message}。请先核对原邮件记录，不要重复发送。`,'inline-error'));}},'primary');actionResult.append(el('p','请逐项核对上方全部地址和主题；点击后将按本次已检查的版本逐封发送。'),confirm);}catch(error){if(current() && view.id===batchId)actionResult.replaceChildren(el('p',error.message,'inline-error'));}finally{operationBusy=false;research.disabled=false;preflight.disabled=false;}},'primary');
    actions.append(selectionCount,research,preflight,actionResult);page.insertBefore(actions,layout);

    const researchGroups=el('details',undefined,'card batch-research-groups'),groupList=el('div'),groupFeedback=el('p','','agent-feedback');
    researchGroups.append(el('summary','本批研究进度与接续'),el('p','每位客户的工作分别保存；断开后先读取进度，已完成或结果不明的工作不会自动重跑。','muted'),button('刷新研究进度',()=>loadResearchGroups(),'quiet'),groupFeedback,groupList);page.insertBefore(researchGroups,layout);
    async function loadResearchGroups(){const batchId=view.id;if(!batchId){groupList.replaceChildren();return;}try{const value=await api(`/api/desk/customer-batches/research-groups?batch_id=${encodeURIComponent(batchId)}`);if(!current() || view.id!==batchId)return;groupList.replaceChildren();for(const group of value.items || []){const box=el('section',undefined,'analysis-block');box.append(el('h3',`${time(group.created_at)} · ${group.requested.length} 位客户`),el('p',group.instruction));for(const oid of group.requested){const item=data?.items.find(row=>row.object_id===oid),job=(group.jobs || []).find(row=>row.object_id===oid),label=item?.customer?.title || oid;const reason=(!job || job.status==='planned') && group.last_reasons?.[oid];box.append(el('p',`${label} · ${job ? (statusNames[job.status] || '状态待核对') : '尚未创建，请核对后继续'}${reason?' · 上次原因：'+reason:''}`));}if(group.status!=='cancelled' && ((group.not_planned || []).length || (group.jobs || []).some(job=>job.status==='planned'))){const resume=button('继续尚未启动的客户研究',async()=>{if(operationBusy)return;operationBusy=true;resume.disabled=true;try{const result=await api('/api/desk/customer-batches/research-continue',{group_id:group.id});if(current() && view.id===batchId){showResearchResults(result);await loadResearchGroups();}}catch(error){if(current() && view.id===batchId)groupFeedback.textContent=`${error.message} 请刷新进度后核对。`;}finally{operationBusy=false;resume.disabled=false;}},'quiet');box.append(resume);}groupList.append(box);}if(!(value.items || []).length)groupList.append(el('p','本批暂无可接续的批量研究。','muted'));groupFeedback.textContent='';}catch(error){if(current() && view.id===batchId)groupFeedback.textContent=`研究进度暂无法读取：${error.message}`;}}

    function resetDetail(){S.detail=null;detailSequence++;detail.replaceChildren(el('p','选择一位客户，在此查看依据、草稿、附件及往来。','empty-state'));}
    function paint(){renderAddChoices();for(const id of picks().send){if(!(data?.items || []).some(row=>row.object_id===id && sendEligible(row)))picks().send.delete(id);}selectionSummary();queue.replaceChildren();const rows=(data?.items || []).filter(item=>(!view.state || item.review_state===view.state) && (!view.query || text([item.customer,item.draft?.to,item.notes]).toLowerCase().includes(view.query.toLowerCase())));count.textContent=`${rows.length} 位客户 · ${data?.title || '尚未选择批次'}`;
      for(const item of rows){const c=item.customer || {},draft=item.draft || {},row=el('article',undefined,`card batch-row${view.selected===item.object_id?' selected':''}`);
        const choices=el('div',undefined,'batch-row-picks');for(const [kind,label] of [['research','选择研究'],['send','选择送检']]){const wrap=el('label'),check=el('input');check.type='checkbox';check.setAttribute('aria-label',`${label} ${c.title || item.object_id}`);check.checked=picks()[kind].has(item.object_id);if(kind==='send')check.disabled=!sendEligible(item);check.addEventListener('change',()=>{if(check.checked && !check.disabled)picks()[kind].add(item.object_id);else picks()[kind].delete(item.object_id);selectionSummary();invalidatePlan();});wrap.append(check,el('span',label));choices.append(wrap);}row.append(choices);
        row.append(el('h3',c.title || item.object_id),el('p',[c.country,c.customer_type,c.source_type].filter(Boolean).join(' · '),'muted'),el('p',`收件人：${draft.to || '尚未准备'} · ${item.quality?.contact_state || '联系入口待核对'}`),el('p',c.summary || c.reason || item.notes || '打开客户，查看适配理由与来源。'),el('p',`${batchReviewNames[item.review_state] || '待审核'}${item.review_stale?' · 草稿已变化，需重新审核':''} · ${draft.status || '尚无草稿'} · 附件 ${draft.attachment_count || 0} 份`));
        if(item.quality?.reasons?.length)row.append(el('p',text(item.quality.reasons),'inline-error'));
        row.append(button('审阅这位客户',()=>openItem(item),'quiet'));queue.append(row);}
      if(!rows.length)queue.append(el('p',data?'当前筛选没有客户。可将已有客户加入批次。':'先选择或创建一个批次。','empty-state'));
    }
    async function read(){const seq=++sequence;if(!view.id){data=null;paint();resetDetail();return;}try{const result=await api(`/api/customer-batches/${encodeURIComponent(view.id)}`);if(!current() || seq!==sequence)return;data=result;paint();return true;}catch(error){if(current())feedback.textContent=error.message;return false;}}
    async function loadBatches(){const result=await api('/api/customer-batches');if(!current())return;select.replaceChildren();for(const item of result.items || []){const option=el('option',item.title);option.value=item.id;select.append(option);}if(!(result.items || []).some(item=>item.id===view.id))view.id=result.items?.[0]?.id || '';select.value=view.id;}
    async function openItem(item){if(dirty()){feedback.textContent='请先保存当前客户的邮件修改，再切换客户。';return;}const seq=++detailSequence;let reviewedRevision=data.revision, reviewedItemRevision=item.item_revision;view.selected=item.object_id;S.detail=null;paint();detail.replaceChildren(el('p','正在读取客户与邮件…'));
      try{const object=objectResult(await api(`/api/desk/object?id=${encodeURIComponent(item.object_id)}`));if(!current() || seq!==detailSequence)return;if(!object || object.id!==item.object_id)throw Error('客户资料与所选客户不一致。');
        detail.replaceChildren(el('h2',object.title || item.customer?.title),el('p',object.summary || item.customer?.summary || '请阅读来源并判断是否值得联系。'));
        const evidence=el('details',undefined,'card');evidence.open=true;evidence.append(el('summary','客户来源、采购依据与推荐产品'));
        for(const fact of object.facts || [])evidence.append(el('p',`${fact.label}：${text(fact.value)}`));
        for(const source of [...(object.links || []),...(item.evidence || [])]){if(source.text)evidence.append(el('p',source.text));const a=link(source.label || source.title || '查看来源 ↗',source.url);if(a)evidence.append(a);if(source.observed_at)evidence.append(el('small',`观察日期：${time(source.observed_at)}`));}
        if(object.content){const original=el('details');original.append(el('summary','客户原始资料'),el('pre',object.content,'mail-review-text'));evidence.append(original);}
        for(const product of item.recommended_products || [])evidence.append(el('p',text(product)));detail.append(evidence);
        const ctx={object,batch:true};S.detail=ctx;mountGmail(ctx,detail);await openGmailComposer(ctx);if(!current() || S.detail!==ctx)return;
        const crm=item.checks?.crm,manualCRM=item.checks?.crm_manual_review,crmEligible=crm?.status==='已读取' && crm.match_status==='未匹配' && crm.stop_state==='未知';
        if(crmEligible || manualCRM?.applied || manualCRM?.stale){
          const card=el('section',undefined,'card batch-crm-review'), status=el('p','','agent-feedback'), fields={};
          card.append(el('h3','记录CRM未匹配的人工核对依据'),el('p','此操作只记录该客户、该范围的人工核对，不等于邮件审核、联系许可或发送授权；不能解除明确退订、拒绝、退信或邮箱检查未知。','muted'));
          function showSaved(review){card.replaceChildren(el('h3','已保存的CRM人工核对依据'),el('p',`记录时间：${time(review.recorded_at)}`),el('p','仅记录该范围的人工核对，不等于邮件审核、联系许可或发送授权；不能解除明确退订、拒绝、退信或邮箱检查未知。','muted'));for(const [key,title] of [['aliases','品牌与法律实体别名'],['independent_sends','独立发送记录'],['stop_records','停止联系记录']]){const proof=review.evidence?.[key] || {},group=el('div',undefined,'analysis-block');group.append(el('h4',title));if(key==='aliases')group.append(el('p',`已核别名：${text(proof.terms) || '未提供'}`));group.append(el('p',`查询位置：${text(proof.locations) || '未提供'}`),el('p',`核查结果：${proof.findings || '未提供'}`));card.append(group);}if(review.note)card.append(el('p',review.note,'muted'));}
          if(manualCRM?.applied===true && !manualCRM.stale){showSaved(manualCRM);detail.append(card);}
          else {
          if(manualCRM?.stale)card.append(el('p',`上次核对已失效（记录于 ${time(manualCRM.recorded_at)}）。客户来源、发件账号、收件地址或CRM内容发生变化，须按当前资料重新核查。`,'inline-error'));
          if(crmEligible){
          for(const [key,title] of [['aliases','品牌与法律实体别名'],['independent_sends','独立发送记录'],['stop_records','停止联系记录']]){const group=el('div',undefined,'analysis-block'), label=el('label'), check=el('input');check.type='checkbox';check.checked=false;check.setAttribute('aria-label',`确认已核${title}`);label.append(check,el('span',`我已核对${title}`));group.append(el('h4',title),label);const locations=addField(group,`${title}：具体查询位置`,'',true,'每行填写一处实际核查的文件、系统页面或链接'),findings=addField(group,`${title}：具体核查结果`,'',true,'写明查到什么、未查到什么，以及核查范围');const terms=key==='aliases'?addField(group,'实际核对的品牌或法律实体别名','',true,'每行一个已查询的名称'):null;fields[key]={check,locations,findings,terms};card.append(group);}
          const lines=value=>value.split(/\r?\n/).map(part=>part.trim()).filter(Boolean);let attempted=false;
          const save=button('记录本客户CRM人工核对依据',async()=>{if(attempted)return;const evidence={};for(const [key,field] of Object.entries(fields)){const locations=lines(field.locations.value),findings=field.findings.value.trim(),terms=field.terms?lines(field.terms.value):null;if(!field.check.checked || !locations.length || !findings || (terms && !terms.length)){status.textContent='请逐项填写具体查询位置、核查结果和已核别名，并主动勾选各项确认。';return;}evidence[key]={checked:true,locations,findings,...(terms?{terms}:{})};}if(dirty()){status.textContent='请先保存邮件修改并重新读取本客户。';return;}if(item.item_revision==null){status.textContent='当前客户快照未知，请重新读取。';return;}attempted=true;save.disabled=true;try{const value=await api('/api/desk/customer-batches/crm-review',{batch_id:view.id,object_id:item.object_id,item_revision:item.item_revision,evidence,confirmed:true});if(!current() || S.detail!==ctx)return;data=value.batch;invalidatePlan();paint();const saved=data.items.find(row=>row.object_id===item.object_id)?.checks?.crm_manual_review;if(saved?.applied===true && !saved.stale){showSaved(saved);card.append(status);}status.textContent='已记录本客户的人工核对依据。请重新读取本客户，再检查其余未知项并审核邮件。';}catch(error){if(current() && S.detail===ctx)status.textContent=`${error.message} 请重新读取本客户后核对；不会自动重试。`;}},'quiet');card.append(save,status);}
          detail.append(card);}
        }
        const review=el('section',undefined,'card batch-review'), notes=addField(review,'本客户审核意见',item.notes || '',true), change=addField(review,'仅此客户的修改要求',item.change_request || '',true), result=el('p','','agent-feedback');ctx.savedBatchReview={notes:notes.value,change:change.value};ctx.hasBatchEdits=()=>notes.value!==ctx.savedBatchReview.notes || change.value!==ctx.savedBatchReview.change;review.append(el('p','请先核对完整收件人、主题、中英文正文和实际附件。审核标记不代表发送授权。普通邮件往来查询不能完整覆盖退信；发送前仍须核对退信及停止联系状态。'));
        for(const [state,label] of Object.entries(batchReviewNames)){if(state==='pending')continue;const action=button(state==='changes_requested'?'保存修改要求':label,async()=>{if(dirty()){result.textContent='请先保存邮件修改，重新读取后再审核。';return;}action.disabled=true;try{const displayedVersion=ctx.displayedDraftVersion?.();if(state==='approved' && displayedVersion==null)throw Error('当前没有可审核的已展示草稿，请重新读取本客户。');const updated=await api(`/api/customer-batches/${encodeURIComponent(view.id)}/items/review`,{...(reviewedItemRevision!=null?{item_revision:reviewedItemRevision}:{revision:reviewedRevision}),object_id:item.object_id,review_state:state,notes:notes.value,change_request:change.value,...(displayedVersion!=null?{draft_version:displayedVersion}:{})});if(!current() || S.detail!==ctx)return;data=updated;ctx.savedBatchReview={notes:notes.value,change:change.value};reviewedRevision=updated.revision;reviewedItemRevision=updated.items.find(row=>row.object_id===item.object_id)?.item_revision;paint();result.textContent=state==='changes_requested'?'已保存此客户的修改要求。':'已保存审核状态。';}catch(error){result.textContent=error.message;}finally{action.disabled=false;}},state==='approved'?'primary':'quiet');review.append(action);}const revise=button('交给 Agent 修改此客户',async()=>{if(!change.value.trim()){result.textContent='请先填写仅此客户的修改要求。';return;}if(dirty()){result.textContent='请先保存邮件修改，再交给 Agent。';return;}revise.disabled=true;try{const displayedVersion=ctx.displayedDraftVersion?.();if(displayedVersion==null)throw Error('请重新读取本客户与草稿，再交给 Agent 修改。');const value=await api('/api/desk/customer-batches/revise',{batch_id:view.id,object_id:item.object_id,...(reviewedItemRevision!=null?{item_revision:reviewedItemRevision}:{revision:reviewedRevision}),draft_version:displayedVersion,instruction:change.value.trim()});if(!current() || S.detail!==ctx)return;data=value.batch;ctx.savedBatchReview.change=change.value;reviewedRevision=data.revision;reviewedItemRevision=data.items.find(row=>row.object_id===item.object_id)?.item_revision;const index=S.jobs.findIndex(job=>job.id===value.job.id);if(index<0)S.jobs.unshift(value.job);else S.jobs[index]=value.job;paint();result.textContent='已交给 Agent，仅修改这位客户；结果仍回到当前批次。';renderAgentJobs(ctx);}catch(error){result.textContent=error.message;}finally{revise.disabled=false;}},'quiet');review.append(button('重新读取本客户与草稿',async()=>{if(dirty()){result.textContent='请先保存邮件修改。';return;}await read();const latest=data?.items.find(row=>row.object_id===item.object_id);if(latest)await openItem(latest);},'quiet'),revise,result);ctx.jobList=el('div',undefined,'batch-jobs');ctx.jobEntry=change;ctx.jobFeedback=result;review.append(ctx.jobList);renderAgentJobs(ctx);detail.append(review);
        const removal=el('section',undefined,'card batch-remove');removal.append(el('p','从本批次移除只取消集合引用；客户资料、邮件草稿及不联系抑制记录继续保留。','muted'));const remove=button('从本批次移除',async()=>{if(dirty() || ctx.hasBatchEdits()){result.textContent='当前有未保存的邮件或审核意见，请先保存后再移出本批次。';return;}remove.disabled=true;const batchId=view.id;try{const updated=await api(`/api/customer-batches/${encodeURIComponent(batchId)}/items/remove`,{revision:data.revision,object_ids:[item.object_id]});if(!current() || view.id!==batchId || S.detail!==ctx)return;data=updated;picks().research.delete(item.object_id);picks().send.delete(item.object_id);view.selected='';invalidatePlan();resetDetail();paint();feedback.textContent='已从本批次移除，客户、草稿和不联系抑制记录仍保留。';}catch(error){if(current() && S.detail===ctx)result.textContent=`${error.message} 请重新读取本客户与批次后核对；本次输入仍保留。`;}},'quiet');removal.append(remove);detail.append(removal);
        ctx.batchJobsChanged=async transitions=>{
          const refreshed=await read();if(!refreshed || !current() || S.detail!==ctx || view.selected!==item.object_id)return;
          const relevant=transitions.filter(job=>job.object_id===item.object_id && job.batch_id===view.id && ['outreach_draft','outreach_research'].includes(job.mode));if(!relevant.length)return;
          const completed=relevant.some(job=>job.status==='completed'),failed=relevant.find(job=>job.status!=='completed');
          if(!completed){result.textContent=`本客户任务${statusNames[failed?.status] || '状态已变化'}${failed?.error?'：'+failed.error:''}；当前草稿保留，请按实际结果处理。`;return;}
          if(dirty() || ctx.hasBatchEdits()){result.textContent='本客户 Agent 已完成并保存结果；你有正在编辑的邮件或审核意见，输入已保留。请保存后点击“重新读取本客户与草稿”。';return;}
          const latest=data?.items.find(row=>row.object_id===item.object_id);if(!latest){result.textContent='任务已完成，但原客户暂未在批次中读取到，请手动重新读取。';return;}
          await openItem(latest);if(current() && S.detail?.object.id===item.object_id && S.detail!==ctx)S.detail.jobFeedback.textContent='本客户 Agent 已完成，已在原批次读取最新客户资料与草稿，请重新审核。';
        };

      }catch(error){if(current() && seq===detailSequence)detail.replaceChildren(el('p',error.message,'inline-error'));}
    }
    select.addEventListener('change',async()=>{if(dirty()){select.value=view.id;feedback.textContent='请先保存当前客户的邮件修改。';return;}view.id=select.value;view.selected='';invalidatePlan();resetDetail();await read();await loadResearchGroups();});search.addEventListener('input',()=>{view.query=search.value;paint();});filter.addEventListener('change',()=>{view.state=filter.value;paint();});
    const add=el('details',undefined,'card batch-add');add.append(el('summary','从已有客户加入批次'));
    const addFilters=el('div',undefined,'batch-controls'), addKind=selectField(addFilters,'待加入对象类型',[['','客户与候选'],['customer','客户'],['prospect','候选']],'');
    const sourceNames={manual_import:'人工导入',website:'网站询盘',alibaba_order_buyer:'国际站订单买家',gmail:'Gmail',local:'已有客户资料',unknown:'未登记渠道'};
    const addSource=selectField(addFilters,'待加入发现渠道',[['','全部渠道'],...[...new Set(S.objects.filter(o=>['customer','prospect'].includes(o.kind)).map(o=>o.source_type || 'unknown'))].sort().map(value=>[value,sourceNames[value] || value])],''),addSearch=addField(addFilters,'搜索待加入客户','',false,'搜索公司、需求或来源'),addCount=el('p','','search-count'),choices=el('div',undefined,'batch-customer-choices'),addStatus=el('p','','agent-feedback');
    view.addSelections ||= new Map();const additionPicks=()=>{if(!view.addSelections.has(view.id))view.addSelections.set(view.id,new Set());return view.addSelections.get(view.id);};
    function additionRows(){const query=addSearch.value.trim().toLowerCase();return [...new Map(S.objects.filter(o=>['customer','prospect'].includes(o.kind)).map(o=>[o.id,o])).values()].filter(o=>(!addKind.value || o.kind===addKind.value) && (!addSource.value || (o.source_type || 'unknown')===addSource.value) && (!query || text([o.title,o.subtitle,o.summary,o.source]).toLowerCase().includes(query)));}
    function renderAddChoices(){const existing=new Set((data?.items || []).map(row=>row.object_id)),selected=additionPicks();for(const id of selected)if(existing.has(id))selected.delete(id);const rows=additionRows(),newRows=rows.filter(o=>!existing.has(o.id));addCount.textContent=`当前结果 ${rows.length} 位 · 已在批次 ${rows.length-newRows.length} 位 · 已选待加入 ${selected.size} 位 · 批次现有 ${existing.size}/500 位`;choices.replaceChildren();for(const object of rows){const label=el('label'),check=el('input');check.type='checkbox';check.setAttribute('aria-label',`加入 ${object.title}`);check.disabled=existing.has(object.id);check.checked=check.disabled || selected.has(object.id);check.addEventListener('change',()=>{if(check.checked && !check.disabled){if(existing.size+selected.size>=500){check.checked=false;addStatus.textContent='每批最多500个客户，请缩小选择范围。';return;}selected.add(object.id);}else selected.delete(object.id);renderAddChoices();});label.append(check,el('span',`${object.title}${check.disabled?' · 已在批次':''}`));choices.append(label);}if(!rows.length)choices.append(el('p','没有符合当前筛选的客户或候选。','muted'));if(newRows.length+existing.size>500)addStatus.textContent='当前筛选结果超过批次500个客户上限，请缩小筛选范围后再选择。';}
    const selectFiltered=button('选择当前筛选结果',()=>{if(!data){addStatus.textContent='请先选择开发批次。';return;}const selected=additionPicks(),existing=new Set(data.items.map(row=>row.object_id)),ids=additionRows().filter(o=>!existing.has(o.id)).map(o=>o.id),combined=new Set([...selected,...ids]);if(existing.size+combined.size>500){addStatus.textContent='当前筛选与已选项超过每批500个客户上限，请缩小筛选范围；本次未新增选择。';return;}for(const id of ids)selected.add(id);addStatus.textContent=`已选中当前筛选中可加入的 ${ids.length} 位客户，其他已选项保留。`;renderAddChoices();},'quiet');
    add.append(addFilters,selectFiltered,button('清空待加入选择',()=>{additionPicks().clear();addStatus.textContent='已清空待加入选择。';renderAddChoices();},'quiet'),addCount,choices,button('加入所选客户',async()=>{const existing=new Set((data?.items || []).map(row=>row.object_id)),ids=[...additionPicks()].filter(id=>!existing.has(id));if(!data || !ids.length){addStatus.textContent='先选择批次和尚未加入的客户。';return;}if(existing.size+ids.length>500){addStatus.textContent='每批最多500个客户，请缩小选择范围。';return;}const batchId=view.id;const updated=await api(`/api/customer-batches/${encodeURIComponent(batchId)}/items`,{revision:data.revision,object_ids:ids});if(!current() || view.id!==batchId)return;data=updated;paint();renderAddChoices();addStatus.textContent=`已将 ${ids.length} 位客户加入批次，已有客户保留。`;},'quiet'),addStatus);page.insertBefore(add,layout);
    addKind.addEventListener('change',()=>{addStatus.textContent='';renderAddChoices();});addSource.addEventListener('change',()=>{addStatus.textContent='';renderAddChoices();});addSearch.addEventListener('input',()=>{addStatus.textContent='';renderAddChoices();});renderAddChoices();
    S.listRefresh=read;resetDetail();await loadBatches();await read();await loadResearchGroups();if(view.selected){const item=data?.items.find(row=>row.object_id===view.selected);if(item)await openItem(item);}
  }
  function workflowEditor(ctx, host) {
    const w = ctx.profile.workflow; if (!w) return; const box = el('details', undefined, 'workflow-editor'), summary = el('summary', `${w.state_label || workflowStates[w.state] || '待处理'} · ${w.priority_label || priorityNames[w.priority] || '正常'} · 调整推进安排`); box.append(summary);
    const form = el('div', undefined, 'profile-form'), transitions = (w.allowed_transitions || []).map(item => typeof item === 'string' ? [item, workflowStates[item] || item] : [item.state, item.label]); if (!transitions.some(item => item[0] === w.state)) transitions.unshift([w.state, w.state_label || workflowStates[w.state] || w.state]); const state = selectField(form, '经营状态', transitions, w.state), priority = selectField(form, '处理优先级', Object.entries(priorityNames), w.priority || 'normal'), bucket = selectField(form, '记录分组', [['active','当前待办'],['history','历史复盘'],['archive','已结束']], w.bucket || 'active'), next = addField(form, '下一动作', w.next_action || ctx.profile.analysis?.next_action, true), due = addField(form, '客户明确截止时间（没有则留空）', w.due_at), note = addField(form, '处理备注', w.note, true), feedback = el('p', '', 'agent-feedback');
    for (const input of [state, priority, bucket, next, due, note]) { input.addEventListener('input', () => { ctx.workflowEditing = true; }); input.addEventListener('change', () => { ctx.workflowEditing = true; }); } form.append(feedback, button('保存推进安排', async () => { try { await api('/api/desk/customer-workflow', {object_id:ctx.object.id,revision:w.revision,state:state.value,priority:priority.value,...(bucket.value !== (w.bucket || 'active') ? {bucket:bucket.value} : {}),next_action:next.value,due_at:due.value,note:note.value}); ctx.workflowEditing = false; await loadProfile(ctx); toast('推进安排已保存。'); } catch(error) { feedback.textContent = customerEditError(error); } }, 'primary'), button('放弃本次修改并重新读取', () => loadProfile(ctx, {discardEdits:true, feedback}), 'quiet')); box.append(form); host.append(box);
  }
  function customerTabs(current) {
    const tabs = el('div', undefined, 'customer-tabs'); for (const [id, label] of [['development', '客户开发'], ['batches', '开发批次'], ['competitors', '同行找客户'], ['inquiries', '询盘处理']]) tabs.append(button(label, () => { location.hash = `/customers?view=${id}`; }, current === id ? 'active' : '')); return tabs;
  }
  async function renderCompetitors() {
    const page = $('page'), serial = S.loadSerial;
    const current = () => S.page === 'customers' && serial === S.loadSerial && parseRoute().query.get('view') === 'competitors';
    page.replaceChildren(heading('客户开发', '同行找客户', '从国际站同行入手，找到买家后直接在这里登记、继续研究。'), customerTabs('competitors'));
    const explanation = el('p', '优先用公司登记全称和统一社会信用代码查询海关。信息来自公开企业资料，实际出口主体以海关记录为准。', 'competitor-intro');
    const search = el('input', undefined, 'search-input'); search.type = 'search'; search.placeholder = '搜索公司名、信用代码或鞋类'; search.setAttribute('aria-label', '搜索同行');
    const count = el('span', '', 'search-count'), bar = el('div', undefined, 'search-bar competitor-search-bar'), list = el('div', undefined, 'row-list competitor-list');
    bar.append(search, count); page.append(explanation, bar, list);
    let data;
    try { data = await api('/api/desk/competitors'); } catch (error) { if (current()) message(error.message); return; }
    if (!current()) return;
    function matchingRows() {
      const query = search.value.trim().toLocaleLowerCase();
      return (data.items || []).filter(item => `${item.company} ${item.direction} ${item.identity?.name || ''} ${item.identity?.credit_code || ''}`.toLocaleLowerCase().includes(query));
    }
    async function copyCompanies(includeCode) {
      const rows = matchingRows().filter(item => text(item.identity?.name).trim());
      const names = rows.map(item => includeCode ? `${item.identity.name}\t${item.identity.credit_code || '信用代码未查到'}` : item.identity.name);
      if (!names.length) { toast('当前没有可复制的公司全称。'); return; }
      if (!navigator.clipboard?.writeText) { toast('当前页面无法使用剪贴板。'); return; }
      try { await navigator.clipboard.writeText(names.join('\n')); toast(`已复制 ${names.length} 家公司${includeCode ? '及信用代码' : '名称'}。`); }
      catch { toast('复制未成功，请检查浏览器剪贴板权限。'); }
    }
    bar.append(button('复制公司及信用代码', () => copyCompanies(true), 'primary competitor-copy-all'),
      button('只复制公司名', () => copyCompanies(false), 'quiet'));
    function openBuyer(id) { location.hash = `/customers?view=development&item=${encodeURIComponent(id)}`; }
    function addBuyer(company) {
      const dialog = el('dialog', undefined, 'intake-dialog competitor-dialog'), form = el('div', undefined, 'competitor-form');
      const competitorName = company.identity?.name || company.company;
      dialog.append(el('h2', `登记 ${competitorName} 的买家线索`), el('p', '填入查询到的公司，保存后可继续研究其业务与联系方式。', 'muted'));
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
            target: `从同行 ${competitorName} 研究中登记的买家线索。`,
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
    function competitorCard(item) {
        const card = el('article', undefined, 'card competitor-row'), info = el('div', undefined, 'competitor-main'), actions = el('div', undefined, 'competitor-actions');
        info.append(el('h3', item.identity?.name || '公司全称尚未查到'));
        if (item.identity?.name) {
          const identity = el('p', `统一社会信用代码：${item.identity.credit_code || '未查到'}`, 'competitor-identity');
          const source = link('查看公开资料 ↗', item.identity.source_url); if (source) identity.append(el('span', ' '), source);
          info.append(identity);
        } else info.append(el('p', `店铺显示名称：${item.company}`, 'competitor-identity'));
        if (item.direction) info.append(el('p', item.direction));
        if (item.sales) { const sold = el('p', item.sales.note, 'competitor-sales'); const source = link('销量依据 ↗', item.sales.source_url); if (source) sold.append(el('span', ' '), source); info.append(sold); }
        buyerLinks(info, item.buyers); const shop = link('查看国际站店铺 ↗', item.store_url); if (shop) actions.append(shop);
        if (item.identity?.name) actions.append(button('复制公司名', async () => { if (!navigator.clipboard?.writeText) { toast('请选择公司名称后复制。'); return; } await navigator.clipboard.writeText(item.identity.name); toast('公司全称已复制。'); }, 'quiet'));
        if (item.identity?.credit_code) actions.append(button('复制信用代码', async () => { if (!navigator.clipboard?.writeText) { toast('请选择信用代码后复制。'); return; } await navigator.clipboard.writeText(item.identity.credit_code); toast('信用代码已复制。'); }, 'quiet'));
        actions.append(button('登记买家', () => addBuyer(item), 'primary'));
        card.append(info, actions); return card;
    }
    function paint() {
      list.replaceChildren(); const rows = matchingRows();
      const known = rows.filter(item => text(item.identity?.name).trim()), missing = rows.filter(item => !text(item.identity?.name).trim());
      count.textContent = `${known.length} 家有公司全称 · ${missing.length} 家未查到`;
      for (const item of known) list.append(competitorCard(item));
      if (missing.length) {
        const section = el('details', undefined, 'competitor-excluded');
        section.open = !!search.value.trim();
        section.append(el('summary', `${missing.length} 家店铺尚未找到公司全称`));
        missing.forEach(item => section.append(competitorCard(item))); list.append(section);
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
    mountGmailEventReconcile(ctx,host);
    ctx.candidateNext = main.querySelector('.candidate-next-action');
    ctx.candidateNextDefault = ctx.candidateNext?.textContent || '';
    ctx.gmailMessages.append(el('h2', 'Gmail 邮件往来'), el('p', '正在读取邮件连接状态…'));
    loadGmail(ctx);
  }
  function mountGmailEventReconcile(ctx,host) {
    const section=el('details',undefined,'gmail-event-reconcile'), content=el('div'), feedback=el('p','','agent-feedback');
    section.append(el('summary','邮件事件与任务核对'),content,feedback);host.append(section);let loaded=false,busy=false;
    const active=()=>S.detail===ctx;
    async function read(){if(busy || !active())return;busy=true;feedback.textContent='正在读取已保存的邮件事件与任务…';try{const data=await api(`/api/desk/gmail/events?object_id=${encodeURIComponent(ctx.object.id)}`);if(!active())return;loaded=true;draw(data);feedback.textContent='';}catch(error){if(active())feedback.textContent=`${error.message} 请重新读取；本页不会自动重试。`;}finally{busy=false;}}
    function draw(data){content.replaceChildren();content.append(el('p',`自动重播 = ${data.automatic_replay===false?'false':'未知'}`,'muted'));if(data.origin_note)content.append(el('p',data.origin_note,'muted'));if(data.warning)content.append(el('p',data.warning,'inline-error'));content.append(button('重新读取邮件事件',read,'quiet'));
      for(const event of data.events || []){const row=el('article',undefined,'agent-job');row.append(el('h3',`邮件 ID：${event.message_id}`),el('p',`事件状态：${event.dispatch_state || '未知'} · relation：${event.relation || '未知'}`),el('p',`关联 Job ID：${event.job_id || '未关联'} · 任务状态：${event.job?.status || '未知'}`));if(event.duplicate_job_link)row.append(el('p','存在重复任务关联，需要核对。','inline-error'));content.append(row);}
      if(!(data.events || []).length)content.append(el('p','此客户没有可展示的已保存邮件事件。','muted'));
      const jobs=el('div');jobs.append(el('h3','此客户已有的 mail_draft 任务'));for(const job of data.candidate_jobs || [])jobs.append(el('p',`Job ID：${job.id} · 状态：${job.status || '未知'} · 来源关系：${job.origin || '未知'}${job.already_linked?' · 已关联事件':''}`));if(!(data.candidate_jobs || []).length)jobs.append(el('p','没有可选择的已有任务。','muted'));content.append(jobs);
      if(!data.available || data.automatic_replay!==false)return;
      const form=el('div',undefined,'profile-form'), eventSelect=selectField(form,'选择要核对的邮件事件',[['','请选择邮件事件'],...(data.events || []).filter(event=>event.manual_link_allowed===true).map(event=>[event.message_id,`${event.message_id} · ${event.dispatch_state}`])],''), jobSelect=selectField(form,'选择已有 mail_draft 任务',[['','请选择已有任务'],...(data.candidate_jobs || []).filter(job=>job.valid_record===true && job.object_id===ctx.object.id && job.mode==='mail_draft' && !job.already_linked).map(job=>[job.id,`${job.id} · ${job.status || '未知'}`])],''), note=addField(form,'人工核对依据','',true,'说明为什么确认此已有任务属于所选邮件，不凭相同客户或相近时间推定。');let attempted=false;
      const confirm=button('确认关联所选邮件与已有任务',async()=>{if(attempted || busy)return;const event=(data.events || []).find(row=>row.message_id===eventSelect.value),job=(data.candidate_jobs || []).find(row=>row.id===jobSelect.value);if(!event?.manual_link_allowed || !job || !note.value.trim()){feedback.textContent='请明确选择邮件事件和已有任务，并填写人工核对依据。';return;}if(!event.snapshot || typeof event.snapshot!=='object'){feedback.textContent='原事件快照未知，请重新读取。';return;}attempted=true;confirm.disabled=true;feedback.textContent='正在保存人工关联…';try{const value=await api('/api/desk/gmail/events/link',{object_id:ctx.object.id,message_id:event.message_id,job_id:job.id,snapshot:event.snapshot,confirmed:true,manual_note:note.value.trim()});if(!active())return;feedback.textContent=`已保存关联：邮件 ${value.message_id} → Job ${value.job_id} · ${value.job_status || '状态未知'} · 自动重播 = ${value.automatic_replay===false?'false':'未知'}。请重新读取核对结果。`;}catch(error){if(active())feedback.textContent=`${error.message} 请重新读取并人工核对；不会自动重试或启动任务。`;}},'quiet');form.append(el('p','点击仅记录你确认的已有关系，不匹配、启动或重播任务。','muted'),confirm);content.append(form);
    }
    section.addEventListener('toggle',()=>{if(section.open && !loaded)read();});
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
      mailActions.append(button('更新邮件往来', () => loadGmail(ctx, true), 'quiet'));
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
      // Approval binds to the draft actually shown here, never a fresh unseen API read.
      ctx.displayedDraftVersion = () => ctx.batch && state.draft.version !== initial.version ? null : state.draft.version;
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
            review(d); editor.hidden=true; preview.hidden=false; feedback.textContent=ctx.batch?'请检查完整内容和附件；保存修改后，请重新读取本客户再标记审核。':'请检查完整内容和附件，确认后才会发送。';
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
          if(ctx.batch){preview.append(el('p','批次邮件须完成本批次的停止联系、退信和重复检查后统一确认，当前此处只供审阅。','artifact-note'),actions);return;}
          const conditions=el('div',undefined,'mail-send-conditions'),checkButton=button('检查这封邮件的发送条件',async()=>{
            checkButton.disabled=true;conditions.replaceChildren(el('p','正在检查真实邮件记录及发送条件…'));const snapshot={version:d.version,to:d.to,subject:d.subject,account:d.account};
            try{const value=await api('/api/desk/gmail/send-preflight',{object_id:ctx.object.id,version:snapshot.version});if(S.detail!==ctx || preview.hidden)return;conditions.replaceChildren();for(const reason of value.reasons || [])conditions.append(el('p',typeof reason==='string'?reason:reason.message || '发送条件尚未核清','inline-error'));
              const address=value=>text(value).trim().toLowerCase();const consistent=!!value.account && !!value.to && Array.isArray(value.attachments) && value.attachments.length===(d.attachments || []).length && value.attachments.every((file,index)=>file.name===d.attachments[index].name && Number(file.size)===Number(d.attachments[index].size)) && value.version===snapshot.version && state.draft.version===snapshot.version && address(value.to)===address(snapshot.to) && value.subject===snapshot.subject && address(value.account)===address(snapshot.account);
              if(value.can_confirm!==true || !value.plan_id || !consistent){conditions.append(el('p',value.can_confirm===true?'检查结果与当前展示草稿不一致，请返回修改并重新读取后检查。':'本次未通过发送条件检查，不能确认发送。','inline-error'));return;}
              if(value.reply_proof)conditions.append(el('p','本次已核实为原客户邮件的回复；已有触达记录按该回复范围检查。','muted'));
              if(value.expires_at)conditions.append(el('p',`本次确认有效至 ${time(value.expires_at)}`,'muted'));let consumed=false;
              const sendButton=button('确认发送这封邮件',async()=>{if(consumed)return;if(state.dirty || state.draft.version!==snapshot.version || state.draft.to!==snapshot.to || state.draft.subject!==snapshot.subject || state.draft.account!==snapshot.account){sendButton.disabled=true;conditions.append(el('p','草稿已变化，请重新读取并检查。','inline-error'));return;}consumed=true;sendButton.disabled=true;checkButton.disabled=true;feedback.textContent='正在提交本次发送确认，请稍候…';try{const plan=await api('/api/desk/gmail/send',{object_id:ctx.object.id,version:snapshot.version,plan_id:value.plan_id,confirmed:true});if(S.detail===ctx)await showOutcome(plan);}catch(error){if(S.detail===ctx)await showOutcome(null,error.message);}},'primary');conditions.append(sendButton);
            }catch(error){if(S.detail===ctx)conditions.replaceChildren(el('p',`${error.message} 请重新读取并检查；不会自动重试。`,'inline-error'));}
          },'quiet');actions.append(checkButton);preview.append(actions,conditions);
          async function showOutcome(plan,error=''){
            let latest=null;try{latest=await api(`/api/desk/gmail/draft?object_id=${encodeURIComponent(ctx.object.id)}`);}catch{}if(S.detail!==ctx)return;
            if(latest)state.draft={...state.draft,...latest};
            if(plan?.status==='sent' || latest?.status==='sent'){if(plan?.status==='sent')state.draft={...state.draft,status:'sent',message_id:plan.message_id || state.draft.message_id,gmail_id:plan.gmail_id || state.draft.gmail_id,sent_at:plan.sent_at || state.draft.sent_at};drawResult();ctx.gmailStamp=null;await loadGmail(ctx);return;}
            if(latest && ['unknown','sending'].includes(latest.status)){drawResult();return;}
            const notSent=plan?.status==='not_sent';preview.replaceChildren(el('h3',notSent?'本次邮件未发送':'发送结果尚未确认'),el('p',plan?.reason || error || '请先核对原草稿和 Gmail 已发送记录。','inline-error'),el('p','本次确认不会自动重试；结果未知时请先核对发送记录。','muted'));
            preview.append(button('重新读取原草稿状态',()=>showOutcome(plan,error),'quiet'));
            if(notSent && latest?.status==='draft')preview.append(button('返回修改并重新检查',()=>{preview.hidden=true;editor.hidden=false;fields(state.draft);feedback.textContent='本次未发送，请修改后重新审核和检查。';},'quiet'));
            feedback.textContent=notSent?'邮件未发送。':'核对结果前不能重复发送。';
          }
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
      else entry.append(el('p', message.translation_stale ? '原文已变化，可在当前对话中让我更新中文对照。' : '尚无中文对照，可在当前对话中让我整理。', 'artifact-note'));
      entry.append(el('h4', '原文'), el('pre', text(message.body), 'source-body'));
      ctx.conversationMessages.append(entry);
    }
  }
  function customerEditError(error) { return error.status === 409 ? `${error.message} 本次输入仍保留。请先复制需要保留的内容，再点击“放弃本次修改并重新读取”查看最新资料。` : error.message; }
  async function loadProfile(ctx, {discardEdits = false, feedback = null} = {}) {
    try { const value = await api(`/api/desk/customer-profile?object_id=${encodeURIComponent(ctx.object.id)}`); if (S.detail !== ctx || (!discardEdits && (ctx.profileEditing || ctx.workflowEditing))) return; if (discardEdits) { ctx.profileEditing = false; ctx.workflowEditing = false; } ctx.profile = value.profile || value; ctx.lastProfileRefresh=Date.now(); if (ctx.summaryParagraph) ctx.summaryParagraph.textContent = ctx.profile.cleaned?.need || '原始需求在下方，可在当前对话中让我整理中文解读。'; renderProfile(ctx); renderConversation(ctx); }
    catch (error) { if (S.detail === ctx) { if (feedback) feedback.textContent = `重新读取未完成，本次输入仍保留：${error.message}`; else if (!ctx.profileEditing && !ctx.workflowEditing) ctx.profileHost.replaceChildren(el('h2', '需求解读与处理'), el('p', error.message, 'inline-error')); } }
  }
  function renderProfile(ctx) {
    const profile = ctx.profile, host = ctx.profileHost; host.replaceChildren(el('h2', '询盘简报')); const provenance = profile.provenance || {}, analysis = profile.analysis || {}, cleaned = profile.cleaned || {};
    if (profile.workflow?.bucket === 'history') host.append(el('p', '历史复盘 · 保留原始记录，不视为当前新询盘', 'eyebrow'));
    if (replyNotice(profile.workflow)) host.append(el('p', `${replyNotice(profile.workflow)}，请查看下方往来。`, 'mail-attention'));
    const waitingForCustomer = profile.workflow?.state === 'waiting_customer';
    const brief = el('section', undefined, 'inquiry-brief'); brief.append(el('p', analysis.brief || analysis.intent && analysis.intent !== 'unknown' && analysis.intent || '先读清客户本次需求，再确定回复与推进动作。', 'brief-judgment'), el('h3', '核心需求'), el('p', analysis.core_need || cleaned.need || '尚未整理，可查看下方原文或在当前对话中让我处理。'));
    if (analysis.fit && analysis.fit !== 'unknown') brief.append(el('h3', '我们怎么承接'), el('p', text(analysis.fit), 'brief-fit'));
    const questions = analysis.questions_now || []; if (!waitingForCustomer && !profile.workflow?.gmail_reply_pending && questions.length) listText(brief, '现在需要问清', questions.slice(0,3));
    brief.append(el('p', `下一步：${profile.workflow?.next_action || analysis.next_action || '阅读原文并确定本次动作'}`, 'next-action'));
    if (!waitingForCustomer && !profile.workflow?.gmail_reply_pending && analysis.recommended_reply) { const value = text(analysis.recommended_reply), reply = el('section', undefined, 'brief-reply'); reply.append(el('h3', '建议回复'), el('p', value.length > 260 ? `${value.slice(0,260)}…` : value)); if (value.length > 260) { const full = el('details'); full.append(el('summary', '查看完整建议回复'), el('pre', value, 'plain-reading')); reply.append(full); } brief.append(reply); }
    if (profile.operator_context) { const context = el('details', undefined, 'operator-context'); context.append(el('summary', '业务补充说明'), el('p', text(profile.operator_context))); brief.append(context); } host.append(brief); workflowEditor(ctx, host);
    const actions = el('div', undefined, 'profile-actions'); actions.append(button('编辑解读与分析', () => editProfile(ctx)), button('重读解读', () => loadProfile(ctx), 'quiet')); host.append(actions); const sourceNotes = [...new Set([provenance.evidence_notes, provenance.source_verification?.note].filter(Boolean).map(text))]; if (sourceNotes.length || provenance.source) { const source = el('details', undefined, 'source-note'); source.append(el('summary', '来源记录')); if (provenance.source) source.append(el('p', text(provenance.source), 'object-source')); sourceNotes.forEach(note => source.append(el('p', note, 'artifact-note'))); host.append(source); }
    const comparison = el('div', undefined, 'bilingual-grid'), zh = el('section'), original = el('details'); zh.append(el('h3', '中文译文 / 解读'), el('pre', profile.translation_zh || '尚未整理中文解读，可在当前对话中让我处理。', 'plain-reading')); original.append(el('summary', '原始需求 · 保留原稿'), el('pre', profile.original_text || '原记录未提供正文', 'plain-reading')); comparison.append(zh, original); host.append(comparison);
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
    form.append(message, button('保存中文解读与分析', async () => { try { await api('/api/desk/customer-profile', { object_id: ctx.object.id, revision: p.revision, source_hash: p.source_hash || p.provenance?.source_hash, translation_zh: translation.value, original_language: p.original_language || 'unknown', cleaned: { ...p.cleaned, company: company.value, country: country.value, quantity: quantity.value, need: need.value }, analysis: { ...p.analysis, fit: fit.value || 'unknown', basis: lines(basis), missing: lines(missing), next_action: next.value }, source_note: sourceNote.value }); ctx.profileEditing = false; await loadProfile(ctx); toast('中文解读与分析已保存，原始需求未改动。'); } catch (error) { message.textContent = customerEditError(error); } }, 'primary'), button('放弃本次修改并重新读取', () => loadProfile(ctx, {discardEdits:true, feedback:message}), 'quiet'), button('返回阅读（不保存本次编辑）', () => { ctx.profileEditing = false; renderProfile(ctx); }, 'quiet')); host.append(form);
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
  function mountCommercial(host, objectId, before = null) {
    const box=el('section',undefined,'card customer-commercial'), content=el('div'), feedback=el('p','','agent-feedback');
    box.append(el('h2','报价、样品与订单'),content,feedback); if(before)host.insertBefore(box,before);else host.append(box);
    let data;
    async function read() {
      try { data=await api(`/api/desk/customer-commercial?object_id=${encodeURIComponent(objectId)}`); draw(); }
      catch(error) { content.replaceChildren(el('p',error.message,'muted')); }
    }
    function draw() {
      content.replaceChildren();
      if(data.next_action)content.append(el('p',`下一步：${data.next_action}`));
      const records=data.records || [];
      if(!records.length)content.append(el('p','还没有报价、样品或订单记录。','muted'));
      for(const row of [...records].reverse()) {
        const item=el('article',undefined,'artifact-row');
        item.append(el('h3',`${data.labels?.kinds?.[row.kind] || row.kind} · ${data.labels?.statuses?.[row.status] || row.status}`),el('p',row.summary));
        if(row.products)item.append(el('p',`商品：${row.products}`));
        if(row.terms)item.append(el('p',`条件：${row.terms}`));
        if(row.actual_result)item.append(el('p',`实际进展：${row.actual_result}`));
        if(row.reference)item.append(el('p',`关联资料：${row.reference}`));
        item.append(button('编辑',()=>editor(row),'quiet'));content.append(item);
      }
      if(data.source_orders?.length)content.append(el('p',`已有国际站订单 ${data.source_orders.length} 条，可在原订单记录查看。`,'muted'));
      const editorHost=el('div'); content.append(button('添加报价、样品或订单',()=>editor(), 'quiet'),editorHost);
      function editor(row={}) {
        editorHost.replaceChildren(); const form=el('div',undefined,'profile-form');
        const kind=selectField(form,'记录类型',[['quotation','报价'],['sample','样品'],['order','订单']],row.kind || 'quotation');
        if(row.id)kind.disabled=true;
        const status=selectField(form,'记录状态',[['draft','内部准备'],['recorded','已有实际记录'],['cancelled','已取消']],row.status || 'draft');
        const summary=addField(form,'当前情况',row.summary,true,'例如：客户希望先确认混码报价');
        const products=addField(form,'相关商品',row.products,false,'选填');
        const terms=addField(form,'价格、条件或样品要求',row.terms,true,'选填');
        const reference=addField(form,'相关资料或订单编号',row.reference,false,'选填');
        const extra=el('details'), extraFields=el('div',undefined,'profile-form');extra.append(el('summary','补充样品、结果和费用'),extraFields);
        const purpose=addField(extraFields,'样品目的',row.purpose,true,'选填');
        const acceptance=addField(extraFields,'验收要求',row.acceptance,true,'选填');
        const exclusions=addField(extraFields,'不包含的内容',row.exclusions,true,'选填');
        const actual=addField(extraFields,'实际进展',row.actual_result,true,'选填');
        const profit=addField(extraFields,'费用与利润依据',row.profit_basis,true,'选填');form.append(extra);
        const owner=addField(form,'负责人',data.owner,false,'选填');
        const next=addField(form,'接下来做什么',data.next_action,true,'选填');
        const save=button('保存记录',async()=>{
          if(!summary.value.trim()){feedback.textContent='请填写当前情况。';return;}
          save.disabled=true;feedback.textContent='正在保存…';
          try { await api('/api/desk/customer-commercial',{object_id:objectId,revision:data.revision,owner:owner.value,next_action:next.value,record:{...(row.id?{id:row.id}:{}),kind:kind.value,status:status.value,summary:summary.value,products:products.value,terms:terms.value,reference:reference.value,purpose:purpose.value,acceptance:acceptance.value,exclusions:exclusions.value,actual_result:actual.value,profit_basis:profit.value}});feedback.textContent='已保存到客户记录。';await read(); }
          catch(error){feedback.textContent=error.message;save.disabled=false;}
        },'primary');form.append(save,button('取消',()=>editorHost.replaceChildren(),'quiet'));editorHost.append(form);
      }
    }
    read();return box;
  }
  async function renderDevelopment() {
    const page = $('page'), routeSerial = S.loadSerial; const current = () => S.page === 'customers' && routeSerial === S.loadSerial && parseRoute().query.get('view') !== 'inquiries'; page.replaceChildren(heading('客户工作台', '客户与机会', '先看需要处理的事，再继续开发目标客群。'), customerTabs('development')); const target = el('details', undefined, 'card discovery-target'); target.append(el('summary', '新建买家研究任务')); const form = el('div', undefined, 'discovery-target-form'), title = addField(form, '研究任务名称', '', false, '例如：为一组产品寻找匹配的买家'), audience = addField(form, '目标客群与研究要求', '', true, '说明市场、买家业务、产品适配与需要核查的证据'); const feedback = el('p', '', 'agent-feedback'), inbox = el('section'), tasks = el('section'), candidates = el('section'), detail = el('section'), sync = el('div', undefined, 'customer-sync'); target.append(form, feedback, button('保存研究任务', async () => { if (!title.value.trim() || !audience.value.trim()) { feedback.textContent = '请先写清任务名称和目标客群。'; return; } try { const result = await api('/api/desk/discovery', { kind: 'research_task', title: title.value, target: audience.value, status: '研究准备' }); await read(); await openItem((result.item || result).id); } catch (error) { feedback.textContent = error.message; } }, 'primary')); page.append(sync, inbox, candidates, tasks, target, detail);
    async function openItem(id) {
      const result = await api(`/api/desk/discovery/item?id=${encodeURIComponent(id)}`); if (!current()) return; const item = result.item || result; const route = parseRoute(), artifact = route.query.get('item') === String(item.id) ? route.query.get('artifact') : null; history.replaceState(null, '', `#/customers?view=development&item=${encodeURIComponent(item.id)}${artifact ? `&artifact=${encodeURIComponent(artifact)}` : ''}`); target.hidden = true; inbox.hidden = true; tasks.hidden = true; candidates.hidden = true; searchPanel.hidden = true; sync.hidden = true; detail.replaceChildren(button('← 返回客户开发列表', () => { location.hash = '/customers?view=development'; }, 'quiet back-development'));
      const layout = el('div', undefined, 'object-layout discovery-detail'), main = el('div', undefined, 'card'); main.append(el('h2', item.title || item.company || '研究记录'), el('p', item.kind === 'research_task' ? '研究任务' : item.business_category || '待确认业务类型', 'provenance-note'));
      if (item.kind === 'candidate') {
        const prior = item.source_record?.analysis || {}, summary = el('section', undefined, 'candidate-summary');
        summary.append(el('h3', '买家摘要'), el('p', item.business_summary || '尚无可展示的业务摘要。'));
        if (item.discovery_reason) { const discovery = el('div'); discovery.append(el('h3', '从哪里找到，为什么适合'), el('p', item.discovery_reason)); const source = (item.evidence || []).find(value => value.url); const sourceLink = link('查看发现依据 ↗', source?.url); if (sourceLink) discovery.append(sourceLink); summary.append(discovery); }
        summary.append(el('p', `联系状态：${item.contact_status_label || '尚未核实联系状态'}`), el('p', `下一步：${item.next_action || '补充推进安排'}`, 'candidate-next-action'));
        main.append(summary);
        const contacts = item.source_record?.contacts || [], site = link('访问公司网站 ↗', item.website); if (contacts.length || site || item.contact_name || item.email || item.phone) { const contactBox = el('section', undefined, 'candidate-contacts'); contactBox.append(el('h3', '联系方式')); if (site) contactBox.append(site); for (const [label,value] of [['联系人',item.contact_name],['邮箱',item.email],['电话',item.phone]]) if(value)contactBox.append(el('p',`${label}：${text(value)}`)); for (const contact of contacts) { const value = typeof contact === 'string' ? contact : contact.value; if (!value) continue; const kind = typeof contact === 'object' ? text(contact.kind).toLowerCase() : ''; const label = ({email:'邮箱',phone:'电话',telephone:'电话',whatsapp:'WhatsApp',wechat:'微信'})[kind] || '联系'; contactBox.append(el('p', `${label}：${text(value)}`)); } main.append(contactBox); }
      }
      const edit = el('div', undefined, 'profile-form'), company = addField(edit, '公司', item.company), website = item.kind === 'candidate' ? addField(edit, '公司网站', item.website) : null, country = item.kind === 'candidate' ? addField(edit, '国家或市场', item.country || item.market_hint) : null, contactName = item.kind === 'candidate' ? addField(edit, '联系人', item.contact_name) : null, email = item.kind === 'candidate' ? addField(edit, '邮箱', item.email) : null, phone = item.kind === 'candidate' ? addField(edit, '电话', item.phone) : null, businessSummary = item.kind === 'candidate' ? addField(edit, '业务摘要', item.business_summary, true) : null, category = item.kind === 'candidate' ? addField(edit, '买家类型', item.business_category) : null, contactStatus = item.kind === 'candidate' ? addField(edit, '联系状态', item.contact_status_label) : null, priority = item.kind === 'candidate' ? selectField(edit, '开发优先级', [['high','优先'],['normal','正常'],['low','稍后']], item.priority || 'normal') : null, aim = addField(edit, item.kind === 'candidate' ? '研究问题' : '目标客群 / 适配问题', item.target, true), notes = addField(edit, '研究记录', item.notes, true), next = addField(edit, '下一步', item.next_action, true), evidence = addField(edit, '新增来源网址（每行一条）', '', true), evidenceText = addField(edit, '新增证据说明', '', true); const editDetails=el('details'); editDetails.append(el('summary','编辑客户资料'),edit); main.append(editDetails);
      const proof = el('div', undefined, 'candidate-evidence'); proof.append(el('h3', '已有候选证据')); for (const value of item.evidence || []) { const row = el('div'); row.append(el('p', value.text || '来源说明未提供')); const a = link('查看来源', value.url); if (a) row.append(a); if (value.observed_at) row.append(el('small', `记录时间 ${time(value.observed_at)}`)); proof.append(row); } if (!(item.evidence || []).length) proof.append(el('p', '尚未登记可核来源，不把研究结论当作已证实事实。', 'muted')); const proofDetails=el('details'); proofDetails.append(el('summary','参考资料'),proof); main.append(proofDetails);
      if (item.kind === 'candidate') { const discoveryReason = addField(edit, '从哪里找到，为什么适合', item.discovery_reason, true); edit.discoveryReason = discoveryReason; }
      async function save(promote = false, selectedEvidence = []) { const additions = evidence.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean).map(url => ({ url, text: evidenceText.value, observed_at: new Date().toISOString() })); const value = await api('/api/desk/discovery/update', { id: item.id, company: company.value, ...(item.kind === 'candidate' ? {title:company.value,website:website.value,country:country.value,contact_name:contactName.value,email:email.value,phone:phone.value,business_summary:businessSummary.value,business_category:category.value,contact_status_label:contactStatus.value,priority:priority.value,discovery_reason:edit.discoveryReason.value} : {}), target: aim.value, notes: notes.value, next_action: next.value, evidence: [...(item.evidence || []), ...additions, ...selectedEvidence], ...(promote ? { status: '推进准备', ready_for_customer: true } : {}) }); toast(promote ? '已标记推进准备。' : '客户资料已保存。'); await read(); await openItem((value.item || value).id || item.id); }
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
      const object = { id: item.object_id || `prospect:${item.id}`, kind: 'prospect', title: item.title || item.company, source: item.source, assets: [] }, artifactSection = el('section', undefined, 'card'); artifactSection.append(el('h2', '研究成果')); const tabs = el('div', undefined, 'artifact-tabs'), editor = el('div'); artifactSection.append(tabs, editor); const ctx = { object, tabs, editor, artifacts: [], selectedId: null, requestedArtifact: parseRoute().query.get('artifact') }; S.detail = ctx; if(item.kind==='candidate'){mountGmail(ctx,main);main.insertBefore(ctx.gmailHost,editDetails);mountCommercial(main,object.id,editDetails);main.append(button('客户资料包 · 查看选款材料',()=>{location.hash='/library?customer='+encodeURIComponent(object.id);},'quiet'));} mountAgentWork(ctx,main); layout.append(main); detail.append(layout, artifactSection); refreshArtifacts(ctx, true); detail.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
      if (item.kind === 'candidate') {
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
  function mountProductCreation(host, object) {
    const box=el('details',undefined,'card'), body=el('div'), feedback=el('p','','agent-feedback');
    box.append(el('summary','用于内容创作'),el('p','选择这款商品的素材和已有创作项目，将素材引用加入项目画布。'),body,feedback);host.append(box);
    let loaded=false;
    box.addEventListener('toggle',async()=>{
      if(!box.open || loaded)return; feedback.textContent='正在读取可用素材与项目…';
      try{
        const data=await api(`/api/desk/product-creation?product_id=${encodeURIComponent(object.id)}`);
        const assets=el('select'), projects=el('select');assets.setAttribute('aria-label','选择商品素材');projects.setAttribute('aria-label','选择创作项目');
        const firstAsset=el('option','请选择商品素材');firstAsset.value='';assets.append(firstAsset);
        const firstProject=el('option','请选择创作项目');firstProject.value='';projects.append(firstProject);
        for(const item of data.assets || []){const option=el('option',`${item.label || item.name} · ${item.name}`);option.value=item.path;assets.append(option);}
        for(const item of data.projects || []){const option=el('option',item.title);option.value=item.id;projects.append(option);}
        const selection=el('div',undefined,'creation-asset-selection');selection.setAttribute('aria-live','polite');
        function showSelection(){
          selection.replaceChildren();
          const selectedAsset=(data.assets || []).find(item=>item.path===assets.value);
          const selectedProject=(data.projects || []).find(item=>item.id===projects.value);
          if(selectedAsset){
            selection.append(el('p',`已选素材：${assetLabel(selectedAsset)} · ${text(selectedAsset.name)}`));
            if(imageAsset(selectedAsset)){
              const thumb=image(selectedAsset,'');
              if(thumb){thumb.style.maxWidth='220px';thumb.style.maxHeight='160px';thumb.style.objectFit='contain';selection.append(thumb);}
            }
            if(safeUrl(selectedAsset.url))selection.append(button('预览选中素材',()=>previewAsset(selectedAsset),'quiet'));
          }
          if(selectedProject)selection.append(el('p',`目标项目：${text(selectedProject.title)}`));
        }
        assets.addEventListener('change',showSelection);projects.addEventListener('change',showSelection);
        const add=button('加入项目画布',async()=>{
          if(!assets.value || !projects.value){feedback.textContent='请选择素材和创作项目。';return;}
          const projectId=projects.value, path=assets.value;add.disabled=true;feedback.textContent='正在加入画布…';
          try{const current=await api(`/api/desk/creation-canvas?object_id=${encodeURIComponent(projectId)}`);const result=await api('/api/desk/product-creation/add',{product_id:object.id,project_id:projectId,path,version:current.canvas.version});feedback.replaceChildren(el('span',result.notice+' '),button('打开创作项目',()=>{location.hash=`/creation?item=${encodeURIComponent(projectId)}`;},'quiet'));}
          catch(error){feedback.textContent=error.message;}finally{add.disabled=false;}
        },'quiet');
        body.append(assets,projects,selection,add);feedback.textContent=data.notice || '';loaded=true;
      }catch(error){feedback.textContent=error.message;}
    });
  }
  function renderObject(object, requestedArtifact) {
    const page = $('page'), top = el('div', undefined, 'detail-top'), info = el('div'); info.append(el('span', objectKind(object), 'eyebrow'), el('h1', text(object.title))); if (object.subtitle && object.kind !== 'customer') info.append(el('p', object.kind === 'product' && /[A-Za-z]/.test(text(object.subtitle)) ? `平台原文：${text(object.subtitle)}` : displayText(object.subtitle))); if (object.kind === 'product') info.append(el('p', '集中查看产品事实、来源依据和素材，继续整理可用的选款资料。'));  top.append(info, button('返回列表', () => { location.hash = object.kind === 'product' ? '/products' : object.kind === 'channel' ? '/channels?view=douyin' : object.kind === 'prospect' ? '/customers?view=development' : '/customers?view=inquiries'; }, 'quiet')); page.replaceChildren(top);
    const layout = el('div', undefined, 'object-layout'), main = el('div', undefined, 'object-main'); const hero = el('section', undefined, 'card detail-hero'), asset = firstImage(object), facts = el('div'); if (asset) hero.append(image(asset, 'hero-image')); else hero.style.gridTemplateColumns = '1fr'; facts.append(el('h2', object.kind === 'product' ? '商品资料' : '需求与背景')); const summaryParagraph = el('p', object.kind === 'customer' ? '原始需求在下方，可在当前对话中让我整理中文解读。' : text(object.summary), object.kind === 'customer' ? 'agent-copy customer-need' : 'agent-copy'); if (object.kind === 'customer' || object.kind === 'channel') facts.append(summaryParagraph); if(object.kind==='product')appendProductLinks(facts,object); const dl = el('dl', undefined, 'object-facts'); const factGroups = summaryFacts(object); for (const item of factGroups.shown) dl.append(el('dt', text(item.label)), el('dd', displayText(item.value) || '资料未提供')); facts.append(dl); if (object.kind !== 'product' && (factGroups.more.length || object.source)) { const details = el('details', undefined, 'extra-facts'); details.append(el('summary', '更多档案与渠道信息')); const more = el('dl', undefined, 'object-facts'); for (const item of factGroups.more) more.append(el('dt', text(item.label)), el('dd', displayText(item.value) || '资料未提供')); details.append(more, el('div', `来源：${text(object.source) || '来源未提供'}`, 'object-source')); facts.append(details); } hero.append(facts); if (object.kind !== 'customer') main.append(hero);
    if (object.kind === 'product' && window.mountProductReview) window.mountProductReview(main, object, api, {preview: previewAsset, listingId: parseRoute().query.get('listing') || '', titleDraft: (box, select) => titleDraftForm(box, object, select)});
    if ((object.assets || []).length) {
      const materials = el('section', undefined, 'card'); materials.append(el('h2', object.kind === 'product' ? '图片与素材' : '需求资料')); const grid = el('div', undefined, 'asset-grid'); let expanded = false;
      function renderAssets() { grid.replaceChildren(); for (const item of object.assets.slice(0, expanded ? object.assets.length : 6)) { const row = el('div', undefined, 'asset-item'), src = safeUrl(item.url); if (imageAsset(item) && src) row.append(image(item, '')); row.append(el('div', assetLabel(item), 'asset-label')); if (src) row.append(button('预览', () => previewAsset(item), 'quiet')); grid.append(row); } }
      materials.append(grid); if (object.assets.length > 6) { const toggle = button(`展开全部 ${object.assets.length} 份素材`, () => { expanded = !expanded; toggle.textContent = expanded ? '收起素材' : `展开全部 ${object.assets.length} 份素材`; renderAssets(); }, 'quiet asset-toggle'); materials.append(toggle); } renderAssets(); main.append(materials);
    }
    if(object.kind==='product')mountProductCreation(main,object);
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
    const artifactSection = el(object.kind === 'customer' ? 'details' : 'section', undefined, 'card'); if(object.kind==='customer' && isWebsite(object))artifactSection.open=true; artifactSection.append(el(object.kind === 'customer' ? 'summary' : 'h2', object.kind === 'customer' ? '回复草稿与工作成果' : '工作成果')); const tabs = el('div', undefined, 'artifact-tabs'), editor = el('div'); artifactSection.append(el('p', '整理出的选款资料、回复草稿和补充内容都保存在这里，可继续编辑。', 'artifact-note'), tabs, editor); if (object.kind === 'product') main.append(artifactSection); else main.insertBefore(artifactSection, main.children[1] || null);
    const ctx = { object, tabs, editor, summaryParagraph, conversationMessages, replyArea, artifacts: [], selectedId: null, requestedArtifact, currentEdit: null }; S.detail = ctx; if (object.kind === 'customer') { ctx.profileHost = el('section', undefined, 'card customer-analysis'); main.insertBefore(ctx.profileHost, main.children[0] || null); main.insertBefore(button('客户资料包 · 选择与组合材料',()=>{location.hash='/library?customer='+encodeURIComponent(object.id);},'quiet'),ctx.profileHost); loadProfile(ctx); mountCommercial(main,object.id,artifactSection); } else if (object.kind === 'prospect') { main.insertBefore(button('客户资料包 · 查看选款材料',()=>{location.hash='/library?customer='+encodeURIComponent(object.id);},'quiet'),artifactSection); } if(object.kind==='customer')mountGmail(ctx,main); mountAgentWork(ctx, main); layout.append(main); page.append(layout); refreshArtifacts(ctx, true);
  }
  function mountAgentWork(ctx, main) {
    const box = el('details', undefined, 'card agent-work'), entry = el('textarea'), feedback = el('p', '', 'agent-feedback'), list = el('div');
    entry.placeholder = '说明希望完成的经营目标或继续事项'; entry.setAttribute('aria-label', '交给 Agent 的工作');
    const start = button('开始工作', async () => {
      if (!entry.value.trim()) { feedback.textContent = '请先写明要完成的工作。'; return; }
      start.disabled = true;
      try { const job = await api('/api/desk/jobs', { object_id: ctx.object.id, instruction: entry.value.trim() }); S.jobs.unshift(job); entry.value = ''; feedback.textContent = '工作已开始。'; renderAgentJobs(ctx); }
      catch (error) { feedback.textContent = error.message; } finally { start.disabled = false; }
    }, 'primary');
    box.append(el('summary', '交给 Agent 执行'), el('p', '可研究、维护资料和继续上次工作；客户开发邮件仍需逐封审核。'), entry, start, feedback, list);
    ctx.jobList = list; ctx.jobEntry = entry; ctx.jobFeedback = feedback; main.append(box); renderAgentJobs(ctx);
  }
  function renderAgentJobs(ctx) {
    if (!ctx.jobList) return; ctx.jobList.replaceChildren();
    for (const job of jobsFor(ctx.object.id).slice(0, 8)) {
      const row = el('article', undefined, 'agent-job');
      row.append(badge(job.status), el('p', text(job.summary || job.error || job.instruction || '工作已创建')));
      if (job.error && job.summary) row.append(el('p', text(job.error), 'inline-error'));
      if (isActive(job)) row.append(button('取消工作', async () => {
        try { const value = await api('/api/desk/job/cancel', { id: job.id }); Object.assign(job, value); renderAgentJobs(ctx); }
        catch (error) { ctx.jobFeedback.textContent = error.message; }
      }, 'quiet'));
      else if (job.session_id) row.append(button('继续这项工作', async () => {
        const instruction = ctx.jobEntry.value.trim(); if (!instruction) { ctx.jobFeedback.textContent = '请先填写继续事项。'; ctx.jobEntry.focus(); return; }
        try { const value = await api('/api/desk/job/resume', { id: job.id, instruction }); Object.assign(job, value); ctx.jobEntry.value = ''; ctx.jobFeedback.textContent = '已继续原工作。'; renderAgentJobs(ctx); }
        catch (error) { ctx.jobFeedback.textContent = error.message; }
      }, 'quiet'));
      if(isActive(job) && (!job.owner_pid || (job.status==='running' && !job.process_id)))mountLegacyJobRecovery(ctx,row,job);
      ctx.jobList.append(row);
    }
  }
  function mountLegacyJobRecovery(ctx,row,job){
    ctx.legacyRecoveryEdits ||= new Map();if(!ctx.legacyRecoveryEdits.has(job.id))ctx.legacyRecoveryEdits.set(job.id,{pid:'',evidence:'',confirmed:false,attempted:false,message:''});const edit=ctx.legacyRecoveryEdits.get(job.id),box=el('details',undefined,'legacy-job-recovery'),form=el('div',undefined,'profile-form');box.append(el('summary','人工核验中断任务并接续'),el('p',job.owner_pid?`已登记原服务 PID：${job.owner_pid}。填写同一 PID，并核实原服务及可能存在的未登记子进程均已退出。`:'此旧任务没有拥有者记录。请从实际日志或进程记录查明原工作台服务 PID，并核实原服务及可能存在的子进程均已退出。','muted'));
    const pid=addField(form,'先前工作台进程 PID',edit.pid),evidence=addField(form,'原服务及子进程退出的具体核验依据',edit.evidence,true,'依据必须包含所填 PID；写明核验过的日志、进程身份和原服务及子进程退出情况。'),label=el('label'),confirmed=el('input'),feedback=el('p',edit.message,'agent-feedback');pid.type='number';pid.min='1';pid.step='1';confirmed.type='checkbox';confirmed.checked=edit.confirmed;confirmed.setAttribute('aria-label','确认已核实原服务及可能存在的子进程均已退出');label.append(confirmed,el('span','我已核实原服务身份，以及原服务和可能存在的子进程均已退出'));
    const remember=()=>{edit.pid=pid.value;edit.evidence=evidence.value;edit.confirmed=confirmed.checked;};pid.addEventListener('input',remember);evidence.addEventListener('input',remember);confirmed.addEventListener('change',remember);
    const submit=button('确认核验并标记可恢复',async()=>{if(edit.attempted)return;remember();const owner=Number(pid.value),proof=evidence.value.trim();if(!Number.isSafeInteger(owner) || owner<=0 || !/^[0-9]+$/.test(pid.value.trim()) || !confirmed.checked || proof.length<20 || proof.length>4000 || !proof.includes(String(owner)) || (job.owner_pid && owner!==job.owner_pid)){feedback.textContent=edit.message='请填写正确的正整数原服务 PID、包含该 PID 的具体退出核验依据，并主动确认；已登记 PID 必须一致。';return;}edit.attempted=true;submit.disabled=true;feedback.textContent=edit.message='正在核验并标记中断状态…';try{const value=await api('/api/desk/job/recover-legacy',{id:job.id,former_owner_pid:owner,evidence:proof,confirmed:true});if(value.id!==job.id || value.status!=='failed' || value.worker_finished!==true)throw Error('任务恢复状态未确认，请重新读取核对');Object.assign(job,value);ctx.legacyRecoveryEdits.delete(job.id);ctx.jobFeedback.textContent='已标记为可恢复，已有成果与会话保留；尚未启动。请核对后使用“继续这项工作”。';renderAgentJobs(ctx);}catch(error){feedback.textContent=edit.message=`${error.message} 不会自动重试或启动任务；请重新读取任务状态后核对。`;}},'quiet');submit.disabled=edit.attempted;
    const reread=button('重新读取该任务状态',async()=>{try{const value=await api(`/api/desk/job?id=${encodeURIComponent(job.id)}`);if(value.id!==job.id)throw Error('返回任务不一致');Object.assign(job,value);edit.confirmed=false;edit.attempted=false;edit.message='已重新读取，请按当前记录再次人工核验。';renderAgentJobs(ctx);}catch(error){feedback.textContent=edit.message=`${error.message} 未确认任务状态，不会重试恢复或启动任务。`;}},'quiet');form.append(label,el('p','这里只标记中断任务可恢复；系统会复核原服务与已登记子进程状态，不会自动重跑。','muted'),submit,reread,feedback);box.append(form);row.append(box);
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
  function editKey(ctx, id) { return `${ctx.object.id}:${id || 'new'}`; }
  function englishReplyDraft(content) { const match=text(content).match(/^##\s*(?:英文正文|英文回复草稿)(?:[^\n]*)\n([\s\S]*?)(?=^##\s|(?![\s\S]))/m); return match ? match[1].replace(/^\s*(?:\*\*)?Subject:(?:\*\*)?[^\n]*\n/im,'').trim() : ''; }
  function chineseReplyDraft(content) { const match=text(content).match(/^##\s*(?:完整中文对照|中文正文|中文对照|中文回复|中文译文|中文翻译)(?:[^\n]*)\n([\s\S]*?)(?=^##\s|(?![\s\S]))/m); return match ? match[1].trim() : ''; }
  function plainEmailDraft(value) { return text(value).replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,'$1: $2').replace(/^\s*\|?\s*:?-{3,}[^\n]*$/gm,'').replace(/^\s*\|(.+)\|\s*$/gm,(_,row)=>row.split('|').map(cell=>cell.trim()).join('  |  ')).replace(/\*\*([^*]+)\*\*/g,'$1').replace(/\n{3,}/g,'\n\n').trim(); }
  function showArtifactEditor(ctx, artifact) {
    const id = artifact?.id || null, key = editKey(ctx, id); let edit = S.edits.get(key);
    if (edit && !edit.dirty && artifact && edit.baseline !== artifact.updated_at) edit = null;
    if (!edit) { edit = { title: artifact?.title || '', content: artifact?.content || '', dirty: false, baseline: artifact?.updated_at || null }; S.edits.set(key, edit); }
    ctx.selectedId = id; if (id) ctx.userPickedNew = false; S.selectedArtifacts.set(String(ctx.object.id), id); ctx.currentEdit = edit; ctx.editor.replaceChildren(); const title = el('input', undefined, 'artifact-title'); title.value = edit.title; title.placeholder = '成果标题'; title.setAttribute('aria-label', '成果标题'); const content = el('textarea', undefined, 'artifact-content'); content.value = edit.content; content.placeholder = '查看或编辑当前商品、客户的工作成果。'; content.setAttribute('aria-label', '成果正文'); const caption = el('span', artifact ? `已保存 · ${time(artifact.updated_at)}` : '尚未保存', 'artifact-caption'), save = button('保存成果', async () => {
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
      const priorStates=new Map(S.jobs.map(job=>[job.id,job.status]));
      const value = await api('/api/desk/jobs'); const prior = JSON.stringify(S.jobs.map(job => [job.id, job.status, job.updated_at])); S.jobs = array(value, 'jobs'); const changed = JSON.stringify(S.jobs.map(job => [job.id, job.status, job.updated_at])) !== prior;
      const transitions=S.jobs.filter(job=>['queued','running'].includes(priorStates.get(job.id)) && !isActive(job));
      let objectsChanged = false, dataChanged = false, websiteUpdated = false, gmailUpdated = false;
      if (Date.now() - S.lastBootstrapPoll >= 12000 || ['loading', 'refreshing', 'pending'].includes(S.websiteStatus.state) || ['loading', 'refreshing', 'pending'].includes(S.alibabaStatus.state)) {
        const result = await api('/api/desk/bootstrap'); S.lastBootstrapPoll = Date.now(); const old = JSON.stringify(S.objects); S.objects = result.objects || S.objects; objectsChanged = old !== JSON.stringify(S.objects); const priorArtifacts = JSON.stringify(S.artifacts.map(item => [item.id, item.updated_at])); S.artifacts = result.artifacts || S.artifacts; dataChanged = priorArtifacts !== JSON.stringify(S.artifacts.map(item => [item.id, item.updated_at])); websiteUpdated = !!result.website_status?.observed_at && result.website_status.observed_at !== S.websiteStatus.observed_at; gmailUpdated = (result.gmail_revision || 0) !== S.gmailRevision; S.gmailRevision = result.gmail_revision || 0; S.websiteStatus = result.website_status || S.websiteStatus; S.alibabaStatus = result.alibaba_status || S.alibabaStatus; if (result.csrf_token) S.token = result.csrf_token; updateWebsiteLabels();
      }
      if (S.detail) { const ctx = S.detail; if (changed) renderAgentJobs(ctx); if(changed && ctx.batch){if(ctx.batchJobsChanged)await ctx.batchJobsChanged(transitions);else if(S.listRefresh)await S.listRefresh();}if(S.detail!==ctx)return; if(ctx.gmailHost && (gmailUpdated || Date.now()-(ctx.lastGmailRefresh || 0)>=12000))loadGmail(ctx); if(ctx.profileHost && !ctx.profileEditing && !ctx.workflowEditing && (gmailUpdated || (isWebsite(ctx.object) && (websiteUpdated || Date.now()-(ctx.lastProfileRefresh || 0)>=120000)))) {ctx.lastProfileRefresh=Date.now();loadProfile(ctx);} if (changed && ctx.profileHost && !ctx.profileEditing) loadProfile(ctx); if (!ctx.batch && (changed || dataChanged || jobsFor(ctx.object.id).some(isActive))) await refreshArtifacts(ctx); }
      else if(S.page==='customers' && parseRoute().query.get('view')==='batches' && changed && S.listRefresh)await S.listRefresh();
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
