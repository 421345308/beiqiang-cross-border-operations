// Revise the two existing brand listings; no price, stock, SKU or fulfillment writes.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
import {MiaoshouHttp} from './miaoshou_http.mjs';
import {invariant,skuInvariant,originalColorPictures} from './focus_media_update.mjs';
const require=createRequire(import.meta.url);
const root='09_国内电商/抖店',priv=root+'/.local/品牌新店';
const file=root+'/数据/品牌首发商品.json';
const read=async f=>JSON.parse(await fs.readFile(f,'utf8'));
const save=async(f,v)=>{await fs.mkdir(path.dirname(f),{recursive:true});await fs.writeFile(f,JSON.stringify(v,null,2)+'\n');};
const sha=b=>createHash('sha256').update(b).digest('hex');
const pause=()=>new Promise(r=>setTimeout(r,2200));
const weight=t=>[...t].reduce((n,c)=>n+(c.charCodeAt(0)>127?2:1),0);
const [mode,model]=process.argv.slice(2);
const plan=await read(file);
if(mode==='build'){
 if(Object.values(plan.models).some(p=>/^(SUBMITTED|BACKEND)/.test(p.publication?.content_revision_state||'')))throw Error('A live content revision exists; do not rebuild or reset its acceptance state');
 const {Resvg}=require(path.resolve('99_临时区/抖店棉鞋优化/runtime/node_modules/@resvg/resvg-js'));
 const cotton='01_产品资产/02_可发布素材/抖店棉鞋_20261014/';
 // Native SVG layouts retain source pixels. No generated angles or repainted shoe details.
 const sources={
  A1689:[
   ['整鞋黑白',cotton+'A1689/优化/素材/净图_blackwhite.png',1254,1254,[36,465,1185,640]],
   ['整鞋全黑',cotton+'A1689/优化/素材/净图_allblack.png',1254,1254,[40,520,1180,570]],
   ['外底实物','01_产品资产/02_可发布素材/抖店品牌首发/A1689/来源/工厂原图_3.jpg',800,800,[90,300,620,300]]
  ],
  ZX9002:[
   ['双鞋斜面',cotton+'ZX9002/优化/工厂补充_双鞋.jpg',800,800,null],
   ['整鞋侧面',cotton+'ZX9002/工厂来源原图_4.jpg',800,800,null],
   ['实物外底',cotton+'ZX9002/工厂来源原图_3.jpg',800,800,null]
  ]
 };
 const titles={A1689:'雷丹森羊冬季加绒棉鞋男针织一脚蹬免系带套脚保暖黑白全黑休闲鞋',ZX9002:'雷丹森羊冬季加绒棉鞋男针织一脚蹬免系带套脚保暖大码日常休闲鞋'};
 for(const [m,rows]of Object.entries(sources)){
  const p=plan.models[m],assets=[];
  for(const [i,[role,src,w,h,crop]]of rows.entries()){
   const bytes=await fs.readFile(src),folder=`01_产品资产/02_可发布素材/抖店品牌首发/${m}/当前优化/实物主图`;
   await fs.mkdir(folder,{recursive:true});
   const view=crop||[0,0,w,h];
   const native=`<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"><rect width="800" height="800" fill="${m==='A1689'?'#e6ecee':'#b8b8b8'}"/><svg width="800" height="800" viewBox="${view.join(' ')}" preserveAspectRatio="xMidYMid meet"><defs><clipPath id="photo"><rect x="${view[0]}" y="${view[1]}" width="${view[2]}" height="${view[3]}"/></clipPath></defs><image clip-path="url(#photo)" width="${w}" height="${h}" href="data:image/${src.endsWith('.png')?'png':'jpeg'};base64,${bytes.toString('base64')}"/></svg></svg>`;
   const stem=`${folder}/主图0${i+1}_${role}`,out=new Resvg(native).render().asPng();
   await fs.writeFile(stem+'.svg',native);await fs.writeFile(stem+'.png',out);
   assets.push({role,path:stem+'.png',source:stem+'.svg',width:800,height:800,sha256:sha(out),bytes:out.length,source_photo:src,source_sha256:sha(bytes),source_crop:crop});
  }
  p.title=titles[m];p.titleWeight=weight(p.title);p.main_assets=assets;p.main_files=assets.map(a=>a.path);
  p.main_rule_review={checked_on:'2026-10-18',rule:'商品信息发布规范3.4',no_overlay_text:true,generated_shoe_angles:false,note:m==='A1689'?'保留完整前景鞋与真实外底，来源另只露部分外底；需补同一加绒实物的独立正斜面/后跟照片，进一步改善首图占比和多角度。':'三张真实来源：整鞋侧面、斜面双鞋与外底；真实绒里近照仍待补拍。'};
  p.publication={...p.publication,content_revision:'TITLE_60_CHAR_AND_REAL_PHOTO_MAIN',content_revision_state:'LOCAL_PENDING_VISUAL_QA'};
 }
 plan.visual_qa={...plan.visual_qa,state:'PENDING_REVISION_REVIEW',asset_set_sha256:sha(Buffer.from(Object.values(plan.models).flatMap(p=>[...p.main_assets,...p.detail_files]).map(a=>a.sha256).join('\n')))};
 await save(file,plan);console.log(JSON.stringify({state:'LOCAL_REVISION_BUILT',titles:Object.fromEntries(Object.entries(plan.models).map(([m,p])=>[m,{title:p.title,characters:p.titleWeight}]))}));
}else{
 if(!['prepare','apply','verify'].includes(mode)||!plan.models[model])throw Error('Usage: build | prepare|apply|verify A1689|ZX9002');
 const p=plan.models[model],revision=sha(Buffer.from(p.title+'\n'+p.main_assets.map(a=>a.sha256).join('\n'))).slice(0,16);
 const dir=priv+'/发布/'+model+'/内容修订/'+revision;
 const c=await MiaoshouHttp.fromSavedSession({sessionPath:'08_工具链/01_业务脚本/抖店妙手/.local/shops/brand/session.json',timeoutMs:45000});
 const profile=await read('08_工具链/01_业务脚本/抖店妙手/.local/shops/brand/session.json');
 const shop=await c.getShopIdentity();if(shop.shopId!==String(profile.expectedShopId)||shop.shopName!==profile.expectedShopName)throw Error('Target store changed');
 const receipt=await read(priv+'/发布/'+model+'/create/response.json'),id=receipt.productId;
 if(typeof id!=='string'||!/^\d+$/.test(id))throw Error('Exact existing product ID required');
 const protectedState=b=>{const v=invariant(b);delete v.name;return v;};
 if(mode==='prepare'){
  const all=Object.values(plan.models).flatMap(p=>[...p.main_assets,...p.detail_files]);
  if(plan.visual_qa.state!=='PASSED'||plan.visual_qa.asset_set_sha256!==sha(Buffer.from(all.map(a=>a.sha256).join('\n'))))throw Error('Current asset set has not passed visual QA');
  if(weight(p.title)!==60)throw Error('Reviewed 60-character title required');
  const b=await c.getProductBase(id);await pause();const s=await c.getProductSku(id);
  if(b.productInfo.productIdStr!==id||b.productInfo.status!==0)throw Error('Existing on-sale product differs');
  const urls=[],cacheFile=priv+'/素材上传.json',cache=await read(cacheFile);
  for(const a of p.main_assets){const bytes=await fs.readFile(a.path);if(sha(bytes)!==a.sha256)throw Error('Reviewed asset changed');let v=cache[a.sha256];if(v&&v.shopId!==shop.shopId)throw Error('Cross-store upload cache');if(!v){await pause();v={shopId:shop.shopId,file:a.path,sha256:a.sha256,uploadedAt:new Date().toISOString(),receipt:await c.uploadImage(a.path)};cache[a.sha256]=v;await save(cacheFile,cache);}urls.push(v.receipt.url);}
  const payload={productId:id,cateId:String(b.productInfo.cid),changeFields:['title','mainImg'],title:p.title,pics:urls,specPic:originalColorPictures(b.productInfo),mainImageThreeToFour:b.productInfo.mainImageThreeToFour||[],whiteBgImgUrl:b.productInfo.whiteBackGroundPicUrl||''};
  await save(dir+'/prepared.json',{payload,before:b,skuBefore:s,protected:protectedState(b.productInfo),skuProtected:skuInvariant(s),assets:p.main_assets});
  console.log(JSON.stringify({model,revision,state:'PREPARED'}));
 }else{
  const pre=await read(dir+'/prepared.json');await pause();const b=await c.getProductBase(id);await pause();const s=await c.getProductSku(id);
  const unchanged=isDeepStrictEqual(protectedState(b.productInfo),pre.protected)&&isDeepStrictEqual(skuInvariant(s),pre.skuProtected);
  if(mode==='apply'){
   if(!unchanged)throw Error('Protected fields drifted; do not write');
   for(const a of pre.assets)if(sha(await fs.readFile(a.path))!==a.sha256)throw Error('Asset drifted');
   let attempt='apply';
   if(process.argv.includes('--retry-qps')){
    const failure=await read(dir+'/apply/failure.json');
    if(failure.code!=='ddApiLocalQpsLimit')throw Error('Retry only allowed after an explicit rate-limit rejection');
    if(b.productInfo.name===p.title)throw Error('Current title already revised; verify instead of retrying');
    attempt='apply-qps-retry';
   }
   await c.saveProduct(pre.payload,{evidenceDir:dir+'/'+attempt});p.publication.content_revision_state='SUBMITTED_PENDING_READBACK';await save(file,plan);console.log(JSON.stringify({model,state:'SUBMITTED',attempt}));
  }else{
   await pause();const audit=await c.getProductAudit(id),last=[...audit.auditList].sort((a,b)=>b.publishTime-a.publishTime)[0];
   const checks={protectedFieldsUnchanged:unchanged,title:b.productInfo.name===p.title,mainCount:b.productInfo.pic.length===p.main_assets.length,auditPassed:last?.title===p.title&&last.publishStatus===1};
   const result={checkedAt:new Date().toISOString(),model,productId:id,checks,verified:Object.values(checks).every(Boolean),pixelComparison:'PENDING',buyerPreview:'PENDING',base:b,sku:s,audit};await save(dir+'/verification.json',result);
   p.publication.content_revision_state=result.verified?'BACKEND_VERIFIED_MEDIA_PIXEL_PENDING':'READBACK_FAILED';p.publication.audit=checks.auditPassed?'PASSED':'PENDING';p.publication.private_content_evidence=dir.replace(root+'/','');await save(file,plan);
   console.log(JSON.stringify({model,verified:result.verified,checks}));if(!result.verified)process.exitCode=2;
  }
 }
}
