// Explicit first-launch executor. Private authorization and receipts are required.
import fs from 'node:fs/promises';
import path from 'node:path';
import {MiaoshouHttp} from './miaoshou_http.mjs';
const dir='09_国内电商/抖店/.local/品牌新店';
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const save=async(p,v)=>{await fs.mkdir(path.dirname(p),{recursive:true});await fs.writeFile(p,JSON.stringify(v,null,2)+'\n');};
const pause=()=>new Promise(r=>setTimeout(r,1350));
const mode=process.argv[2],model=process.argv[3];
if(!['sizes','prepare-product','publish','verify'].includes(mode)||!['A1689','ZX9002'].includes(model))throw Error('Usage: sizes|prepare-product|publish|verify A1689|ZX9002');
const c=await MiaoshouHttp.fromSavedSession({sessionPath:'08_工具链/01_业务脚本/抖店妙手/.local/shops/brand/session.json',timeoutMs:45000});
const a=await read(dir+'/履约授权.json'),p=await read(dir+'/商品准备/'+model+'/prepared.json');
const profile=await read('08_工具链/01_业务脚本/抖店妙手/.local/shops/brand/session.json');
const shop=await c.getShopIdentity();
if(!profile.expectedShopId||shop.shopId!==String(profile.expectedShopId)||shop.shopName!==profile.expectedShopName||shop.shopId!==a.shopId||shop.shopId!==p.shop.shopId)throw Error('Shop identity differs');
if(a.sale_price_cny!==94||a.coupon_cny!==5||a.stock_per_sku!==100||a.delivery_delay_day!==1)throw Error('Explicit approved baseline differs');
const out=dir+'/发布/'+model;
if(mode!=='verify'){
 let created=false;try{await fs.access(out+'/create/response.json');created=true;}catch(e){if(e.code!=='ENOENT')throw e;}
 if(created)throw Error('This launch already has a creation receipt; reconcile the existing product instead of recreating templates or listings');
}
if(mode==='sizes'){
 const payload={cateId:p.cateId,sizeTempSubType:'shoes',selectedSpecs:['脚长(cm)'],specOptions:['脚长(cm)'],templateId:null,fixedSizeName:'尺码',specMap:{'尺码':p.sizes.map(String),'脚长(cm)':p.sizes.map(s=>String((s-35)*.5+22.5))},title:'尺码推荐',tempName:`雷丹森羊${model}加绒标准参考`,desc:'标准参考脚长，非实测鞋内长；厚袜及脚型不同请咨询选码',isShareable:'0'};
 const r=await c.saveSizeTemplate(payload,{evidenceDir:out+'/size-create'});
 if(!r.data?.templateId||!r.data?.componentFrontData)throw Error('Size creation response schema changed; inspect receipt');
 await pause();await save(out+'/size-readback.json',await c.getSizeTemplateInfo(r.data.templateId));
 console.log(JSON.stringify({model,sizeTemplateCreated:true,rows:p.sizes.length}));
}
if(mode==='prepare-product'){
 if(!a.freight_id||!a.address_verified)throw Error('Saved address and actual new-store freight template required');
 const freight=await c.getFreightTemplates();
 if(!freight.freightTemplatedList.some(x=>String(x.template.id)===a.freight_id))throw Error('Freight template not found in target store');
 await pause();const rules=await c.getCategoryInfo(p.cateId);await save(out+'/rules-current.json',rules);
 if(!rules.brandOption.some(b=>String(b.brandId)===p.standardBrandId&&b.nameCn==='雷丹森羊'))throw Error('Brand changed');
 const size=await read(out+'/size-create/response.json');
 const rule=rules.productSpecRule.requiredSpecDetails.find(x=>String(x.sellPropertyId)==='4709');
 const options=rule.propertyValues;
 const vals=p.sizes.map(s=>{const v=options.find(v=>String(v.sellPropertyValueName)===String(s));if(!v)throw Error('Current size option missing '+s);return {valueName:String(s),oriValueName:String(s),valueId:v.sellPropertyValueId};});
 await pause();const rec=await c.recommendCategory({name:p.title,mainImgUrls:p.pics});await save(out+'/recommendation.json',rec);
 if(!rec.data.recommendCategoryList.some(x=>x.cateIds.map(String).includes(p.cateId)))throw Error('Category no longer recommended');
 const old=await read('09_国内电商/抖店/.local/evidence/ZX9002-create-request-attempt4.json');
 // Inherit the observed field shape, never the old store's IDs or commercial values.
 const payload={...old,cateId:p.cateId,title:p.title,standardBrandId:p.standardBrandId,attrValues:{...p.attrValues,'3171':model},categoryPropertyPics:Object.fromEntries(Object.keys({...p.attrValues,'3171':model}).map(k=>[k,{}])),pics:p.pics,description:p.description,
 specValues:[{propertyId:2752,propertyName:'颜色分类',values:p.colorImages.map(v=>({valueName:v.color,oriValueName:v.color,valueId:0}))},{propertyId:4709,propertyName:'鞋码大小',values:vals}],
 specPricesV2:p.colorImages.flatMap((v,i)=>p.sizes.map(s=>({price:94,stock:100,stockNum:100,code:`LDSY-${model}-F-${i+1}-${s}`,skuStatus:true,sellProperties:[{isPresellSpecValue:false,propertyName:'颜色分类',oriValueName:v.color,valueName:v.color},{isPresellSpecValue:false,propertyName:'鞋码大小',oriValueName:String(s),valueName:String(s)}]}))),
 specPic:p.colorImages.map(v=>v.url),freightId:a.freight_id,mobile:a.mobile,deliveryDelayDay:'1',supply7dayReturn:'7-1',afterSaleServiceV2:{three_guarantees:{service_type:'1',duration:'90'}},sizeInfoTemplateId:size.data.templateId,sizeInfoTemplateUrl:'',componentFrontData:size.data.componentFrontData,templateName:size.data.templateName,sizeTempType:'shoes',shareable:false,
 categoryRecommendId:rec.data.categoryRecommendId,categoryRecommendCheckStr:rec.data.categoryRecommendCheckStr,commit:1,status:0};
 if(payload.specPricesV2.length!==p.sku_count||payload.pics.length!==5||payload.description.length!==8)throw Error('Prepared asset/SKU count differs');
 await save(out+'/payload.json',payload);console.log(JSON.stringify({model,prepared:true,skus:payload.specPricesV2.length,price:94,couponTarget:89}));
}
if(mode==='publish'){
 const payload=await read(out+'/payload.json');
 const list=await c.listProducts({pageSize:100,isDraft:false});await pause();const drafts=await c.listProducts({pageSize:100,isDraft:true});
 if(list.total!==list.productList.length||drafts.total!==drafts.productList.length)throw Error('Full catalog reconciliation needed');
 if([...list.productList,...drafts.productList].some(x=>x.name===p.title||JSON.stringify(x).includes(`LDSY-${model}-`)))throw Error('Potential existing launch; reconcile instead of creating');
 await pause();const r=await c.createProduct(payload,{evidenceDir:out+'/create'});console.log(JSON.stringify({model,receipt:r}));
}
if(mode==='verify'){
 const receipt=await read(out+'/create/response.json');const id=String(receipt.productId??receipt.data?.productId??'');
 if(!/^\d+$/.test(id))throw Error('Inspect exact product ID in creation receipt');
 for(const [key,fn]of [['base',()=>c.getProductBase(id)],['sku',()=>c.getProductSku(id)],['audit',()=>c.getProductAudit(id)]]){await pause();await save(out+'/'+key+'-readback.json',await fn());}
 console.log(JSON.stringify({model,productId:id,readbackSaved:true}));
}
