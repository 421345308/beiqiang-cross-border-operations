// Runs only on the vendor origin. Never reads browser credentials or returns raw responses.
(() => {
  'use strict';
  if (location.origin !== 'https://v2-dd.chengji-inc.com' || window !== window.top) return;
  const validId = value => typeof value === 'string' && /^[0-9]{1,40}$/.test(value);
  const id = value => validId(value) ? value : (Number.isSafeInteger(value) && value >= 0 ? String(value) : null);
  const fail = code => { throw new Error(code); };
  async function request(path, body) {
    const response = await fetch(path, {method: 'POST', credentials: 'same-origin', headers: {Accept: 'application/json', ...(body ? {'Content-Type': 'application/x-www-form-urlencoded'} : {})}, ...(body ? {body} : {})});
    if (!response.ok) fail('request_failed');
    const data = await response.json();
    if (data?.result !== 'success') fail(String(data?.code) === '50001' ? 'session_expired' : 'request_failed');
    return data;
  }
  async function identity() {
    const data = await request('/api/v2/common/overall/getShopInfo');
    const shopId = id(data.shopId);
    if (!shopId || typeof data.userNick !== 'string' || !data.userNick) fail('schema_changed');
    return shopId;
  }
  async function execute(job) {
    try {
      if (!job || !['connection-check', 'products'].includes(job.operation) || !validId(job.expected_shop_id)) fail('schema_changed');
      const params = job.params;
      if (!params || typeof params !== 'object' || Array.isArray(params)) fail('schema_changed');
      const before = await identity();
      if (before !== job.expected_shop_id) fail('shop_mismatch');
      let output = {};
      if (job.operation === 'products') {
        const {page, pageSize, isDraft} = params;
        if (!Number.isSafeInteger(page) || page < 1 || ![20, 40, 50, 100, 200, 500, 1000].includes(pageSize) || (isDraft !== undefined && typeof isDraft !== 'boolean') || Object.keys(params).some(k => !['page','pageSize','isDraft'].includes(k))) fail('schema_changed');
        const form = new URLSearchParams({page: String(page), pageNo: String(page), pageSize: String(pageSize), isLoadVideoInfo: '1'});
        if (isDraft !== undefined) form.set('isDraft', isDraft ? '1' : '0');
        const data = await request('/api/v2/product/product/searchProductList', form);
        if (!Array.isArray(data.productList) || !Number.isSafeInteger(data.total) || data.total < 0 || data.productList.length > pageSize) fail('schema_changed');
        const items = data.productList.map(row => {
          const productId = row?.productIdStr ?? row?.productId;
          if (!validId(productId)) fail('schema_changed');
          const item = {productId};
          for (const key of ['name', 'title', 'status', 'cid', 'cateId']) {
            const value = row[key];
            if ((typeof value === 'string' && value.length <= 500) || typeof value === 'boolean' || Number.isSafeInteger(value)) item[key] = value;
          }
          return item;
        });
        output = {items, total: data.total};
      } else if (Object.keys(params).length) fail('schema_changed');
      const after = await identity();
      if (before !== after || after !== job.expected_shop_id) fail('shop_mismatch');
      return {shop_id_before: before, shop_id_after: after, ...output};
    } catch (error) {
      const code = ['session_expired', 'shop_mismatch', 'schema_changed', 'request_failed'].includes(error?.message) ? error.message : 'request_failed';
      return {error: code};
    }
  }
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (sender.id !== chrome.runtime.id) return;
    if (message?.type === 'identity') {
      identity().then(shopId => sendResponse({shopId}), () => sendResponse({error: 'request_failed'}));
      return true;
    }
    if (message?.type === 'execute') {
      execute(message.job).then(sendResponse);
      return true;
    }
  });
  setInterval(() => { chrome.runtime.sendMessage({type: 'tick'}).catch(() => {}); }, 3000);
})();
