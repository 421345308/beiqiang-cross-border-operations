import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const root = new URL('./', import.meta.url);
const manifest = JSON.parse(await readFile(new URL('manifest.json', root), 'utf8'));
test('manifest has fixed origins and no credential or debugging permissions', () => {
  assert.deepEqual(manifest.host_permissions.sort(), ['http://127.0.0.1:8766/*', 'https://v2-dd.chengji-inc.com/*'].sort());
  assert.deepEqual(manifest.permissions.sort(), ['activeTab', 'storage'].sort());
  assert.equal(manifest.externally_connectable, undefined);
});

async function harness(shopIds = ['123', '123']) {
  const calls = [];
  let handler;
  const window = {}; window.top = window;
  const context = {location: {origin: 'https://v2-dd.chengji-inc.com'}, window, URLSearchParams,
    setInterval: () => {},
    chrome: {runtime: {id: 'ext', onMessage: {addListener: fn => handler = fn}}},
    fetch: async (path, options) => {
      calls.push({path, options});
      const identity = path.endsWith('getShopInfo');
      return {ok: true, json: async () => identity ? {result: 'success', shopId: shopIds.shift(), userNick: 'private', shopToken: 'SECRET'} : {result: 'success', total: 1, productList: [{productIdStr: '999', title: 'shoe', secret: 'SECRET'}]}};
    }};
  vm.runInNewContext(await readFile(new URL('content.js', root), 'utf8'), context);
  const send = job => new Promise(resolve => handler({type: 'execute', job}, {id: 'ext'}, resolve));
  return {calls, send};
}
test('projects fields and reads only fixed endpoints', async () => {
  const {calls, send} = await harness();
  const data = await send({operation: 'products', expected_shop_id: '123', params: {page: 1, pageSize: 20}});
  assert.equal(data.items[0].productId, '999');
  assert.equal(data.items[0].title, 'shoe');
  assert.equal(JSON.stringify(data).includes('SECRET'), false);
  assert.deepEqual(calls.map(c => c.path), ['/api/v2/common/overall/getShopInfo', '/api/v2/product/product/searchProductList', '/api/v2/common/overall/getShopInfo']);
  assert.ok(calls.every(c => c.options.method === 'POST' && c.options.credentials === 'same-origin'));
});
test('wrong shop blocks product request and unknown operation blocks every request', async () => {
  const {calls, send} = await harness(['456']);
  assert.equal((await send({operation: 'products', expected_shop_id: '123', params: {page: 1, pageSize: 20}})).error, 'shop_mismatch');
  assert.equal(calls.length, 1);
  assert.equal((await send({operation: 'delete', expected_shop_id: '123', params: {}})).error, 'schema_changed');
  assert.equal(calls.length, 1);
});
test('changed session after product read discards all product data', async () => {
  const {send} = await harness(['123', '456']);
  const data = await send({operation: 'products', expected_shop_id: '123', params: {page: 1, pageSize: 20}});
  assert.equal(data.error, 'shop_mismatch');
  assert.equal(data.items, undefined);
});
