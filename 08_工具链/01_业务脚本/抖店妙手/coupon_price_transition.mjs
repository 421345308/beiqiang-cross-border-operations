import fs from'node:fs/promises';import{isDeepStrictEqual}from'node:util';import{MiaoshouHttp}from'./miaoshou_http.mjs';
const dir='09_国内电商/抖店/.local/evidence/buyer-final',read=async f=>JSON.parse(await fs.readFile(f,'utf8')),mode=process.argv[2],plan=await read(process.argv[3]||dir+'/new-seven-coupon-plan.json');
if(!['prepare','apply','verify'].includes(mode))throw Error('Explicit prepare/apply/verify required');
if(plan.attempt_label&&!/^[a-z0-9-]{1,48}$/.test(plan.attempt_label))throw Error('Invalid attempt label');
const c=await MiaoshouHttp.fromSavedSession({timeoutMs:30000}),sleep=ms=>new Promise(r=>setTimeout(r,ms));
const save=async(f,d)=>{await fs.writeFile(f+'.tasktmp',JSON.stringify(d,null,2)+'\n');await fs.rename(f+'.tasktmp',f);};
const identity=(b,trimRemark=false)=>b.specPrices.map(x=>({id:String(x.skuId),stock:x.stockNum,code:x.code,properties:x.sellProperties.map(v=>({...v,...(trimRemark&&typeof v.remark==='string'?{remark:v.remark.trim()}:{} )})),status:x.skuStatus})).sort((a,b)=>a.id.localeCompare(b.id));
const mediaPaths=urls=>urls.map(x=>new URL(x).pathname);
if(mode==='apply'){const coupon=await read(plan.coupon_receipt||dir+'/new-seven-coupon-created.json');const scope=plan.coupon_scope_product_ids||plan.plans.map(x=>x.productId);if(!coupon.verifiedActive||coupon.discount!==5||!isDeepStrictEqual([...coupon.productIds].sort(),[...scope].sort()))throw Error('Coupon not verified for exact scope');}
for(const p of plan.plans){const before=await read(dir+'/'+p.model+'-coupon-before.json'),b=before.base.productInfo,sku=before.sku,e=dir+'/'+p.model+'-coupon-price';
 if(mode==='prepare'){
  const rows=structuredClone(sku.specPricesV2);for(const r of rows){if(!r.skuStatus)continue;if(r.price!==(p.original_base??p.target_net))throw Error('Price changed');r.price=p.proposed_base_by_sku?.[String(r.skuId)]??p.proposed_base;}
  const picMap=new Map(b.specPics.map(x=>[String(x.specDetailId),x.pic]));const specPic=b.specPics.length?b.specs.find(x=>x.propertyId===2752).values.map(v=>picMap.get(String(v.id))||''):[];
  const payload={productId:p.productId,cateId:String(b.cid),changeFields:['sku'],presellType:b.presellType,deliveryDelayDay:b.deliveryDelayDay,withSkuType:sku.withSkuType,isStandardSkuInfo:sku.isStandardSkuInfo?1:0,specValues:sku.specValues,specPricesV2:rows,specPic};
  if(plan.trimSpecRemarkWhitespace)for(const s of payload.specValues)for(const v of s.values)if(typeof v.remark==='string')v.remark=v.remark.trim();
  await save(e+'-prepared.json',{model:p.model,targetNet:p.target_net,discount:5,basePrice:p.proposed_base,payload});
 }else if(mode==='apply'){
  const now=(await c.getProductBase(p.productId)).productInfo;if(!isDeepStrictEqual(identity(now),identity(b))||!isDeepStrictEqual(now.specPrices.map(x=>[String(x.skuId),x.price]),b.specPrices.map(x=>[String(x.skuId),x.price])))throw Error('Live baseline changed '+p.model);
  const prepared=await read(e+'-prepared.json');await c.saveProduct(prepared.payload,{evidenceDir:e+'-apply'+(plan.attempt_label?'-'+plan.attempt_label:'')});console.log(JSON.stringify({model:p.model,state:'PRICE_SUBMITTED',base:p.proposed_base,coupon:5,target:p.target_net}));await sleep(1300);
 }else{
  const after=await c.getProductBase(p.productId),n=after.productInfo,audit=await c.getProductAudit(p.productId);
  // The same image object is served from p3/p9 CDN aliases. Compare ordered object paths.
  const oldPrices=new Map(b.specPrices.map(x=>[String(x.skuId),x]));
  const checks={allSkuIdentitiesStocksCodesAndStatusesPreserved:isDeepStrictEqual(identity(b,plan.trimSpecRemarkWhitespace===true),identity(n)),basePrice:n.specPrices.every(x=>{const old=oldPrices.get(String(x.skuId));return old&&x.price===(old.skuStatus?(p.proposed_base_by_sku?.[String(x.skuId)]??p.proposed_base):old.price);}),title:b.name===n.name,mainImages:isDeepStrictEqual(mediaPaths(b.pic),mediaPaths(n.pic)),details:isDeepStrictEqual(mediaPaths(b.descriptionImgList),mediaPaths(n.descriptionImgList)),colorImages:isDeepStrictEqual(b.specPics.map(x=>({...x,pic:x.pic?new URL(x.pic).pathname:''})),n.specPics.map(x=>({...x,pic:x.pic?new URL(x.pic).pathname:''}))),specs:isDeepStrictEqual(b.specs,n.specs),sizeTemplate:b.sizeInfoTemplateId===n.sizeInfoTemplateId,freight:b.freightId===n.freightId,dispatch:b.deliveryDelayDay===n.deliveryDelayDay,returns:isDeepStrictEqual(b.afterSaleService,n.afterSaleService),guarantees:isDeepStrictEqual(b.afterSaleServiceV2,n.afterSaleServiceV2),onSale:n.status===0};
  const v={model:p.model,checkedAt:new Date().toISOString(),verified:Object.values(checks).every(Boolean),checks,basePrice:p.proposed_base,coupon:5,targetNet:p.target_net,after,audit};await save(e+'-verification'+(plan.attempt_label?'-'+plan.attempt_label:'')+'.json',{...v,approvedSpecRemarkWhitespaceTrim:plan.trimSpecRemarkWhitespace===true});console.log(JSON.stringify({model:p.model,verified:v.verified,checks}));if(!v.verified)throw Error('Price verification failed '+p.model);
 }
}
