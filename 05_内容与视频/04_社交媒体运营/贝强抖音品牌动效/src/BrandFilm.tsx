import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
const FPS=24;
const font='"Microsoft YaHei", "PingFang SC", sans-serif';
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(.22,1,.36,1);
const enter=(f:number,start=3,end=14)=>interpolate(f,[start,end],[0,1],{...clamp,easing:ease});

const Caption:React.FC<{title:string;sub?:string;light?:boolean;opening?:boolean}>=({title,sub,light=false,opening=false})=>{
 const f=useCurrentFrame();
 return <>
  <div style={{position:'absolute',left:82,top:opening?132:195,right:opening?490:145,fontFamily:font,color:light?'#fff8ec':'#302b25',
   fontSize:opening?64:79,lineHeight:1.2,fontWeight:500,letterSpacing:3,
   opacity:enter(f,opening?0:3,opening?8:14),translate:`0px ${interpolate(f,[0,14],[12,0],clamp)}px`,
   textShadow:light?'0 2px 15px rgba(20,15,10,.2)':'none'}}>{title}</div>
  {sub&&<div style={{position:'absolute',left:86,top:opening?222:307,right:opening?490:145,fontFamily:font,color:light?'#fff8ec':'#51483d',
   fontSize:opening?31:38,lineHeight:1.35,letterSpacing:2,opacity:enter(f,10,22)}}>{sub}</div>}
 </>;
};
const Footage:React.FC<{src:string;title:string;sub?:string;sourceStart?:number;opening?:boolean}>=({src,title,sub,sourceStart=0,opening=false})=>{
 const walk=src.endsWith('walking.mp4'); const rest=src.endsWith('settling.mp4');
 return <AbsoluteFill style={{backgroundColor:'#ede5d8'}}>
  <div style={{position:'absolute',left:0,right:0,top:walk?330:0,bottom:0}}>
   <OffthreadVideo src={staticFile(src)} startFrom={Math.round(sourceStart*FPS)} muted style={{width:'100%',height:'100%',objectFit:'contain'}}/>
  </div>
  {rest&&<div style={{position:'absolute',left:0,right:0,top:0,height:420,background:'linear-gradient(180deg,rgba(32,27,20,.48),rgba(32,27,20,.25) 65%,transparent)'}}/>}
  <Caption title={title} sub={sub} opening={opening} light={rest}/>
 </AbsoluteFill>;
};
const Still:React.FC<{src:string;title:string;sub?:string;duration:number;dark?:boolean}>=({src,title,sub,duration,dark=false})=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{backgroundColor:'#ede5d8',overflow:'hidden'}}>
  <Img src={staticFile(src)} style={{width:'100%',height:'100%',objectFit:'contain',scale:interpolate(f,[0,duration*FPS],[1,1.012],clamp),transformOrigin:'50% 55%'}}/>
  {dark&&<AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.20),transparent 30%)'}}/>}
  <Caption title={title} sub={sub} light={dark}/>
 </AbsoluteFill>;
};
const Closing:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{backgroundColor:'#eee7dc',overflow:'hidden',fontFamily:font,color:'#2d2821'}}>
  <Img src={staticFile('campaign-product.png')} style={{width:'100%',height:'100%',objectFit:'contain',scale:interpolate(f,[0,108],[1,1.008],clamp),transformOrigin:'50% 69%'}}/>
  <div style={{position:'absolute',left:86,top:142,opacity:enter(f,3,15),translate:`0px ${14*(1-enter(f,3,15))}px`}}>
   <div style={{fontSize:138,fontWeight:600,letterSpacing:11,lineHeight:1.2}}>贝强</div>
   <div style={{fontSize:27,letterSpacing:8,marginTop:17}}>BEIQIANG</div>
  </div>
  <div style={{position:'absolute',left:90,top:402,fontSize:52,letterSpacing:4,opacity:enter(f,14,27)}}>针织袜子鞋</div>
  <div style={{position:'absolute',left:90,right:140,top:510,fontSize:43,letterSpacing:2,lineHeight:1.35,color:'#564e43',opacity:enter(f,34,48)}}>把日常，穿得舒服一点</div>
 </AbsoluteFill>;
};
/** One 32-second film; all generated action plays at native speed without cropping. */
export const BrandFilm:React.FC=()=>{
 const f=useCurrentFrame(); const dark=(f>=72&&f<108)||(f>=504&&f<600);
 return <AbsoluteFill style={{backgroundColor:'#eee7dc'}}>
  <Audio src={staticFile('brand-score.wav')} volume={1}/>
  <Sequence from={0} durationInFrames={72}><Footage src="dynamic/walking.mp4" title="针织袜子鞋" sub="把日常，穿得舒服一点" opening/></Sequence>
  <Sequence from={72} durationInFrames={36}><Still src="sock-knit.png" title="从织纹，靠近一点。" duration={1.5} dark/></Sequence>
  <Sequence from={108} durationInFrames={72}><Footage src="dynamic/tactile.mp4" title="触得到的针织纹理"/></Sequence>
  <Sequence from={180} durationInFrames={48}><Still src="campaign-collar.png" title="袜式鞋口" sub="免系带 · 套脚结构" duration={2}/></Sequence>
  <Sequence from={228} durationInFrames={120}><Footage src="dynamic/donning-clean.mp4" title="一脚蹬，穿好就走。"/></Sequence>
  <Sequence from={348} durationInFrames={84}><Footage src="dynamic/release.mp4" title="理好鞋口，再出门。"/></Sequence>
  <Sequence from={432} durationInFrames={72}><Footage src="dynamic/walking.mp4" sourceStart={3} title="走一段。"/></Sequence>
  <Sequence from={504} durationInFrames={96}><Footage src="dynamic/settling.mp4" title="歇一会儿。"/></Sequence>
  <Sequence from={600} durationInFrames={60}><Still src="campaign-overhead.png" title="针织 · 套脚 · 日常" duration={2.5}/></Sequence>
  <Sequence from={660} durationInFrames={108}><Closing/></Sequence>
  {f<660&&<div style={{position:'absolute',left:85,top:f<72?65:91,fontFamily:font,fontSize:29,fontWeight:600,letterSpacing:3,color:dark?'#fff8ec':'#302b25'}}>贝强 <span style={{fontSize:23,letterSpacing:4,marginLeft:12}}>BEIQIANG</span></div>}
 </AbsoluteFill>;
};
