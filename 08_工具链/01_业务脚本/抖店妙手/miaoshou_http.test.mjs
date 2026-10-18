import test from 'node:test';
import assert from 'node:assert/strict';
import https from 'node:https';
import {EventEmitter} from 'node:events';
import {mkdtemp, readFile, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, dirname, basename, resolve} from 'node:path';
import {MiaoshouHttp} from './miaoshou_http.mjs';

test('shop mismatch stops external mutations; matching profile records the verified shop', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'miaoshou-shop-test-'));
  const original = https.request;
  const calls = [];
  let serverShop = '200';
  https.request = (url, options, callback) => {
    calls.push(url.pathname);
    const req = new EventEmitter();
    req.setTimeout = () => req;
    req.end = () => queueMicrotask(() => {
      const res = new EventEmitter(); res.statusCode = 200; callback(res);
      res.emit('data', Buffer.from(JSON.stringify(url.pathname.endsWith('getShopInfo')
        ? {result:'success',shopId:serverShop,userNick:'test shop',shopToken:'DO_NOT_RETURN'}
        : {result:'success'})));
      res.emit('end');
    });
    return req;
  };
  try {
    const image = join(dir, 'test.png');
    await writeFile(image, Buffer.from([137,80,78,71,13,10,26,10]));
    const missing = new MiaoshouHttp({cookie:'test=1'});
    await assert.rejects(missing.uploadImage(image), {code:'shop_target_missing'});
    assert.equal(calls.length, 0);
    const bound = new MiaoshouHttp({cookie:'test=1',expectedShopId:'100'});
    await assert.rejects(bound.uploadImage(image), {code:'shop_mismatch'});
    await assert.rejects(bound.setProductStatus(['123'],1,{evidenceDir:join(dir,'wrong')}), {code:'shop_mismatch'});
    assert(calls.every(p => p.endsWith('getShopInfo')));
    await assert.rejects(readFile(join(dir,'wrong','attempt.json')), {code:'ENOENT'});
    serverShop = '100';
    assert.deepEqual(await bound.getShopIdentity(), {shopId:'100',shopName:'test shop'});
    await bound.setProductStatus(['123'],1,{evidenceDir:join(dir,'right')});
    assert.equal(calls.filter(p => p.endsWith('batchProcessProduct')).length, 1);
    const attempt = JSON.parse(await readFile(join(dir,'right','attempt.json')));
    assert.equal(attempt.targetShop.shopId, '100');
    const session = join(dir,'session.json'); await bound.saveSession({sessionPath:session});
    await assert.rejects(MiaoshouHttp.fromSavedSession({sessionPath:session,expectedShopId:'300'}));
    const restored = await MiaoshouHttp.fromSavedSession({sessionPath:session});
    serverShop = '300';
    await assert.rejects(restored.setProductStatus(['123'],1,{evidenceDir:join(dir,'restored')}), {code:'shop_mismatch'});
  } finally {
    https.request = original;
    assert.equal(dirname(resolve(dir)), resolve(tmpdir()));
    assert(basename(dir).startsWith('miaoshou-shop-test-'));
    await rm(dir, {recursive:true,force:true});
  }
});
