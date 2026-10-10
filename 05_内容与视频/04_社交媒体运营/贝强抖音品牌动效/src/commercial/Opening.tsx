import React from 'react';
import {AbsoluteFill,useCurrentFrame} from 'remotion';
import {Frame,FullPhoto,Identity,motion,palette} from './common';
export const Opening:React.FC=()=>{
 const f=useCurrentFrame();
 return <Frame fade={false}>
  <FullPhoto file="sock-city.png" zoom={motion(f,[0,132],[1.08,1])} dx={motion(f,[0,132],[-16,0])}/>
  <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(242,237,227,.65),transparent 45%,transparent 75%,rgba(242,237,227,.7))'}}/>
  <Identity/>
  <div style={{position:'absolute',left:86,top:280,color:palette.ink,fontSize:122,lineHeight:1.35,fontWeight:600,letterSpacing:5,opacity:motion(f,[0,12],[.5,1]),translate:`0 ${motion(f,[0,22],[18,0])}px`}}>穿上，<br/>就出发。</div>
  <div style={{position:'absolute',left:88,top:650,color:palette.ink,fontSize:46,letterSpacing:3,opacity:motion(f,[18,40],[0,1])}}>针织袜子鞋 · 套脚设计</div>
 </Frame>;
};
