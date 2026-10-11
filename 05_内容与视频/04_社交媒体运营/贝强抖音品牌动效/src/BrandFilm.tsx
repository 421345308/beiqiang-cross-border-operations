import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {TIMELINE, FPS, TOTAL_FRAMES} from './timeline';
const font='"Microsoft YaHei", "PingFang SC", sans-serif';
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(.22,1,.36,1);
const enter=(f:number,start=0,end=8)=>interpolate(f,[start,end],[0,1],{...clamp,easing:ease});

const Brand:React.FC<{light?:boolean}>=({light=false})=><div style={{position:'absolute',left:82,top:82,fontFamily:font,fontSize:29,fontWeight:600,letterSpacing:3,color:light?'#fff5e6':'#302b25'}}>贝强 <span style={{fontSize:23,letterSpacing:4,marginLeft:12}}>BEIQIANG</span></div>;
const Caption:React.FC<{title:string;sub?:string;light?:boolean;immediate?:boolean;header?:boolean}>=({title,sub,light=false,immediate=false,header=false})=>{
 const f=useCurrentFrame();
 return <>
  <div style={{position:'absolute',left:82,top:header?180:190,right:125,fontFamily:font,color:light?'#fff8ec':'#302b25',fontSize:header?70:76,lineHeight:1.25,fontWeight:500,letterSpacing:3,opacity:immediate?1:enter(f),translate:immediate?'0px 0px':`0px ${12*(1-enter(f))}px`,textShadow:light?'0 2px 15px rgba(20,15,10,.2)':'none'}}>{title}</div>
  {sub&&<div style={{position:'absolute',left:86,top:header?275:305,right:145,fontFamily:font,color:light?'#eee2d0':'#51483d',fontSize:header?31:36,lineHeight:1.35,letterSpacing:2,opacity:immediate?1:enter(f,5,13)}}>{sub}</div>}
 </>;
};
/** Raster shoe identity stays fixed. Lighting moves across its alpha silhouette. */
const ProductOpening:React.FC=()=>{
 const f=useCurrentFrame();
 const lightX=interpolate(f,[0,36,72],[-300,880,1200],clamp);
 const mask={maskImage:`url("${staticFile('sock-hero.png')}")`,maskSize:'contain',maskRepeat:'no-repeat',maskPosition:'center'};
 return <AbsoluteFill style={{overflow:'hidden',background:'#25211e',fontFamily:font,color:'#fff1dc'}}>
  <AbsoluteFill style={{background:`radial-gradient(ellipse at ${68+f*.15}% 52%,#95806a 0%,#4b4036 31%,#25211e 68%)`}}/>
  <div style={{position:'absolute',left:82,top:188,right:130,fontSize:126,letterSpacing:7,lineHeight:1.16,fontWeight:600}}>
   {['针织','袜子鞋'].map((t,i)=><div key={t} style={{overflow:'hidden'}}><div style={{opacity:enter(f,i*4,i*4+10),translate:`0px ${52*(1-enter(f,i*4,i*4+10))}px`}}>{t}</div></div>)}
  </div>
  <div style={{position:'absolute',left:86,top:524,fontSize:27,letterSpacing:9,opacity:enter(f,12,20),color:'#d7c1a2'}}>KNIT / SLIP-ON</div>
  <div style={{position:'absolute',left:150,top:1480,width:790,height:86,borderRadius:'50%',background:'rgba(0,0,0,.45)',filter:'blur(34px)',scale:interpolate(f,[0,45],[1.08,1],{...clamp,easing:ease})}}/>
  <div style={{position:'absolute',left:52,top:664,width:976,height:976,scale:interpolate(f,[0,54],[1.07,1],{...clamp,easing:ease}),translate:`0px ${interpolate(f,[0,38],[20,0],{...clamp,easing:ease})}px`}}>
   <Img src={staticFile('sock-hero.png')} style={{width:'100%',height:'100%',filter:'brightness(1.35) contrast(1.02)',objectFit:'contain'}}/>
   <AbsoluteFill style={{...mask,background:`linear-gradient(110deg,transparent ${lightX-190}px,rgba(255,231,196,.22) ${lightX}px,transparent ${lightX+190}px)`,mixBlendMode:'screen'}}/>
  </div>
  <div style={{position:'absolute',left:85,top:1684,fontSize:36,letterSpacing:3,color:'#ebdbc6',opacity:enter(f,20,28)}}>免系带 · 套脚结构</div>
  <Brand light/>
 </AbsoluteFill>;
};
const Footage:React.FC<{src:string;title:string;sub?:string;sourceFrame?:number;immediate?:boolean}>=({src,title,sub,sourceFrame=0,immediate=false})=>{
 const walk=src.endsWith('walking.mp4');const rest=src.endsWith('settling.mp4');
 return <AbsoluteFill style={{backgroundColor:'#ede5d8'}}>
  <div style={{position:'absolute',left:0,right:0,top:walk?330:0,bottom:0}}><OffthreadVideo src={staticFile(src)} startFrom={sourceFrame} muted style={{width:'100%',height:'100%',objectFit:'contain'}}/></div>
  {rest&&<div style={{position:'absolute',left:0,right:0,top:0,height:420,background:'linear-gradient(180deg,rgba(32,27,20,.48),rgba(32,27,20,.25) 65%,transparent)'}}/>}
  <Brand light={rest}/><Caption title={title} sub={sub} light={rest} header={walk} immediate={immediate}/>
 </AbsoluteFill>;
};
const Still:React.FC<{src:string;title:string;sub?:string;duration:number;dark?:boolean;detail?:boolean;immediate?:boolean}>=({src,title,sub,duration,dark=false,detail=false,immediate=false})=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{backgroundColor:'#ede5d8',overflow:'hidden'}}>
  <Img src={staticFile(src)} style={{width:'100%',height:'100%',objectFit:'contain',scale:interpolate(f,[0,duration*FPS],detail?[1.15,1.18]:[1.025,1],{...clamp,easing:ease}),transformOrigin:detail?'52% 58%':'50% 55%'}}/>
  {dark&&<AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.50),transparent 42%)'}}/>}
  <Brand light={dark}/><Caption title={title} sub={sub} light={dark} immediate={immediate}/>
 </AbsoluteFill>;
};
const Closing:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{backgroundColor:'#eee7dc',overflow:'hidden',fontFamily:font,color:'#2d2821'}}>
  <Img src={staticFile('campaign-product.png')} style={{width:'100%',height:'100%',objectFit:'contain',scale:interpolate(f,[0,72],[1.025,1],{...clamp,easing:ease}),transformOrigin:'50% 69%'}}/>
  <div style={{position:'absolute',left:86,top:142,opacity:enter(f,0,8),translate:`0px ${12*(1-enter(f,0,8))}px`}}><div style={{fontSize:138,fontWeight:600,letterSpacing:11,lineHeight:1.2}}>贝强</div><div style={{fontSize:27,letterSpacing:8,marginTop:17}}>BEIQIANG</div></div>
  <div style={{position:'absolute',left:90,top:402,fontSize:52,letterSpacing:4,opacity:enter(f,6,14)}}>针织袜子鞋</div>
  <div style={{position:'absolute',left:90,right:140,top:510,fontSize:43,letterSpacing:2,lineHeight:1.35,color:'#564e43',opacity:enter(f,14,24)}}>把日常，穿得舒服一点</div>
 </AbsoluteFill>;
};
export const BrandFilm:React.FC=()=> <AbsoluteFill style={{backgroundColor:'#eee7dc'}}>
 <Audio src={staticFile('brand-score.wav')} volume={1}/>
 {TIMELINE.map(s=><Sequence key={s.id} from={s.from} durationInFrames={s.frames}>
  {s.id==='opening'?<ProductOpening/>:s.id==='closing'?<Closing/>:s.video?<Footage src={s.src} sourceFrame={s.sourceFrame} title={s.title} sub={s.sub} immediate={s.immediate}/>:<Still src={s.src} title={s.title} sub={s.sub} duration={s.frames/FPS} dark={s.dark} detail={s.detail} immediate={s.immediate}/>}
 </Sequence>)}
</AbsoluteFill>;
export {TOTAL_FRAMES};
