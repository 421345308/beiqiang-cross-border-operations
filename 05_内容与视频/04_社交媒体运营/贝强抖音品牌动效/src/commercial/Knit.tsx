import React from 'react';
import {Img,staticFile,useCurrentFrame} from 'remotion';
import {Frame,Heading,Identity,motion,palette} from './common';
export const Knit:React.FC=()=>{
 const f=useCurrentFrame();
 return <Frame><Identity/><Heading kicker="01 / KNIT" title="针织鞋面" sub="看得见的细密织纹"/>
  <div style={{position:'absolute',left:0,top:655,width:1080,height:1265,overflow:'hidden'}}>
   <Img src={staticFile('sock-knit.png')} style={{width:'100%',height:'100%',objectFit:'cover',scale:motion(f,[0,177],[1.12,1]),translate:`${motion(f,[0,177],[-18,0])}px 0`}}/>
   <div style={{position:'absolute',inset:0,background:'linear-gradient(180deg,rgba(242,237,227,.25),transparent 20%)'}}/>
   <svg viewBox="0 0 1080 1265" style={{position:'absolute',inset:0,width:'100%',height:'100%',opacity:.65}}>
    {[0,1,2].map(i=><path key={i} d={`M 80 ${850+i*36} C 280 ${580+i*36}, 570 ${940+i*36}, 990 ${470+i*36}`} fill="none" stroke="#d8b79a" strokeWidth={1.4} strokeDasharray={1500} strokeDashoffset={motion(f,[28+i*7,115+i*7],[1500,0])}/>)}
   </svg>
  </div>
  <div style={{position:'absolute',left:88,top:579,width:motion(f,[20,75],[0,905]),height:2,background:palette.accent,opacity:.5}}/>
 </Frame>;
};
