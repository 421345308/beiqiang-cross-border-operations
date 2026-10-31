import test from 'node:test';
import assert from 'node:assert/strict';
import {readShop} from './douyin_overview.mjs';
const profile={id:'brand',title:'品牌店',url:new URL('file:///C:/private/session.json')};
test('missing identity does not contact platform',async()=>{let calls=0;const row=await readShop(profile,{load:async()=>({cookie:'secret'}),factory:()=>{calls++;}});assert.equal(calls,0);assert.equal(row.error.code,'target_missing');assert.ok(!JSON.stringify(row).includes('secret'));});
test('explicit shop identity and only products operation',async()=>{const row=await readShop(profile,{load:async()=>({expectedShopId:'123',cookie:'secret'}),factory:options=>{assert.equal(options.expectedShopId,'123');return {execute:async(op,args)=>{assert.equal(op,'products');assert.equal(args.isDraft,false);return {ok:true,data:{items:[{productId:'456',title:'鞋'}]},collectedAt:'2026-10-31'};}};}});assert.equal(row.data.items.length,1);assert.ok(!JSON.stringify(row).includes('secret'));});
