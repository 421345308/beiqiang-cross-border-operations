'use strict';
(() => {
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const act = (text, handler, cls) => { const b = node('button', text, cls); b.type = 'button'; b.addEventListener('click', () => Promise.resolve(handler()).catch(error => window.alert(error.message || '操作未完成'))); return b; };
  const field = (tag, placeholder) => { const e = node(tag); if (placeholder) e.placeholder = placeholder; return e; };
  const toolbar = (...items) => { const n = node('div', undefined, 'module-toolbar'); n.append(...items); return n; };
  const status = (target, text, kind = '') => { target.textContent = text; target.className = `module-status ${kind}`; };
  const prettyDate = value => value ? date(value) : '未提供';
  const external = (label, url) => { try { const parsed = new URL(url); if (parsed.protocol !== 'https:') return null; const a = node('a', label, 'module-link'); a.href = parsed.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; } catch { return null; } };
  const changeErrors = { INVALID_ARGUMENT: '请检查标题、变更理由和依据文件是否完整。', INVALID_EVIDENCE_PATH: '依据文件路径不可用，请选择项目内真实存在的资料。', PROTECTED_PRODUCT: '此商品有来源保护，不能通过本流程提交。', LOCAL_TITLE_MISSING: '本地商品档案缺少原标题，请先补齐原记录。', NO_CHANGE: '拟改标题与当前正式标题一致，无需提交。', PLATFORM_NOT_APPROVED: '商品当前不是可修改的正式审核通过状态。', PLATFORM_VERSION_CONFLICT: '正式商品已变化，请重新准备差异。', LOCAL_VERSION_CONFLICT: '本地商品档案已变化，请先核对原记录。', VERSION_CONFLICT: '变更记录版本已更新，请重新打开核对。', ALREADY_ATTEMPTED_RECONCILE_ONLY: '本记录已尝试提交，只能沿原记录回读，不能重复发送。', INTERNAL_TEST_NOT_SUBMITTABLE: '内部验收草案不可提交平台。', TITLE_SCHEMA_UNVERIFIED: '平台标题结构尚未核实，未提交。', TITLE_SCHEMA_MISMATCH: '平台标题结构不匹配，未提交。', SCHEMA_UNAVAILABLE: '暂未取得平台修改结构，未提交。', PRODUCT_CHANGE_IN_PROGRESS: '该商品已有标题变更正在核对，请先查看原记录。', NOT_SUBMITTED: '本记录尚未提交，不需要执行提交后回读。' };
  async function request(path, body) {
    const options = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workbench-Token': state.data?.csrf_token || '' }, body: JSON.stringify(body) };
    const response = await fetch(path, options); let value;
    try { value = await response.json(); } catch { throw new Error('服务暂未返回可读取的结果，请稍后重试。'); }
    if (!response.ok || value.ok === false) { const message = response.status === 409 && path === '/api/canvases' ? '草稿已在其他页面更新，请重新打开核对；本次未保存内容仍保留。' : typeof value.error === 'string' ? value.error : value.error?.message || changeErrors[value.error?.code] || '服务暂不可用，请检查连接后重试。'; const error = new Error(String(message).slice(0, 400)); error.code = typeof value.error === 'object' ? value.error?.code : undefined; error.status = response.status; error.change = value.change || null; throw error; }
    return value;
  }
  const dataPart = (result, key) => result.data?.[key] ?? result.data ?? result[key];
  const arrayItems = value => Array.isArray(value) ? value : value?.items || [];
  const nodeContent = value => typeof value === 'string' ? value : Array.isArray(value) ? value.filter(item => typeof item === 'string').join('\n') : '';
  const uuid = () => crypto.randomUUID ? crypto.randomUUID() : `node-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const titleBlock = (root, eyebrow, title, description) => { const h = node('div', undefined, 'module-header'), text = node('div'); text.append(node('span', eyebrow, 'eyebrow'), node('h1', title), node('p', description)); h.append(text); root.append(h); };
  const c = { ready: false, canvas: { title: '未命名视频草稿', nodes: [] }, selected: null, dirty: false, zoom: 1, remoteProject: null, remoteWorkspace: '', remoteProjects: [], page: 1 };
  const refs = {};
  const mediaCache = new Map();
  const mediaKey = item => `${item.id}:${item.media_path || ''}`;
  function changed() { c.dirty = true; status(refs.canvasStatus, '本地修改尚未保存'); }
  function leaveDraft() { if (c.saving) { status(refs.canvasStatus, '正在保存，请稍后再切换草稿。'); return false; } return !c.dirty || window.confirm('当前本地草稿尚未保存，继续会放弃本次未保存的修改。'); }
  function canvasDimensions() { return { width: Math.max(1800, ...c.canvas.nodes.map(n => Number(n.x) + 330)), height: Math.max(1200, ...c.canvas.nodes.map(n => Number(n.y) + (n.type === 'asset' ? 430 : 250))) }; }
  function drawLines() {
    const { width, height } = canvasDimensions(); refs.wires.setAttribute('width', width); refs.wires.setAttribute('height', height); refs.wires.replaceChildren();
    for (let i = 1; i < c.canvas.nodes.length; i++) { const a = c.canvas.nodes[i - 1], b = c.canvas.nodes[i], path = document.createElementNS('http://www.w3.org/2000/svg', 'path'); const x = Number(a.x) + 260, y = Number(a.y) + 40, endX = Number(b.x), endY = Number(b.y) + 40; path.setAttribute('d', `M ${x} ${y} C ${x + 60} ${y}, ${endX - 60} ${endY}, ${endX} ${endY}`); refs.wires.append(path); }
  }
  function resizeCanvas() { const { width, height } = canvasDimensions(); refs.surface.style.width = `${width}px`; refs.surface.style.height = `${height}px`; refs.surface.style.transform = `scale(${c.zoom})`; refs.bounds.style.width = `${width * c.zoom}px`; refs.bounds.style.height = `${height * c.zoom}px`; drawLines(); }
  function selectCard(id) { c.selected = id; refs.surface.querySelectorAll('.canvas-node').forEach(el => el.classList.toggle('selected', el.dataset.id === id)); renderEditor(); }
  const kindLabel = type => ({ text: '文本', shot: '镜头', asset: '素材' }[type] || '文本');
  function renderCanvas() {
    refs.title.value = c.canvas.title || ''; refs.surface.replaceChildren(refs.wires);
    if (!c.canvas.nodes.length) refs.surface.append(node('div', '空白本地画布。添加文本、镜头或素材卡片，再拖动排列；连接线按卡片顺序显示。这里不会自动调用付费生成。', 'canvas-empty'));
    for (const item of c.canvas.nodes) {
      const card = node('article', undefined, `canvas-node${item.id === c.selected ? ' selected' : ''}`); card.dataset.id = item.id; card.style.left = `${item.x}px`; card.style.top = `${item.y}px`;
      const head = node('div', undefined, 'canvas-node-head'); head.append(node('span', `${c.canvas.nodes.indexOf(item) + 1} · ${kindLabel(item.type)}`), node('span', '拖动')); head.tabIndex = 0; head.setAttribute('aria-label', `选择并拖动 ${item.title || kindLabel(item.type)}`);
      head.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectCard(item.id); } });
      head.addEventListener('pointerdown', event => {
        if (event.button !== 0) return; event.preventDefault(); selectCard(item.id); const start = { x: event.clientX, y: event.clientY, left: item.x, top: item.y }; head.setPointerCapture(event.pointerId);
        const move = next => { item.x = Math.max(0, Math.round(start.left + (next.clientX - start.x) / c.zoom)); item.y = Math.max(0, Math.round(start.top + (next.clientY - start.y) / c.zoom)); card.style.left = `${item.x}px`; card.style.top = `${item.y}px`; changed(); resizeCanvas(); };
        const end = () => { head.removeEventListener('pointermove', move); head.removeEventListener('pointerup', end); head.removeEventListener('pointercancel', end); };
        head.addEventListener('pointermove', move); head.addEventListener('pointerup', end); head.addEventListener('pointercancel', end);
      });
      card.append(head, node('h4', item.title || '未命名卡片'), node('p', item.content || '选择卡片，在左侧编辑内容。')); if (item.type === 'asset') card.append(mediaPreview(item)); card.addEventListener('click', event => { if (!event.target.closest('video,audio,img,button,a,input,textarea')) selectCard(item.id); }); refs.surface.append(card);
    }
    resizeCanvas(); renderEditor();
  }
  function verifiedMedia(value) {
    if (!value || !['image', 'video', 'audio'].includes(value.kind) || typeof value.path !== 'string' || !value.path || typeof value.url !== 'string' || !value.url || typeof value.mime_type !== 'string' || !value.mime_type.startsWith(`${value.kind}/`)) throw new Error('服务未返回有效的本地媒体引用，未显示预览。');
    const url = new URL(value.url, window.location.origin);
    if (url.origin !== window.location.origin || url.pathname !== '/api/media/file' || url.username || url.password || url.hash || url.searchParams.get('path') !== value.path) throw new Error('服务未返回已核本地媒体地址，未显示预览。');
    return { ...value, url: url.pathname + url.search };
  }
  function mediaPreview(item) {
    const box = node('div', undefined, 'asset-preview'); const saved = mediaCache.get(mediaKey(item));
    if (!item.media_path) { box.append(node('p', '尚未选择项目素材。填写相对路径后点击“检查并预览”。', 'subtle')); return box; }
    box.append(node('div', item.media_path, 'asset-path'));
    if (saved?.status !== 'ready') { box.append(node('p', saved?.message || '尚未检查实际素材，未加载预览。', saved?.status === 'error' ? 'module-status error' : 'subtle')); return box; }
    let media;
    try { media = verifiedMedia(saved.media); } catch (error) { box.append(node('p', error.message, 'module-status error')); return box; }
    const preview = node(media.kind === 'image' ? 'img' : media.kind); preview.src = media.url;
    if (media.kind === 'image') { preview.alt = media.name || item.title || '项目图片素材'; preview.loading = 'lazy'; }
    else { preview.controls = true; preview.preload = 'metadata'; if (media.kind === 'video') preview.playsInline = true; }
    preview.addEventListener('error', () => { preview.remove(); if (!box.querySelector('.asset-load-error')) box.append(node('p', '素材读取失败或文件已变化。请重新检查路径后预览。', 'module-status error asset-load-error')); });
    preview.addEventListener('click', event => event.stopPropagation());
    const enlarge = act('放大预览', () => { if (typeof preview.pause === 'function') preview.pause(); openMediaPreview(media); }); enlarge.addEventListener('click', event => event.stopPropagation());
    box.append(preview, enlarge, node('div', `${media.name || '本地素材'} · ${media.mime_type} · ${Number.isFinite(media.size) ? `${media.size.toLocaleString('zh-CN')} 字节` : '大小未提供'}`, 'subtle')); return box;
  }
  function openMediaPreview(reference) {
    const media = verifiedMedia(reference), dialog = node('dialog', undefined, 'media-lightbox');
    const preview = node(media.kind === 'image' ? 'img' : media.kind), content = node('div', undefined, 'media-lightbox-content'), message = node('div', '', 'module-status'); preview.src = media.url;
    if (media.kind === 'image') preview.alt = media.name || '本地项目素材';
    else { preview.controls = true; preview.preload = 'metadata'; if (media.kind === 'video') preview.playsInline = true; }
    preview.addEventListener('error', () => status(message, '素材读取失败或文件已变化。关闭后请重新检查路径。', 'error'));
    content.append(preview); dialog.append(toolbar(node('h2', media.name || '实际素材预览'), act('关闭预览', () => dialog.close())), node('p', media.path, 'subtle'), message, content);
    dialog.addEventListener('close', () => { if (typeof preview.pause === 'function') { preview.pause(); preview.removeAttribute('src'); preview.load(); } dialog.remove(); }); document.body.append(dialog); dialog.showModal();
  }
  async function resolveMedia(item, { quiet = false } = {}) {
    const requestedPath = (item.media_path || '').trim(); if (!requestedPath) { if (!quiet) status(refs.canvasStatus, '请先填写项目相对素材路径。', 'error'); return; }
    const key = mediaKey(item); if (mediaCache.get(key)?.status === 'loading') return; mediaCache.set(key, { status: 'loading', message: '正在核对本地文件与媒体类型…' });
    try {
      const result = await request('/api/media/resolve', { path: requestedPath }), media = verifiedMedia(result.media);
      if (!c.canvas.nodes.includes(item) || (item.media_path || '').trim() !== requestedPath) return;
      if (item.media_path !== media.path) { item.media_path = media.path; changed(); }
      mediaCache.set(mediaKey(item), { status: 'ready', media }); if (!quiet) status(refs.canvasStatus, '实际素材已核对，预览仅在本机读取；未上传远端。', 'success');
    } catch (error) { if (!c.canvas.nodes.includes(item)) return; mediaCache.set(key, { status: 'error', message: error.message }); if (!quiet) status(refs.canvasStatus, error.message, 'error'); }
    renderCanvas();
  }
  function resolveSavedMedia() { for (const item of c.canvas.nodes) if (item.type === 'asset' && item.media_path) resolveMedia(item, { quiet: true }); }
  function renderEditor() {
    const target = refs.editor; target.replaceChildren(node('h3', '卡片内容')); const item = c.canvas.nodes.find(n => n.id === c.selected);
    if (!item) { target.append(node('p', '选择画布卡片后编辑标题和文字。', 'subtle')); return; }
    const title = field('input', '卡片标题'), content = field('textarea', '提示词、镜头说明或素材引用'); title.value = item.title; content.value = item.content;
    title.addEventListener('input', () => { item.title = title.value; const card = [...refs.surface.querySelectorAll('.canvas-node')].find(n => n.dataset.id === item.id); if (card) card.querySelector('h4').textContent = item.title || '未命名卡片'; changed(); });
    content.addEventListener('input', () => { item.content = content.value; const card = [...refs.surface.querySelectorAll('.canvas-node')].find(n => n.dataset.id === item.id); if (card) card.querySelector('p').textContent = item.content || '选择卡片，在左侧编辑内容。'; changed(); });
    const actions = toolbar(act('前移一位', () => { const index = c.canvas.nodes.indexOf(item); if (index > 0) { [c.canvas.nodes[index - 1], c.canvas.nodes[index]] = [c.canvas.nodes[index], c.canvas.nodes[index - 1]]; changed(); renderCanvas(); } }), act('删除卡片', () => { c.canvas.nodes = c.canvas.nodes.filter(n => n.id !== item.id); c.selected = null; changed(); renderCanvas(); }));
    target.append(node('label', `${kindLabel(item.type)} · 标题`), title, node('label', '提示文字 / 内容'), content);
    if (item.type === 'asset') {
      const path = field('input', '05_内容与视频/项目/素材.png'); path.value = item.media_path || ''; path.setAttribute('aria-label', '项目相对素材路径');
      path.addEventListener('input', () => { item.media_path = path.value; changed(); const card = [...refs.surface.querySelectorAll('.canvas-node')].find(el => el.dataset.id === item.id); card?.querySelector('.asset-preview')?.replaceWith(mediaPreview(item)); });
      target.append(node('label', '项目相对素材路径（图片 / 视频 / 音频）'), path, node('p', '仅读取后端核准的本地文件。路径文字不会被当作网址或文件地址直接加载。', 'subtle'), act('检查并预览实际素材', () => resolveMedia(item)));
    }
    target.append(actions, act('复制此内容到 LibTV 文本节点…', () => syncNode(item)));
  }
  function addCard(type) { const index = c.canvas.nodes.length; const item = { id: uuid(), type, title: `${kindLabel(type)} ${index + 1}`, content: '', x: 45 + (index % 4) * 310, y: 45 + Math.floor(index / 4) * 230 }; c.canvas.nodes.push(item); c.selected = item.id; changed(); renderCanvas(); }
  async function refreshCanvases() {
    const result = await request('/api/canvases'); const rows = result.canvases || []; refs.saved.replaceChildren(new Option('打开已保存的本地草稿', '')); rows.forEach(row => refs.saved.add(new Option(`${row.title} · ${prettyDate(row.updated_at)}`, row.id)));
    if (c.canvas.id) refs.saved.value = c.canvas.id;
  }
  async function saveCanvas() {
    if (c.saving) return; c.saving = true; c.canvas.title = refs.title.value.trim() || '未命名视频草稿'; const snapshot = JSON.stringify(c.canvas); status(refs.canvasStatus, '正在保存本地草稿…');
    try {
      const result = await request('/api/canvases', { ...(c.canvas.id ? { id: c.canvas.id, updated_at: c.canvas.updated_at } : {}), title: c.canvas.title, nodes: c.canvas.nodes, ...(c.canvas.project_id ? { project_id: c.canvas.project_id } : {}), ...(c.canvas.workspace_id ? { workspace_id: c.canvas.workspace_id } : {}) });
      const saved = result.canvas || result.data || result;
      if (JSON.stringify(c.canvas) === snapshot) { c.canvas = saved; c.dirty = false; status(refs.canvasStatus, `已保存到本机 · ${prettyDate(c.canvas.updated_at)}。未修改 LibTV。`, 'success'); }
      else { c.canvas.id = saved.id; c.canvas.updated_at = saved.updated_at; c.dirty = true; status(refs.canvasStatus, '上一版已保存；保存期间的新修改仍未保存。'); }
      await refreshCanvases(); renderCanvas();
    } catch (error) { status(refs.canvasStatus, error.message, 'error'); }
    finally { c.saving = false; }
  }
  async function confirmRemote(title, description, perform) {
    const dialog = node('dialog', undefined, 'module-confirm'); dialog.append(node('h2', title), node('p', '这是明确的 LibTV 远端写入；仅创建画布或文本节点，不运行图片/视频生成。'), node('pre', description));
    const confirm = act('确认执行这项远端操作', async () => { confirm.disabled = true; try { await perform(); dialog.close(); } catch (error) {
      const uncertain = error.code === 'WRITE_RESULT_UNCONFIRMED' || /TIMEOUT|TIMED_OUT/i.test(String(error.code || '')) || error.status === 504 || error instanceof TypeError;
      status(message, uncertain ? `${error.message}\n操作结果尚未确认。请关闭此窗口，先重新读取目标画布核对；不要重复创建。` : error.message, 'error');
      confirm.disabled = uncertain;
    } }, 'primary'), message = node('div', '', 'module-status'); dialog.append(message, toolbar(act('取消', () => dialog.close()), confirm)); document.body.append(dialog); dialog.addEventListener('close', () => dialog.remove()); dialog.showModal();
  }
  async function loadWorkspaces() {
    status(refs.remoteStatus, '正在读取 LibTV 工作空间…');
    try { const result = await request('/api/tools/libtv/workspaces'); const workspaces = arrayItems(dataPart(result, 'workspaces')); refs.workspace.replaceChildren(new Option('选择 LibTV 工作空间', ''), new Option('根目录（0）', '0')); workspaces.filter(row => String(row.id) !== '0').forEach(row => refs.workspace.add(new Option(row.name || row.id, row.id))); status(refs.remoteStatus, workspaces.length ? `已读取 ${workspaces.length} 个工作空间。` : '当前返回没有工作空间；未生成示例画布。'); }
    catch (error) { status(refs.remoteStatus, error.message, 'error'); }
  }
  async function loadProjects() {
    const id = refs.workspace.value; if (!id) { status(refs.remoteStatus, '先选择工作空间。'); return; }
    status(refs.remoteStatus, '正在读取远端画布列表…');
    try { const result = await request(`/api/tools/libtv/projects?workspace_id=${encodeURIComponent(id)}`); c.remoteProjects = arrayItems(dataPart(result, 'projects')); c.remoteWorkspace = id; refs.project.replaceChildren(new Option('选择远端画布（只读）', '')); c.remoteProjects.forEach(row => refs.project.add(new Option(row.name || row.id, row.id))); c.remoteProject = null; refs.remoteInfo.replaceChildren(); status(refs.remoteStatus, c.remoteProjects.length ? `找到 ${c.remoteProjects.length} 个远端画布。` : '本次未返回画布。'); }
    catch (error) { status(refs.remoteStatus, error.message, 'error'); }
  }
  async function readProject() {
    const id = refs.project.value; if (!id) { status(refs.remoteStatus, '先选择远端画布。'); return; } c.remoteProject = null; refs.remoteInfo.replaceChildren(); status(refs.remoteStatus, '正在只读获取远端节点与文本内容…');
    try {
      const result = await request(`/api/tools/libtv/project?project_id=${encodeURIComponent(id)}`); const project = dataPart(result, 'project'); if (!project || !project.id) throw new Error('画布返回缺少标识，未导入。');
      if (!project.name) project.name = c.remoteProjects.find(row => String(row.id) === String(project.id))?.name || '';
      const nodeResult = await request(`/api/tools/libtv/nodes?project_id=${encodeURIComponent(id)}`), detailed = dataPart(nodeResult, 'nodes'), summaries = new Map((project.nodes || []).map(item => [String(item.id), item]));
      project.nodes = arrayItems(detailed).map(item => { const summary = summaries.get(String(item.id)) || {}; return { ...summary, ...item, title: item.title || summary.title || '', content: item.content ?? summary.content, x: item.x ?? summary.x, y: item.y ?? summary.y }; });
      c.remoteProject = project; refs.remoteInfo.append(node('p', `${project.name || project.id} · ${project.nodes.length} 个远端节点。仅查询，未写入远端。`, 'subtle'), node('p', `远端画布 ID：${project.id}`, 'subtle'));
      if (detailed?.text_content_complete === false) refs.remoteInfo.append(node('p', '部分文本正文尚未取全：本次最多补读前 10 个文本节点。未返回内容不代表空白。', 'module-notice'));
      const preview = node('details'), list = node('div', undefined, 'remote-preview'); preview.append(node('summary', `查看已读取的 ${project.nodes.length} 个节点`));
      for (const item of project.nodes) { const text = nodeContent(item.content); list.append(node('p', `${item.title || item.id} · ${item.type || '类型未提供'}\n${text ? text.slice(0, 500) + (text.length > 500 ? '…' : '') : '本次未返回正文'}`)); }
      preview.append(list); refs.remoteInfo.append(preview); const link = external('打开官方画布 ↗', project.official_url); if (link) refs.remoteInfo.append(link); refs.remoteInfo.append(act('导入为本地草稿', importRemote)); status(refs.remoteStatus, `只读获取完成 · ${prettyDate(nodeResult.source?.collectedAt || result.source?.collectedAt)}`, 'success');
    } catch (error) { status(refs.remoteStatus, error.message, 'error'); }
  }
  function importRemote() {
    if (!c.remoteProject || !leaveDraft()) return; const project = c.remoteProject;
    c.canvas = { title: `${project.name || 'LibTV 画布'} · 本地草稿`, project_id: project.id, workspace_id: project.workspace_id || refs.workspace.value, nodes: (project.nodes || []).map((n, i) => ({ id: String(n.id || uuid()), type: /image|video|audio|asset/i.test(n.type || '') ? 'asset' : /shot|scene/i.test(n.type || '') ? 'shot' : 'text', title: String(n.title || `节点 ${i + 1}`), content: nodeContent(n.content), x: Number.isFinite(Number(n.x)) ? Math.max(0, Number(n.x)) : 45 + (i % 4) * 310, y: Number.isFinite(Number(n.y)) ? Math.max(0, Number(n.y)) : 45 + Math.floor(i / 4) * 230 })) }; c.selected = null; changed(); renderCanvas(); status(refs.canvasStatus, '已导入为未保存的本地草稿。修改与保存不会同步到 LibTV。');
  }
  function syncNode(item) {
    const project = c.remoteProject; if (!project || refs.project.value !== String(project.id)) { status(refs.remoteStatus, '先读取并核对目标远端画布，再同步文本节点。', 'error'); return; }
    return confirmRemote('确认创建远端文本节点', `工作空间：${refs.workspace.options[refs.workspace.selectedIndex]?.text || project.workspace_id || '未提供'}\n目标画布：${project.name || project.id}\n画布 ID：${project.id}\n标题：${item.title}\n位置：${item.x}, ${item.y}\n\n${item.content}`, async () => { const result = await request('/api/tools/libtv/create-text-node', { project_id: project.id, title: item.title, content: item.content, x: item.x, y: item.y, confirmed: true }); const created = dataPart(result, 'node'); status(refs.remoteStatus, `远端文本节点已创建\n画布 ID：${project.id}\n节点 ID：${created?.id || '回执未提供，请先回读，不要重复创建'}\n本地草稿保持独立。`, 'success'); });
  }
  function createRemoteProject() {
    const workspace = refs.workspace.value, name = refs.remoteName.value.trim(); if (!workspace || !name) { status(refs.remoteStatus, '先选择工作空间并填写新远端画布名称。','error'); return; }
    return confirmRemote('确认新建 LibTV 远端画布', `工作空间：${refs.workspace.options[refs.workspace.selectedIndex]?.text}\n工作空间 ID：${workspace}\n新画布名称：${name}`, async () => { const result = await request('/api/tools/libtv/create-project', { name, workspace_id: workspace, confirmed: true }); const created = dataPart(result, 'project'); await loadProjects(); if (created?.id) { if (![...refs.project.options].some(option => option.value === String(created.id))) refs.project.add(new Option(created.name || name, String(created.id))); if (!c.remoteProjects.some(row => String(row.id) === String(created.id))) c.remoteProjects.push({ ...created, name: created.name || name }); refs.project.value = String(created.id); } status(refs.remoteStatus, `远端画布已创建\n名称：${name}\n画布 ID：${created?.id || '回执未提供，请先回读，不要重复创建'}\n请选择只读打开，核对实际节点。`, 'success'); });
  }
  function initVideo() {
    if (c.ready) return; c.ready = true; const root = document.getElementById('video-view'); titleBlock(root, 'VIDEO WORKSPACE', '把想法排成镜头', '本地草稿在本机保存。LibTV 远端画布通过明确的读取或确认操作连接；本轮不提供付费生成。');
    refs.title = field('input', '本地草稿标题'); refs.title.value = c.canvas.title; refs.title.addEventListener('input', () => { c.canvas.title = refs.title.value; changed(); }); refs.saved = field('select'); refs.saved.add(new Option('打开已保存的本地草稿', ''));
    refs.saved.addEventListener('change', async () => { if (!refs.saved.value || !leaveDraft()) return; try { const result = await request(`/api/canvases/${encodeURIComponent(refs.saved.value)}`); c.canvas = result.canvas || result.data || result; c.selected = null; c.dirty = false; renderCanvas(); resolveSavedMedia(); status(refs.canvasStatus, '已打开本地保存的草稿，不代表 LibTV 远端最新状态。'); } catch (error) { status(refs.canvasStatus, error.message, 'error'); } });
    root.append(toolbar(refs.title, act('新建本地草稿', () => { if (leaveDraft()) { c.canvas = { title: '未命名视频草稿', nodes: [] }; c.selected = null; c.dirty = false; renderCanvas(); status(refs.canvasStatus, '新建本地草稿，尚未保存。'); } }), act('保存到本机', saveCanvas, 'primary'), refs.saved)); refs.canvasStatus = node('div', '', 'module-status'); root.append(refs.canvasStatus);
    const layout = node('div', undefined, 'canvas-layout'), side = node('aside', undefined, 'canvas-side'), cards = node('section', undefined, 'card'); cards.append(node('h3', '添加卡片'), toolbar(act('＋ 文本', () => addCard('text')), act('＋ 镜头', () => addCard('shot')), act('＋ 素材', () => addCard('asset'))));
    const remote = node('section', undefined, 'card'); remote.append(node('span', 'LIBTV 远端 · 不自动同步', 'remote-label')); refs.workspace = field('select'); refs.workspace.add(new Option('先读取工作空间', '')); refs.project = field('select'); refs.project.add(new Option('先读取画布列表', '')); refs.workspace.addEventListener('change', () => { c.remoteProject = null; refs.remoteInfo.replaceChildren(); refs.project.replaceChildren(new Option('重新读取画布列表', '')); }); refs.project.addEventListener('change', () => { c.remoteProject = null; refs.remoteInfo.replaceChildren(); }); refs.remoteName = field('input', '新远端画布名称'); refs.remoteStatus = node('div', '', 'module-status'); refs.remoteInfo = node('div');
    remote.append(toolbar(act('读取工作空间', loadWorkspaces), refs.workspace, act('读取远端画布列表', loadProjects), refs.project, act('只读打开远端画布', readProject), refs.remoteName, act('新建远端画布…', createRemoteProject)), refs.remoteStatus, refs.remoteInfo);
    refs.editor = node('section', undefined, 'card module-form canvas-editor'); side.append(cards, remote, refs.editor); const board = node('div'); const zoom = field('input'); zoom.type = 'range'; zoom.min = '40'; zoom.max = '150'; zoom.value = '100'; zoom.setAttribute('aria-label', '画布缩放'); const zoomLabel = node('span', '100%', 'subtle'); zoom.addEventListener('input', () => { c.zoom = Number(zoom.value) / 100; zoomLabel.textContent = `${zoom.value}%`; resizeCanvas(); });
    refs.viewport = node('div', undefined, 'canvas-viewport'); refs.bounds = node('div', undefined, 'canvas-bounds'); refs.surface = node('div', undefined, 'canvas-surface'); refs.wires = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); refs.wires.classList.add('canvas-wires'); refs.surface.append(refs.wires); refs.bounds.append(refs.surface); refs.viewport.append(refs.bounds); board.append(toolbar(node('span', '缩放'), zoom, zoomLabel, node('span', '拖动卡片标题移动 · 顺序连线', 'subtle')), refs.viewport); layout.append(side, board); root.append(layout); renderCanvas(); refreshCanvases().catch(error => status(refs.canvasStatus, error.message, 'error'));
  }
  // Alibaba panels are loaded independently: unavailable services stay unknown,
  // never turn into invented zero metrics or illustrative product cards.
  const a = { ready: false, tab: 'products', page: 1, pageSize: 20, product: null, capabilities: null, productsLoaded: false };
  const ar = {};
  function initAlibaba() {
    if (a.ready) return; a.ready = true; const root = document.getElementById('alibaba-view'); titleBlock(root, 'ALIBABA.COM', '国际站经营', '商品、客户与订单、经营数据分别读取实际来源；本地优化草稿不会自动提交平台。'); ar.tabs = node('div', undefined, 'module-tabs');
    for (const [id, label] of [['products', '商品'], ['customers', '客户与订单'], ['metrics', '经营数据']]) ar.tabs.append(act(label, () => switchAlibaba(id)));
    ar.message = node('div', '', 'module-status'); ar.body = node('div'); root.append(ar.tabs, ar.message, ar.body); loadCapabilities(); switchAlibaba('products');
  }
  async function loadCapabilities() { try { const result = await request('/api/tools/alibaba/capabilities'); a.capabilities = result.data?.capabilities || result.data || result.capabilities || {}; } catch (error) { a.capabilitiesError = error.message; } if (a.tab === 'customers') renderCapabilityCards(); }
  function switchAlibaba(tab) { a.tab = tab; [...ar.tabs.children].forEach((el, i) => el.classList.toggle('active', i === ['products', 'customers', 'metrics'].indexOf(tab))); ar.body.replaceChildren(); status(ar.message, ''); if (tab === 'products') renderProductsPanel(); if (tab === 'customers') renderCustomers(); if (tab === 'metrics') renderMetrics(); }
  function renderProductsPanel() {
    ar.products = node('div', undefined, 'product-grid'); ar.detail = node('section', undefined, 'module-detail'); ar.pagination = node('div', undefined, 'module-toolbar'); ar.pageLabel = node('span', '', 'subtle'); const prev = act('上一页', () => { if (a.page > 1) { a.page--; loadProducts(); } }); const next = act('下一页', () => { a.page++; loadProducts(); }); ar.prev = prev; ar.next = next;
    ar.body.append(toolbar(act('读取平台商品', () => loadProducts()), act('查看本地优化草稿', loadProductDrafts), act('标题变更记录', loadTitleChanges), node('span', '商品数量只用于翻页，不代表经营表现。', 'subtle')), ar.products); ar.pagination.append(prev, ar.pageLabel, next); ar.body.append(ar.pagination, ar.detail); loadProducts();
  }
  function productRows(result) { return arrayItems(result.data?.products || result.data); }
  async function loadProducts() {
    const page = a.page; ar.prev.disabled = true; ar.next.disabled = true; status(ar.message, '正在读取国际站商品…');
    try { const result = await request(`/api/tools/alibaba/products?page=${page}&page_size=${a.pageSize}`); if (a.tab !== 'products') return; const rows = productRows(result); ar.products.replaceChildren(); rows.forEach(product => {
      const card = node('article', undefined, 'card product-card'); const imageUrl = product.main_image?.images?.[0] || product.image_url || product.image;
      if (typeof imageUrl === 'string' && /^https:\/\//i.test(imageUrl)) { const image = node('img', undefined, 'product-image'); image.src = imageUrl; image.alt = product.subject || product.title || '商品主图'; image.loading = 'lazy'; image.referrerPolicy = 'no-referrer'; image.addEventListener('error', () => image.remove()); card.append(image); }
      card.append(node('h3', product.subject || product.title || '平台未提供标题'), node('div', `商品 ID：${product.id || product.product_id || '未提供'}`, 'subtle')); if (product.status) card.append(node('div', `平台状态：${product.status}`, 'subtle')); card.append(act('读取商品详情', () => loadProduct(product.id || product.product_id))); const link = external('打开平台商品 ↗', product.platformUrl || product.pc_detail_url || product.url || product.platform_url); if (link) card.append(link); ar.products.append(card);
    }); if (!rows.length) ar.products.append(node('p', '本次没有返回商品；未填充示例数据。', 'empty'));
      const pagination = result.pagination || result.data?.pagination || {}; ar.pageLabel.textContent = `第 ${page} 页 · 本页 ${rows.length} 条${Number.isFinite(pagination.total) ? ` · 平台共 ${pagination.total} 条` : ''}`; ar.prev.disabled = page <= 1; ar.next.disabled = pagination.hasMore === false || (Number.isFinite(pagination.total) ? page * a.pageSize >= pagination.total : rows.length < a.pageSize); status(ar.message, `商品读取完成 · ${prettyDate(result.source?.collectedAt || result.source?.attemptedAt)} · 使用项目现有国际站连接`, 'success');
    } catch (error) { if (a.tab === 'products') { ar.products.replaceChildren(); status(ar.message, error.message, 'error'); ar.prev.disabled = a.page <= 1; ar.next.disabled = true; } }
  }
  async function loadProduct(id) {
    if (!id) { status(ar.message, '该条记录缺少商品 ID，无法查询详情。', 'error'); return; } status(ar.message, '正在获取真实商品详情…');
    try { const result = await request(`/api/tools/alibaba/product?product_id=${encodeURIComponent(id)}`); if (a.tab !== 'products') return; const product = result.data?.product || result.data; a.product = product; const subject = product.subject || product.title || ''; ar.detail.replaceChildren(node('h2', subject || '商品详情')); const dl = node('dl');
      for (const [label, value] of [['商品 ID', product.id || product.product_id || id], ['平台状态', product.status], ['获取时间', prettyDate(result.source?.collectedAt || result.source?.attemptedAt)], ['类目', product.category_name || product.category_id], ['详情摘要', product.description]]) if (value !== undefined && value !== null && value !== '') dl.append(node('dt', label), node('dd', String(value))); ar.detail.append(dl); const link = external('在平台打开此商品 ↗', product.platformUrl || product.pc_detail_url || product.url || product.platform_url); if (link) ar.detail.append(link);
      const draftHost = node('section'); ar.detail.append(draftHost); renderProductDraftEditor({ product_id: String(product.id || id), subject_before: subject, subject_after: subject, notes: '' }, draftHost);

    } catch (error) { status(ar.message, error.message, 'error'); }
  }
  function renderProductDraftEditor(draft, host) {
    host.replaceChildren(); const form = node('div', undefined, 'module-form'), after = field('textarea', '拟优化的标题'), notes = field('textarea', '优化依据、待确认信息'), evidence = field('textarea', '项目相对依据路径，每行一条');
    after.value = draft.subject_after || ''; notes.value = draft.notes || ''; evidence.value = '02_Alibaba运营/05_扩品工程/数据/国际站商品.json';
    const message = node('div', '', 'module-status'), changes = node('div'); let saving = false, preparing = false;
    const save = act(draft.id ? '保存当前草稿修改' : '保存本地优化草稿', async () => {
      if (saving) return; saving = true; save.disabled = true;
      try {
        const result = await request('/api/product-drafts', { ...(draft.id ? { id: draft.id, updated_at: draft.updated_at } : {}), product_id: String(draft.product_id), subject_before: draft.subject_before || '', subject_after: after.value, notes: notes.value });
        Object.assign(draft, result.draft || result); save.textContent = '保存当前草稿修改'; status(message, `同一本地草稿已保存 · ${prettyDate(draft.updated_at)}。未提交国际站。`, 'success');
      } catch (error) { status(message, error.status === 409 ? '草稿已在其他页面修改，请重新打开核对；当前输入仍保留。' : error.message, 'error'); }
      finally { saving = false; save.disabled = false; }
    }, 'primary');
    const prepare = act('准备标题差异（只读核对）', async () => {
      if (preparing) return; if (!after.value.trim()) { status(message, '请先填写拟修改标题。', 'error'); return; } if (!notes.value.trim()) { status(message, '请填写本次标题变更的具体理由。', 'error'); return; }
      preparing = true; prepare.disabled = true; status(message, '正在读取正式标题并准备具名差异；尚未提交平台…');
      try { const result = await request('/api/product-changes/prepare', { product_id: String(draft.product_id), proposed_title: after.value, rationale: notes.value, evidence: evidence.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean) }); renderTitleChange(result.change, changes); status(message, '标题差异已准备，请核对目标、正式原值、拟改值及本地依据。此步骤未提交平台。', 'success'); }
      catch (error) { status(message, error.message, 'error'); if (error.change) renderTitleChange(error.change, changes); }
      finally { preparing = false; prepare.disabled = false; }
    });
    form.append(node('h3', draft.id ? '继续编辑本地商品草稿' : '本地商品优化草稿'), node('p', `目标商品：${draft.product_id}。草稿只保存提案；平台提交和回执仅保存在独立标题变更记录中。`, 'module-notice'), node('label', '保存时的原标题'), node('p', draft.subject_before || '原草稿未提供标题', 'draft-original'), node('label', '拟修改标题'), after, node('label', '备注与修改依据'), notes, toolbar(save), node('label', '变更依据（已填现有商品档案，可补逐款原始资料）'), evidence, node('p', '新增材料、功能或商业承诺须有逐款事实依据，不能只靠改写标题。准备差异会读取当前平台标题。只有后续具名确认才提交；正式回读、本地同步和公开呈现分别显示。', 'subtle'), prepare, message); host.append(form, changes);
  }
  const titleStateLabels = { prepared: '差异已准备 · 尚未提交', outcome_unknown: '提交结果未知 · 只可回读', submitted: '请求已提交 · 待核正式结果', business_rejected: '平台未接受本次提交', formal_pending: '正式结果待回读', formal_verified: '正式接口已核 · 本地同步待核', local_conflict: '本地记录冲突 · 尚未同步完成', local_synced: '正式回读与本地同步已完成' };
  const stepStateLabels = { 'not-synced': '尚未同步', 'outcome-unknown': '结果未知', 'business-rejected': '未接受', 'not-started': '尚未开始', not_started: '尚未开始', 'not-submitted': '尚未提交', pending: '待核对', 'not-verified': '尚未验收', not_verified: '尚未验收', verified: '已核对', submitted: '已提交', sent: '已发送请求', unknown: '结果未知', failed: '失败', rejected: '未接受', updated: '已更新', synced: '已同步', conflict: '存在冲突', matched: '已一致' };
  function renderTitleChange(change, host) {
    host.replaceChildren(); if (!change || !change.id || !change.productId) { host.append(node('p', '未取得可核的标题变更记录，不能提交。', 'module-status error')); return; }
    const section = node('section', undefined, 'title-change-step'); if (change.internalTest === true) section.append(node('p', '内部验收草案 · 不可提交', 'module-notice')); section.append(node('h3', titleStateLabels[change.state] || `当前状态：${change.state || '未提供'}`), node('p', `目标商品 ID：${change.productId} · 变更记录：${change.id} · 版本 ${change.version}`, 'subtle'));
    const diff = node('div', undefined, 'title-review-diff'), before = node('div'), after = node('div'); before.append(node('strong', '当前正式标题'), node('p', change.diff?.before ?? '未提供')); after.append(node('strong', '拟提交标题'), node('p', change.diff?.after ?? '未提供')); diff.append(before, after); section.append(diff);
    if (change.diff?.localBefore !== undefined) section.append(node('p', `本地记录原值：${change.diff.localBefore || '未提供'}`, 'subtle'));
    if (change.rationale) section.append(node('p', `修改依据：${change.rationale}`));
    if (Array.isArray(change.evidence) && change.evidence.length) { const list = node('ul'); change.evidence.forEach(value => list.append(node('li', typeof value === 'string' ? value : value.path || '依据记录'))); section.append(node('h4', '依据文件'), list); }
    const steps = node('dl'); for (const [label, step] of [['平台提交', change.submission], ['正式接口回读', change.formal], ['本地档案同步', change.localSync], ['公开页面验收', change.publicVerification]]) { const state = step?.state; steps.append(node('dt', label), node('dd', state ? stepStateLabels[state] || state : '尚未取得状态')); } section.append(steps);
    if (change.localSync?.indexState === 'pending-regeneration') section.append(node('p', '本地商品档案已同步；派生索引尚待重新生成。', 'module-notice'));
    if (change.formal?.title) section.append(node('p', `正式回读标题：${change.formal.title}`));
    const publicDone = ['verified', 'matched'].includes(change.publicVerification?.state); section.append(node('p', publicDone ? '公开页面已有独立验收记录，请以该记录范围为准。' : '公开页面尚未完成独立验收，不能把提交成功、正式回读或本地同步称为全部完成。', 'module-notice'));
    const message = node('div', '', 'module-status'), actions = toolbar();
    if (change.state === 'prepared' && change.internalTest !== true) actions.append(act('审阅并确认向该商品提交标题…', () => confirmTitleApply(change, host), 'primary'));
    else section.append(node('p', change.internalTest === true ? '内部验收记录只用于核对差异，不会发起平台写请求。' : '本记录不再重复发送平台写请求；结果未知、待正式回读或本地冲突时，先沿原记录核对。', 'subtle'));
    actions.append(act('重读这条变更记录', async () => { try { const result = await request(`/api/product-changes/${encodeURIComponent(change.id)}`); renderTitleChange(result.change, host); } catch (error) { status(message, error.message, 'error'); } }));
    if (change.state !== 'prepared') actions.append(act('回读结果并核对本地同步', async () => { try { const result = await request(`/api/product-changes/${encodeURIComponent(change.id)}/reconcile`, {}); renderTitleChange(result.change, host); } catch (error) { if (error.change) renderTitleChange(error.change, host); else status(message, error.message, 'error'); } }));
    section.append(actions, message); host.append(section);
  }
  function confirmTitleApply(change, host) {
    if (change.state !== 'prepared' || change.internalTest === true) return; const dialog = node('dialog', undefined, 'module-confirm');
    dialog.append(node('h2', '确认向国际站提交这一条标题差异'), node('p', `目标商品：${change.productId}。仅修改标题，不包含其他商品或字段。`), node('pre', `变更记录：${change.id}\n审阅版本：${change.version}\n\n正式原标题：\n${change.diff?.before || ''}\n\n拟提交标题：\n${change.diff?.after || ''}`));
    const label = node('label', undefined, 'named-confirm'), checked = field('input'); checked.type = 'checkbox'; label.append(checked, document.createTextNode(` 我确认向商品 ${change.productId} 提交上述标题差异`)); const message = node('div', '', 'module-status');
    const submit = act('确认提交给这一个商品', async () => {
      if (!checked.checked || submit.dataset.sent === 'yes') return; submit.dataset.sent = 'yes'; submit.disabled = true; checked.disabled = true; status(message, '正在提交具名标题差异；请勿重复操作…');
      try { const result = await request(`/api/product-changes/${encodeURIComponent(change.id)}/apply`, { confirmed: true, expected_version: change.version }); renderTitleChange(result.change, host); dialog.close(); }
      catch (error) {
        if (error.change) renderTitleChange(error.change, host);
        else renderTitleChange({ ...change, state: 'outcome_unknown', submission: { state: 'unknown' } }, host);
        status(message, `${error.message}\n请关闭本窗口，沿同一变更记录回读核对；此处不会重复发送平台请求。`, 'error');
      }
    }, 'primary'); submit.disabled = true; checked.addEventListener('change', () => { if (submit.dataset.sent !== 'yes') submit.disabled = !checked.checked; });
    dialog.append(label, node('p', '确认后会发起真实平台写请求。成功响应仍须区分正式回读、本地同步及公开验收。', 'module-notice'), message, toolbar(act('取消 / 关闭', () => dialog.close()), submit)); document.body.append(dialog); dialog.addEventListener('close', () => dialog.remove()); dialog.showModal();
  }
  async function loadTitleChanges() {
    try { const result = await request('/api/product-changes'); if (a.tab !== 'products') return; ar.detail.replaceChildren(node('h2', '标题变更与执行回执'), node('p', '这是提交状态的唯一记录。未知结果沿原记录核对，不重新创建同一提交。', 'module-notice')); const detail = node('section'), rows = result.changes || []; if (!rows.length) ar.detail.append(node('p', '尚无标题变更记录。', 'empty')); for (const change of rows) { const row = node('article', undefined, 'card module-list'); row.append(node('h3', `商品 ${change.productId}`), node('p', `${titleStateLabels[change.state] || change.state || '状态未提供'} · ${change.id}`, 'subtle'), act('打开原变更记录', async () => { const item = await request(`/api/product-changes/${encodeURIComponent(change.id)}`); renderTitleChange(item.change, detail); })); ar.detail.append(row); } ar.detail.append(detail); } catch (error) { status(ar.message, error.message, 'error'); }
  }
  async function loadProductDrafts() {
    try {
      const result = await request('/api/product-drafts'); if (a.tab !== 'products') return; ar.detail.replaceChildren(node('h2', '本机保存的优化草稿'), node('p', '草稿仅保留提案，不记录或推断平台提交状态；实际提交请看“标题变更记录”。', 'module-notice')); const rows = result.drafts || [];
      if (!rows.length) ar.detail.append(node('p', '尚未保存本地草稿。', 'empty'));
      rows.forEach(draft => { const row = node('article', undefined, 'card module-list'), editor = node('section'); row.append(node('h3', draft.subject_after || '未填写拟改标题'), node('p', `商品 ID：${draft.product_id} · ${prettyDate(draft.updated_at)} · 本地草稿`, 'subtle'), node('p', `原标题：${draft.subject_before || '未提供'}`), node('p', draft.notes || ''), toolbar(act('重新打开编辑这份草稿', () => renderProductDraftEditor(draft, editor)), act('重新读取平台详情', () => loadProduct(draft.product_id))), editor); ar.detail.append(row); });
    } catch (error) { status(ar.message, error.message, 'error'); }
  }
  function renderCustomers() {
    ar.body.append(node('h2', '客户与订单'), node('p', '查询和操作能力以当前授权接口为准。未接入的模块保留明确说明，不以空列表冒充没有客户或订单。', 'module-notice')); ar.customerBody = node('div', undefined, 'module-list'); ar.body.append(toolbar(act('重读接入说明', async () => { await loadCapabilities(); renderCapabilityCards(); })), ar.customerBody); renderCapabilityCards();
  }
  function renderCapabilityCards() {
    if (a.tab !== 'customers') return; ar.customerBody.replaceChildren();
    if (!a.capabilities) { ar.customerBody.append(node('p', a.capabilitiesError || '正在获取当前接口能力，请稍后点击重新核对。', 'module-status')); return; }
    const business = a.capabilities.business || {};
    const statusLabels = { supported: '已接入', 'not-authorized': '当前未授权', 'not-verified': '待核实', 'not-integrated': '尚未接入', 'permission-required': '需要平台权限', 'authorized-not-integrated': '已授权，尚未接入' };
    for (const [key, name] of [['inquiries', '客户与询盘'], ['quotations', '报价'], ['orders', '订单']]) {
      const cap = business[key], card = node('article', undefined, 'card'); card.append(node('h3', `${name} · ${cap ? statusLabels[cap.status] || cap.status || '状态未知' : '未取得接口状态'}`), node('p', cap?.reason || '该模块尚未取得可核接口状态，不显示假数据。', 'subtle'));
      if (cap?.entry) { const link = external('打开既有业务入口 ↗', cap.entry); if (link) card.append(link); else { card.append(node('p', `既有项目：${cap.entry}`, 'subtle')); if (/\.md$/.test(cap.entry)) card.append(act('查看既有项目资料', () => openDocument(cap.entry))); } }
      ar.customerBody.append(card);
    }
    if (business.orders?.status === 'supported') {
      const orders = node('section', undefined, 'module-detail'), rows = node('div', undefined, 'module-list'), detail = node('div', undefined, 'card module-detail'), message = node('div', '', 'module-status'); let page = 1;
      const pageLabel = node('span', '', 'subtle'), prev = act('上一页订单', () => { if (page > 1) { page--; load(); } }), next = act('下一页订单', () => { page++; load(); });
      async function load() {
        prev.disabled = true; next.disabled = true; status(message, '正在查询平台订单…');
        try {
          const result = await request(`/api/tools/alibaba/orders?page=${page}&page_size=20`); rows.replaceChildren(); const items = arrayItems(result.data?.orders || result.data);
          for (const item of items) { const row = node('article', undefined, 'card'); row.append(node('h3', `订单 ${item.trade_id || item.id}`), node('p', `创建：${item.create_date?.format_date || '平台未提供'} · 状态：${item.trade_status || item.status || '平台未提供'}`, 'subtle'), act('查询此订单详情', () => showOrder(item.id || item.trade_id))); rows.append(row); }
          if (!items.length) rows.append(node('p', '本次平台查询未返回订单；未据此推断成交或经营表现。', 'empty'));
          const pagination = result.pagination || {}; pageLabel.textContent = `第 ${page} 页 · 本页 ${items.length} 条`; prev.disabled = page <= 1; next.disabled = pagination.hasMore === false || items.length < 20; status(message, `平台订单读取完成 · ${prettyDate(result.source?.collectedAt || result.source?.attemptedAt)}`, 'success');
        } catch (error) { rows.replaceChildren(); status(message, error.message, 'error'); prev.disabled = page <= 1; }
      }
      async function showOrder(id) {
        status(message, '正在读取所选订单…');
        try { const result = await request(`/api/tools/alibaba/order?order_id=${encodeURIComponent(id)}`), item = result.data?.order || result.data; detail.replaceChildren(node('h3', `订单 ${item.trade_id || item.id}`)); const dl = node('dl'); for (const [label, value] of [['订单 ID', item.id], ['交易 ID', item.trade_id], ['创建时间', item.create_date?.format_date], ['修改时间', item.modify_date?.format_date], ['平台状态', item.trade_status || item.status]]) dl.append(node('dt', label), node('dd', value === undefined || value === null ? '平台未提供' : String(value))); detail.append(dl, node('p', '仅显示本次接口实际返回字段；未返回买家、金额、交货等信息时不作补填。', 'subtle')); status(message, `订单详情读取完成 · ${prettyDate(result.source?.collectedAt || result.source?.attemptedAt)}`, 'success'); } catch (error) { status(message, error.message, 'error'); }
      }
      orders.append(node('h2', '平台订单查询'), toolbar(act('重读订单', load), prev, pageLabel, next), message, rows, detail); ar.customerBody.append(orders); load();
    }
  }
  async function renderMetrics() {
    ar.body.append(node('h2', '经营数据'), node('p', '此入口读取本地已有经营复核档案，展示该档案的日期和统计窗；不会冒充即时平台经营报表。', 'module-notice')); const body = node('div'); ar.body.append(toolbar(act('重读本地经营档案', () => fetchMetrics(body))), body); await fetchMetrics(body);
  }
  async function fetchMetrics(body) {
    status(ar.message, '正在读取有日期的经营档案…');
    try { const result = await request('/api/channel-metrics/alibaba'); if (a.tab !== 'metrics') return; body.replaceChildren(); const info = node('div', undefined, 'card'); info.append(node('p', `来源：${result.source || '未提供'}`), node('p', `档案日期：${prettyDate(result.observed_at)} · 统计窗：${typeof result.period === 'string' ? result.period : result.period ? JSON.stringify(result.period) : '未提供'} · 时区：${result.timezone || '未提供'}`)); body.append(info); const grid = node('div', undefined, 'metric-grid'); for (const [key, label] of [['search_impressions', '搜索曝光'], ['search_clicks', '搜索点击'], ['visitors', '访客'], ['inquiries', '询盘'], ['tm_buyers', 'TM 买家'], ['marketing_clicks', '营销点击']]) { const card = node('div', undefined, 'card'); const value = result.metrics?.[key]; card.append(node('span', label, 'subtle'), node('strong', value === undefined || value === null ? '未取得' : String(value))); grid.append(card); } body.append(grid); for (const warning of result.warnings || []) body.append(node('p', String(warning), 'module-notice')); status(ar.message, '历史经营档案已读取。', 'success'); } catch (error) { status(ar.message, error.message, 'error'); body.replaceChildren(node('p', '没有取得可展示的经营数据，未用 0 代替。', 'empty')); }
  }
  window.WorkbenchModules = { show(view) { if (view === 'video') initVideo(); if (view === 'alibaba') initAlibaba(); } };
  window.addEventListener('beforeunload', event => { if (c.dirty) { event.preventDefault(); event.returnValue = ''; } });
})();
