'use strict';

// The workbench passes its own DOM helpers; this page only reads the local API.
window.renderSupplierIndex = async function ({ page, current, api, goObject, setRefresh, el, button, link, heading, empty }) {
  page.replaceChildren(heading('产品与供应', '寻找合作厂家', '按鞋款、工艺与证据筛选合作线索，实际接单与供货条件仍需逐款确认。'));
  page.append(button('← 返回产品', () => { location.hash = '/products'; }, 'quiet'));
  const form = el('div', undefined, 'search-bar');
  const input = (label, placeholder) => { const item = el('input', undefined, 'search-input'); item.type = 'search'; item.placeholder = placeholder; item.setAttribute('aria-label', label); form.append(item); return item; };
  const query = input('搜索厂家或型号', '厂家、型号或关键词');
  const product = input('筛选品类', '品类或鞋型');
  const process = input('筛选工艺', '工艺');
  const select = (label, all) => { const item = el('select'); item.setAttribute('aria-label', label); const option = el('option', all); option.value = ''; item.append(option); form.append(item); return item; };
  const city = select('筛选所在地', '全部所在地'), identity = select('筛选厂家身份', '全部身份状态'), custom = select('筛选定制证据', '全部定制证据');
  const count = el('span', '', 'search-count'), list = el('div', undefined, 'row-list'); form.append(count); page.append(form, list);
  const kindLabels = { SUPPLIER_PRODUCT_PAGE:'供应商商品页', SUPPLIER_SELF_CLAIM:'供应商自述', OWNER_REPORTED:'负责人经历', INDEPENDENT_PUBLIC:'独立公开资料', WORKSPACE_RECORD:'工作区记录' };
  const statusLabels = { SELF_CLAIMED_FACTORY:'供应商自述为工厂', SELF_CLAIMED_FACTORY_AND_AGENT:'供应商自述有工厂并代理', UNVERIFIED:'未核实', UNKNOWN:'未知', OWNER_REPORTED_SINGLE_CASE:'负责人曾就一例沟通', PRODUCT_PAGE_SELF_CLAIM:'商品页自述', SUPPLIER_SELF_CLAIM:'供应商自述' };

  function evidenceBlock(items) {
    if (!items?.length) return null;
    const group = el('details'); group.append(el('summary', '查看依据'));
    for (const item of items) {
      const row = el('p'), kind = kindLabels[item.kind] || item.kind || '未知';
      row.append(el('strong', kind), el('span', [item.observed_on, item.summary].filter(Boolean).join(' · ') ? ` · ${[item.observed_on, item.summary].filter(Boolean).join(' · ')}` : ''));
      if (item.path) row.append(el('span', ` · 记录：${item.path}`));
      const source = link(' 查看来源 ↗', item.url); if (source) row.append(source);
      group.append(row);
    }
    return group;
  }
  function addClaim(card, title, claim) {
    const status = claim?.status || '未知';
    card.append(el('p', `${title}：${statusLabels[status] || status}${claim?.summary ? ` · ${claim.summary}` : ''}`));
    const evidence = evidenceBlock(claim?.evidence); if (evidence) card.append(evidence);
  }
  function addDirections(card, title, claims) {
    if (!claims?.length) return;
    card.append(el('h4', title));
    for (const claim of claims) {
      const row = el('p', [claim.name, claim.scope].filter(Boolean).join(' · ') || '资料未注明');
      if (title === '产品方向') {
        const urls = [...new Set((claim.evidence || []).filter(item => item.kind === 'SUPPLIER_PRODUCT_PAGE' && item.url).map(item => item.url))];
        urls.forEach((url, index) => { const source = link(` 查看来源商品${urls.length > 1 ? ` ${index + 1}` : ''} ↗`, url); if (source) row.append(source); });
      }
      card.append(row);
      const evidence = evidenceBlock(claim.evidence); if (evidence) card.append(evidence);
    }
  }
  function sourceRow(item, unassociated = false) {
    const row = el('div', undefined, 'supplier-source-row');
    const source = link(item.model || '未标注型号', item.url);
    row.append(source || el('span', item.model || '未标注型号'));
    if (unassociated && item.supplier_label) row.append(el('span', ` · 来源文字：${item.supplier_label}`));
    if (item.observed_at) row.append(el('span', ` · 记录时间：${item.observed_at}`));
    const roles = { adopted: '产品档案采用指向', candidate: '候选来源', reference: '历史/参考来源' };
    for (const related of item.products || []) {
      const line = el('p', `${roles[related.role] || '来源关系'}：`), label = related.current_model || related.id;
      if (related.id) line.append(button(label, () => goObject(`product:${related.id}`), 'quiet')); else line.append(el('span', '产品未标注'));
      if (related.category_clues?.length) line.append(el('span', ` · 产品分类线索：${related.category_clues.join('、')}`));
      if (related.source_state) line.append(el('span', ` · 档案状态：${related.source_state}`));
      row.append(line);
    }
    if (!item.products?.length) row.append(el('p', '来源款线索，尚未关联产品档案。', 'muted'));
    return row;
  }
  function drawSupplier(row) {
    const card = el('article', undefined, 'card');
    card.append(el('h3', row.names?.[0] || '未命名供应商'));
    if (row.names?.length > 1) card.append(el('p', `其他名称：${row.names.slice(1).join('、')}`, 'muted'));
    const shop = link('查看来源店铺 ↗', row.shop_url); if (shop) card.append(shop);
    const profile = row.profile || {};
    if (!row.has_profile) card.append(el('p', '目前仅有商品来源线索，未据此认定厂家身份或能力。', 'muted'));
    addDirections(card, '产品方向', profile.product_directions);
    addDirections(card, '工艺方向', profile.process_directions);
    addClaim(card, '厂家身份', profile.factory_identity);
    addClaim(card, '定制情况', profile.customization);
    const loc = profile.location || {};
    card.append(el('p', `所在地：${[loc.city, loc.type, loc.summary].filter(Boolean).join(' · ') || '未知'}`));
    const locationEvidence = evidenceBlock(loc.evidence); if (locationEvidence) card.append(locationEvidence);
    for (const interaction of profile.owner_interactions || []) {
      if (interaction.summary) card.append(el('p', `负责人经历：${interaction.summary}`));
      const ev = evidenceBlock(interaction.evidence); if (ev) card.append(ev);
    }
    if (profile.open_questions?.length) card.append(el('p', `沟通时确认：${profile.open_questions.join('；')}`));
    const sources = el('details'); sources.append(el('summary', `来源款线索（${(row.sources || []).length}）`));
    sources.append(el('p', '历史页面与产品关联仅供追溯，不代表当前库存或可供条件。', 'muted'));
    for (const item of row.sources || []) sources.append(sourceRow(item));
    card.append(sources); return card;
  }
  function fillOptions(node, values, all, labels = {}) {
    const selected = node.value; node.replaceChildren(); const first = el('option', all); first.value = ''; node.append(first);
    for (const value of values || []) { const option = el('option', labels[value] || value); option.value = value; node.append(option); }
    node.value = selected;
  }
  let timer, sequence = 0;
  function invalidate() {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
    sequence += 1;
    count.textContent = '正在查找…';
    list.replaceChildren();
  }
  async function find() {
    if (!current()) return;
    const request = ++sequence, params = new URLSearchParams();
    for (const [key, value] of [['q',query.value], ['product',product.value], ['process',process.value], ['city',city.value], ['identity',identity.value], ['customization_evidence',custom.value]]) if (value.trim()) params.set(key, value.trim());
    count.textContent = '正在查找…';
    try {
      const result = await api(`/api/desk/suppliers?${params}`); if (request !== sequence || !current()) return;
      fillOptions(city, result.options?.cities, '全部所在地');
      fillOptions(identity, result.options?.identities, '全部身份状态', statusLabels);
      fillOptions(custom, result.options?.customization_evidence, '全部定制证据', kindLabels);
      list.replaceChildren(); count.textContent = `${result.suppliers.length} 个供应商`;
      for (const row of result.suppliers) list.append(drawSupplier(row));
      if (result.unassociated_sources?.length) {
        const card = el('article', undefined, 'card');
        card.append(el('h3', '尚未关联供应商的来源款'), el('p', '这些历史来源未归到供应商档案，不推测厂家或当前供货。', 'muted'));
        for (const item of result.unassociated_sources) card.append(sourceRow(item, true));
        list.append(card);
      }
      if (!result.suppliers.length && !result.unassociated_sources?.length) empty(list, '没有找到匹配线索，可尝试其他鞋型、型号或放宽筛选。');
    } catch (error) {
      if (request === sequence && current()) {
        const notice = error.status === 404 ? '当前工作台服务版本尚未更新，厂家查询暂不可用。请等待当前工作结束后重启工作台服务。' : error.message;
        count.textContent = ''; list.replaceChildren(el('div', notice, 'empty'));
      }
    }
  }
  function findNow() {
    if (!current()) return;
    invalidate();
    return find();
  }
  for (const field of [query, product, process]) field.addEventListener('input', () => {
    if (!current()) return;
    invalidate();
    timer = setTimeout(() => { timer = undefined; find(); }, 250);
  });
  for (const field of [city, identity, custom]) field.addEventListener('change', findNow);
  setRefresh(findNow); await find();
};
