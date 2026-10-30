import {test} from 'node:test';
import assert from 'node:assert/strict';
import {MiaoshouConnector} from './index.mjs';
import {resolve} from 'node:path';

const secret = 'DO_NOT_RETURN_SESSION_SECRET';
function fixture(overrides = {}) {
  const calls = [];
  const client = {
    async getShopIdentity() { calls.push('identity'); return {shopId:'123', shopName: secret, shopToken: secret}; },
    async listProducts(args) { calls.push(args); return {total:21, productList: Array.from({length: args.page === 1 ? 20 : 1}, (_,i) => ({productIdStr:String((args.page-1)*20+i+1), name:'shoe', cookie:secret, mobile:secret}))}; },
    async getProductBase() { return {productInfo:{productIdStr:'1', name:'shoe', mobile:secret, address:secret}}; },
    async getProductSku() { return {specPricesV2:[{skuId:'9',price:94,stock:100, shopToken:secret, sellProperties:[{propertyName:'鞋码',valueName:'40',phone:secret}]}]}; },
    async getProductAudit() { return {auditList:[{publishStatus:1, publishTime:12,title:'shoe',reason:secret}]}; },
    ...overrides,
  };
  const connector = new MiaoshouConnector({sessionPath:resolve('fake-session-never-read.json'),expectedShopId:'123', clientFactory:async()=>client});
  return {connector,calls};
}
test('capabilities does not load session; writes disabled',async()=>{
  const c = new MiaoshouConnector({clientFactory:()=>{throw Error('must not load');}});
  const r = await c.execute('capabilities'); assert.equal(r.ok,true); assert.ok(r.data.futureWrites.every(x=>!x.enabled));
  assert.equal(r.collectedAt,null); assert.equal(r.attemptedAt,null);
});
test('explicit target required before loading session',async()=>{
  const c = new MiaoshouConnector({clientFactory:()=>{throw Error('must not load');}});
  const r = await c.execute('products'); assert.equal(r.error.code,'invalid_input');
  assert.equal(r.collectedAt,null); assert.equal(r.attemptedAt,null);
});
test('cross-shop prevents product requests',async()=>{
  const {connector,calls} = fixture({getShopIdentity:async()=>({shopId:'999'})});
  const r = await connector.execute('products'); assert.equal(r.error.code,'shop_mismatch'); assert.equal(calls.length,0); assert.equal(r.data,undefined);
});
test('pagination retains total and next page; no hidden all-page scan',async()=>{
  const {connector,calls} = fixture();
  const a = await connector.execute('products',{page:1,pageSize:20,isDraft:false});
  assert.equal(a.pagination.nextPage,2); assert.equal(a.data.items.length,20);
  const b = await connector.execute('products',{page:2,pageSize:20});
  assert.equal(b.pagination.total,21); assert.equal(b.pagination.hasMore,false);
  assert.equal(calls.filter(x=>typeof x==='object').length,2);
  assert.ok(!JSON.stringify([a,b]).includes(secret));
});
test('detail plus SKU plus audit projects only business fields',async()=>{
  const {connector} = fixture(); const r = await connector.execute('product',{productId:'1'});
  assert.equal(r.ok,true); assert.equal(r.data.skus[0].price,94); assert.equal(r.data.audits[0].publishStatus,1);
  assert.ok(!JSON.stringify(r).includes(secret)); assert.ok(r.collectedAt);
});
test('expired and arbitrary errors never expose receipts or messages',async()=>{
  for (const code of ['50001','ENOTFOUND',secret]) {
    const {connector} = fixture({getShopIdentity:async()=>{throw Object.assign(Error(secret),{code,receipt:{cookie:secret}});}});
    const r = await connector.execute('connection-check'); assert.equal(r.ok,false); assert.equal(r.error.connectionIssue,true); assert.ok(!JSON.stringify(r).includes(secret));
    assert.equal(r.collectedAt,null); assert.ok(r.attemptedAt);
  }
});
test('SKU IDs preserve precise strings, normalize safe integers and reject unsafe numbers',async()=>{
  for (const [row, expected] of [[{skuIdStr:'9007199254740993',skuId:9007199254740992},'9007199254740993'],[{skuId:123},'123'],[{skuId:'9007199254740993'},'9007199254740993']]) {
    const {connector} = fixture({getProductSku:async()=>({specPricesV2:[row]})});
    const r = await connector.execute('product',{productId:'1'});
    assert.equal(r.ok,true); assert.equal(r.data.skus[0].skuId,expected); assert.equal(r.data.skus[0].skuIdStr,undefined);
  }
  const {connector} = fixture({getProductSku:async()=>({specPricesV2:[{skuId:9007199254740992}]})});
  const r = await connector.execute('product',{productId:'1'});
  assert.equal(r.ok,false); assert.equal(r.error.code,'schema_changed'); assert.equal(r.collectedAt,null); assert.equal(r.data,undefined);
});
test('schema failure and imprecise numeric IDs fail closed',async()=>{
  const {connector} = fixture({listProducts:async()=>({total:1,productList:[{productId:9007199254740992}]})});
  assert.equal((await connector.execute('products')).error.code,'schema_changed');
});
test('session changing during read suppresses all data',async()=>{
  let n=0; const {connector} = fixture({getShopIdentity:async()=>({shopId:++n===1?'123':'999'})});
  const r = await connector.execute('products',{pageSize:20}); assert.equal(r.error.code,'shop_mismatch'); assert.equal(r.data,undefined);
});
