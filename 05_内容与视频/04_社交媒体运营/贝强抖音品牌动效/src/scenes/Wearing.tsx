import React from 'react';
import {AbsoluteFill, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';

const font='"Microsoft YaHei", "PingFang SC", sans-serif';
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(.22,1,.36,1);
const enter=(f:number,a=8,b=30)=>interpolate(f,[a,b],[0,1],{...clamp,easing:ease});

const Structure:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#eee7db',overflow:'hidden',color:'#2e2923',fontFamily:font}}>
  <Img src={staticFile('sock-comfort.png')} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${interpolate(f,[0,144],[1,1.01],clamp)})`,transformOrigin:'55% 60%'}}/>
  <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(255,249,237,.18),transparent 40%)'}}/>
  <div style={{position:'absolute',left:90,top:184,fontSize:90,letterSpacing:3,opacity:enter(f),translate:`0px ${22*(1-enter(f))}px`}}>免系带</div>
  <div style={{position:'absolute',left:94,top:316,fontSize:46,letterSpacing:2,opacity:enter(f,18,40)}}>一脚蹬设计</div>
  <div style={{position:'absolute',left:94,top:464,fontSize:44,letterSpacing:2,opacity:enter(f,44,66)}}>袜式鞋口 · 套脚结构</div>
 </AbsoluteFill>;
};

const Action:React.FC<{src:string;title:string;subtitle?:string;cameraMove?:boolean}>=({src,title,subtitle,cameraMove=false})=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#e4d6c3',overflow:'hidden',fontFamily:font}}>
  <OffthreadVideo src={staticFile(src)} muted style={{width:'100%',height:'100%',objectFit:'cover',transform:cameraMove?`scale(${interpolate(f,[0,240],[1,1.03],clamp)})`:'none',transformOrigin:'50% 52%'}}/>
  <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(34,27,19,.28),transparent 32%,transparent 80%,rgba(34,27,19,.12))'}}/>
  <div style={{position:'absolute',left:88,right:80,top:156,color:'#fff9ed',fontSize:84,fontWeight:500,lineHeight:1.2,letterSpacing:2,textShadow:'0 3px 18px rgba(35,25,15,.14)',opacity:enter(f,12,35),translate:`0px ${20*(1-enter(f,12,35))}px`}}>{title}</div>
  {subtitle&&<div style={{position:'absolute',left:92,top:290,color:'#fff9ed',fontSize:44,letterSpacing:1,opacity:enter(f,40,63)}}>{subtitle}</div>}
 </AbsoluteFill>;
};

const Bridge:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'#eee9de',overflow:'hidden',fontFamily:font,color:'#352f28'}}>
  <Img src={staticFile('campaign-fabric.png')} style={{position:'absolute',inset:-80,width:1240,height:2080,objectFit:'cover',transform:`scale(1.18) translateY(${interpolate(f,[0,96],[30,-35],clamp)}px)`}}/>
  <AbsoluteFill style={{background:'rgba(255,249,239,.15)'}}/>
  <div style={{position:'absolute',left:90,top:660,fontSize:104,lineHeight:1.48,fontWeight:500,letterSpacing:4}}>
   {['让日常','自在一点'].map((s,i)=><div key={s} style={{overflow:'hidden'}}><div style={{translate:`0px ${125*(1-enter(f,i*9,i*9+25))}px`}}>{s}</div></div>)}
  </div>
 </AbsoluteFill>;
};

/** 8–23s: visible structure, full collar release, full step, then a tactile bridge. */
export const Wearing:React.FC=()=> <AbsoluteFill>
 <Sequence from={0} durationInFrames={144}><Structure/></Sequence>
 <Sequence from={144} durationInFrames={240}><Action src="dynamic/release.mp4" title="穿好，就出发。"/></Sequence>
 <Sequence from={384} durationInFrames={240}><Action src="dynamic/step-v2.mp4" title="迈开步。" subtitle="把舒服，带进日常" cameraMove/></Sequence>
 <Sequence from={624} durationInFrames={96}><Bridge/></Sequence>
</AbsoluteFill>;
