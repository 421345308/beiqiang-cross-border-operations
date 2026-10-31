/** Explicit known shop profiles; read-only, never discovers sessions or changes platforms. */
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {MiaoshouConnector} from './connectors/miaoshou/index.mjs';
const profiles = [
  {id:'legacy',title:'既有零售店',url:new URL('../01_业务脚本/抖店妙手/.local/session.json',import.meta.url)},
  {id:'brand',title:'雷丹森羊品牌店',url:new URL('../01_业务脚本/抖店妙手/.local/shops/brand/session.json',import.meta.url)}
];
export async function readShop(profile, {load=async p=>JSON.parse(await readFile(p,'utf8')),factory=options=>new MiaoshouConnector(options)}={}) {
  const base={id:profile.id,title:profile.title,scope:'显式单页商品读取；平台填报库存不等于实物库存'};
  let saved;try {saved=await load(profile.url);}catch{return {...base,ok:false,error:{code:'profile_unavailable',message:'此店配置缺失或不可读取'},collectedAt:null};}
  if(!/^\d+$/.test(String(saved.expectedShopId || '')))return {...base,ok:false,error:{code:'target_missing',message:'此店配置未指定目标店铺，未读取商品'},collectedAt:null};
  const connector=factory({sessionPath:fileURLToPath(profile.url),expectedShopId:String(saved.expectedShopId)});
  const result=await connector.execute('products',{page:1,pageSize:100,isDraft:false});
  return {...base,...result};
}
export async function readShops(){return {shops:await Promise.all(profiles.map(profile=>readShop(profile))),notice:'按店隔离读取；未执行任何平台修改。列表为第一页，完整目录需显式继续分页。'};}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try { process.stdout.write(JSON.stringify(await readShops())); } catch { process.stdout.write(JSON.stringify({shops:[],error:'抖店数据暂不可读'})); process.exitCode=1; }
}
