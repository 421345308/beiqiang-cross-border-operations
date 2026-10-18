// Local typography and contact sheets; embeds existing real photographs unchanged.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
const {Resvg}=require(path.resolve(process.env.BEIQIANG_RESVG_MODULE||'99_临时区/抖店棉鞋优化/runtime/node_modules/@resvg/resvg-js'));
const root='09_国内电商/抖店',media='01_产品资产/02_可发布素材/抖店品牌首发';
const plan=JSON.parse(await fs.readFile(root+'/数据/品牌首发商品.json','utf8'));
const x=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const rect=(a,b,w,h,c)=>`<rect x="${a}" y="${b}" width="${w}" height="${h}" fill="${c}"/>`;
const text=(a,b,s,n=30,c='#283b30',w=400)=>`<text x="${a}" y="${b}" font-size="${n}" fill="${c}" font-weight="${w}">${x(s)}</text>`;
async function img(f,a,b,w,h){const data=await fs.readFile(f);return `<image href="data:image/${f.endsWith('.png')?'png':'jpeg'};base64,${data.toString('base64')}" x="${a}" y="${b}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet"/>`;}
async function render(file,w,h,body){const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" font-family="Microsoft YaHei">${rect(0,0,w,h,'#f4f3ed')}${body}</svg>`;const bytes=new Resvg(svg,{font:{fontFiles:['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/msyhbd.ttc'],loadSystemFonts:false}}).render().asPng();await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file+'.svg',svg);await fs.writeFile(file+'.png',bytes);return {path:file+'.png',source:file+'.svg',width:w,height:h,sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length};}
const dir=media+'/品牌展示草案';const assets=[];
assets.push({...await render(dir+'/文字头像草案',512,512,rect(24,24,464,464,'#304b3d')+text(90,232,'雷丹',142,'#f8f4e9',700)+text(90,400,'森羊',142,'#f8f4e9',700)),role:'文字头像设计草案，未上传店铺，不冒充商标注册图样'});
const a='01_产品资产/02_可发布素材/抖店棉鞋_20261014/A1689/优化/素材/净图_blackwhite.png',z='01_产品资产/02_可发布素材/抖店棉鞋_20261014/ZX9002/优化/工厂补充_双鞋.jpg';
assets.push({...await render(dir+'/店招设计草案',1600,600,rect(0,0,760,600,'#304b3d')+text(58,133,'雷丹森羊',84,'#fff7e7',700)+text(58,238,'日常出门',62,'#fff7e7',700)+text(58,320,'先选适合自己的鞋',58,'#fff7e7',700)+text(60,435,'套脚免系带 / 加绒版本 / 按款选码',28,'#e3e9dc')+await img(a,780,70,390,420)+await img(z,1190,70,390,420)+text(800,550,'加绒套脚｜黑白 / 全黑',25)+text(1210,550,'加绒大码｜38—47码',25)),role:'店招排版草案，1600×600为设计画布；未核平台槽位规格，未发布'});
for(const [model,p]of Object.entries(plan.models)){
 const heroSvg=await fs.readFile(p.main_assets[0].source,'utf8');
 const end=heroSvg.lastIndexOf('</svg>');
 const brandAd=heroSvg.slice(0,end)+rect(480,5,308,43,'#fff9ed')+text(498,36,'雷丹森羊',27,'#304b3d',700)+heroSvg.slice(end);
 const bytes=new Resvg(brandAd,{font:{fontFiles:['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/msyhbd.ttc'],loadSystemFonts:false}}).render().asPng();
 const file=media+'/'+model+'/广告草案/品牌文字版';await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file+'.svg',brandAd);await fs.writeFile(file+'.png',bytes);
 assets.push({model,role:'广告静态素材草案；品牌文字位于画面外，无投放',path:file+'.png',source:file+'.svg',width:800,height:800,sha256:createHash('sha256').update(bytes).digest('hex')});
 const reviewDir=root+'/.local/品牌新店/视觉核验';await fs.mkdir(reviewDir,{recursive:true});
 for(const [name,images]of [['主图',p.main_assets],['详情上',p.detail_files.slice(0,4)],['详情下',p.detail_files.slice(4)]]){
  const cols=name==='主图'?5:4,tile=360,h=800;
  let body='';for(let i=0;i<images.length;i++){const asset=images[i];body+=text(i*tile+8,30,asset.role,19)+await img(asset.path,i*tile+4,46,tile-8,h-58);}
  await render(reviewDir+'/'+model+'_'+name,cols*tile,h,body);
 }
 p.media_binding={version:'加绒',colors:p.colors,sku_color_files:[],note:'颜色规格图从当前来源档案逐色绑定；正式准备时按文件哈希和颜色名核，不把广告图填入SKU'};
 // Store explicit source colour identities; never infer them from list position at upload time.
 const source=JSON.parse(await fs.readFile(root+'/数据/'+(model==='A1689'?'旧混款整理':'棉鞋内容优化')+'.json','utf8')).models[model];
 p.media_binding.sku_color_files=p.colors.map((color,i)=>({color,path:source.color_files[i]}));
}
plan.brand_assets=assets;
plan.state='LOCAL_CONTENT_PREPARED_PENDING_VISUAL_AND_COMMERCIAL';
await fs.writeFile(root+'/数据/品牌首发商品.json',JSON.stringify(plan,null,2)+'\n');
const rel=f=>path.relative(path.resolve(root+'/.local'),path.resolve(f)).split(path.sep).map(encodeURIComponent).join('/');
let review=await fs.readFile(root+'/.local/品牌首发图文审核.html','utf8');
review=review.replace('重点商品实测与拍摄.html','品牌首发实测与拍摄.html');
review=review.replace('</main>',`<section><h2>品牌展示与广告草案</h2><p>文字头像、店招及广告中的品牌文字均为设计草案；无鞋面Logo合成，没有发布装修或启动投放。</p><div class="gallery">${assets.map(a=>`<figure><img src="${rel(a.path)}"><figcaption>${x(a.role)}</figcaption></figure>`).join('')}</div></section></main>`);
await fs.writeFile(root+'/.local/品牌首发图文审核.html',review);
console.log(JSON.stringify({models:Object.keys(plan.models),main:10,detail:16,brand_assets:assets.length,review:root+'/.local/品牌首发图文审核.html'}));
