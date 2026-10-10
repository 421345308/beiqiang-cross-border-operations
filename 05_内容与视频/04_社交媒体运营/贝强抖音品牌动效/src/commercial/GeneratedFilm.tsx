import React from 'react';
import {AbsoluteFill,Audio,Sequence,interpolate,staticFile,useCurrentFrame} from 'remotion';
import {FullPhoto,Identity,clamp,motion,palette} from './common';

const shots=[
  {file:'sock-city.png',title:'穿上，\n就出发。',sub:'针织袜子鞋 · 套脚设计',size:119},
  {file:'generated-hero-v3.png',title:'贝强',sub:'针织袜子鞋',size:142},
  {file:'generated-knit-v3.png',title:'针织鞋面',sub:'看得见的细密织纹',size:94},
  {file:'generated-wear-v3.png',title:'套脚设计',sub:'少一步系带',size:103},
  {file:'sock-comfort.png',title:'袜套鞋口',sub:'从鞋面，延伸到脚踝',size:96},
  {file:'sock-park.png',title:'把舒适，\n穿进日常。',sub:'通勤 · 散步 · 日常穿搭',size:104},
  {file:'generated-hero-v3.png',title:'贝强鞋业',sub:'针织袜子鞋',size:106},
];

export const Scene:React.FC<{index:number;duration:number;cover?:boolean;fadeIn?:boolean}>=({index,duration,cover=false,fadeIn=false})=> {
  const current=useCurrentFrame();const f=cover?70:current;const s=shots[index];
  const p=motion(f,[5,25],[0,1]);const detail=index===2;
  const scale=detail?motion(f,[0,duration],[1,1.055]):motion(f,[0,duration],[1.045,1]);
  return <AbsoluteFill style={{opacity:(index===0&&!fadeIn)||cover?1:motion(f,[0,12],[0,1]),background:palette.paper,color:palette.ink,overflow:'hidden'}}>
    <FullPhoto file={s.file} zoom={scale} dx={detail?motion(f,[0,duration],[0,-10]):motion(f,[0,duration],[-10,0])}/>
    {index===5&&<AbsoluteFill style={{opacity:motion(f,[85,101],[0,1])}}><FullPhoto file="sock-city.png" zoom={motion(f,[85,duration],[1.04,1])}/></AbsoluteFill>}
    <AbsoluteFill style={{background:detail?'linear-gradient(180deg,rgba(246,239,226,.3),transparent 30%,transparent 75%,rgba(0,0,0,.35))':'linear-gradient(180deg,rgba(244,239,228,.64),rgba(244,239,228,.08) 32%,transparent 58%,rgba(244,239,228,.18))'}}/>
    <Identity/>
    <div style={{position:'absolute',left:86,top:index===0?267:280,width:890,opacity:p,transform:`translateY(${(1-p)*24}px)`}}>
      <div style={{whiteSpace:'pre-line',fontSize:s.size,fontWeight:500,lineHeight:1.28,letterSpacing:3}}>{s.title}</div>
      {!detail&&<div style={{fontSize:47,lineHeight:1.45,marginTop:28,letterSpacing:2,color:'#655b4c'}}>{s.sub}</div>}
    </div>
    {detail&&<div style={{position:'absolute',left:86,bottom:190,color:'#faf4e9',fontSize:47,letterSpacing:2,opacity:motion(f,[20,40],[0,1])}}>{s.sub}</div>}
    {index===3&&<div style={{position:'absolute',left:86,bottom:190,fontSize:42,letterSpacing:2,opacity:motion(f,[20,40],[0,1])}}>提拉鞋口，穿上出发。</div>}
    {index===6&&<>
      <div style={{position:'absolute',left:86,bottom:232,fontSize:45,letterSpacing:2,opacity:motion(f,[20,42],[0,1])}}>一脚穿上，自在出发。</div>
      <div style={{position:'absolute',left:86,bottom:168,fontSize:27,color:'#5e5548',letterSpacing:1,opacity:motion(f,[30,50],[0,1])}}>泉州贝强鞋业服饰有限公司</div>
    </>}
  </AbsoluteFill>;
};

export const GeneratedBrandFilm:React.FC=()=> <AbsoluteFill style={{background:palette.paper,fontFamily:'"Microsoft YaHei",sans-serif'}}>
  <Sequence from={0} durationInFrames={117}><Scene index={0} duration={117}/></Sequence>
  <Sequence from={105} durationInFrames={117}><Scene index={1} duration={117}/></Sequence>
  <Sequence from={210} durationInFrames={132}><Scene index={2} duration={132}/></Sequence>
  <Sequence from={330} durationInFrames={132}><Scene index={3} duration={132}/></Sequence>
  <Sequence from={450} durationInFrames={147}><Scene index={4} duration={147}/></Sequence>
  <Sequence from={585} durationInFrames={192}><Scene index={5} duration={192}/></Sequence>
  <Sequence from={765} durationInFrames={135}><Scene index={6} duration={135}/></Sequence>
  <Audio src={staticFile('music-commercial.wav')} volume={f=>interpolate(f,[0,18,852,900],[0,.9,.9,0],clamp)}/>
</AbsoluteFill>;

export const GeneratedCover:React.FC=()=> <AbsoluteFill style={{fontFamily:'"Microsoft YaHei",sans-serif'}}><Scene index={6} duration={135} cover/></AbsoluteFill>;
