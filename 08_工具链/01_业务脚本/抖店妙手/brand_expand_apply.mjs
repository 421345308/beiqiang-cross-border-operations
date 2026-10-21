// Execute only explicitly approved styles; preserve existing listings and per-object receipts.
import fs from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';import {isDeepStrictEqual} from 'node:util';
import {MiaoshouHttp} from './miaoshou_http.mjs';import {invariant,skuInvariant} from './focus_media_update.mjs';
const root='09_国内电商/抖店',priv=root+'/.local/品牌新店',file=root+'/数据/品牌首发商品.json';
const read=async f=>JSON.parse(await fs.readFile(f,'utf8')),save=async(f,v)=>{await fs.mkdir(path.dirname(f),{recursive:true});await fs.writeFile(f,JSON.stringify(v,null,2)+'\n');},sha=b=>createHash('sha256').update(b).digest('hex');
const pause=()=>new Promise(r=>setTimeout(r,2300));
const [mode,model]=process.argv.slice(2),allowed=['M889','H7212','ZX2116','ZX9507','A116','K6116','A212','8811','A507','H7116','K6212','L0017','R1811','R1601','M8506','A502','T55836','A218','A008','ZX2212','8008','K6689','T5503','T5505','A350','A206'];
if(!['prepare','publish','verify','protect-existing'].includes(mode)||(mode!=='protect-existing'&&!allowed.includes(model)))throw Error('Usage: prepare|publish|verify MODEL | protect-existing');
const plan=await read(file),candidate=plan.expansion_candidates?.models?.[model],p=plan.models[model]??candidate;
if(mode!=='protect-existing'){
 const price=p?.commercial?.sale_price_cny;
 if(!([94,97].includes(price)||(model==='L0017'&&price===109)))throw Error('Style requires a confirmed daily price tier');
 if(p.commercial.coupon_cny!==5||p.commercial.target_price_cny!==price-5||!p.publication.price_approved)throw Error('Approved commercial values differ');
}
const profilePath='08_工具链/01_业务脚本/抖店妙手/.local/shops/brand/session.json',profile=await read(profilePath),c=await MiaoshouHttp.fromSavedSession({sessionPath:profilePath,timeoutMs:45000});
const shop=await c.getShopIdentity();if(shop.shopId!==String(profile.expectedShopId)||shop.shopName!==profile.expectedShopName)throw Error('Shop differs');
const existingFile=priv+'/扩品保护基线.json';let existing;try{existing=await read(existingFile);}catch(e){if(e.code!=='ENOENT')throw e;existing={};for(const m of ['A1689','ZX9002']){const id=(await read(priv+'/发布/'+m+'/create/response.json')).productId;await pause();const b=await c.getProductBase(id);await pause();const s=await c.getProductSku(id);existing[m]={id,base:invariant(b.productInfo),sku:skuInvariant(s)};}await save(existingFile,existing);}
if(mode==='protect-existing'){
 const checks={};for(const[m,v]of Object.entries(existing)){await pause();const b=await c.getProductBase(v.id);await pause();const s=await c.getProductSku(v.id);checks[m]=isDeepStrictEqual(invariant(b.productInfo),v.base)&&isDeepStrictEqual(skuInvariant(s),v.sku);}
 await save(priv+'/当前核验/扩品后原两款保护.json',{checkedAt:new Date().toISOString(),checks});console.log(JSON.stringify(checks));if(Object.values(checks).some(v=>!v))process.exitCode=2;
}else{
 const dir=priv+'/发布/'+model,expectedPrice=p.commercial.sale_price_cny;
 const catalog=async()=>{let all=[];for(const isDraft of [false,true]){await pause();const r=await c.listProducts({pageSize:100,isDraft});if(r.total!==r.productList.length)throw Error('Full pagination required');all.push(...r.productList);}return all;};
 if(mode==='prepare'){
  try{await fs.access(dir+'/create/attempt.json');throw Error('Creation attempted; reconcile instead');}catch(e){if(e.code!=='ENOENT')throw e;}
  const qa=candidate?candidate.acceptance.visual_qa:plan.visual_qa;
  const allAssets=candidate?[...p.main_assets,...p.detail_files]:Object.values(plan.models).flatMap(v=>[...v.main_assets,...v.detail_files]);if(qa.state!=='PASSED'||qa.asset_set_sha256!==sha(Buffer.from(allAssets.map(a=>a.sha256).join('\n'))))throw Error('Current visual QA required');
  const currentCatalog=await catalog();
  if(currentCatalog.some(v=>v.name===p.title||v.productNum===model||v.goodsNo===model||v.goodsNum===model))throw Error('Potential existing style; inspect SKUs');
  if(candidate){
   const inspected=await read(priv+'/当前核验/全店规格查重.json');
   if(new Date()-new Date((await read(priv+'/当前核验/catalog-summary.json')).checkedAt)>3600000)throw Error('Refresh full catalog and SKU inspection');
   if(currentCatalog.some(v=>!inspected.some(i=>i.id===String(v.productIdStr??v.productId))))throw Error('Catalog changed; inspect all new SKU identities');
   if(inspected.some(i=>i.productNum===model||i.skus.some(s=>String(s.code).includes(model)||s.sellProperties.some(v=>String(v.valueName).includes(model)))))throw Error('Potential existing SKU identity');
  }
  const cacheFile=priv+'/素材上传.json',cache=await read(cacheFile);
  const upload=async(f,expected)=>{const b=await fs.readFile(f),h=sha(b);if(expected&&h!==expected)throw Error('Asset drifted');let entry=cache[h];if(entry&&entry.shopId!==shop.shopId)throw Error('Wrong-shop cache');if(!entry){await pause();entry={shopId:shop.shopId,file:f,sha256:h,uploadedAt:new Date().toISOString(),receipt:await c.uploadImage(f)};cache[h]=entry;await save(cacheFile,cache);}return entry.receipt.url;};
  const pics=[],description=[],specPic=[];for(const a of p.main_assets)pics.push(await upload(a.path,a.sha256));for(const a of p.detail_files)description.push(await upload(a.path,a.sha256));for(const a of p.media_binding.sku_color_files){const h=p.sourceEvidence.find(v=>v.path===a.path)?.sha256;if(!h)throw Error('Colour provenance missing');specPic.push(await upload(a.path,h));}
  await pause();const rec=await c.recommendCategory({name:p.title,mainImgUrls:pics});await save(dir+'/recommendation.json',rec);const cat=rec.data.recommendCategoryList.find(v=>v.catePath==='鞋靴>男鞋>休闲鞋');if(!cat)throw Error('Recommended category differs');const cateId=String(cat.cateIds.filter(Boolean).at(-1));
  await pause();const rules=await c.getCategoryInfo(cateId);await save(dir+'/rules-current.json',rules);
  const attrs={};for(const[name,value]of [['鞋面材质',p.upper||'织物'],['鞋底材质',p.sole],['功能',p.fleece===false?p.function:'保暖'],['闭合方式',p.closure],['鞋面内里材质',p.fleece===false?p.inner:'人造短毛绒'],['适用季节',p.fleece===false?'通用':'冬季']]){const r=rules.cateAttrList.find(a=>a.propertyName===name),o=r?.options.find(a=>a.name===value);if(!o){if(r&&!r.required&&(value===undefined||name==='闭合方式'&&value==='鞋带装饰'))continue;throw Error('Current attribute missing '+name+'/'+value);}attrs[String(r.propertyId)]=r.type==='multi_select'?[String(o.valueId)]:String(o.valueId);}
  const brand=rules.brandOption.filter(v=>v.nameCn==='雷丹森羊');if(brand.length!==1)throw Error('Brand not unique');const brandRule=rules.cateAttrList.find(a=>a.propertyName==='品牌');attrs[String(brandRule.propertyId)]=String(brand[0].brandId);attrs['3171']=model;
  if(rules.cateAttrList.some(r=>r.required&&attrs[String(r.propertyId)]===undefined))throw Error('Required attribute missing');
  const sizes=Array.from({length:p.sizes[1]-p.sizes[0]+1},(_,i)=>p.sizes[0]+i);let size;try{size=await read(dir+'/size-create/response.json');}catch(e){if(e.code!=='ENOENT')throw e;await pause();size=await c.saveSizeTemplate({cateId,sizeTempSubType:'shoes',selectedSpecs:['脚长(cm)'],specOptions:['脚长(cm)'],templateId:null,fixedSizeName:'尺码',specMap:{'尺码':sizes.map(String),'脚长(cm)':sizes.map(s=>String((s-35)*.5+22.5))},title:'尺码推荐',tempName:`雷丹森羊${model}${p.fleece===false?'常规':'加绒'}标准参考`,desc:'标准参考脚长，非实测鞋内长；厚袜及脚型不同请咨询选码',isShareable:'0'},{evidenceDir:dir+'/size-create'});}
  await pause();await save(dir+'/size-readback.json',await c.getSizeTemplateInfo(size.data.templateId));
  const auth=await read(priv+'/履约授权.json');if(auth.shopId!==shop.shopId||!auth.address_verified||!auth.freight_id)throw Error('Fulfillment not verified');
  const options=rules.productSpecRule.requiredSpecDetails.find(v=>String(v.sellPropertyId)==='4709').propertyValues,base=await read(priv+'/发布/A1689/payload.json');
  const payload={...base,title:p.title,cateId,standardBrandId:String(brand[0].brandId),attrValues:attrs,categoryPropertyPics:Object.fromEntries(Object.keys(attrs).map(k=>[k,{}])),pics,description,
   specValues:[{propertyId:2752,propertyName:'颜色分类',values:p.colors.map(valueName=>({valueName,oriValueName:valueName,valueId:0}))},{propertyId:4709,propertyName:'鞋码大小',values:sizes.map(s=>{const v=options.find(v=>String(v.sellPropertyValueName)===String(s));if(!v)throw Error('Size option missing');return {valueName:String(s),oriValueName:String(s),valueId:v.sellPropertyValueId};})}],
   specPricesV2:p.colors.flatMap((color,i)=>sizes.map(s=>({price:expectedPrice,stock:100,stockNum:100,code:`LDSY-${model}-${p.fleece===false?'R':'F'}-${i+1}-${s}`,skuStatus:true,sellProperties:[{isPresellSpecValue:false,propertyName:'颜色分类',oriValueName:color,valueName:color},{isPresellSpecValue:false,propertyName:'鞋码大小',oriValueName:String(s),valueName:String(s)}]}))),specPic,freightId:auth.freight_id,mobile:auth.mobile,
   sizeInfoTemplateId:size.data.templateId,componentFrontData:size.data.componentFrontData,templateName:size.data.templateName,categoryRecommendId:rec.data.categoryRecommendId,categoryRecommendCheckStr:rec.data.categoryRecommendCheckStr,commit:1,status:0};
  if(pics.length!==3||description.length!==8)throw Error('Reviewed media counts differ');await save(dir+'/payload.json',payload);p.publication.state='PREPARED_PENDING_CREATE';await save(file,plan);console.log(JSON.stringify({model,prepared:true,skus:payload.specPricesV2.length,price:expectedPrice,target:expectedPrice-5}));
 }else if(mode==='publish'){
  const payload=await read(dir+'/payload.json');if((await catalog()).some(v=>v.name===p.title))throw Error('Existing title; reconcile');let attempt='create';
  if(process.argv.includes('--retry-qps')){const f=await read(dir+'/create/failure.json');if(f.code!=='ddApiLocalQpsLimit')throw Error('Not an explicit rate-limit failure');attempt='create-qps-retry';}
  await pause();const r=await c.createProduct(payload,{evidenceDir:dir+'/'+attempt});if(attempt!=='create')await save(dir+'/creation-result.json',r);p.publication.state='CREATED_PENDING_AUDIT';await save(file,plan);console.log(JSON.stringify({model,created:true}));
 }else{
  let receipt;try{receipt=await read(dir+'/creation-result.json');}catch(e){if(e.code!=='ENOENT')throw e;receipt=await read(dir+'/create/response.json');}const id=receipt.productId;if(typeof id!=='string'||!/^\d+$/.test(id))throw Error('Exact product ID required');
  await pause();const base=await c.getProductBase(id);await pause();const sku=await c.getProductSku(id);await pause();const audit=await c.getProductAudit(id);const b=base.productInfo,expected=await read(dir+'/payload.json'),last=[...audit.auditList].sort((a,b)=>b.publishTime-a.publishTime)[0];
  const rows=sku.specPricesV2||sku.specPrices;const checks={onSale:b.status===0,title:b.name===p.title,brand:String(b.standardBrandId)===expected.standardBrandId,freight:String(b.freightId)===String(expected.freightId),main:b.pic.length===3,details:b.descriptionImgList.length===8,skus:rows?.length===expected.specPricesV2.length,prices:rows?.every(v=>Number(v.price)===expectedPrice),stock:rows?.every(v=>Number(v.stock??v.stockNum)===100),codes:rows?.every(v=>expected.specPricesV2.some(e=>e.code===v.code)),specs:rows?.every(v=>Number(v.skuStatus)===1&&expected.specPricesV2.some(e=>e.code===v.code&&JSON.stringify(e.sellProperties.map(x=>x.valueName))===JSON.stringify(v.sellProperties.map(x=>x.valueName)))),nextDay:Number(b.deliveryDelayDay)===1,returns:b.afterSaleService?.supplyDayReturnSelector==='7-1',warranty:Number(b.afterSaleServiceV2?.threeGuarantees?.duration)===90&&Number(b.afterSaleServiceV2?.threeGuarantees?.serviceType)===1,audit:last?.title===p.title&&last.publishStatus===1};
  const result={checkedAt:new Date().toISOString(),model,productId:id,checks,verified:Object.values(checks).every(Boolean),pixelComparison:'PENDING',buyerPreview:'PENDING',base,sku,audit};await save(dir+'/verification.json',result);
  Object.assign(p.publication,{state:result.verified?'ON_SALE_BACKEND_VERIFIED_MEDIA_PENDING':'READBACK_PENDING_OR_DIFFERENT',private_content_evidence:dir.replace(root+'/',''),product_id_storage:'精确字符串仅在本地创建回执和verification.json保存',sku_count:expected.specPricesV2.length,audit:checks.audit?'PASSED':'PENDING',coupons:'PENDING_SCOPE_EXTENSION'});await save(file,plan);console.log(JSON.stringify({model,verified:result.verified,checks}));if(!result.verified)process.exitCode=2;
 }
}
