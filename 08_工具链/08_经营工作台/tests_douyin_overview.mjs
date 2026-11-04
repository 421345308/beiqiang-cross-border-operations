import test from 'node:test';
import assert from 'node:assert/strict';
import {readShop,readShops,readBrandSnapshot} from './douyin_overview.mjs';
import {createHash} from 'node:crypto';
const profile={id:'brand',title:'品牌店',url:new URL('file:///C:/private/session.json')};
test('missing identity does not contact platform',async()=>{let calls=0;const row=await readShop(profile,{load:async()=>({cookie:'secret'}),factory:()=>{calls++;}});assert.equal(calls,0);assert.equal(row.error.code,'target_missing');assert.ok(!JSON.stringify(row).includes('secret'));});
test('explicit shop identity and only products operation',async()=>{const row=await readShop(profile,{load:async()=>({expectedShopId:'123',cookie:'secret'}),factory:options=>{assert.equal(options.expectedShopId,'123');return {execute:async(op,args)=>{assert.equal(op,'products');assert.equal(args.isDraft,false);return {ok:true,data:{items:[{productId:'456',title:'鞋'}]},collectedAt:'2026-10-31'};}};}});assert.equal(row.data.items.length,1);assert.ok(!JSON.stringify(row).includes('secret'));});
test('explicit unbound session check does not read products or reveal identity',async()=>{let calls=0;const row=await readShop(profile,{load:async()=>({cookie:'secret'}),checkUnbound:true,probe:async()=>{calls++;throw Object.assign(new Error('secret'),{code:'50001'});},factory:()=>{throw Error('must not read products');}});assert.equal(calls,1);assert.equal(row.error.code,'target_missing');assert.equal(row.session.state,'expired');assert.ok(!JSON.stringify(row).includes('secret'));});
test('valid unbound session still requires target and returns no identity',async()=>{const row=await readShop(profile,{load:async()=>({cookie:'secret'}),checkUnbound:true,probe:async()=>({shopId:'7654321'}),factory:()=>{throw Error('must not read products');}});assert.equal(row.session.state,'valid_unbound');assert.equal(row.ok,false);assert.ok(!JSON.stringify(row).includes('7654321'));});
test('product summaries omit shop and product identifiers',async()=>{const row=await readShop(profile,{load:async()=>({expectedShopId:'123'}),factory:()=>({execute:async()=>({ok:true,data:{shopId:'123',items:[{productId:'456',title:'鞋'}]}})})});assert.deepEqual(row.data,{items:[{title:'鞋'}]});assert.ok(!JSON.stringify(row).includes('456'));});
const header=Buffer.from('c9ccc6b749442cc9ccc6b7b1eacce2','hex');
function snapshotLoader(body, changes={}) {
  const bytes=Buffer.concat([header,Buffer.from('\n'+body)]);
  const meta={capturedAt:'2026-11-04T18:49:43+08:00',sha256:createHash('sha256').update(bytes).digest('hex'),...changes};
  return async path=>String(path).endsWith('.json') ? Buffer.from(JSON.stringify(meta)) : bytes;
}
test('brand snapshot exposes titles only, with original observation time',async()=>{
  const data=await readBrandSnapshot({load:snapshotLoader('"123456789\t","shoe, one"\n"987654321\t","shoe ""two"""\n')});
  assert.equal(data.available,true);assert.equal(data.count,2);assert.equal(data.capturedAt,'2026-11-04T18:49:43+08:00');
  assert.deepEqual(data.items,[{title:'shoe, one'},{title:'shoe "two"'}]);assert.ok(!JSON.stringify(data).includes('123456789'));assert.match(data.notice,/非实时/);
});
test('missing and invalid brand snapshots fail closed without sensitive errors',async()=>{
  for(const load of [async()=>{throw Error('private data');},snapshotLoader('123,shoe\n',{sha256:'bad'}),snapshotLoader('123,shoe,extra\n'),snapshotLoader('123,"unterminated\n'),snapshotLoader('123,shoe\n',{capturedAt:'bad'})]) {
    const data=await readBrandSnapshot({load});assert.equal(data.available,false);assert.ok(!JSON.stringify(data).includes('private data'));assert.ok(!('items' in data));
  }
});
test('single-shop read never contacts the other shop',async()=>{
  const calls=[];const result=await readShops({shop:'brand',checkUnbound:true,reader:async(profile,options)=>{calls.push([profile.id,options.checkUnbound]);return {id:profile.id,ok:false};}});
  assert.deepEqual(calls,[['brand',true]]);assert.equal(result.shops.length,1);
  await assert.rejects(()=>readShops({shop:'other',reader:async()=>{throw Error('must not run');}}));
});
