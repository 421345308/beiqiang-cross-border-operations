import {MiaoshouConnector} from './index.mjs';

export async function main(args = process.argv.slice(2)) {
  const [operation, ...rest] = args;
  const allowed = new Set(['session-path','expected-shop-id','page','page-size','is-draft','product-id']);
  const options = {};
  let valid = true;
  for (let i = 0; i < rest.length; i += 2) {
    const key = rest[i]?.replace(/^--/, '');
    if (!rest[i]?.startsWith('--') || !allowed.has(key) || options[key] !== undefined || rest[i + 1] === undefined) { valid = false; break; }
    options[key] = rest[i + 1];
  }
  if (options['is-draft'] !== undefined && !['true','false'].includes(options['is-draft'])) valid = false;
  const connector = new MiaoshouConnector({sessionPath: options['session-path'], expectedShopId: options['expected-shop-id']});
  const result = await connector.execute(valid ? operation : '__invalid__', {
    page: options.page === undefined ? 1 : Number(options.page),
    pageSize: options['page-size'] === undefined ? 100 : Number(options['page-size']),
    isDraft: options['is-draft'] === undefined ? undefined : options['is-draft'] === 'true', productId: options['product-id'],
  });
  process.stdout.write(JSON.stringify(result) + '\n');
  if (!result.ok) process.exitCode = 1;
  return result;
}
import {pathToFileURL} from 'node:url';
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
