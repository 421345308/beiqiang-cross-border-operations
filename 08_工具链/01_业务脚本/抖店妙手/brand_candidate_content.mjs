// Local candidate preparation only. Never creates products or changes existing listings.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const root='09_国内电商/抖店', privateRoot=root+'/.local/品牌新店';
const read=async f=>JSON.parse(await fs.readFile(f,'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
const planFile=root+'/数据/品牌首发商品.json',plan=await read(planFile);
const current=await read(privateRoot+'/来源/下一批候选.json');
const old={...(await read(root+'/数据/旧混款整理.json')).models,...(await read(root+'/数据/棉鞋内容优化.json')).models};
const definitions={
 A116:{source:'1547777',canonical:'BQ018',title:'雷丹森羊冬季加绒棉鞋男针织系带松紧可调低帮黑白全黑通勤休闲鞋',headline:['脚背松紧','自己调合适'],footer:'系带调节，结合脚背与袜厚选码',style:['黑白简洁轮廓','通勤穿搭少费心'],reason:'给喜欢简洁低帮外观、希望自己调整脚背松紧的通勤消费者。与套脚款的区别是系带调节，不宣称无需用手或专业运动性能。',hypothesis:'准确匹配冬季加绒、系带休闲鞋需求；首图清楚展示完整双鞋，详情先回答松紧调节和配码。观察点击后的选码咨询、支付与尺码退款。'},
 K6116:{source:'1763985',canonical:'BQ027',title:'雷丹森羊冬季加绒棉鞋男针织系带松紧可调立体底边黑白日常休闲鞋',headline:['针织纹理','搭出休闲感'],footer:'系带外观与立体底边，实物细节看得见',style:['立体底边轮廓','日常搭配有层次'],reason:'给重视鞋面纹理与侧面轮廓、日常搭长裤的消费者。用真实底边和编织细节区别A116；不把底边造型转写成回弹、防滑或增高数据。',hypothesis:'通过系带、针织、加绒和可辨认的外观匹配休闲穿搭需求；首图表现双鞋与底边，第二屏解释调节，减少只看外形误购。'},
 A212:{source:'2076977',canonical:'BQ048',title:'雷丹森羊冬季加绒棉鞋男针织一脚蹬免系带低帮黑白全黑日常休闲鞋',headline:['出门少一步','不用系鞋带'],footer:'一脚蹬结构，省去系鞋带步骤',style:['简洁针织轮廓','日常长裤好搭'],reason:'给不想反复系鞋带、喜欢简洁低帮鞋型的消费者。真实利益是省系带；脚背高低与袜厚仍影响穿着，不承诺免弯腰或无需用手。',hypothesis:'用一脚蹬、免系带和加绒版本清楚匹配需求；详情区分与系带款的选择，结合脚长、袜厚和脚背说明，观察误购和选码退款。'}
};
const candidates={};
for(const [model,d] of Object.entries(definitions)){
 if(plan.models[model]) throw Error('Style already exists; reconcile published product: '+model);
 if(plan.expansion_candidates?.models?.[model]?.publication?.state?.includes('CREATED')||plan.expansion_candidates?.models?.[model]?.publication?.private_content_evidence) throw Error('Candidate already submitted; do not rebuild '+model);
 if(plan.expansion_candidates?.models?.[model]?.commercial?.price_approved||plan.expansion_candidates?.models?.[model]?.acceptance?.visual_qa?.state==='PASSED') throw Error('Reviewed candidate exists; edit in place instead of resetting '+model);
 const source=current.find(x=>x.id===d.source),s=old[model];
 if(!source||!source.source_model.startsWith(model)||!s.color_names.every(c=>source.colors.includes(c))||source.sizes.join(',')!==Array.from({length:11},(_,i)=>String(35+i)).join(',')) throw Error('Source scope changed '+model);
 const titleWeight=[...d.title].reduce((n,c)=>n+(c.charCodeAt(0)>255?2:1),0);
 if(titleWeight!==60) throw Error('Title must contain 60 weighted characters '+model+': '+titleWeight);
 const folder='01_产品资产/02_可发布素材/抖店品牌首发/'+model+'/当前优化';
 await fs.mkdir(folder+'/实物主图',{recursive:true});
 const main_assets=[];
 const selected=model==='K6116'?[s.main_files[1],s.main_files[2],s.main_files[0]]:s.main_files.slice(0,3);
 for(const [i,src] of selected.entries()){
  const bytes=await fs.readFile(src),dest=folder+'/实物主图/主图0'+(i+1)+path.extname(src);
  await fs.writeFile(dest,bytes);main_assets.push({role:'同款实物角度'+(i+1),path:dest,source_photo:src,sha256:hash(bytes),bytes:bytes.length});
 }
 const sourceEvidence=await Promise.all([...new Set([...s.color_files,...s.main_files])].map(async f=>({path:f,sha256:hash(await fs.readFile(f))})));
 const p={...s,title:d.title,titleWeight,canonical_sku:d.canonical,canonical:'数据/'+(model==='K6116'?'棉鞋内容优化':'旧混款整理')+'.json#models.'+model,
  main_files:main_assets.map(a=>a.path),main_assets,detail_files:[],detail_output_dir:folder+'/详情',sourceEvidence,
  benefit_headline:d.headline,benefit_footer:d.footer,benefit_subtitle:'仅售加绒版 · 35—45码',scene_photo:main_assets[0].path,scene_kind:'actual_product',detail_photo:main_assets[0].path,upper_crop:null,
  style_headline:d.style,style_subtitle:'实物轮廓展示 · 日常休闲搭配',style_caption:model==='A116'?'外底纹路实拍，不替代性能测试':model==='K6116'?'立体底边造型，黑白与全黑可选':'简洁鞋面，日常搭配长裤',
  mixed_versions:false,versions:['加绒'],sizes:[35,45],colors:s.color_names,
  choice_copy:'仅售加绒版。尺码表为参考脚长，非实测鞋内长；结合脚背和袜厚选择，不确定请咨询。',guarantee_days:90,
  media_binding:{version:'加绒',colors:s.color_names,sku_color_files:s.color_names.map((color,i)=>({color,path:s.color_files[i]}))},
  source_current:{...source,scope:'当前来源加绒颜色尺码与原包对应；共享旧属性不当作加绒材料证明，非实物库存盘点'},
  purchase_reason:d.reason,recommendation_hypothesis:d.hypothesis,
  commercial:{sale_price_cny:null,coupon_cny:5,target_price_cny:null,proposal:'建议沿新店日常价层级94减5、券后89；本轮新增款价格尚未确认，不填作已批准',price_approved:false},
  publication:{state:'LOCAL_CANDIDATE_NOT_SUBMITTED',catalog_duplicate_check:'PENDING_SESSION_RENEWAL',dynamic_category:'PENDING',sku_count:22,real_measurements:'PENDING',price_approved:false},
  acceptance:{visual_qa:'PENDING',real_fleece_closeup:'PENDING_FACTORY',label_photo:'PENDING_FACTORY',buyer_preview:'NOT_CREATED',app_checkout:'NOT_CREATED'}};
 for(const key of ['platform_id','product_id','route','active_colors_before','price_edit','visual_qa','visual_qa_scope','white_fleece_version','forecast_price','title_current','status','buyer_verification','previous_title','before_latest_revision_title','before_consumer_title','consumer_visual_qa','current_coupon_pricing','title_weight'])delete p[key];
 candidates[model]=p;
}
plan.expansion_candidates={updated_on:'2026-10-20',authorization:'负责人要求继续按规范上贝强工厂店商品、逐款优化；新款定价建议与已批准价格分开。',state:'LOCAL_PREPARATION_SESSION_RENEWAL_REQUIRED',models:candidates};
await fs.writeFile(planFile,JSON.stringify(plan,null,2)+'\n');
await fs.writeFile(privateRoot+'/商品准备/下一批内容渲染.json',JSON.stringify({models:candidates},null,2)+'\n');
console.log(JSON.stringify({candidates:Object.keys(candidates),publishedProductsChanged:0,priceApproval:false}));
