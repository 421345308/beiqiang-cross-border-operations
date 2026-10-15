// Execute reviewed consumer pages on existing listing identities. Private identity/evidence stays local.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash}from'node:crypto';
import {isDeepStrictEqual}from'node:util';
import {MiaoshouHttp}from'./miaoshou_http.mjs';
const root='09_国内电商/抖店',read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const mode=process.argv[2],selected=process.argv.slice(3);
if(!['upload','apply','verify','activate','repair-brand'].includes(mode)||!selected.length)throw Error('Explicit mode and models required');
const old=await read(root+'/数据/旧混款整理.json'),four=await read(root+'/数据/棉鞋内容优化.json');
const plan={...old.models,...four.models},ids=await read(root+'/.local/evidence/style-split/targets.json');
const progress=await read(root+'/.local/执行进度.json');for(const x of progress.new_cotton.products)if(four.models[x.model])ids[x.model]=x.productId;
const baseDir=root+'/.local/evidence/retail-family';await fs.mkdir(baseDir,{recursive:true});
const save=async(f,d)=>{await fs.mkdir(path.dirname(f),{recursive:true});await fs.writeFile(f+'.tasktmp',JSON.stringify(d,null,2)+'\n');await fs.rename(f+'.tasktmp',f);};
const hash=b=>createHash('sha256').update(b).digest('hex');
const client=await MiaoshouHttp.fromSavedSession({timeoutMs:45000});
const cacheFile=baseDir+'/uploads.json';let uploads={};try{uploads=await read(cacheFile);}catch(e){if(e.code!=='ENOENT')throw e;}
const color=s=>s.sellProperties.find(x=>x.propertyName==='颜色分类')?.valueName;
const priceSnapshot=b=>b.specPrices.map(s=>({id:String(s.skuId),price:s.price,stock:s.stockNum,code:s.code})).sort((a,b)=>a.id.localeCompare(b.id));
const keepName=(m,n)=>m==='M889'?/^889(?:黑白|米白|全黑)(?:加绒)?$/.test(n):m==='A116'?/^a116(?:黑白|全黑)加绒$/i.test(n):true;
const displayName=(m,n)=>m==='M889'?n.replace(/^889/,''):m==='A116'?n.replace(/^a116/i,''):n;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function url(file){const key=hash(await fs.readFile(file));if(!uploads[key])throw Error('Not uploaded '+file);return uploads[key].url;}
for(const model of selected){
 const p=plan[model],id=ids[model],dir=baseDir+'/'+model;if(!p||!id)throw Error('Unknown reviewed model');await fs.mkdir(dir,{recursive:true});
 try{
 if(mode==='upload'){
  if(p.visual_qa!=='PASSED'&&p.consumer_visual_qa!=='PASSED')throw Error('Visual review not passed '+model);
  const files=[...p.main_files,...p.color_files,...p.detail_files.map(x=>x.path)];
  const assets=[];for(const file of [...new Set(files)]){const key=hash(await fs.readFile(file));assets.push({file,sha256:key});if(!uploads[key]){await sleep(1250);const r=await client.uploadImage(file);uploads[key]={url:r.url,file,sha256:key};await save(cacheFile,uploads);}}
  await save(dir+'/assets.json',assets);console.log(JSON.stringify({model,state:'UPLOADED',files:assets.length}));
 }else if(mode==='apply'){
  try{await fs.access(dir+'/apply/attempt.json');throw Error('Existing attempt: inspect verification; do not rewrite baseline');}catch(e){if(e.code!=='ENOENT')throw e;}
  const assets=await read(dir+'/assets.json');for(const a of assets)if(hash(await fs.readFile(a.file))!==a.sha256)throw Error('Reviewed asset changed');
   if(['M889','A116'].includes(model))for(const dep of [...['8811','A1689','A212','A507','H7116','H7212','K6212','L0017','R1811'],...(model==='A116'?['M889']:[])]){const v=await read(baseDir+'/'+dep+'/verification.json');const ready=v.verified||(dep==='M889'&&v.contentAndPriceVerified&&v.identityMigration?.allMapped);if(!ready||!v.auditPassed||v.status!==0)throw Error('Independent family not ready '+dep);}
  const base=await client.getProductBase(id),b=base.productInfo;if(b.productIdStr!==id)throw Error('Identity changed');
  const before={base};const fields=['title','mainImg','descImg'];
  const payload={productId:id,cateId:String(b.cid),changeFields:fields,title:p.title,pics:await Promise.all(p.main_files.map(url)),description:await Promise.all(p.detail_files.map(x=>url(x.path))),mainImageThreeToFour:b.mainImageThreeToFour||[],whiteBgImgUrl:b.whiteBackGroundPicUrl||''};
  if(old.models[model]&&!['A212','H7116','K6212'].includes(model)){
   const category=await client.getCategoryInfo(String(b.cid)),attrs={'1687':String(b.standardBrandId)};
   for(const[k,list]of Object.entries(b.productFormatNew||{})){
    const rule=category.cateAttrList.find(x=>String(x.propertyId)===k);if(!rule)continue;
    const values=list.map(x=>rule.type==='measure'?{name:x.name,...x.measureInfo}:rule.type==='text'||x.diyType===1?x.name:String(x.value));attrs[k]=rule.type==='multi_select'||rule.type==='measure'?values:values[0];
   }
   const set=(id,names)=>{const rule=category.cateAttrList.find(x=>x.propertyId===id);if(!rule)return;const vals=names.map(n=>{const o=rule.options.find(x=>x.name===n);if(!o)throw Error('Unsupported attribute '+id+' '+n);return String(o.value);});attrs[id]=rule.type==='multi_select'?vals:vals[0];};
   attrs['3171']=model;
   set(b.cid===1000007649?883:2064,['织物']);
   set(b.cid===1000007649?1506:3029,['EVA']);
   if(category.cateAttrList.some(x=>x.propertyId===810&&x.required))set(810,p.mixed_versions?['包裹性']:['保暖']);
   if(model==='H7212'){set(810,['保暖']);set(3284,['人造短毛绒']);set(1343,['冬季']);}
   if(model==='M889'){set(3284,['织物','人造短毛绒']);set(1343,['四季通用']);set(2563,['休闲鞋']);attrs['6509']=[{name:'0cm',templateId:572,values:[{moduleId:1223,value:'0',unitId:39,unitName:'cm',prefix:'',suffix:'',prefixId:0,suffixId:0,valueId:0}]}];}
   if(model==='L0017'){delete attrs['810'];delete attrs['3197'];delete attrs['680'];set(1714,['日常休闲']);}
   fields.push('base');
   Object.assign(payload,{sourceTitle:b.name,standardBrandId:String(b.standardBrandId),attrValues:attrs,categoryPropertyPics:{},isEvaluateOpened:b.isEvaluateOpened,shortProductName:p.mixed_versions?'针织休闲鞋加绒可选':'加绒针织休闲鞋',recommendRemark:'',mobile:(b.mobile||'').trim(),freightId:String(b.freightId),weightValue:b.weightValue,weightUnit:b.weightUnit,limitPerBuyer:b.limitPerBuyer,maximumPerOrder:b.maximumPerOrder,minimumPerOrder:b.minimumPerOrder,supply7dayReturn:b.afterSaleService.supplyDayReturnSelector,remark:b.extra?.stone?.remark||'',referencePrice:b.referencePrice||'',referencePriceCertificateType:b.referencePriceCertificate?.certificateType||'',referencePriceCertificateUrls:b.referencePriceCertificate?.certificateUrls||'',presellType:b.presellType,presellConfigLevel:b.presellConfigLevel,namePrefix:b.namePrefix,nameSuffix:b.nameSuffix,isSaveNewShareableSizTemplate:false,threeGuaranteesServiceType:String(b.afterSaleServiceV2.threeGuarantees?.serviceType||1),threeGuaranteesDuration:String(b.afterSaleServiceV2.threeGuarantees?.duration||90),isLargeProduct:b.afterSaleServiceV2.isLargeProduct?'1':'0',sizeInfoTemplateId:b.sizeInfoTemplateId,sizeInfoTemplateUrl:''});
  }
  const colors=b.specs.find(x=>x.propertyId===2752).values;
  const oldPics=new Map(b.specPics.map(x=>[String(x.specDetailId),x.pic]));
  const binding={};for(let i=0;i<p.color_names.length;i++)binding[p.color_names[i]]=await url(p.color_files[i]);
  payload.specPic=colors.map(x=>binding[displayName(model,x.name)]||oldPics.get(String(x.id))||b.pic[0]);
  if(['M889','A116','H7212'].includes(model)){
   const sku=await client.getProductSku(id);before.sku=sku;
   const specValues=structuredClone(sku.specValues),rows=structuredClone(sku.specPricesV2);
   if(model==='H7212'){
    for(const s of rows)s.skuStatus=0;
    if(specValues[0].values.some(x=>x.valueName==='黑白加绒'))throw Error('New fleece SKU already exists; inspect instead of retry');
    specValues[0].values.push({oriValueName:'黑白加绒',valueName:'黑白加绒',valueId:0,remark:'',isAddedDefaultSpec:0});
    const source=await client.getProductSku(ids.M889),prices=source.specPricesV2.filter(x=>color(x)==='7212黑白加绒');
    if(prices.length!==11||new Set(prices.map(x=>x.price)).size!==1)throw Error('Source fleece price not unambiguous');
    before.priceSource=prices;
    for(const size of specValues.find(x=>x.propertyId===4709).values)rows.push({price:prices[0].price,stock:100,stockNum:100,code:'H7212-加绒-'+size.valueName,skuStatus:1,sellProperties:[{propertyName:'颜色分类',oriValueName:'黑白加绒',valueName:'黑白加绒',isPresellSpecValue:false},{propertyName:'鞋码大小',oriValueName:size.valueName,valueName:size.valueName,isPresellSpecValue:false}]});
    payload.specPic.push(binding['黑白加绒']);
   }else{
    // Keep existing specification names. Renaming a value regenerates platform SKU IDs.
    for(const s of rows){if(!keepName(model,color(s)))s.skuStatus=0;}
    if(model==='M889'){
     if(specValues[0].values.some(x=>x.valueName==='米白加绒'))throw Error('White fleece already exists; inspect readback');
     const source=sku.specPricesV2.filter(x=>color(x)==='889黑白加绒');if(source.length!==11||new Set(source.map(x=>x.price)).size!==1)throw Error('Unclear existing M889 fleece price');before.whiteFleecePriceSource=source;
     specValues[0].values.push({oriValueName:'米白加绒',valueName:'米白加绒',valueId:0,remark:'',isAddedDefaultSpec:0});payload.specPic.push(binding['米白加绒']);
     for(const size of specValues.find(x=>x.propertyId===4709).values)rows.push({price:source[0].price,stock:100,stockNum:100,code:'M889-1-米白加绒-'+size.valueName,skuStatus:1,sellProperties:[{propertyName:'颜色分类',oriValueName:'米白加绒',valueName:'米白加绒',isPresellSpecValue:false},{propertyName:'鞋码大小',oriValueName:size.valueName,valueName:size.valueName,isPresellSpecValue:false}]});
    }
   }
   fields.push('sku');Object.assign(payload,{presellType:b.presellType,deliveryDelayDay:b.deliveryDelayDay,withSkuType:sku.withSkuType,isStandardSkuInfo:sku.isStandardSkuInfo?1:0,specValues,specPricesV2:rows});
  }
  const weight=[...p.title].reduce((n,c)=>n+(c.charCodeAt(0)>127?2:1),0);if(weight>60||payload.pics.length<3||payload.description.length!==8)throw Error('Content count/length invalid');
  await save(dir+'/before.json',before);await save(dir+'/prepared.json',{payload,assets,priceSnapshot:priceSnapshot(b),colorBindings:binding});
  await client.saveProduct(payload,{evidenceDir:dir+'/apply'});console.log(JSON.stringify({model,state:'SUBMITTED',skuChange:fields.includes('sku'),priceEdit:false}));
 }else if(mode==='repair-brand'){
  if(model!=='L0017')throw Error('Only the confirmed erroneous L0017 legacy brand is in this correction');
  const prepared=await read(dir+'/prepared.json');await save(dir+'/brand-correction-before.json',await client.getProductBase(id));
  prepared.payload.standardBrandId='596120136';prepared.payload.attrValues['1687']='596120136';prepared.payload.namePrefix='';prepared.payload.nameSuffix='';prepared.expectedBrandId=596120136;prepared.lastSubmissionEvidence='repair-brand';
  await save(dir+'/prepared.json',prepared);await client.saveProduct(prepared.payload,{evidenceDir:dir+'/repair-brand'});console.log(JSON.stringify({model,state:'LEGACY_BRAND_CORRECTED_SUBMITTED'}));
 }else if(mode==='verify'){
  const before=(await read(dir+'/before.json')).base.productInfo,prepared=await read(dir+'/prepared.json');
  const base=await client.getProductBase(id),audit=await client.getProductAudit(id),b=base.productInfo;
  const previous=new Map(prepared.priceSnapshot.map(x=>[x.id,x]));
  const pricesPreserved=b.specPrices.filter(x=>previous.has(String(x.skuId))).every(x=>{const old=previous.get(String(x.skuId));return x.price===old.price&&x.code===old.code;});
  const stockPreserved=b.specPrices.filter(x=>previous.has(String(x.skuId))).every(x=>x.stockNum===previous.get(String(x.skuId)).stock);
  const oldIdsKept=prepared.priceSnapshot.every(x=>b.specPrices.some(s=>String(s.skuId)===x.id));
  let identityMigration=null;
  if(model==='M889'&&!oldIdsKept){
   const names=s=>s.sellProperties.map(p=>p.propertyName+'='+displayName(model,p.valueName)).sort().join('|');
   const missing=before.specPrices.filter(s=>!b.specPrices.some(n=>String(n.skuId)===String(s.skuId)));
   const mappings=missing.map(s=>{const matches=b.specPrices.filter(n=>names(n)===names(s));if(matches.length!==1)return{oldId:String(s.skuId),matched:false};const n=matches[0];return{oldId:String(s.skuId),newId:String(n.skuId),oldColor:color(s),newColor:color(n),size:s.sellProperties.find(x=>x.propertyName==='鞋码大小')?.valueName,oldPrice:s.price,newPrice:n.price,oldStock:s.stockNum,newStock:n.stockNum,codePreserved:s.code===n.code,matched:s.price===n.price&&s.stockNum===n.stockNum&&s.code===n.code};});
   identityMigration={reason:'Specification display-name edit caused platform SKU regeneration; no further existing specification names will be changed',count:mappings.length,allMapped:mappings.every(x=>x.matched),mappings,campaignBindingsVerified:false};await save(dir+'/sku-identity-migration.json',identityMigration);
  }
  const urlPath=x=>new URL(x).pathname;
  const checks={title:b.name===p.title,mainCount:b.pic.length===p.main_files.length,details:b.descriptionImgList.length===8,distinct:new Set(b.descriptionImgList.map(urlPath)).size===8,mainDetailDisjoint:!b.pic.some(x=>b.descriptionImgList.map(urlPath).includes(urlPath(x))),detailsUpdated:!isDeepStrictEqual(b.descriptionImgList.map(urlPath),before.descriptionImgList.map(urlPath)),pricesPreserved,oldIdsKept,stockPreserved,freight:b.freightId===before.freightId,dispatch:b.deliveryDelayDay===before.deliveryDelayDay,sizeTemplate:b.sizeInfoTemplateId===before.sizeInfoTemplateId,returns:isDeepStrictEqual(b.afterSaleService,before.afterSaleService),guarantees:isDeepStrictEqual(b.afterSaleServiceV2,before.afterSaleServiceV2)};
  checks.brandPreserved=b.standardBrandId===before.standardBrandId;
  if(prepared.expectedBrandId){delete checks.brandPreserved;checks.correctedBrand=b.standardBrandId===prepared.expectedBrandId;}
  let sizeEquivalence=null;
  if(!checks.sizeTemplate){const oldSize=await client.getSizeTemplateInfo(before.sizeInfoTemplateId),newSize=await client.getSizeTemplateInfo(b.sizeInfoTemplateId);const decode=x=>JSON.parse(x.sizeTemplateInfo.componentFrontData);const a=decode(oldSize),n=decode(newSize);sizeEquivalence={oldSize,newSize,sameTable:isDeepStrictEqual(a.configTable,n.configTable),sameSizes:isDeepStrictEqual(a.selectedSize,n.selectedSize),sameSpecs:isDeepStrictEqual(a.selectedSpecs,n.selectedSpecs)};checks.sizeTemplate=sizeEquivalence.sameTable&&sizeEquivalence.sameSizes&&sizeEquivalence.sameSpecs;await save(dir+'/size-equivalence.json',sizeEquivalence);}
  if(model==='H7212'){checks.returns=b.afterSaleService.supplyDayReturnSelector===before.afterSaleService.supplyDayReturnSelector;checks.guarantees=b.afterSaleServiceV2.threeGuarantees?.serviceType===1&&b.afterSaleServiceV2.threeGuarantees?.duration===90;}
  if(prepared.payload.changeFields.includes('base'))checks.consumerShortName=b.shortProductName===prepared.payload.shortProductName;
  const active=b.specPrices.filter(x=>x.skuStatus),activeColors=[...new Set(active.map(color))];
  if(model==='M889')checks.onlyOwnFamily=activeColors.every(x=>['黑白','米白','全黑','全黑加绒','黑白加绒','米白加绒'].includes(x))&&active.length===66;
  if(model==='A116')checks.onlyOwnFamily=activeColors.every(x=>/^a116(?:黑白|全黑)加绒$/i.test(x))&&active.length===22;
  if(model==='H7212')checks.onlyFleece=activeColors.length===1&&activeColors[0]==='黑白加绒'&&active.length===11;
  const latest=[...audit.auditList].sort((a,b)=>b.publishTime-a.publishTime)[0];
  const attempt=await read(dir+'/'+(prepared.lastSubmissionEvidence||'apply')+'/attempt.json');
  const result={checkedAt:new Date().toISOString(),model,productId:id,verified:Object.values(checks).every(Boolean),contentAndPriceVerified:Object.entries(checks).filter(([k])=>k!=='oldIdsKept').every(([,v])=>v)&&(!identityMigration||identityMigration.allMapped),identityMigration:identityMigration?{count:identityMigration.count,allMapped:identityMigration.allMapped,campaignBindingsVerified:false}:null,checks,auditPassed:latest?.title===p.title&&latest?.publishStatus===1&&latest?.publishTime>=Date.parse(attempt.startedAt)/1000-5,status:b.status,activeSkuCount:active.length,activeColors,prices:[...new Set(active.map(x=>x.price))],latestAudit:latest,base,audit};
  await save(dir+'/verification.json',result);console.log(JSON.stringify({model,verified:result.verified,auditPassed:result.auditPassed,status:b.status,checks,activeSkuCount:active.length,prices:result.prices}));
 }else{
  const v=await read(dir+'/verification.json');if(!v.verified||!v.auditPassed||v.status!==1)throw Error('Only verified warehouse pages can activate');
  const r=await client.setProductStatus([id],0,{evidenceDir:dir+'/activate'});if(r.failCount||!r.successProductIds?.includes(id))throw Error('Activation business failure: '+JSON.stringify(r.failReason));console.log(JSON.stringify({model,state:'ACTIVATION_ACCEPTED'}));
 }
 }catch(e){await save(dir+'/last-error.json',{mode,message:e.message,code:e.code||null,at:new Date().toISOString()});throw e;}
 await sleep(1500);
}
