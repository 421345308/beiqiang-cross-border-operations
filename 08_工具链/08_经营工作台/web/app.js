'use strict';
const $ = (id) => document.getElementById(id);
const state = { data: null, run: null, view: 'overview', busy: false, polling: false };
const labels = { queued: '等待启动', running: '正在运行', awaiting_review: '待你审查', accepted: '已采纳', rejected: '未采纳 / 提案保留', failed: '运行失败', cancelled: '已暂停 / 草稿保留', interrupted: '运行中断' };
function el(tag, text, cls) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; }
function notice(message = '') { $('notice').textContent = message; $('notice').hidden = !message; }
async function api(path, body) {
  const options = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workbench-Token': state.data?.csrf_token || '' }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  let data; try { data = await response.json(); } catch { throw new Error('本地服务返回了无法读取的内容，请检查服务后重试。'); }
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : '操作未完成，请稍后重试。');
  return data;
}
function button(text, action, cls) { const node = el('button', text, cls); node.type = 'button'; node.addEventListener('click', action); return node; }
function badge(status) { return el('span', labels[status] || status || '未记录', `badge ${status || ''}`); }
function date(value) { if (!value) return ''; const d = new Date(value); return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('zh-CN', { hour12: false }); }
function eventText(event) { if (typeof event === 'string') return event; if (event.message || event.text || event.content) return String(event.message || event.text || event.content); if (event.item?.text) { if (event.item.type === 'agent_message') { try { return `已生成提案：${JSON.parse(event.item.text).summary}`; } catch {} } return event.item.text; } return { 'thread.started': 'Sol 会话已建立', 'turn.started': '正在阅读资料并处理要求', 'turn.completed': '本轮模型处理完成，正在核验提案', 'turn.failed': '本轮处理失败', 'item.started': '正在处理资料', 'item.completed': '已完成一项处理' }[event.type] || event.type || '执行记录已更新'; }
function empty(target, text) { target.replaceChildren(el('div', text, 'empty')); }
function show(view) { state.view = view; for (const name of ['overview', 'execute', 'history', 'video', 'alibaba']) $(`${name}-view`).hidden = name !== view; document.querySelectorAll('[data-view]').forEach(n => n.classList.toggle('active', n.dataset.view === view)); $('view-label').textContent = { overview: '经营总览', execute: '任务执行', history: '运行记录', video: '视频画布', alibaba: '国际站' }[view]; if (view === 'history') renderHistory(); window.WorkbenchModules?.show(view); }
function sourceLink(label, path) { return button(label || '打开原资料', () => openDocument(path), 'link'); }
async function openDocument(path) { const panel = $('document-panel'); $('document-title').textContent = path || '项目资料'; $('document-content').textContent = '正在读取…'; if (!panel.open) panel.showModal(); try { const data = await api(`/api/document?path=${encodeURIComponent(path)}`); $('document-content').textContent = data.content || '该资料暂无内容。'; } catch (error) { $('document-content').textContent = error.message; } }
function taskContext() { const task = state.data?.tasks?.find(t => String(t.id) === $('task-select').value); $('selected-context').replaceChildren(); if (!task) return; $('selected-context').append(el('div', `当前业务进度：${task.status || '未记录'}`), el('div', `下一步：${task.next || '请结合原资料明确'}`)); if (task.source) $('selected-context').append(sourceLink('查看原项目', task.source)); }
function renderTasks() {
  const tasks = state.data.tasks || []; $('tasks').replaceChildren(); const selected = $('task-select').value; $('task-select').replaceChildren();
  for (const task of tasks) {
    const option = el('option', task.title); option.value = task.id; $('task-select').append(option);
    const card = el('article', undefined, 'card task-card'); const head = el('div', undefined, 'card-heading'); head.append(el('span', task.owner || '业务原档案', 'eyebrow'), el('span', task.status || '未记录', 'badge')); card.append(head, el('h3', task.title));
    const details = el('dl', undefined, 'task-detail'); for (const [label, value] of [['当前结果', task.result], ['下一步', task.next], ['依赖', task.dependency]]) { if (value) details.append(el('dt', label), el('dd', value)); } card.append(details);
    const bottom = el('div', undefined, 'task-bottom'); const links = el('div', undefined, 'links'); if (task.source) links.append(sourceLink('原项目', task.source)); for (const evidence of task.evidence || []) if (evidence.path) links.append(sourceLink(evidence.label || '成果资料', evidence.path)); bottom.append(links, button('推进任务 →', () => { $('task-select').value = task.id; taskContext(); show('execute'); $('instruction').focus(); })); card.append(bottom); $('tasks').append(card);
  }
  if (tasks.some(t => String(t.id) === selected)) $('task-select').value = selected;
  if (!tasks.length) empty($('tasks'), '原项目尚未提供可执行任务。刷新资料后再试。');
  $('start').disabled = state.busy || !tasks.length; taskContext();
}
function renderHistory() { const target = $('history'); target.replaceChildren(); const runs = state.data?.runs || []; if (!runs.length) return empty(target, '还没有运行记录。选择一项业务任务，开始第一次推进。'); for (const run of [...runs].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))) { const row = el('article', undefined, 'history-row'); const info = el('div'); info.append(el('strong', run.title || run.task_id || '本地任务'), el('p', `${date(run.created_at)} · ${run.model || 'gpt-6.1-sol'}`, 'subtle'), el('p', run.summary || run.instruction || '', 'subtle')); const side = el('div'); side.append(badge(run.status), button('查看运行', () => selectRun(run.id), 'quiet')); row.append(info, side); target.append(row); } }
function renderRun() {
  const run = state.run; $('run-actions').replaceChildren(); if (!run) { $('run-status').textContent = '尚未启动'; $('run-meta').textContent = ''; empty($('run-log'), '选择任务并填写要求后，这里会显示 Sol 的真实执行记录。'); $('review').hidden = true; return; }
  $('run-status').replaceWith(Object.assign(badge(run.status), { id: 'run-status' })); $('run-meta').textContent = `${run.model || 'gpt-6.1-sol'} · ${date(run.created_at)}${run.updated_at ? ` · 最近更新 ${date(run.updated_at)}` : ''}`;
  if (run.usage && typeof run.usage === 'object') { const usage = [['输入', run.usage.input_tokens], ['缓存输入', run.usage.cached_input_tokens], ['输出', run.usage.output_tokens]].filter(([, value]) => Number.isFinite(value)); if (usage.length) $('run-meta').append(el('div', `实际用量：${usage.map(([label, value]) => `${label} ${value.toLocaleString('zh-CN')}`).join(' · ')} tokens`)); }
  const log = $('run-log'); const detailsOpen = log.querySelector('details')?.open || false; const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 35; log.replaceChildren();
  const diagnostics = [];
  for (const event of run.events || []) { if (event.type === 'cli_output') { diagnostics.push(eventText(event)); continue; } const row = el('div', undefined, 'event'); if (event.timestamp || event.at || event.created_at) row.append(el('span', date(event.timestamp || event.at || event.created_at), 'event-time')); row.append(el('span', eventText(event))); log.append(row); }
  if (!log.childNodes.length) log.append(el('div', ['queued', 'running'].includes(run.status) ? '正在等待执行记录…' : '本次没有执行日志。'));
  if (run.error) log.append(el('div', `运行未完成：${String(run.error)}`, 'danger'));
  else if (['failed', 'interrupted'].includes(run.status)) log.append(el('div', '本次运行未完成，请展开运行详情查看原因，或补充要求后继续。', 'danger'));
  if (diagnostics.length || run.error) { const details = el('details', undefined, 'run-details'); details.open = detailsOpen; details.append(el('summary', '运行详情'), el('pre', [...diagnostics, ...(run.error ? [`失败原因：${String(run.error)}`] : [])].join('\n'))); log.append(details); }
  if (atBottom) log.scrollTop = log.scrollHeight;
  if (['queued', 'running'].includes(run.status)) $('run-actions').append(button('暂停运行', () => mutateRun('cancel', {})));
  const reviewKey = JSON.stringify([run.id, run.status, run.result, run.changes, run.summary]);
  if ($('review').dataset.key !== reviewKey) { renderReview(); $('review').dataset.key = reviewKey; }
}
function renderReview() {
  const run = state.run, target = $('review'); target.replaceChildren(); const result = run.result || {}; const changes = result.changes || run.changes || []; const reviewable = ['awaiting_review', 'rejected', 'cancelled', 'failed', 'interrupted'].includes(run.status);
  target.hidden = !reviewable && run.status !== 'accepted'; if (target.hidden) return;
  target.append(el('span', run.status === 'accepted' ? (changes.length ? '已回写原项目' : '已采纳分析结果 · 原文未改') : '提案审查 · 采纳前不会回写', 'eyebrow'), el('h2', '这次推进的结果'), el('p', result.summary || run.summary || '尚未形成完整提案，可补充要求后继续。', 'review-summary'));
  for (const change of changes) { const group = el('section', undefined, 'change'); group.append(el('div', change.path || '修订内容', 'change-path')); if (change.path) group.append(sourceLink('查看当前原文', change.path)); if (change.reason) group.append(el('p', change.reason, 'subtle')); const diff = el('div', undefined, 'diff'); for (const [label, text, cls] of [['修改前', change.before, 'before'], ['建议修改后', change.after, 'after']]) { const column = el('div'); column.append(el('div', label, 'diff-label'), el('pre', text ?? '（无内容）', cls)); diff.append(column); } group.append(diff); target.append(group); }
  if (result.next_steps?.length) { target.append(el('h3', '建议下一步')); const list = el('ul'); result.next_steps.forEach(s => list.append(el('li', typeof s === 'string' ? s : JSON.stringify(s)))); target.append(list); }
  if (!reviewable) return;
  const box = el('div', undefined, 'review-instruction'); const label = el('label', '补充要求，继续完善提案'); label.htmlFor = 'revision-instruction'; const input = el('textarea'); input.id = 'revision-instruction'; input.placeholder = '指出需要补充、调整或不采纳的原因…'; box.append(label, input); target.append(box); const actions = el('div', undefined, 'actions');
  if (run.status === 'awaiting_review') actions.append(button(changes.length ? '确认采纳并回写原项目' : '确认采纳分析结果', () => mutateRun('accept', {}), 'primary'));
  actions.append(button('继续完善', () => { const instruction = input.value.trim(); if (!instruction) { notice('请先写下本次继续完善的具体要求。'); input.focus(); return; } mutateRun('resume', { instruction }); }));
  if (run.status === 'awaiting_review') actions.append(button('不采纳，保留草稿', () => mutateRun('reject', {}), 'quiet')); target.append(actions); if (run.status === 'rejected') target.append(el('p', '此提案未采纳，原提案与执行记录已保留，可补充要求继续完善。', 'hint')); if (run.status === 'cancelled') target.append(el('p', '此提案未采纳，草稿与执行记录已保留。', 'hint'));
}
function busy(value) { state.busy = value; $('start').disabled = value || !state.data?.tasks?.length; $('refresh').disabled = value; $('review').querySelectorAll('button').forEach(n => n.disabled = value); $('run-actions').querySelectorAll('button').forEach(n => n.disabled = value); }
async function selectRun(id) { try { notice(); const run = await api(`/api/runs/${encodeURIComponent(id)}`); state.run = run.run || run; show('execute'); renderRun(); } catch (error) { notice(error.message); } }
async function mutateRun(action, body) { if (state.busy || !state.run) return; const runId = state.run.id; busy(true); try { notice(); await api(`/api/runs/${encodeURIComponent(runId)}/${action}`, body); await refreshRuns(); const full = await api(`/api/runs/${encodeURIComponent(runId)}`); state.run = full.run || full; renderRun(); if (action === 'reject') notice('提案未采纳，原文未改，提案与执行记录已保留。'); if (action === 'accept') { notice((state.run.result?.changes || state.run.changes || []).length ? '提案已采纳，原项目已回写。' : '分析结果已采纳，原文未改。'); await bootstrap(false); } } catch (error) { notice(error.message); } finally { busy(false); } }
async function refreshRuns() { const data = await api('/api/runs'); state.data.runs = data.runs || []; if (state.view === 'history') renderHistory(); }
async function bootstrap(first = true) { $('refresh').disabled = true; try { const data = await api('/api/bootstrap'); state.data = data; $('long-term').textContent = data.goals?.long_term || '长期目标尚未读取，请查看原项目资料。'; $('phase').textContent = data.goals?.phase || '当前阶段尚未读取'; $('model').textContent = data.capabilities?.model || 'gpt-6.1-sol'; $('connection').textContent = '本地服务已连接'; renderTasks(); if (first) { const active = (data.runs || []).find(r => ['running', 'queued', 'awaiting_review'].includes(r.status)); if (active) { const full = await api(`/api/runs/${encodeURIComponent(active.id)}`); state.run = full.run || full; } renderRun(); } if (state.view === 'history') renderHistory(); } catch (error) { $('connection').textContent = '本地服务暂不可用'; notice(`${error.message} 可点击“刷新资料”重新连接。`); if (!state.data) empty($('tasks'), '未能读取业务资料。请确认本地工作台服务已启动。'); } finally { $('refresh').disabled = false; } }
document.querySelectorAll('[data-view]').forEach(n => n.addEventListener('click', () => show(n.dataset.view)));
$('task-select').addEventListener('change', taskContext); $('refresh').addEventListener('click', () => { notice(); bootstrap(!state.data); }); $('close-document').addEventListener('click', () => $('document-panel').close());
$('start').addEventListener('click', async () => { const instruction = $('instruction').value.trim(); if (!instruction) { notice('请填写本次具体要求，让 Sol 知道要完成什么。'); $('instruction').focus(); return; } busy(true); try { notice(); const data = await api('/api/runs', { task_id: $('task-select').value, instruction }); state.run = data.run || data; renderRun(); await refreshRuns(); } catch (error) { notice(error.message); } finally { busy(false); } });
async function poll() { if (state.polling || !state.data || state.busy) return; state.polling = true; try { await refreshRuns(); if (state.run) { const data = await api(`/api/runs/${encodeURIComponent(state.run.id)}`); state.run = data.run || data; renderRun(); } $('connection').textContent = '本地服务已连接'; } catch { $('connection').textContent = '连接中断 · 将自动重连'; } finally { state.polling = false; } }
bootstrap(); setInterval(poll, 2500);
