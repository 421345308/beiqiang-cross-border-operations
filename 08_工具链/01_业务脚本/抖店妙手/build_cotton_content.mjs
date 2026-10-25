// Native SVG information design. Real product photos remain embedded, not repainted.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const require = createRequire(import.meta.url);
const runtime = process.env.BEIQIANG_RESVG_MODULE || '99_临时区/抖店棉鞋优化/runtime/node_modules/@resvg/resvg-js';
const {Resvg} = require(path.resolve(runtime));
const root=process.cwd(), file=process.argv[2]||'09_国内电商/抖店/数据/棉鞋内容优化.json';
const reviewFile=process.argv[3]||'09_国内电商/抖店/.local/棉鞋内容新版审核.html';
const plan=JSON.parse(await fs.readFile(file,'utf8'));
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const cache=new Map();
async function photo(file){if(!cache.has(file)){const b=await fs.readFile(file);cache.set(file,`data:image/${file.toLowerCase().endsWith('.png')?'png':'jpeg'};base64,${b.toString('base64')}`);}return cache.get(file);}
const hash=b=>createHash('sha256').update(b).digest('hex');
const rect=(x,y,w,h,fill,rx=0,extra='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" ${extra}/>`;
function text(x,y,s,size=30,fill='#252b29',weight=400,extra=''){return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}" ${extra}>${esc(s)}</text>`;}
function wrap(s,max){const rows=[];let line='',len=0;for(const c of s){const n=c.charCodeAt(0)>255?1:.55;if(len+n>max&&!/[，。；？！、]/u.test(c)){rows.push(line);line='';len=0;}line+=c;len+=n;}if(line)rows.push(line);return rows;}
function para(x,y,s,size=27,width=688,fill='#636760',lineHeight=43){return wrap(s,width/size).map((r,i)=>text(x,y+i*lineHeight,r,size,fill)).join('');}
async function img(file,x,y,w,h,{cover=false,crop=null,round=20}={}){
 const id='clip'+(++imgId);const uri=await photo(file);
 const pic=crop?`<svg x="${x}" y="${y}" width="${w}" height="${h}" viewBox="${crop.join(' ')}" preserveAspectRatio="xMidYMid slice"><image href="${uri}" x="0" y="0" width="800" height="800"/></svg>`:`<image href="${uri}" x="${x}" y="${y}" width="${w}" height="${h}" preserveAspectRatio="${cover?'xMidYMid slice':'xMidYMid meet'}"/>`;
 return `<defs><clipPath id="${id}">${rect(x,y,w,h,'#fff',round)}</clipPath></defs><g clip-path="url(#${id})">${rect(x,y,w,h,'#fff',round)}${pic}</g>`;
}
let imgId=0;
function svg(model,index,height,accent,body){return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="800" height="${height}" viewBox="0 0 800 ${height}" font-family="Microsoft YaHei">${rect(0,0,800,height,'#f5f1e9')}${rect(56,38,46,4,accent)}${text(116,48,'日常休闲系列',20,accent,600)}${body}${rect(56,height-54,688,1,'#d9d6cd')}${text(56,height-24,'日常休闲 · 按规格选择版本',18,'#777a72')}${text(744,height-24,String(index).padStart(2,'0')+' / 08',18,'#777a72',400,'text-anchor="end"')}</svg>`;}
function head(title,sub,accent){return text(56,132,title,52,'#242b27',700)+para(56,187,sub,27,688,accent);}
const catalog=[];
for(const [model,p]of Object.entries(plan.models)){
 const fleece=p.fleece!==false;
 if(process.argv[4]&&process.argv[4]!=='--review-only'&&model!==process.argv[4])continue;
 if(process.argv[4]==='--review-only'){catalog.push({model,title:p.title,main:p.main_files,details:p.detail_files});continue;}
 const dir=p.detail_output_dir||path.join('99_临时区/商品素材制作/抖店',model,'优化','详情');await fs.mkdir(dir,{recursive:true});
 const pages=[];
 // 1. Interest first: a daily scene and a specific wearing benefit.
 let b=text(56,144,p.benefit_headline[0],78,'#252c27',700)+text(56,237,p.benefit_headline[1],78,'#252c27',700)+text(56,282,p.benefit_subtitle,26,p.accent);
 b+=await img(p.scene_photo,0,310,800,730,{cover:true,round:0});
 b+=rect(56,983,p.scene_kind==='ai_styling'?286:300,40,'#242b27',7,'fill-opacity=".82"')+text(72,1011,p.scene_kind==='actual'?'同款外观上脚展示':p.scene_kind==='actual_product'?'实物外观展示':'AI穿搭场景示意',23,'#fff');
 b+=text(56,1097,p.benefit_footer,33,p.accent,700)+text(56,1142,'日常通勤  /  下楼买菜  /  饭后散步',25,'#676d63');
 pages.push(['01_出门场景与穿着利益',1220,b]);
 // 2. Explain comfort through visible, real construction; crop the original photo.
 b=head('日常舒适，从合脚开始',p.closure==='套脚'?'免去系鞋带步骤，让日常出门省事一点':p.closure==='系带'?'松紧自己调，穿着更合自己的脚背':'穿前先核对脚型与尺码，日常选鞋更清楚',p.accent);
 b+=await img(p.main_files[0],56,244,688,410,{crop:p.upper_crop,round:22});
 b+=rect(76,596,280,40,'#fff',8,'fill-opacity=".94"')+text(94,624,'鞋面与穿脱结构 · 实物展示',20,p.accent,600);
 const features=[p.upper_feature||['针织鞋面','织物鞋面，搭配日常休闲穿着。'],[p.closure==='套脚'?'省去系带步骤':p.closure==='系带'?'脚背松紧自己调':'鞋带装饰外观',p.closure==='套脚'?'套脚鞋口设计，出门少一道系鞋带的步骤。':p.closure==='系带'?'系带可以调整松紧，结合脚背和袜厚选择。':'选码结合脚型与穿袜厚度，合脚是日常舒适的开始。'],p.rear_feature];
 features.forEach((a,i)=>{const y=722+i*142;b+=rect(56,y-31,54,54,p.accent,14)+text(83,y+6,String(i+1).padStart(2,'0'),24,'#fff',700,'text-anchor="middle"')+text(130,y,a[0],36,'#252c27',700)+para(130,y+49,a[1],26,610,'#656e62',39);});
 pages.push(['02_舒适好穿结构讲解',1200,b]);
 // 3. Winter value and everyday situations, without fabricating a fleece macro.
 b=rect(0,82,800,1054,'#a35b3c')+text(56,164,'天凉的时候',66,'#fff6e9',700)+text(56,250,'换上加绒这一款',66,'#fff6e9',700)+para(56,306,'人造短毛绒内里，为日常出门添一层暖意。',27,688,'#fff0dd');
 b+=await img(p.warmth_photo||p.detail_photo,56,356,688,420,{round:22});
 b+=rect(76,715,246,40,'#242b27',7,'fill-opacity=".82"')+text(92,743,p.warmth_photo?'加绒鞋口与内里实拍':'鞋型与配色实拍展示',22,'#fff');
 ['通勤路上','下楼买菜','饭后散步'].forEach((s,i)=>{const x=56+i*232;b+=rect(x,824,220,116,'#fff3e4',16)+text(x+110,877,s,31,'#8a482e',700,'text-anchor="middle"')+text(x+110,915,'秋冬日常穿着',21,'#8a6550',400,'text-anchor="middle"');});
 b+=text(56,1016,'认准颜色规格里的「加绒」标识',33,'#fff6e9',700)+para(56,1070,'按自己的脚型、脚背与穿袜习惯，参考脚长选择合适尺码。',25,688,'#ffe8d2',39);
 if(!fleece){
  b=head('日常这一双，先看结构',p.daily_subtitle||'常规版本 · 结合场景、脚型与袜厚选择',p.accent);
  b+=await img(p.detail_photo,56,260,688,570,{round:22});
  b+=text(56,905,p.daily_headline||'把款式和穿着选择看清楚',38,p.accent,700);
  b+=para(56,968,p.daily_copy||'本商品为常规内里版本；下单前核对配色与尺码。脚背、袜厚和脚型不同，穿着感受也有差异。',27,688,'#636760',43);
 }
 pages.push([fleece?'03_加绒日常场景':'03_常规版本与穿着选择',1200,b]);
 // 4. Distinctive styling, supported by actual outsole and profile photos.
 b=text(56,146,p.style_headline[0],72,'#252c27',700)+text(56,236,p.style_headline[1],72,'#252c27',700)+text(56,286,p.style_subtitle,26,p.accent);
 b+=await img(p.sole_photo,56,326,688,570,{round:22});
 b+=rect(56,928,688,144,'#fff',20)+text(84,982,p.style_caption,34,p.accent,700)+para(84,1029,(p.sole?'外底材质：'+p.sole+'  ·  ':'')+p.color_names.join(' / '),25,630,'#6a7067',37);
 pages.push(['04_轮廓搭配与外底实拍',1150,b]);

 // 5. True colour variants.
 b=head(p.color_names.length===1?'这款配色，日常好搭':'先选配色，再选尺码',p.mixed_versions?'加绒重点配色；常规版及其他配色见商品规格':'本款当前售卖的'+(fleece?'加绒':'常规')+'颜色规格',p.accent);
 if(p.color_names.length===1){b+=await img(p.color_files[0],56,250,688,610,{round:24});b+=text(400,925,p.color_names[0],42,p.accent,700,'text-anchor="middle"');}
 else{for(let i=0;i<p.color_names.length;i++){const y=240+i*340,range=p.color_size_ranges?.[p.color_names[i]];b+=await img(p.color_files[i],56,y,370,300,{round:20});b+=text(458,y+133,p.color_names[i],34,p.accent,700)+text(458,y+182,range?range[0]+'—'+range[1]+'码':fleece?'加绒版本':'常规版本',24,'#686e66');}}
 const colorNoteY=Math.max(978,240+p.color_names.length*340+28);
 b+=para(56,colorNoteY,p.choice_copy,22,688);
 pages.push(['05_颜色规格选择',Math.max(1100,colorNoteY+130),b]);
 // 6. Complete readable product parameters.
 b=head('商品信息，一页看清','下单前核对款式、材质、颜色和尺码',p.accent);
 const facts=[['可选版本',p.mixed_versions?'常规 / 加绒':fleece?'加绒款':'常规款'],['鞋面材质',p.upper||'织物'],['内里材质',p.mixed_versions?'按常规 / 加绒规格区分':fleece?'人造短毛绒':p.inner],['外底材质',p.sole],['闭合方式',p.closure],['穿着选择',p.mixed_versions?'按气温选择内里版本':fleece?'秋冬日常穿着':'日常休闲穿着'],['可选颜色',p.mixed_versions?'配色以商品规格为准':p.color_names.join(' / ')],['可选尺码',p.start_size+'—'+p.end_size+'码']].filter(([,value])=>value);
 facts.forEach(([k,v],i)=>{const y=238+i*90,units=[...String(v)].reduce((n,c)=>n+(c.charCodeAt(0)>255?1:.55),0),fontSize=Math.min(29,Math.floor(420/Math.max(1,units)));b+=rect(56,y,688,86,i%2?'#ebe7de':'#fff',10)+text(82,y+54,k,29,'#73796d')+(fontSize<21?para(288,y+34,v,24,420,'#283126',32):text(288,y+54,v,fontSize,'#283126',600));});
 b+=para(56,979,p.size_range_note||(p.mixed_versions?'常规与加绒分别选择，请核对商品颜色规格中的版本。':fleece?'本页展示加绒款，请按颜色规格中的加绒标识选购。':'本页展示常规款，请按配色、脚长、脚背及袜厚选购。'),24,688);
 pages.push(['06_商品参数',1100,b]);
 // 7. Authorized foot-length guidance, not inner-shoe measurements.
 b=head('按脚长参考选码','标准尺码参考  ·  单位：厘米',p.accent);
 b+=rect(56,232,688,62,p.accent,12)+text(224,274,'鞋码',30,'#fff',700,'text-anchor="middle"')+text(574,274,'参考脚长',30,'#fff',700,'text-anchor="middle"');
 for(let size=p.start_size;size<=p.end_size;size++){const n=size-p.start_size,y=304+n*53;b+=rect(56,y,688,49,n%2?'#ebe7de':'#fff',8)+text(224,y+35,String(size),28,'#283126',500,'text-anchor="middle"')+text(574,y+35,String(22.5+(size-35)*.5),28,'#283126',500,'text-anchor="middle"');}
 const sy=324+(p.end_size-p.start_size+1)*53;
 b+=text(56,sy+20,'脚长怎么量？',34,p.accent,700)+para(56,sy+70,'脚跟贴墙站立，测量脚跟到最长脚趾的距离；两脚分别测量，参考较长的一只。',25,688)+para(56,sy+180,(p.size_range_note?p.size_range_note+' ':'')+'尺码表为选码参考，非鞋内长。不同脚型、脚背与穿袜厚度会影响穿着感受。',22,688,'#777b72',36);
 pages.push(['07_脚长尺码指南',Math.max(1210,sy+310),b]);
 // 8. Policy information, matching existing shop configuration.
 b=head('下单与售后，都写清楚','发货、运费及服务按店铺现行规则办理',p.accent);
 const policy=[['次日发货','具体预计发货时间，请以订单页面展示为准。'],['包邮范围','偏远地区按运费模板计费，下单前核对收货地址运费。'],['7天无理由','退换货按平台及店铺规则办理，商品应符合退换条件。'],[(p.guarantee_days||90)+'天寄修','保修期内提供维修（寄修），申请方式请联系店铺客服。']];
 policy.forEach(([h,c],i)=>{const y=242+i*178;b+=rect(56,y,688,160,'#fff',20)+rect(56,y+20,5,56,p.accent,2)+text(84,y+57,h,39,p.accent,700)+para(84,y+106,c,25,626,'#666d62',36);});
 b+=para(56,998,'运费险按实际保险规则赔付，售后以平台及店铺处理结果为准。',22,688);
 pages.push(['08_发货与售后服务',1120,b]);
 const files=[];
 for(let i=0;i<pages.length;i++){
  const [name,height,body]=pages[i],source=svg(model,i+1,height,p.accent,body),svgPath=path.join(dir,name+'.svg'),pngPath=path.join(dir,name+'.png');
  await fs.writeFile(svgPath,source);
  const rendered=new Resvg(source,{font:{fontFiles:['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/msyhbd.ttc'],loadSystemFonts:false,defaultFontFamily:'Microsoft YaHei'},fitTo:{mode:'width',value:800}}).render().asPng();
  await fs.writeFile(pngPath,rendered);
  files.push({role:name,path:pngPath.replaceAll('\\','/'),source:svgPath.replaceAll('\\','/'),width:800,height,sha256:hash(rendered),bytes:rendered.length});
 }
 p.detail_files=files;p.layout_method='原生SVG信息排版，嵌入实物照片；产品摄影不由排版程序重画';
 catalog.push({model,title:p.title,main:p.main_files,details:files});
 console.log(JSON.stringify({model,detailScreens:files.length,totalBytes:files.reduce((a,f)=>a+f.bytes,0),mainImages:p.main_files.length}));
}
if(process.argv[4]!=='--review-only') {
plan.status='LOCAL_ASSETS_RENDERED_NEEDS_VISUAL_QA';
await fs.writeFile(file+'.tasktmp',JSON.stringify(plan,null,2)+'\n');await fs.rename(file+'.tasktmp',file);
}
const uri=file=>'file:///'+path.resolve(file).replaceAll('\\','/');
let html='<!doctype html><meta charset="utf-8"><title>棉鞋新版商品内容审核</title><style>body{font-family:Microsoft YaHei;background:#eeede8;color:#222;margin:0;padding:24px}section{max-width:1280px;margin:auto auto 50px}h1{font-size:30px}h2{font-size:26px}.title{background:white;padding:20px;font-size:20px}.main{display:flex;gap:10px;overflow:auto;margin:20px 0}.main img{height:220px}.details{display:flex;gap:12px;overflow:auto}.details figure{min-width:320px;margin:0}.details img{width:320px;vertical-align:top}figcaption{font-size:14px;margin-bottom:8px}</style><h1>消费者商品页 · 内容审核</h1><p>标题、主图与8屏独立详情；这是本地新版，发布状态以项目入口为准。</p>';
for(const c of catalog){html+=`<section><h2>${esc(c.model)}</h2><p class="title">${esc(c.title)}</p><div class="main">${(await Promise.all(c.main.map(async f=>`<img src="${await photo(f)}">`))).join('')}</div><div class="details">${(await Promise.all(c.details.map(async f=>`<figure><figcaption>${esc(f.role)}</figcaption><a href="${uri(f.path)}"><img src="${await photo(f.path)}"></a></figure>`))).join('')}</div></section>`;}
await fs.writeFile(reviewFile,html);
