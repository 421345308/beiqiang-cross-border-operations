import https from 'node:https';
import {mkdir, readFile, rename, writeFile} from 'node:fs/promises';
import {dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';

const ORIGIN = 'https://v2-dd.chengji-inc.com';
const DEFAULT_SESSION_PATH = fileURLToPath(new URL('./.local/session.json', import.meta.url));
const ENDPOINTS = Object.freeze({
  importFiles: {method: 'POST', path: '/api/v2/move/import/getImportFileList'},
  categories: {method: 'GET', path: '/api/v2/product/batch/getProductCateTree'},
  categoryInfo: {method: 'POST', path: '/api/v2/product/create_product/getCreateBaseInfoByCateId'},
  freightTemplates: {method: 'POST', path: '/api/v2/product/create_product/getFreightTemplateList'},
  recommendCategory: {method: 'POST', path: '/api/v2/product/create_product/getRecommendCategory'},
  productBase: {method: 'POST', path: '/api/v2/product/product/getProductBaseEditInfo'},
  productSku: {method: 'POST', path: '/api/v2/product/product/getProductSkuEditInfo'},
  productAudit: {method: 'POST', path: '/api/v2/product/product/getProductAuditList'},
  sizeTemplateInfo: {method: 'POST', path: '/api/v2/product/product/getSizeTemplateInfo'},
  products: {method: 'POST', path: '/api/v2/product/product/searchProductList'},
  sizeTemplateInit: {method: 'POST', path: '/api/v2/move/size_temp/getSizeTempInitData'},
  uploadImage: {method: 'POST', path: '/api/v2/move/batch/uploadImage'},
  saveSizeTemplate: {method: 'POST', path: '/api/v2/move/size_temp/saveSizeTemp'},
  createProduct: {method: 'POST', path: '/api/v2/product/create_product/createProduct'},
  saveProduct: {method: 'POST', path: '/api/v2/product/product/saveEditProductInfo'},
  productStatus: {method: 'POST', path: '/api/v2/product/product/batchProcessProduct'},
});

function encodeForm(params) {
  const out = new URLSearchParams();
  const append = (value, key) => {
    if (value === undefined) return;
    if (value !== null && typeof value === 'object') {
      for (const [child, item] of Object.entries(value)) append(item, key ? `${key}[${child}]` : child);
    } else out.append(key, value === null ? '' : String(value));
  };
  append(params, '');
  return Buffer.from(out.toString());
}

export class MiaoshouError extends Error {
  constructor(message, code, httpStatus) {
    super(message);
    this.name = 'MiaoshouError';
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

// Use the user's existing, authorized session. Persistence is explicit and local.
// Only fixed, observed business endpoints are exposed. There is no automatic login.
export class MiaoshouHttp {
  #cookie;
  constructor({cookie, timeoutMs = 15000} = {}) {
    if (!cookie || /[\r\n]/.test(cookie)) throw new Error('A valid Miaoshou cookie is required');
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new Error('Invalid timeoutMs');
    this.#cookie = cookie;
    this.timeoutMs = timeoutMs;
  }

  clearSession() { this.#cookie = ''; }

  static async fromSavedSession({sessionPath = DEFAULT_SESSION_PATH, ...options} = {}) {
    const saved = JSON.parse(await readFile(sessionPath, 'utf8'));
    if (saved.schemaVersion !== 1 || saved.origin !== ORIGIN) throw new Error('Unrecognized saved Miaoshou session');
    return new MiaoshouHttp({...options, cookie: saved.cookie});
  }

  async saveSession({sessionPath = DEFAULT_SESSION_PATH} = {}) {
    if (!this.#cookie) throw new Error('Session cleared');
    await mkdir(dirname(sessionPath), {recursive: true});
    const savedAt = new Date().toISOString();
    const tempPath = `${sessionPath}.${randomUUID()}.tmp`;
    await writeFile(tempPath, JSON.stringify({schemaVersion: 1, origin: ORIGIN, savedAt, cookie: this.#cookie}) + '\n', {mode: 0o600});
    await rename(tempPath, sessionPath);
    return {sessionPath, savedAt};
  }

  async #request(endpoint, params = {}, multipart = null) {
    if (!this.#cookie) throw new Error('Session cleared');
    const {path, method} = ENDPOINTS[endpoint];
    const body = multipart?.body ?? (method === 'POST' ? encodeForm(params) : Buffer.alloc(0));
    return await new Promise((resolve, reject) => {
      const request = https.request(new URL(path, ORIGIN), {
        method,
        headers: {
          Accept: 'application/json',
          Cookie: this.#cookie,
          ...(body.length ? {'Content-Type': multipart?.type ?? 'application/x-www-form-urlencoded', 'Content-Length': body.length} : {}),
        },
      }, response => {
        const chunks = [];
        let size = 0;
        response.on('data', chunk => {
          size += chunk.length;
          if (size > 16 * 1024 * 1024) request.destroy(new Error('Response exceeds size limit'));
          else chunks.push(chunk);
        });
        response.on('error', reject);
        response.on('end', () => {
          const status = response.statusCode;
          if (status !== 200) return reject(new MiaoshouError(`HTTP ${status}`, 'http_error', status));
          let result;
          try { result = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
          catch { return reject(new MiaoshouError('Expected JSON; login or platform check may be required', 'non_json', status)); }
          if (result.result !== 'success') {
            const code = String(result.code ?? 'unknown');
            const message = code === '50001' ? 'Miaoshou session expired; renew through the normal login flow' : `Miaoshou request failed (${code}): ${result.reason || ''}`;
            const error = new MiaoshouError(message, code, status);
            error.receipt = result;
            return reject(error);
          }
          resolve(result);
        });
      });
      request.setTimeout(this.timeoutMs, () => request.destroy(new Error('Request timeout')));
      request.on('error', reject);
      request.end(body);
    });
  }

  async listImportFiles({pageNo = 1, pageSize = 10} = {}) {
    if (!Number.isInteger(pageNo) || pageNo < 1) throw new Error('Invalid pageNo');
    // 10 is the size observed in the actual browser request; no larger limit is assumed.
    if (pageSize !== 10) throw new Error('Only the verified pageSize 10 is supported');
    const result = await this.#request('importFiles', {pageNo, pageSize});
    if (!Array.isArray(result.data?.importTaskList) || !Number.isInteger(result.data?.importTaskTotal)) {
      throw new MiaoshouError('Import file response schema changed', 'schema_changed', 200);
    }
    return result.data;
  }

  async getCategories() {
    const result = await this.#request('categories');
    if (!result.productCateTree || typeof result.productCateTree !== 'object' || Array.isArray(result.productCateTree) || !Array.isArray(result.recentCategoryList)) {
      throw new MiaoshouError('Category response schema changed', 'schema_changed', 200);
    }
    return {productCateTree: result.productCateTree, recentCategoryList: result.recentCategoryList};
  }

  async getCategoryInfo(cateId) {
    if (!/^\d+$/.test(String(cateId))) throw new Error('Invalid cateId');
    // useGetCidInfo-cf7156fe.js passes exactly {cateId}; no fabricated fields.
    return await this.#request('categoryInfo', {cateId: String(cateId)});
  }

  async getFreightTemplates() {
    // refresh=0 reads existing settings without asking the provider to refresh them.
    return await this.#request('freightTemplates', {refresh: 0});
  }

  async recommendCategory({name, mainImgUrls}) {
    if (!name || !Array.isArray(mainImgUrls) || !mainImgUrls.length || mainImgUrls.some(x => typeof x !== 'string')) throw new Error('Title and image URL strings are required');
    return await this.#request('recommendCategory', {name, mainImgUrls});
  }

  async getProductBase(productId) {
    if (!/^\d+$/.test(String(productId))) throw new Error('Invalid productId');
    return await this.#request('productBase', {productId: String(productId)});
  }

  async getProductSku(productId) {
    if (!/^\d+$/.test(String(productId))) throw new Error('Invalid productId');
    return await this.#request('productSku', {productId: String(productId)});
  }

  async listProducts({page = 1, pageSize = 100, isDraft} = {}) {
    if (!Number.isInteger(page) || page < 1 || ![20, 40, 50, 100, 200, 500, 1000].includes(pageSize)) throw new Error('Invalid observed pagination');
    return await this.#request('products', {page, pageNo: page, pageSize, isLoadVideoInfo: 1, ...(isDraft === undefined ? {} : {isDraft: isDraft ? 1 : 0})});
  }

  async getProductAudit(productId) {
    if (!/^\d+$/.test(String(productId))) throw new Error('Invalid productId');
    return await this.#request('productAudit', {productId: String(productId)});
  }

  async getSizeTemplateInfo(sizeInfoTemplateId) {
    if (!/^\d+$/.test(String(sizeInfoTemplateId))) throw new Error('Invalid sizeInfoTemplateId');
    // Observed index-3798b1c7.js calls exactly {sizeInfoTemplateId}.
    return await this.#request('sizeTemplateInfo', {sizeInfoTemplateId: String(sizeInfoTemplateId)});
  }

  async getSizeTemplateInit(cateId) {
    if (!/^\d+$/.test(String(cateId))) throw new Error('Invalid cateId');
    return await this.#request('sizeTemplateInit', {subType: 'shoes', cateId: String(cateId)});
  }

  async uploadImage(filePath) {
    const bytes = await readFile(filePath);
    const isJpeg = bytes[0] === 0xff && bytes[1] === 0xd8;
    const isPng = bytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]));
    if ((!isJpeg && !isPng) || !bytes.length || bytes.length > 10 * 1024 * 1024) throw new Error('Expected JPEG/PNG up to 10 MB');
    const boundary = `----Beiqiang${randomUUID()}`;
    const type = isJpeg ? 'image/jpeg' : 'image/png';
    const ext = isJpeg ? 'jpg' : 'png';
    const body = Buffer.concat([
      Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="uploadWarePreviewImg"; filename="product.${ext}"\r\nContent-Type: ${type}\r\n\r\n`), bytes,
      Buffer.from(`\r\n--${boundary}\r\nContent-Disposition: form-data; name="uploadType"\r\n\r\nlocalImg\r\n--${boundary}\r\nContent-Disposition: form-data; name="enableUploadMultiple"\r\n\r\nfalse\r\n--${boundary}--\r\n`),
    ]);
    return await this.#request('uploadImage', {}, {body, type: `multipart/form-data; boundary=${boundary}`});
  }

  async #recordWrite(endpoint, payload, evidenceDir) {
    if (!evidenceDir) throw new Error('A new private evidence directory is required for each reviewed write');
    await mkdir(evidenceDir, {recursive: true});
    // Exclusive creation also blocks an unknown-result retry after a timeout or crash.
    await writeFile(`${evidenceDir}/request.json`, JSON.stringify(payload, null, 2) + '\n', {flag: 'wx', mode: 0o600});
    await writeFile(`${evidenceDir}/attempt.json`, JSON.stringify({endpoint, startedAt: new Date().toISOString(), state: 'STARTED_DO_NOT_AUTO_RETRY'}) + '\n', {flag: 'wx', mode: 0o600});
    try {
      const result = await this.#request(endpoint, payload);
      await writeFile(`${evidenceDir}/response.json`, JSON.stringify(result, null, 2) + '\n', {flag: 'wx', mode: 0o600});
      return result;
    } catch (error) {
      await writeFile(`${evidenceDir}/failure.json`, JSON.stringify({code: error.code, message: error.message, receipt: error.receipt, resultUnknown: !error.receipt}, null, 2) + '\n', {flag: 'wx', mode: 0o600});
      throw error;
    }
  }

  async saveSizeTemplate(payload, {evidenceDir} = {}) {
    if (!payload?.specMap || !payload?.fixedSizeName || payload.sizeTempSubType !== 'shoes') throw new Error('A reviewed shoe size template is required');
    if (payload.templateId) throw new Error('This method only creates a separate template; existing shared templates are not overwritten');
    return await this.#recordWrite('saveSizeTemplate', payload, evidenceDir);
  }

  async createProduct(payload, {evidenceDir} = {}) {
    if (![0, 1].includes(payload?.commit) || ![0, 1, 2].includes(payload?.status)) throw new Error('Explicit commit/status required');
    if (!payload?.title || !payload?.cateId || !payload?.categoryRecommendId || !payload?.categoryRecommendCheckStr) throw new Error('Reviewed fields and current recommendation are required');
    if (!Array.isArray(payload?.specPricesV2) || !payload.specPricesV2.length || payload.specPricesV2.some(s => !(s.price > 0) || !Number.isInteger(s.stockNum) || s.stockNum < 0)) throw new Error('Invalid yuan prices or stock');
    // Individual skuPictureUrl is a separate material-centre field, not a temp upload URL.
    if (payload.specPricesV2.some(s => s.skuPictureUrl)) throw new Error('Individual SKU material images are not yet verified; use the verified colour specPic flow');
    return await this.#recordWrite('createProduct', payload, evidenceDir);
  }

  async saveProduct(payload, {evidenceDir} = {}) {
    if (!/^\d+$/.test(String(payload?.productId)) || !Array.isArray(payload?.changeFields) || !payload.changeFields.length) throw new Error('Reviewed productId and changeFields are required');
    if (payload.changeFields.some(x => !['base', 'sku', 'mainImg', 'descImg', 'mainImgVideo', 'quality', 'title'].includes(x))) throw new Error('Unknown edit field group');
    return await this.#recordWrite('saveProduct', {productInfo: JSON.stringify(payload)}, evidenceDir);
  }

  async setProductStatus(productIds, status, {evidenceDir} = {}) {
    if (!Array.isArray(productIds) || !productIds.length || productIds.length > 100 || productIds.some(x => typeof x !== 'string' || !/^\d+$/.test(x)) || ![0, 1].includes(status)) throw new Error('Reviewed string IDs and explicit status 0/1 are required');
    return await this.#recordWrite('productStatus', {productIds, batchTypeValue: status, batchType: 'status', isDraft: 0}, evidenceDir);
  }
}
