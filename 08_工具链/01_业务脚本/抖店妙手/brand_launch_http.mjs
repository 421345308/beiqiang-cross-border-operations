// New brand-store preparation only. No create/edit/status/coupon/ad operations here.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {MiaoshouHttp} from './miaoshou_http.mjs';
const root='09_国内电商/抖店',dir=root+'/.local/品牌新店';
const read=async f=>JSON.parse(await fs.readFile(f,'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
async function save(f,v){await fs.mkdir(path.dirname(f),{recursive:true});await fs.writeFile(f+'.tmp',JSON.stringify(v,null,2)+'\n');await fs.rename(f+'.tmp',f);}
const pause=()=>new Promise(r=>setTimeout(r,1350));
const mode=process.argv[2];if(!['inspect','prepare'].includes(mode))throw Error('Usage: brand_launch_http.mjs inspect|prepare');
const profileFile='08_工具链/01_业务脚本/抖店妙手/.local/shops/brand/session.json';
const profile=await read(profileFile);
if(!profile.expectedShopId||!profile.expectedShopName)throw Error('Brand profile must contain a verified target shop');
const client=await MiaoshouHttp.fromSavedSession({sessionPath:profileFile,timeoutMs:45000});
const shop=await client.getShopIdentity();
if(shop.shopId!==String(profile.expectedShopId)||shop.shopName!==profile.expectedShopName)throw Error('Profile and current shop differ; do not prepare');
await save(dir+'/当前核验/identity-http.json',{...shop,checkedAt:new Date().toISOString()});
async function products(isDraft){let total=null;const ids=new Set(),rows=[];for(let page=1;page<=100;page++){await pause();const r=await client.listProducts({page,pageSize:100,isDraft});if(!Array.isArray(r.productList)||!Number.isInteger(r.total))throw Error('Product schema changed');if(total===null)total=r.total;if(r.total!==total)throw Error('Catalog changed during pagination');await save(dir+'/当前核验/'+(isDraft?'drafts':'products')+'-page-'+page+'.json',r);for(const row of r.productList){const id=row.productIdStr;if(!id||ids.has(id))throw Error('Missing exact product identity or duplicate page');ids.add(id);rows.push(row);}if(rows.length===total)return rows;if(!r.productList.length)throw Error('Incomplete catalog pagination');}throw Error('Pagination safety limit');}
const live=await products(false),drafts=await products(true);
const snapshot={shop,checkedAt:new Date().toISOString(),products:live.length,drafts:drafts.length,complete:true};
await save(dir+'/当前核验/catalog-summary.json',snapshot);
if(mode==='inspect'){
 await pause();await save(dir+'/当前核验/freight-http.json',await client.getFreightTemplates());
 console.log(JSON.stringify({state:'NEW_STORE_READ_CONNECTED',products:live.length,drafts:drafts.length}));
}else{
 if(live.length||drafts.length)throw Error('New store no longer empty; reconcile actual products before first-launch preparation');
 const plan=await read(root+'/数据/品牌首发商品.json');
 const all=Object.values(plan.models).flatMap(p=>[...p.main_assets,...p.detail_files]);
 if(plan.visual_qa?.state!=='PASSED'||plan.visual_qa.asset_set_sha256!==hash(Buffer.from(all.map(a=>a.sha256).join('\n'))))throw Error('Current whole asset set must pass visual QA');
 let cache={};try{cache=await read(dir+'/素材上传.json');}catch(e){if(e.code!=='ENOENT')throw e;}
 async function url(file,expected){const bytes=await fs.readFile(file),sha=hash(bytes);if(expected&&sha!==expected)throw Error('Asset changed after review');let entry=cache[sha];if(entry&&entry.shopId!==shop.shopId)throw Error('Upload cache belongs to another shop');if(!entry){await pause();const receipt=await client.uploadImage(file);if(typeof receipt.url!=='string'||!receipt.url.startsWith('https://'))throw Error('Upload response schema changed');entry={shopId:shop.shopId,file,sha256:sha,uploadedAt:new Date().toISOString(),receipt};cache[sha]=entry;await save(dir+'/素材上传.json',cache);}return entry.receipt.url;}
 for(const [model,p]of Object.entries(plan.models)){
  const main=[],details=[],colors=[];
  for(const a of p.main_assets)main.push(await url(a.path,a.sha256));
  for(const a of p.detail_files)details.push(await url(a.path,a.sha256));
  for(const c of p.media_binding.sku_color_files){const expected=p.sourceEvidence.find(a=>a.path===c.path)?.sha256;if(!expected)throw Error('Missing colour-source evidence');colors.push({color:c.color,url:await url(c.path,expected)});}
  await pause();const recommendation=await client.recommendCategory({name:p.title,mainImgUrls:main});
  await save(dir+'/商品准备/'+model+'/category-recommendation.json',recommendation);
  const chosen=recommendation.data?.recommendCategoryList?.find(x=>x.catePath==='鞋靴>男鞋>休闲鞋');
  if(!chosen)throw Error('Expected available casual category not recommended; inspect current evidence');
  const cateId=String(chosen.cateIds.filter(Boolean).at(-1));await pause();
  const rules=await client.getCategoryInfo(cateId);await save(dir+'/商品准备/'+model+'/category-rules.json',rules);
  const brands=rules.brandOption.filter(b=>b.nameCn===plan.brand.name);
  if(brands.length!==1)throw Error('Brand must resolve uniquely in current shop/category');
  const attr=(name,value)=>{const rule=rules.cateAttrList.find(a=>a.propertyName===name),option=rule?.options?.find(v=>v.name===value);if(!rule||!option)throw Error('Missing current attribute '+name+'/'+value);return [String(rule.propertyId),rule.type==='multi_select'?[String(option.valueId)]:String(option.valueId)];};
  const attrs=Object.fromEntries([attr('品牌',plan.brand.name),attr('鞋面材质','织物'),attr('鞋底材质','EVA'),attr('功能','保暖'),attr('闭合方式','套脚'),attr('鞋面内里材质','人造短毛绒'),attr('适用季节','冬季')]);
  // Brand attribute can contain legacy duplicate labels; bind the actual brandOption ID.
  if(!rules.cateAttrList.find(a=>a.propertyName==='品牌')?.options.some(v=>String(v.valueId)===String(brands[0].brandId)))throw Error('Brand option and attribute identity differ');
  attrs[String(rules.cateAttrList.find(a=>a.propertyName==='品牌').propertyId)]=String(brands[0].brandId);
  if(rules.cateAttrList.some(a=>a.required&&attrs[String(a.propertyId)]===undefined))throw Error('Additional required attribute must be reviewed');
  const prepared={model,shop,preparedAt:new Date().toISOString(),state:'ASSETS_UPLOADED_NOT_PRODUCT_CREATED',submit_ready:false,title:p.title,brand:plan.brand.name,pics:main,description:details,colorImages:colors,sizes:Array.from({length:p.sizes[1]-p.sizes[0]+1},(_,i)=>p.sizes[0]+i),version:'加绒',price:null,stock:null,freightId:null,mobile:null,deliveryDelayDay:null,threeGuarantees:null,coupon:null,unresolved:['新店定价与用券方案','真实发退货地址/服务电话、运费与履约配置','当前类目/品牌/尺码组件正式字段','实测与试穿、ZX9002真实绒里近照'],source_asset_set_sha256:plan.visual_qa.asset_set_sha256};
  prepared.cateId=cateId;prepared.catePath=chosen.catePath;prepared.standardBrandId=String(brands[0].brandId);prepared.attrValues=attrs;
  prepared.attribute_basis='原图与已确认来源支持的通用材料/结构判断，非成分测试；保暖为加绒日常用途，不承诺温标。品牌从新店当前规则匹配。';
  prepared.sku_count=colors.length*prepared.sizes.length;
  prepared.unresolved[2]='尺码组件须在最终范围与商业字段确认后独立新建；类目/品牌/必填属性已按当前规则准备';
  await save(dir+'/商品准备/'+model+'/prepared.json',prepared);
  console.log(JSON.stringify({model,state:prepared.state,main:main.length,details:details.length,colors:colors.length,recommendationKeys:Object.keys(recommendation)}));
 }
}
