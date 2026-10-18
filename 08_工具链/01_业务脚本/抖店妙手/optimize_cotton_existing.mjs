// Update reviewed content on the existing four cotton products; never creates listings.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
import {MiaoshouHttp} from './miaoshou_http.mjs';
const root='09_国内电商/抖店';
const load=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const plan=await load(root+'/数据/棉鞋内容优化.json');
const progress=await load(root+'/.local/执行进度.json');
const model=process.argv[2],mode=process.argv[3]||'prepare';
if(!Object.hasOwn(plan.models,model)||!['prepare','apply','verify'].includes(mode))throw Error('Select reviewed model and prepare/apply/verify');
const p=plan.models[model];
const object=progress.new_cotton.products.find(x=>x.model===model&&x.status===0);
if(!object)throw Error('No existing active listing identity');
const productId=object.productId;
const revision=process.argv[4]||'';if(revision&&!/^[a-z0-9-]+$/.test(revision))throw Error('Invalid evidence revision');
const evidence=`${root}/.local/evidence/content-optimization/${model}${revision?'/'+revision:''}`;
await fs.mkdir(evidence,{recursive:true});
const client=await MiaoshouHttp.fromSavedSession({timeoutMs:45000});
const save=async(file,data)=>{const out=`${evidence}/${file}.json`;await fs.writeFile(out+'.tasktmp',JSON.stringify(data,null,2)+'\n');await fs.rename(out+'.tasktmp',out);};
function expectedSku(base){return base.specPrices.map(s=>({id:String(s.skuId),price:s.price,code:s.code,status:s.skuStatus})).sort((a,b)=>a.id.localeCompare(b.id));}
let phase=mode;
try {
if(mode==='prepare'){
 phase='read-current-base';
 const before=await client.getProductBase(productId);const b=before.productInfo;
 if(b.productIdStr!==productId||b.cid!==1000007614)throw Error('Identity/category changed');
 await save('before',before);
 phase='read-category';const category=await client.getCategoryInfo(String(b.cid));await save('category',category);
 const mainHash=new Set();const files=[...p.main_files,...p.color_files,...p.detail_files.map(x=>x.path)];
 let uploads={};try{uploads=await load(`${evidence}/uploads.json`);}catch(e){if(e.code!=='ENOENT')throw e;if(revision)uploads=await load(`${root}/.local/evidence/content-optimization/${model}/uploads.json`);}
 for(const file of [...new Set(files)]){
  const raw=await fs.readFile(file),sha=createHash('sha256').update(raw).digest('hex');
  if(p.main_files.includes(file))mainHash.add(sha);
  if(p.detail_files.some(d=>d.path===file)&&mainHash.has(sha))throw Error('Exact main/detail duplicate');
  if(!uploads[sha]){phase='upload:'+path.basename(file);await new Promise(r=>setTimeout(r,1200));const result=await client.uploadImage(file);uploads[sha]={url:result.url,sha256:sha,local:file};await save('uploads',uploads);}
 }
 const urlOf=async file=>uploads[createHash('sha256').update(await fs.readFile(file)).digest('hex')].url;
 const images=await Promise.all(p.main_files.map(urlOf));const details=await Promise.all(p.detail_files.map(x=>urlOf(x.path)));
 const colorMap={};for(let i=0;i<p.color_names.length;i++)colorMap[p.color_names[i]]=await urlOf(p.color_files[i]);
 const colors=b.specs.find(x=>x.propertyId===2752).values.map(x=>x.name);
 if(colors.some(x=>!colorMap[x]))throw Error('Colour identity mismatch');
 phase='recommend-category';await new Promise(r=>setTimeout(r,2500));const recommended=await client.recommendCategory({name:p.title,mainImgUrls:images});await save('recommendation',recommended);
 if(!recommended.data.recommendCategoryList.some(x=>x.cateIds.map(String).includes(String(b.cid))))throw Error('Current category not recommended');
 const attrs={'1687':String(b.standardBrandId)};
 for(const [id,list]of Object.entries(b.productFormatNew)){
  const rule=category.cateAttrList.find(x=>String(x.propertyId)===id);if(!rule)throw Error('Attribute schema mismatch '+id);
  const values=list.map(x=>rule.type==='text'||x.diyType===1?x.name:String(x.value));
  attrs[id]=rule.type==='multi_select'?values:values[0];
 }
 const payload={productId,cateId:String(b.cid),changeFields:['base','mainImg','descImg'],title:p.title,sourceTitle:b.name,standardBrandId:String(b.standardBrandId),attrValues:attrs,categoryPropertyPics:{},
 isEvaluateOpened:b.isEvaluateOpened,shortProductName:b.shortProductName,recommendRemark:b.recommendRemark,mobile:(b.mobile||'').trim(),freightId:String(b.freightId),weightValue:b.weightValue,weightUnit:b.weightUnit,limitPerBuyer:b.limitPerBuyer,maximumPerOrder:b.maximumPerOrder,minimumPerOrder:b.minimumPerOrder,supply7dayReturn:b.afterSaleService.supplyDayReturnSelector,remark:b.extra?.stone?.remark||'',referencePrice:b.referencePrice||'',referencePriceCertificateType:b.referencePriceCertificate?.certificateType||'',referencePriceCertificateUrls:b.referencePriceCertificate?.certificateUrls||'',presellType:b.presellType,presellConfigLevel:b.presellConfigLevel,namePrefix:b.namePrefix,nameSuffix:b.nameSuffix,isSaveNewShareableSizTemplate:false,threeGuaranteesServiceType:String(b.afterSaleServiceV2.threeGuarantees.serviceType),threeGuaranteesDuration:String(b.afterSaleServiceV2.threeGuarantees.duration),isLargeProduct:b.afterSaleServiceV2.isLargeProduct?'1':'0',sizeInfoTemplateId:b.sizeInfoTemplateId,sizeInfoTemplateUrl:'',
 pics:images,description:details,specPic:colors.map(c=>colorMap[c]),mainImageThreeToFour:b.mainImageThreeToFour||[],whiteBgImgUrl:b.whiteBackGroundPicUrl||'',categoryRecommendCheckStr:recommended.data.categoryRecommendCheckStr,categoryRecommendId:recommended.data.categoryRecommendId};
 const weight=[...p.title].reduce((n,c)=>n+(c.charCodeAt(0)<128?1:2),0);if(weight>60||weight<55||images.length<3||details.length!==8)throw Error('Content completeness check failed');
 if(Object.hasOwn(payload,'specPricesV2')||payload.changeFields.includes('sku'))throw Error('Content operation must not write commercial SKU fields');
 const assetHashes=await Promise.all(files.map(async file=>({file,sha256:createHash('sha256').update(await fs.readFile(file)).digest('hex')})));
 await save('prepared',{payload,assetHashes,titleWeight:weight,baselineSku:expectedSku(b),detailCount:details.length,mainCount:images.length,productId});
 console.log(JSON.stringify({model,state:'PREPARED',titleWeight:weight,mainImages:images.length,detailScreens:details.length}));
}else if(mode==='apply'){
 const prepared=await load(`${evidence}/prepared.json`);
 for(const a of prepared.assetHashes){if(createHash('sha256').update(await fs.readFile(a.file)).digest('hex')!==a.sha256)throw Error('Reviewed asset changed after preparation');}
 const fresh=await client.getProductBase(productId);
 if(JSON.stringify(expectedSku(fresh.productInfo))!==JSON.stringify(prepared.baselineSku))throw Error('SKU identity/price changed since preparation: re-review');
 const fields=['freightId','deliveryDelayDay','sizeInfoTemplateId','standardBrandId'];const old=(await load(`${evidence}/before.json`)).productInfo;
 if(fields.some(k=>String(fresh.productInfo[k])!==String(old[k])))throw Error('Commercial baseline changed');
 phase='submit-content';const result=await client.saveProduct(prepared.payload,{evidenceDir:`${evidence}/apply`});
 console.log(JSON.stringify({model,state:'SUBMITTED',result:result.result}));
}else{
 const prepared=await load(`${evidence}/prepared.json`);const before=(await load(`${evidence}/before.json`)).productInfo;
 const base=await client.getProductBase(productId);const audit=await client.getProductAudit(productId);await save('after',{base,audit});
 const b=base.productInfo;
 const sameImage=(a,b)=>new URL(a).pathname===new URL(b).pathname;
 const detailUpdateRequired=prepared.payload.description.some(x=>!before.descriptionImgList.some(y=>sameImage(x,y)));
 const detailChanged=b.descriptionImgList.some((x,i)=>!before.descriptionImgList[i]||!sameImage(x,before.descriptionImgList[i]));
 let mainSequenceMatches=true;
 if(revision){const previous=(await load(`${root}/.local/evidence/content-optimization/${model}/prepared.json`)).payload.pics;
 mainSequenceMatches=prepared.payload.pics.every((x,i)=>{const ix=previous.findIndex(y=>sameImage(x,y));return ix>=0&&sameImage(b.pic[i],before.pic[ix]);});}
 const content={mainSequenceMatches,expectedDetailChangeLanded:!detailUpdateRequired||detailChanged,title:b.name===prepared.payload.title,mainCount:b.pic.length===prepared.mainCount,detailCount:b.descriptionImgList.length===8,detailDistinct:new Set(b.descriptionImgList.map(x=>new URL(x).pathname)).size===8,mainDetailDisjoint:!b.descriptionImgList.some(x=>b.pic.some(y=>new URL(x).pathname===new URL(y).pathname)),mainUnique:new Set(b.pic.map(x=>new URL(x).pathname)).size===prepared.mainCount,colorImageCount:b.specPics.length===p.color_names.length};
 const commerce={skuPriceCodeIdentity:JSON.stringify(expectedSku(b))===JSON.stringify(prepared.baselineSku),freight:b.freightId===before.freightId,dispatch:b.deliveryDelayDay===before.deliveryDelayDay,sizeTemplate:b.sizeInfoTemplateId===before.sizeInfoTemplateId,returns:isDeepStrictEqual(b.afterSaleService,before.afterSaleService),guarantees:isDeepStrictEqual(b.afterSaleServiceV2,before.afterSaleServiceV2)};
 const latest=[...audit.auditList].sort((a,b)=>b.publishTime-a.publishTime)[0];
 const result={model,productId,content,commerce,actualTitle:b.name,mainCount:b.pic.length,detailCount:b.descriptionImgList.length,skuCount:b.specPrices.length,prices:[...new Set(b.specPrices.map(x=>x.price))],status:b.status,latestAudit:latest,verified:Object.values(content).every(Boolean)&&Object.values(commerce).every(Boolean),auditPassed:latest?.title===p.title&&latest?.publishStatus===1&&latest?.publishTime>=Date.parse((await load(`${evidence}/apply/attempt.json`)).startedAt)/1000-5};
 await save('verification',result);console.log(JSON.stringify({model,verified:result.verified,auditPassed:result.auditPassed,title:b.name,mainImages:result.mainCount,detailScreens:result.detailCount,skuCount:result.skuCount,prices:result.prices}));
}

}catch(e){await save('last-error',{model,mode,phase,code:e.code||null,message:e.message,time:new Date().toISOString()});throw e;}
