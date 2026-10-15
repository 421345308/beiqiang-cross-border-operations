import https from 'node:https';
import {mkdir, readFile, rename, writeFile} from 'node:fs/promises';
import {dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';

const ORIGIN = 'https://v2-dd.chengji-inc.com';
const DEFAULT_SESSION_PATH = fileURLToPath(new URL('./.local/session.json', import.meta.url));
const READ_ENDPOINTS = Object.freeze({
  importFiles: {method: 'POST', path: '/api/v2/move/import/getImportFileList'},
  categories: {method: 'GET', path: '/api/v2/product/batch/getProductCateTree'},
});

export class MiaoshouError extends Error {
  constructor(message, code, httpStatus) {
    super(message);
    this.name = 'MiaoshouError';
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

// Use the user's existing, authorized session. Persistence is explicit and local.
// There is deliberately no arbitrary URL, write endpoint, or automatic login.
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

  async #read(endpoint, params = {}) {
    if (!this.#cookie) throw new Error('Session cleared');
    const {path, method} = READ_ENDPOINTS[endpoint];
    const body = method === 'POST' ? new URLSearchParams(params).toString() : '';
    return await new Promise((resolve, reject) => {
      const request = https.request(new URL(path, ORIGIN), {
        method,
        headers: {
          Accept: 'application/json',
          Cookie: this.#cookie,
          ...(body ? {'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': Buffer.byteLength(body)} : {}),
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
            const message = code === '50001' ? 'Miaoshou session expired; renew through the normal login flow' : `Miaoshou request failed (${code})`;
            return reject(new MiaoshouError(message, code, status));
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
    const result = await this.#read('importFiles', {pageNo, pageSize});
    if (!Array.isArray(result.data?.importTaskList) || !Number.isInteger(result.data?.importTaskTotal)) {
      throw new MiaoshouError('Import file response schema changed', 'schema_changed', 200);
    }
    return result.data;
  }

  async getCategories() {
    const result = await this.#read('categories');
    if (!result.productCateTree || typeof result.productCateTree !== 'object' || Array.isArray(result.productCateTree) || !Array.isArray(result.recentCategoryList)) {
      throw new MiaoshouError('Category response schema changed', 'schema_changed', 200);
    }
    return {productCateTree: result.productCateTree, recentCategoryList: result.recentCategoryList};
  }
}
