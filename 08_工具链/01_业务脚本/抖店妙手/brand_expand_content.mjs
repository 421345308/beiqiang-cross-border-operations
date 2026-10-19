// Native layouts for the explicitly approved four new brand styles. No external mutation.
import fs from 'node:fs/promises';import path from 'node:path';import {createHash} from 'node:crypto';import {createRequire} from 'node:module';
const root='09_国内电商/抖店',file=root+'/数据/品牌首发商品.json';
const read=async f=>JSON.parse(await fs.readFile(f,'utf8')),sha=b=>createHash('sha256').update(b).digest('hex');
const plan=await read(file),batch=await read(root+'/数据/棉鞋上品包.json');
const old={...(await read(root+'/数据/旧混款整理.json')).models,...(await read(root+'/数据/棉鞋内容优化.json')).models};
const titles={M889:'雷丹森羊冬季加绒棉鞋男针织系带松紧可调黑白全黑米白日常休闲鞋',H7212:'雷丹森羊冬季加绒棉鞋男针织一脚蹬免系带包头低帮黑白日常休闲鞋',ZX2116:'雷丹森羊冬季加绒棉鞋男针织系带松紧可调大码黑白全黑日常休闲鞋',ZX9507:'雷丹森羊冬季加绒棉鞋男针织一脚蹬免系带大码黑杏全黑日常休闲鞋'};
const require=createRequire(import.meta.url),{Resvg}=require(path.resolve('99_临时区/抖店棉鞋优化/runtime/node_modules/@resvg/resvg-js'));
for(const [model,title]of Object.entries(titles)){
 if(plan.models[model])throw Error('Style already present; do not reset '+model);
 const s=old[model],factory=await read(root+'/.local/品牌新店/来源/'+model+'.json');
 if(!factory.colors||!s.color_names.every(c=>factory.colors.includes(c))||factory.sizes.length!==s.end_size-s.start_size+1)throw Error('Current factory scope differs '+model);
 const folder='01_产品资产/02_可发布素材/抖店品牌首发/'+model+'/当前优化';await fs.mkdir(folder+'/实物主图',{recursive:true});
 let photos=s.main_files.slice(0,3);if(model==='H7212')photos=[s.main_files[1],s.main_files[2],s.main_files[0]];
 if(model==='ZX2116'){
  const src=s.main_files[2],bytes=await fs.readFile(src),crop=[35,25,365,750];
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"><rect width="800" height="800" fill="#eee"/><svg width="800" height="800" viewBox="${crop.join(' ')}" preserveAspectRatio="xMidYMid meet"><defs><clipPath id="sole"><rect x="35" y="25" width="365" height="750"/></clipPath></defs><image clip-path="url(#sole)" width="800" height="800" href="data:image/jpeg;base64,${bytes.toString('base64')}"/></svg></svg>`;
  const stem=folder+'/实物主图/外底独立实物';await fs.writeFile(stem+'.svg',svg);await fs.writeFile(stem+'.png',new Resvg(svg).render().asPng());photos[2]=stem+'.png';
 }
 const assets=[];for(const [i,src]of photos.entries()){const bytes=await fs.readFile(src),dest=folder+'/实物主图/主图0'+(i+1)+(src.endsWith('.png')?'.png':'.jpg');await fs.writeFile(dest,bytes);assets.push({role:model==='ZX2116'&&i===2?'同款外底实物':model==='H7212'&&i===2?'同款外观上脚':`实物主图${i+1}`,path:dest,source_photo:src,sha256:sha(bytes),bytes:bytes.length});}
 const realScene=assets[0].path,all=[...new Set([...s.color_files,...s.main_files,realScene])];
 const sourceEvidence=await Promise.all(all.map(async f=>({path:f,sha256:sha(await fs.readFile(f))})));
 const price=['M889','H7212'].includes(model)?94:97;
 const p={...s,canonical:'数据/'+(['M889','H7212'].includes(model)?'旧混款整理':'棉鞋内容优化')+'.json#models.'+model,title,titleWeight:60,shortTitle:model==='H7212'?'加绒包头套脚休闲鞋':s.closure==='系带'?'加绒针织系带休闲鞋':'加绒大码套脚休闲鞋',sizes:[s.start_size,s.end_size],versions:['加绒'],colors:s.color_names,mixed_versions:false,main_files:assets.map(a=>a.path),main_assets:assets,detail_files:[],detail_output_dir:folder+'/详情',scene_photo:realScene,scene_kind:'actual_product',upper_crop:null,detail_photo:realScene,sourceEvidence,choice_copy:'本商品只售加绒版；按配色、脚长、脚背与袜厚选择，尺码表为参考脚长，非鞋内长实测。',benefit_subtitle:'仅售加绒版 · '+s.start_size+'—'+s.end_size+'码',guarantee_days:90,
  source_current:{url:factory.url,source_model:factory.source_model,observed_at:factory.observed_at,price:factory.price,selected_colors:s.color_names,sizes:factory.sizes,scope:'加绒颜色及原包对应；来源普通属性不覆盖加绒版本，非实物库存盘点'},
  media_binding:{version:'加绒',colors:s.color_names,sku_color_files:s.color_names.map((color,i)=>({color,path:s.color_files[i]}))},
  commercial:{sale_price_cny:price,coupon_cny:5,target_price_cny:price-5,approved_on:'2026-10-19',approval:'负责人明确按建议分档：M889/H7212券后89；ZX2116/ZX9507券后92；已有两款价格不变',cost_basis:'来源标价与负责人约50元成本分别记录，不视为已结算进价'},
  publication:{state:'LOCAL_EXPANSION_APPROVED_NEEDS_VISUAL_QA',product_id:null,size_measurements:'PENDING_FACTORY',price_approved:true},
  main_rule_review:{no_overlay_text:true,shoe_repainted:false,note:model==='M889'?'三色完整双鞋；仍需补独立后跟及外底角度，不把配色差异当性能证据。':model==='ZX2116'?'只取共有真实外底区域，排除常规灰色内里；待补完整加绒双鞋多角度。':'真实外观照片，保持本款结构与配色；补实际加绒内里和随货标签。'}};
 if(model==='M889'){p.benefit_footer='加绒系带休闲鞋，脚背松紧自己调';p.style_subtitle='仅售加绒版 · 日常休闲';}
 if(model==='ZX2116'){p.sole_photo=assets[2].path;p.style_headline=['外底纹路','实物细节看清楚'];p.style_subtitle='真实外底展示 · 纹路不替代性能实测';p.caption='外底纹路，按实物外观展示';}
 // Reuse content evidence only; the old shop's acceptance and coupon states are not portable.
 for(const key of ['platform_id','product_id','route','active_colors_before','price_edit','visual_qa','visual_qa_scope','white_fleece_version','forecast_price','title_current','status','buyer_verification','previous_title','before_latest_revision_title','before_consumer_title','consumer_visual_qa','current_coupon_pricing','title_weight'])delete p[key];
 plan.models[model]=p;
}
plan.updated_on='2026-10-19';plan.state='FOUR_ADDITIONAL_STYLES_APPROVED_CONTENT_PREPARATION';plan.visual_qa={state:'PENDING_EXPANSION_REVIEW',prior:'首发两款验收证据保留，新四款未验收'};
await fs.writeFile(file,JSON.stringify(plan,null,2)+'\n');console.log(JSON.stringify({added:Object.keys(titles),existingProductsPreserved:2}));
