import React from 'react';
import {AbsoluteFill,Audio,Img,Sequence,interpolate,staticFile,useCurrentFrame} from 'remotion';
import {FullPhoto,Identity,clamp,motion,palette} from './common';
import {Scene as ProductScene} from './GeneratedFilm';

// Reuse the accepted generated textile. The ribbon is an abstract brand motif.
const Cloth:React.FC<{f:number;closing?:boolean}>=({f,closing=false})=><div style={{
  position:'absolute',left:motion(f,[0,135],closing?[-240,-110]:[-450,-160]),
  top:closing?930:890,width:1580,height:1053,opacity:closing?.88:.72,
  translate:`0 ${Math.sin(f/60)*12}px`,rotate:`${motion(f,[0,135],[-12,1])}deg`,
}}>
  <Img src={staticFile('ribbon-v2.png')} style={{width:'100%',height:'100%',objectFit:'contain'}}/>
</div>;

const WarmScene:React.FC<{closing?:boolean;cover?:boolean}>=({closing=false,cover=false})=>{
  const current=useCurrentFrame();const f=cover?85:current;
  const p=motion(f,[6,27],[0,1]);
  return <AbsoluteFill style={{background:'#eee4d3',overflow:'hidden',color:palette.ink,opacity:closing&&!cover?motion(f,[0,12],[0,1]):1}}>
    <AbsoluteFill style={{opacity:closing?.28:.85}}>
      <FullPhoto file="space-v2.png" zoom={motion(f,[0,135],[1.13,1.025])} dx={motion(f,[0,135],[-16,0])}/>
    </AbsoluteFill>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(247,240,226,.68),transparent 42%,transparent 82%,rgba(242,232,212,.76))'}}/>
    <Cloth f={f} closing={closing}/>
    {closing&&<>
      <div style={{position:'absolute',left:130,top:1490,width:800,height:100,borderRadius:'50%',background:'radial-gradient(ellipse,rgba(67,49,30,.2),transparent 70%)',filter:'blur(13px)'}}/>
      <Img src={staticFile('sock-hero.png')} style={{position:'absolute',left:60,top:630,width:960,height:960,objectFit:'contain',scale:motion(f,[0,135],[.98,1.015]),translate:`0 ${motion(f,[0,135],[12,-6])}px`,filter:'drop-shadow(0 20px 22px #634b2a25)'}}/>
    </>}
    <Identity/>
    <div style={{position:'absolute',left:86,top:280,width:890,opacity:p,translate:`0 ${(1-p)*24}px`}}>
      <div style={{fontSize:closing?106:102,lineHeight:1.3,letterSpacing:3,whiteSpace:'pre-line',fontWeight:500}}>{closing?'贝强鞋业':'细密织纹，\n日常自在。'}</div>
      <div style={{fontSize:47,lineHeight:1.45,marginTop:28,letterSpacing:2,color:'#655b4c'}}>{closing?'针织袜子鞋':'贝强 · 针织袜子鞋'}</div>
    </div>
    {closing&&<div style={{position:'absolute',left:86,bottom:168,opacity:motion(f,[20,42],[0,1])}}>
      <div style={{fontSize:45,letterSpacing:2,marginBottom:30}}>一脚穿上，自在出发。</div>
      <div style={{fontSize:27,letterSpacing:1,color:'#5e5548'}}>泉州贝强鞋业服饰有限公司</div>
    </div>}
  </AbsoluteFill>;
};

const WeaveTransition:React.FC=()=>{
  const f=useCurrentFrame();
  return <AbsoluteFill style={{overflow:'hidden',pointerEvents:'none'}}>
    <div style={{position:'absolute',left:motion(f,[0,30],[-2150,1350]),top:250,width:2200,height:1467,rotate:'-15deg',scale:1.3,opacity:interpolate(f,[0,7,20,30],[0,1,1,0],clamp)}}>
      <Img src={staticFile('ribbon-v2.png')} style={{width:'100%',height:'100%',objectFit:'contain'}}/>
    </div>
  </AbsoluteFill>;
};

export const WarmGeneratedBrandFilm:React.FC=()=> <AbsoluteFill style={{background:palette.paper,fontFamily:'"Microsoft YaHei",sans-serif'}}>
  <Sequence from={0} durationInFrames={132}><WarmScene/></Sequence>
  <Sequence from={120} durationInFrames={117}><ProductScene index={0} duration={117} fadeIn/></Sequence>
  <Sequence from={225} durationInFrames={117}><ProductScene index={1} duration={117}/></Sequence>
  <Sequence from={330} durationInFrames={132}><ProductScene index={2} duration={132}/></Sequence>
  <Sequence from={450} durationInFrames={132}><ProductScene index={3} duration={132}/></Sequence>
  <Sequence from={570} durationInFrames={147}><ProductScene index={4} duration={147}/></Sequence>
  <Sequence from={705} durationInFrames={192}><ProductScene index={5} duration={192}/></Sequence>
  <Sequence from={885} durationInFrames={135}><WarmScene closing/></Sequence>
  <Sequence from={318} durationInFrames={30}><WeaveTransition/></Sequence>
  <Sequence from={873} durationInFrames={30}><WeaveTransition/></Sequence>
  <Audio src={staticFile('music-commercial.wav')} volume={f=>interpolate(f,[0,18,972,1020],[0,.9,.9,0],clamp)}/>
</AbsoluteFill>;

export const WarmGeneratedCover:React.FC=()=> <AbsoluteFill style={{fontFamily:'"Microsoft YaHei",sans-serif'}}><WarmScene closing cover/></AbsoluteFill>;
