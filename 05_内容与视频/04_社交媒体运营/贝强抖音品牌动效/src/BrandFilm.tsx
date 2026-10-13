import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Opening} from './Opening';
import {Closing} from './Closing';
import {TIMELINE, TOTAL_FRAMES} from './timeline';
const font='"Microsoft YaHei", "PingFang SC", sans-serif';
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(.22,1,.36,1);
const Texture:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#221f1c',overflow:'hidden'}}>
  <Img src={staticFile('sock-knit.png')} style={{width:'100%',height:'100%',objectFit:'cover',scale:interpolate(f,[0,36],[1.10,1.04],{...clamp,easing:ease}),transformOrigin:'65% 58%'}}/>
  <div style={{position:'absolute',left:74,bottom:275,fontFamily:font,color:'#fff5e6',fontSize:55,letterSpacing:4}}>波纹针织鞋面</div>
 </AbsoluteFill>;
};
const Collar:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#ede5d8',overflow:'hidden',fontFamily:font}}>
  <Img src={staticFile('campaign-collar.png')} style={{width:'100%',height:'100%',objectFit:'cover',scale:interpolate(f,[0,60],[1.035,1],{...clamp,easing:ease}),transformOrigin:'55% 58%'}}/>
  <div style={{position:'absolute',left:76,top:212,color:'#342e25',fontSize:78,letterSpacing:5,lineHeight:1.2}}>袜式鞋口</div>
  <div style={{position:'absolute',left:80,top:328,color:'#5c5143',fontSize:34,letterSpacing:3}}>免系带 · 套脚结构</div>
 </AbsoluteFill>;
};
const Footage:React.FC<{src:string;sourceFrame?:number;walk?:boolean}>=({src,sourceFrame=0,walk=false})=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#ede5d8',overflow:'hidden'}}>
  <OffthreadVideo src={staticFile(src)} startFrom={sourceFrame} muted style={{width:'100%',height:'100%',objectFit:'cover'}}/>
  {walk&&<div style={{position:'absolute',left:76,top:210,fontFamily:font,color:'#40372d',fontSize:56,letterSpacing:4,opacity:interpolate(f,[68,78,128,143],[0,1,1,0],clamp),textShadow:'0 1px 12px rgba(255,248,235,.7)'}}>穿进日常</div>}
 </AbsoluteFill>;
};
export const BrandFilm:React.FC=()=> <AbsoluteFill style={{background:'#ede5d8'}}>
 <Audio src={staticFile('brand-score.wav')} volume={1}/>
 {TIMELINE.map(s=><Sequence key={s.id} from={s.from} durationInFrames={s.frames}>
  {s.id==='opening'?<Opening/>:s.id==='closing'?<Closing/>:s.id==='knit'?<Texture/>:s.id==='collar'?<Collar/>:<Footage src={s.src} sourceFrame={s.sourceFrame} walk={s.id==='walk'}/>}
 </Sequence>)}
</AbsoluteFill>;
export {TOTAL_FRAMES};
