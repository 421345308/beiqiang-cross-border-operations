// Native SVG editorial layouts. Source photographs are embedded without repainting.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
const {Resvg}=require(path.resolve('99_临时区/抖店棉鞋优化/runtime/node_modules/@resvg/resvg-js'));
const root='09_国内电商/抖店',media='01_产品资产/02_可发布素材/抖店重点优化';
const cotton=JSON.parse(await fs.readFile(root+'/数据/棉鞋内容优化.json','utf8'));
const old=JSON.parse(await fs.readFile(root+'/数据/旧混款整理.json','utf8'));
const raw='01_产品资产/01_原始数据包/抖店加绒鞋包_M889_20261014/图片/';
const retro=media+'/RETRO0594/来源/';
const plan={schema_version:1,updated_on:'2026-10-17',state:'PREPARED_PENDING_LIVE_READ',scope:'仅标题、主图、详情及对应消费者短标题；价格、优惠、SKU、库存、运费、尺码组件与品牌属性保持现状',brand:{name:'雷丹森羊',direction:'负责人明确的自主品牌方向',platform_registration:'待核',assets:'待负责人提供位置',publication:'本轮不将无品牌字段改为该品牌；品牌名含羊不代表羊毛材质'},models:{}};
const specs={
 ZX9002:{canonical:'数据/棉鞋内容优化.json#models.ZX9002',...cotton.models.ZX9002,title:'秋冬加绒棉鞋男士针织一脚蹬免系带大码日常休闲鞋',shortTitle:'男士加绒套脚休闲鞋',hook:['秋冬出门','少一道系带步骤'],sub:'针织套脚 · 加绒款 · 38—47码',color:'#485b62',closure:'套脚',a:cotton.models.ZX9002.main_files[0],b:cotton.models.ZX9002.detail_photo,c:cotton.models.ZX9002.sole_photo,heroCrop:null,structureCrop:[70,180,650,440],fleece:null,regular:false,guide:'这款为加绒版，按本款尺码表参考脚长；厚袜、脚背较高时先核对穿着余量。',notes:[['针织鞋口','套脚设计，省去系鞋带这一步。'],['后跟提环','穿鞋时可辅助提拉后跟。'],['立体外底','深色配色，鞋底轮廓清楚可见。']]},
 A1689:{canonical:'数据/旧混款整理.json#models.A1689',...old.models.A1689,title:'针织一脚蹬休闲鞋男女款免系带日常出门常规加绒可选',shortTitle:'针织套脚休闲鞋',hook:['下楼走走','套上就出门'],sub:'免系带套脚 · 常规 / 加绒可选',color:'#536c60',closure:'套脚',a:old.models.A1689.main_files[0],b:old.models.A1689.color_files[0],c:old.models.A1689.color_files[1],heroCrop:null,structureCrop:[60,330,670,460],fleece:raw+'A1689黑白加绒.jpg',fleeceCrop:[0,0,292,292],regular:true,guide:'套脚鞋口需兼顾脚长和脚背；常规、加绒的包裹感可能不同，厚袜不要直接照搬薄袜选码。',notes:[['套脚鞋口','不需要系鞋带，穿脱前看清鞋口与脚背。'],['针织纹理','近看鞋面编织，按实际颜色选择。'],['黑白 / 全黑','两种配色，按日常裤装和个人喜好选择。']]},
 M889:{canonical:'数据/旧混款整理.json#models.M889',...old.models.M889,title:'针织系带休闲鞋男女款松紧可调日常通勤常规加绒可选',shortTitle:'针织系带休闲鞋',hook:['脚背松紧','自己调一调'],sub:'系带设计 · 日常休闲 · 常规 / 加绒可选',color:'#806b52',closure:'系带',a:raw+'M889黑白加绒.JPG',b:old.models.M889.color_files[1],c:old.models.M889.color_files[2],heroCrop:[0,180,800,510],structureCrop:[120,185,575,290],fleece:raw+'M889黑白加绒.JPG',fleeceCrop:[410,215,320,170],regular:true,guide:'先用脚长选参考码，再通过系带调整脚背松紧；系带可调不等于所有脚型都合适。',notes:[['系带调节','按脚背调整松紧，不强行勒紧鞋带。'],['前后提环','穿鞋时可辅助整理鞋舌与后跟。'],['立体侧墙','黑白、全黑与米白，轮廓和配色分别看。']]},
 RETRO0594:{canonical:'数据/重点商品优化.json#models.RETRO0594',title:'针织系带休闲鞋男女款日常百搭黑白米白全黑加绒可选',shortTitle:'日常系带休闲鞋',hook:['日常裤装','搭出自己的样子'],sub:'针织系带 · 黑白 / 米白 / 全黑 · 加绒可选',color:'#77705b',closure:'系带',a:retro+'平台主图_3.jpg',b:retro+'平台主图_2.jpg',c:retro+'平台主图_4.jpg',heroCrop:[0,125,800,510],structureCrop:[70,185,660,290],fleece:null,regular:true,start_size:35,end_size:45,sole:'EVA',color_names:['黑白','米白色','全黑'],color_files:[retro+'平台主图_2.jpg',retro+'平台主图_3.jpg',retro+'平台主图_4.jpg'],guide:'先核对颜色与内里版本，再按本款脚长参考选码；喜欢的外观不代替合脚确认。',notes:[['针织鞋面','织物纹理与配色，近看更清楚。'],['系带结构','根据自己的脚背调整松紧。'],['立体鞋底轮廓','配普通牛仔裤、休闲裤，先看自己喜欢的整体比例。']],source_scope:'现有平台独立链接照片与字段；未凭889货号合并到M889，未宣称升级效果或耐久/吸汗性能'}
};
const x=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const hash=b=>createHash('sha256').update(b).digest('hex');
const R=(a,b,c,d,f,rx=0)=>`<rect x="${a}" y="${b}" width="${c}" height="${d}" fill="${f}" rx="${rx}"/>`;
const T=(a,b,s,size=28,color='#25332f',weight=400,other='')=>`<text x="${a}" y="${b}" font-size="${size}" fill="${color}" font-weight="${weight}" ${other}>${x(s)}</text>`;
function lines(s,n=24){let out=[],t='';for(const c of s){if(t.length>=n&&!/[，。、；：]/.test(c)){out.push(t);t='';}t+=c;}if(t)out.push(t);return out;}
const P=(a,b,s,size=26,width=688,color='#5d6962',lh=43)=>lines(s,Math.floor(width/size)).map((v,i)=>T(a,b+i*lh,v,size,color)).join('');
let serial=0;const cache=new Map();
function dimensions(b){if(b[0]===137)return [b.readUInt32BE(16),b.readUInt32BE(20)];for(let i=2;i<b.length;){if(b[i]!==255){i++;continue;}const marker=b[i+1];i+=2;if(marker===0xd8||marker===0xd9)continue;const n=b.readUInt16BE(i);if([0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf].includes(marker))return [b.readUInt16BE(i+5),b.readUInt16BE(i+3)];i+=n;}throw Error('Image dimensions not found');}
async function I(file,a,b,w,h,crop=null){if(!cache.has(file)){const bytes=await fs.readFile(file);const [iw,ih]=dimensions(bytes);cache.set(file,{uri:`data:image/${bytes[0]===137?'png':'jpeg'};base64,${bytes.toString('base64')}`,iw,ih});}const {uri,iw,ih}=cache.get(file),id='clip'+serial++;return `<defs><clipPath id="${id}">${R(a,b,w,h,'#fff',18)}</clipPath></defs><g clip-path="url(#${id})">${R(a,b,w,h,'#fff',18)}${crop?`<svg x="${a}" y="${b}" width="${w}" height="${h}" viewBox="${crop.join(' ')}" preserveAspectRatio="xMidYMid meet"><image href="${uri}" width="${iw}" height="${ih}"/></svg>`:`<image href="${uri}" x="${a}" y="${b}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet"/>`}</g>`;}
function page(body,h=1100){return `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="${h}" viewBox="0 0 800 ${h}" font-family="Microsoft YaHei">${R(0,0,800,h,'#f4f3ed')}${body}</svg>`;}
function header(title,sub,color){return R(48,40,54,5,color)+T(116,54,'日常休闲 · 选对自己的鞋',20,color,600)+T(48,142,title,50,'#26332d',700)+P(48,192,sub,25,704,color);}
function footer(p,h){return R(48,h-60,704,1,'#d7ddd6')+T(48,h-25,p.regular?'常规 / 加绒可选 · 内里版本以所选规格为准':'秋冬加绒款 · 颜色尺码以所选规格为准',20,'#667265');}
const box=(a,b,w,h,title,body,c)=>R(a,b,w,h,'#fff',18)+T(a+24,b+48,title,32,c,700)+P(a+24,b+94,body,25,w-48);
function footDiagram(y){return `<g transform="translate(62 ${y})">${R(0,0,676,260,'#fff',18)}<path d="M125 216 C78 198 79 163 98 128 C111 101 102 59 127 40 C151 22 189 24 204 56 C220 93 205 131 213 164 C221 204 190 226 163 226Z" fill="#dce7df" stroke="#627a6a" stroke-width="3"/><path d="M270 30 L270 226 M260 40 L270 30 L280 40 M260 216 L270 226 L280 216" fill="none" stroke="#627a6a" stroke-width="3"/>${T(315,75,'站立量脚长',33,'#2e4c39',700)}${P(315,125,'脚跟贴墙，量到最长脚趾；左右脚各量一次，参考较长的一只。',25,315)}${T(315,225,'测量方法示意，非鞋楦尺寸',19,'#768477')}</g>`;}
async function writeAsset(model,role,body,h){const folder=`${media}/${model}/当前优化`;await fs.mkdir(folder,{recursive:true});const svg=page(body,h),png=new Resvg(svg,{font:{fontFiles:['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/msyhbd.ttc'],loadSystemFonts:false}}).render().asPng();const file=folder+'/'+role;await fs.writeFile(file+'.svg',svg);await fs.writeFile(file+'.png',png);return {role,path:file+'.png',source:file+'.svg',width:800,height:h,sha256:hash(png),bytes:png.length};}
for(const [model,p]of Object.entries(specs)){
 const weight=[...p.title].reduce((a,c)=>a+(c.charCodeAt(0)>255?2:1),0);if(weight>60)throw Error(model+' title too long '+weight);
 const mains=[],details=[];
 let body=R(0,0,800,800,'#fff')+R(0,0,800,170,p.color)+T(42,74,p.hook[0],50,'#fff',700)+T(42,139,p.hook[1],50,'#fff',700)+await I(p.a,14,184,772,490,p.heroCrop)+T(42,724,p.sub,29,p.color,700)+T(42,770,p.regular?'看清内里版本，再选颜色尺码':'套脚设计 · 结合脚长和穿袜习惯选码',21,'#68776d');
 mains.push(await writeAsset(model,'主图01_选购理由',body,800));
 body=header(p.closure==='套脚'?'省去系带这一步':'脚背松紧自己调',p.closure==='套脚'?'套脚结构，近看鞋口与鞋面':'系带结构，按自己的脚背调整',p.color)+await I(p.b,38,248,724,380)+box(38,650,724,111,p.notes[0][0],p.notes[0][1],p.color);
 mains.push(await writeAsset(model,'主图02_穿脱结构',body,800));
 body=header(p.regular?'同款选购，先看版本':'秋冬加绒，认准版本',p.regular?'常规 / 加绒分别选择，价格以所选规格为准':'当前商品为加绒版，外观与鞋口分别看',p.color);
 body+=await I(p.fleece||p.c,42,248,p.fleece?350:716,330,p.fleeceCrop||null);
 if(p.fleece)body+=T(427,330,'加绒款细节',35,p.color,700)+P(427,385,'本款加绒细节，内里版本看所选规格。',26,320);
 body+=box(42,610,716,145,p.regular?'别只看“最低价”':'按自己的脚型选择',p.regular?'最低价格可能对应其他版本；认准颜色里的加绒标识。':'袜子厚度、脚背与脚长一起考虑，拿不准先咨询。',p.color);
 mains.push(await writeAsset(model,'主图03_内里版本',body,800));
 body=header('配色先看清，再下单','按个人衣着和喜好选，不混用其他款图片',p.color);
 const cp=p.color_files||[p.a];const cn=p.color_names||['本款配色'];
 for(let i=0;i<Math.min(cp.length,3);i++){const yy=235+i*155;body+=await I(cp[i],42,yy,290,145)+T(365,yy+78,cn[i],32,p.color,700);}
 body+=T(42,758,p.regular?'常规和加绒规格分别确认':'本款加绒配色以规格选择为准',23,'#617264');mains.push(await writeAsset(model,'主图04_颜色选择',body,800));
 body=header('合脚，先从选码开始','脚长 + 脚背 + 袜厚，一起考虑',p.color)+await I(p.a,42,238,716,345,p.heroCrop)+P(50,623,p.guide,26,700,'#415442',43)+T(50,772,'选码参考不等于实测鞋内长',21,p.color,700);mains.push(await writeAsset(model,'主图05_选码提醒',body,800));
 body=header(p.closure==='套脚'?'出门省点事，先看穿脱':'日常好搭，也要合脚',p.closure==='套脚'?'一双休闲鞋，先解决每天穿鞋的小麻烦':'看清鞋型轮廓，再结合脚型和内里选择',p.color)+await I(p.c,42,250,716,450);
 body+=box(42,736,716,220,p.closure==='套脚'?'少一道系鞋带步骤':'松紧与搭配，自己掌握',p.closure==='套脚'?'套脚结构适合偏好免系带的人；穿鞋时可用手整理鞋口和后跟，结合自己的脚型与穿袜习惯选择。':'系带可以按脚背调整，配色与轮廓可结合日常裤装选择；通勤、下楼出门，搭配自己常穿的衣服。',p.color)+footer(p,1100);details.push(await writeAsset(model,'详情01_需求与选择',body,1100));
 body=header('近看结构，选得明白','具体到这双鞋，少一点空泛形容',p.color)+await I(p.a,42,245,716,370,p.structureCrop);
 p.notes.forEach(([title,copy],i)=>body+=box(42,650+i*145,716,128,title,copy,p.color));body+=footer(p,1170);details.push(await writeAsset(model,'详情02_实物结构讲解',body,1170));
 body=header(p.regular?'常规还是加绒，选清楚':'加绒版本，秋冬日常选',p.regular?'不要只按外观和最低价格判断内里':'外观结构与内里版本分开看',p.color);
 if(p.fleece)body+=await I(p.fleece,42,248,716,380,p.fleeceCrop||null)+T(48,680,'加绒内里细节展示',27,p.color,700);
 else body+=await I(p.b,42,248,716,360)+P(48,653,'图示为本款外观；内里版本以当前商品规格为准。',25,704);
 body+=box(42,724,344,220,p.regular?'常规版':'加绒版',p.regular?'选择常规规格；按自己的日常穿袜情况参考选码。':'当前商品仅为加绒版本；结合脚长和袜厚选择。',p.color)+box(404,724,354,220,'加绒选购提醒','多一层内里，包裹感可能不同；厚袜不要直接照搬薄袜习惯。',p.color)+footer(p,1100);details.push(await writeAsset(model,'详情03_版本区别',body,1100));
 const ch=Math.max(1080,300+cp.length*255+160);body=header('配色和版本，逐项核对','先选外观，再确认内里版本和尺码',p.color);
 for(let i=0;i<cp.length;i++){body+=await I(cp[i],42,240+i*255,390,235)+T(458,330+i*255,cn[i],31,p.color,700)+P(458,380+i*255,p.regular?'常规 / 加绒以对应规格为准':'本款加绒颜色',24,290);}
 body+=footer(p,ch);details.push(await writeAsset(model,'详情04_逐色对应',body,ch));
 body=header('看清鞋底，也看穿搭','纹路、侧墙与配色，近看再选择',p.color)+await I(model==='ZX9002'?p.c:p.b,42,250,716,470)+box(42,760,716,225,'日常休闲的穿着选择','外底材质：'+p.sole+'。侧墙轮廓与鞋面配色相互呼应，结合日常衣着选择；湿滑地面请留意脚下。',p.color)+footer(p,1100);details.push(await writeAsset(model,'详情05_外底与适用',body,1100));
 body=header('选码先看脚长，再看脚背','同一码，脚型和袜子不同，感受也可能不同',p.color)+footDiagram(242)+P(48,562,p.guide,29,704,'#405440',49);
 body+=box(42,720,716,230,'拿不准时，把这三项告诉客服','① 较长一只脚的脚长  ② 脚背高低与前掌宽窄感受  ③ 常穿薄袜还是厚袜。按这款、这版判断，不全店统一加一码。',p.color)+footer(p,1100);details.push(await writeAsset(model,'详情06_脚型袜厚选码',body,1100));
 const count=p.end_size-p.start_size+1,hh=390+count*54+170;body=header('本款脚长参考表','单位：厘米 · 参考脚长，非鞋内长实测',p.color)+R(42,238,716,60,p.color,10)+T(205,279,'鞋码',29,'#fff',700)+T(485,279,'参考脚长',29,'#fff',700);
 for(let i=0;i<count;i++){const size=p.start_size+i,y=310+i*54;body+=R(42,y,716,50,i%2?'#e7ece5':'#fff',6)+T(218,y+35,size,27)+T(530,y+35,(22.5+(size-35)*.5).toFixed(1),27);}
 body+=P(48,350+count*54,'两脚分别测量，参考较长的一只；脚背、脚围和袜厚会影响穿着感受。标准参考不替代逐款试穿。',24,704,'#62715f',39)+footer(p,hh);details.push(await writeAsset(model,'详情07_脚长参考表',body,hh));
 body=header('下单前，这几件事看清楚','版本、颜色、尺码和服务，逐项确认',p.color);
 const facts=[['鞋面 / 外底','织物 / '+p.sole],['穿脱结构',p.closure],['内里选择',p.regular?'常规 / 加绒可选':'加绒版'],['尺码范围',p.start_size+'—'+p.end_size+'码'],['配送与售后','包邮范围、偏远地区运费及退换服务，以订单页和店铺现行规则为准。']];
 let y=240;for(const [a,b]of facts){const h=a==='配送与售后'?205:108;body+=box(42,y,716,h,a,b,p.color);y+=h+14;}
 body+=footer(p,1160);details.push(await writeAsset(model,'详情08_参数与服务',body,1160));
 const inputs=[...new Set([p.a,p.b,p.c,p.fleece,...cp].filter(Boolean))];const sourceEvidence=await Promise.all(inputs.map(async f=>({path:f,sha256:hash(await fs.readFile(f))})));
 plan.models[model]={canonical:p.canonical,title:p.title,shortTitle:p.shortTitle,titleWeight:weight,closure:p.closure,sizes:[p.start_size,p.end_size],versions:p.regular?['常规','加绒']:['加绒'],sourceEvidence,main_files:mains.map(x=>x.path),main_assets:mains,detail_files:details,identity_note:p.source_scope||'沿当前单款证据和正式对象对应；不重绘实物、不改品牌属性',publication:{state:'PREPARED_PENDING_LIVE_READ',prices:'UNCHANGED_REQUIRED',coupons:'UNCHANGED_REQUIRED',sku_identity:'UNCHANGED_REQUIRED',size_measurements:'PENDING_FACTORY'}};
 console.log(JSON.stringify({model,main:mains.length,details:details.length,titleWeight:weight}));
}
await fs.writeFile(root+'/数据/重点商品优化.json',JSON.stringify(plan,null,2)+'\n');
let cards='';for(const [m,p]of Object.entries(plan.models)){cards+=`<section id="${m}"><h2>${x(m)} <small>${x(p.title)}</small></h2><p>制作完成；正式提交状态以实时回读为准。价格、优惠、规格与履约不作调整。</p><h3>主图</h3><div class="gallery">${p.main_assets.map(a=>`<figure><img src="${path.relative(path.resolve(root+'/.local'),path.resolve(a.path)).split(path.sep).map(encodeURIComponent).join('/')}"><figcaption>${x(a.role)}</figcaption></figure>`).join('')}</div><h3>详情</h3><div class="gallery details">${p.detail_files.map(a=>`<figure><img loading="lazy" src="${path.relative(path.resolve(root+'/.local'),path.resolve(a.path)).split(path.sep).map(encodeURIComponent).join('/')}"><figcaption>${x(a.role)}</figcaption></figure>`).join('')}</div></section>`;}
const doc=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>重点商品图文当前审核</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei";margin:0;background:#f3f4ef;color:#27362f}main{max-width:1440px;padding:30px;margin:auto}h1{font-size:30px}section{margin:30px 0;padding:25px;background:white;border-radius:14px}small{display:block;font-size:18px;color:#647367}nav a{margin-right:20px;color:#356650}.gallery{display:grid;grid-template-columns:repeat(5,1fr);gap:13px}.gallery.details{grid-template-columns:repeat(4,1fr)}figure{margin:0}img{width:100%;border:1px solid #dce3dc;cursor:zoom-in}figcaption{font-size:13px}dialog{border:0;padding:10px;max-width:94vw;max-height:94vh}dialog img{width:auto;max-width:88vw;max-height:87vh;object-fit:contain}button{padding:8px 16px} @media(max-width:800px){.gallery,.gallery.details{grid-template-columns:repeat(2,1fr)}main{padding:15px}}</style><main><h1>重点商品图文 · 当前审核</h1><p>2026-10-17｜消费者需求、实物结构、版本与选码。点击图片可放大。原件保留，图中没有添加品牌身份或未经实测的性能数值。</p><nav>${Object.keys(plan.models).map(m=>`<a href="#${m}">${m}</a>`).join('')}<a href="重点商品实测与拍摄.html">实测表与逐款脚本</a></nav>${cards}</main><dialog id="zoom"><button onclick="this.parentElement.close()">关闭</button><br><img></dialog><script>document.querySelectorAll('figure img').forEach(img=>img.addEventListener('click',()=>{document.querySelector('#zoom img').src=img.src;document.querySelector('#zoom').showModal()}));</script></html>`;
await fs.writeFile(root+'/.local/重点商品图文审核.html',doc);
