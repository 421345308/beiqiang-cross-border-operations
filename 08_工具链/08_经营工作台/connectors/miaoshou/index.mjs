import {isAbsolute} from 'node:path';
import {MiaoshouHttp} from '../../../01_业务脚本/抖店妙手/miaoshou_http.mjs';

export const capabilities = Object.freeze({connector: 'miaoshou', version: 1, mode: 'read-only',
  operations: ['capabilities', 'connection-check', 'products', 'product'],
  futureWrites: [{operation: 'uploadImage', enabled: false}, {operation: 'createProduct', enabled: false},
    {operation: 'saveProduct', enabled: false}, {operation: 'saveSizeTemplate', enabled: false},
    {operation: 'setProductStatus', enabled: false}],
  coverage: '商品、SKU、审核只读；不含订单、支付、退款、广告或罗盘数据'});

class ConnectorError extends Error { constructor(code) { super(code); this.code = code; } }
const fail = code => { throw new ConnectorError(code); };
const exactId = value => typeof value === 'string' && /^\d+$/.test(value);
const scalar = value => ['string','boolean','number'].includes(typeof value) && (typeof value !== 'number' || Number.isFinite(value));
// Explicit projections: never forward raw platform responses, receipts, account fields or exceptions.
const pick = (row, keys) => Object.fromEntries(keys.filter(k => scalar(row?.[k])).map(k => [k, row[k]]));
function product(row) {
  const id = row?.productIdStr ?? row?.productId;
  if (!exactId(id)) fail('schema_changed');
  return {productId: id, ...pick(row, ['name','title','status','cid','cateId'])};
}
function skuIdentity(row) {
  const value = row?.skuIdStr ?? row?.skuId;
  if (value === undefined) return {};
  if (exactId(value)) return {skuId: value};
  if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0) return {skuId: String(value)};
  fail('schema_changed');
}
function errorInfo(error) {
  const code = String(error?.code ?? '');
  if (code === 'shop_mismatch') return {code, connectionIssue: true, message: '连接店铺与指定目标不符；未采集商品。'};
  if (code === 'invalid_input') return {code, connectionIssue: false, message: '参数无效；须显式指定绝对会话路径及字符串店铺ID。'};
  if (code === 'schema_changed') return {code, connectionIssue: false, message: '平台数据格式变化，未生成不完整结果。'};
  if (code === '50001') return {code: 'session_expired', connectionIssue: true, message: '连接已过期，请通过正常登录续期指定店铺会话。'};
  return {code: 'connection_failed', connectionIssue: true, message: '连接或平台请求失败；请检查指定店铺会话和网络。'};
}

export class MiaoshouConnector {
  constructor({sessionPath, expectedShopId, clientFactory = options => MiaoshouHttp.fromSavedSession(options), now = () => new Date().toISOString()} = {}) {
    this.options = {sessionPath, expectedShopId}; this.clientFactory = clientFactory; this.now = now;
  }
  async execute(operation, input = {}) {
    const envelope = {connector: 'miaoshou', operation, collectedAt: null, attemptedAt: null};
    try {
      if (operation === 'capabilities') return {...envelope, ok: true, data: capabilities};
      if (!capabilities.operations.includes(operation)) fail('invalid_input');
      const {sessionPath, expectedShopId} = this.options;
      if (typeof sessionPath !== 'string' || !isAbsolute(sessionPath) || !exactId(expectedShopId)) fail('invalid_input');
      const {page = 1, pageSize = 100, isDraft} = input;
      if (operation === 'products' && (!Number.isSafeInteger(page) || page < 1 || ![20,40,50,100,200,500,1000].includes(pageSize) || (isDraft !== undefined && typeof isDraft !== 'boolean'))) fail('invalid_input');
      if (operation === 'product' && !exactId(input.productId)) fail('invalid_input');
      envelope.attemptedAt = this.now();
      const client = await this.clientFactory(this.options);
      const verify = async () => {
        const identity = await client.getShopIdentity();
        if (!exactId(identity?.shopId)) fail('schema_changed');
        if (identity.shopId !== expectedShopId) fail('shop_mismatch');
      };
      await verify();
      let data, pagination;
      if (operation === 'connection-check') data = {shopId: expectedShopId, readable: true, writable: false};
      if (operation === 'products') {
        const response = await client.listProducts({page, pageSize, isDraft});
        if (!Array.isArray(response?.productList) || !Number.isSafeInteger(response.total) || response.total < 0 || response.productList.length > pageSize) fail('schema_changed');
        const items = response.productList.map(product);
        if (new Set(items.map(x => x.productId)).size !== items.length || response.total < items.length || (!items.length && (page - 1) * pageSize < response.total)) fail('schema_changed');
        const hasMore = page * pageSize < response.total;
        if (hasMore && items.length !== pageSize) fail('schema_changed');
        data = {shopId: expectedShopId, items};
        pagination = {page, pageSize, total: response.total, returned: items.length, hasMore, nextPage: hasMore ? page + 1 : null, scope: isDraft === undefined ? 'platform-default' : isDraft ? 'drafts' : 'products'};
      }
      if (operation === 'product') {
        const base = await client.getProductBase(input.productId);
        await verify();
        const sku = await client.getProductSku(input.productId);
        await verify();
        const audit = await client.getProductAudit(input.productId);
        const summary = product(base?.productInfo);
        if (summary.productId !== input.productId) fail('schema_changed');
        const rows = sku?.specPricesV2 ?? sku?.specPrices;
        if (!Array.isArray(rows) || !Array.isArray(audit?.auditList)) fail('schema_changed');
        data = {shopId: expectedShopId, product: summary,
          skus: rows.map(row => ({...skuIdentity(row), ...pick(row, ['code','price','stock','stockNum','skuStatus']), sellProperties: Array.isArray(row.sellProperties) ? row.sellProperties.map(p => pick(p, ['propertyName','valueName','oriValueName'])) : []})),
          audits: audit.auditList.map(row => pick(row, ['publishTime','publishStatus','title'])),
          priceUnit: 'yuan', stockMeaning: '平台填报库存，不代表实物盘点'};
      }
      // Catch a session identity change during a multi-request read before returning any data.
      await verify();
      return {...envelope, collectedAt: this.now(), ok: true, data, ...(pagination ? {pagination} : {})};
    } catch (error) { return {...envelope, ok: false, error: errorInfo(error)}; }
  }
}
