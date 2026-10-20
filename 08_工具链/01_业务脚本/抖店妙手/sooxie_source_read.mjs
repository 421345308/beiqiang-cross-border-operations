/** Anonymous, read-only Beiqiang supplier-page reader. No browser or saved login. */
import https from 'node:https';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

function request(url, fields) {
  return new Promise((resolve, reject) => {
    const body = fields ? new URLSearchParams(fields).toString() : '';
    const req = https.request(url, {
      method: fields ? 'POST' : 'GET',
      headers: {'user-agent': 'Mozilla/5.0', referer: 'https://bqgcd.sooxie.com/',
        ...(fields ? {'content-type': 'application/x-www-form-urlencoded', 'content-length': Buffer.byteLength(body)} : {})},
    }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => {
        if (response.statusCode !== 200) return reject(new Error(`HTTP ${response.statusCode}`));
        resolve(Buffer.concat(chunks).toString('utf8'));
      });
    });
    req.setTimeout(15000, () => req.destroy(new Error('Supplier request timed out')));
    req.on('error', reject);
    req.end(body);
  });
}

function clean(value = '') {
  return value.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').trim();
}

export async function readSource(id) {
  if (!/^\d+$/.test(String(id))) throw new Error('Use a numeric source product ID');
  const url = `https://bqgcd.sooxie.com/detail/${id}`;
  const html = await request(url);
  const list = key => Array.from((html.match(new RegExp(`<p id="${key}">([\\s\\S]*?)</p>`))?.[1] || '').matchAll(/<em[^>]*>([\s\S]*?)<\/em>/g), m => clean(m[1]));
  // This transient page nonce is supplied to the same site's normal detail reader.
  // Never log or save it, and never save login cookies with public product data.
  const nonce = html.match(/token\s*=\s*'([^']+)'/)?.[1] || html.match(/token\s*=\s*"([^"]+)"/)?.[1];
  if (!nonce) throw new Error(`No current detail nonce on source ${id}`);
  const detail = JSON.parse(await request('https://sooxie.com/api/Detail/index', {id: String(id), token: nonce}));
  return {
    id: String(id), url, observed_at: new Date().toISOString(),
    title: clean(html.match(/<h2[^>]*>([\s\S]*?)<\/h2>/)?.[1]),
    source_model: clean(html.match(/货号：<u>([^<]+)<\/u>/)?.[1]),
    price: Number(html.match(/class="meri-price">([\d.]+)</)?.[1]) || null,
    colors: list('color'), sizes: list('size'),
    attributes: Array.from((detail.sku || '').matchAll(/<span>([^<]+)<\/span>/g), m => clean(m[1])),
    // The detail endpoint's alt list is only a subset. Read this product's hero
    // and lazy-loaded description photographs; never include related-product cards.
    // A source description may itself mix models, so images still need identity QA.
    gallery: [...new Set([
      html.match(/id="photoBig"[\s\S]*?<img[^>]*src="([^"]+)"/)?.[1],
      ...Array.from(html.matchAll(/<img[^>]*class="Lazyload"[^>]*data-url="([^"]+)"/g), m => m[1]),
      ...Array.from((detail.img || '').matchAll(/alt='([^']+)'/g), m => m[1]),
    ].filter(Boolean))],
    gallery_basis: '当前页photoBig首图、Lazyload详情原图及详情接口补充；不读取关联推荐卡片，源页自身混款仍须逐图审核。',
    scope: 'Source-page observations only; shared normal/fleece attributes require variant review. No physical stock count is asserted.',
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = process.argv.slice(2);
  if (!args.length || args.includes('--help')) {
    console.log('node sooxie_source_read.mjs ID [ID ...] [--output FILE]\nRead-only: Beiqiang public product pages plus their observed detail endpoint.');
  } else {
    const outputIndex = args.indexOf('--output');
    const output = outputIndex >= 0 ? args[outputIndex + 1] : undefined;
    if (outputIndex >= 0 && !output) throw new Error('--output requires a file');
    const ids = outputIndex >= 0 ? args.slice(0, outputIndex) : args;
    const results = [];
    for (const id of ids) results.push(await readSource(id));
    const json = JSON.stringify(results, null, 2) + '\n';
    if (output) await fs.writeFile(output, json); else console.log(json);
  }
}
