import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

export const palette={paper:'#f2ede3',ink:'#282a28',accent:'#a46648',muted:'#727468'};
export const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
export const motion=(f:number,range:number[],values:number[])=>interpolate(f,range,values,{...clamp,easing:Easing.bezier(.18,.7,.25,1)});
export const Frame:React.FC<{children:React.ReactNode;fade?:boolean}>=({children,fade=true})=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:palette.paper,overflow:'hidden',opacity:fade?motion(f,[0,12],[0,1]):1}}>{children}</AbsoluteFill>;
};
export const Identity:React.FC<{light?:boolean}>=({light=false})=><div style={{position:'absolute',left:86,top:135,color:light?'#fff':palette.ink,fontSize:35,fontWeight:600,letterSpacing:5}}>贝强<span style={{marginLeft:22,fontFamily:'Arial',fontSize:25,letterSpacing:5,fontWeight:400}}>BEIQIANG</span></div>;
export const Heading:React.FC<{title:string;sub?:string;kicker?:string;top?:number}>=({title,sub,kicker,top=280})=>{
 const f=useCurrentFrame();
 return <div style={{position:'absolute',left:86,top,color:palette.ink,width:898}}>
  {kicker&&<div style={{fontSize:29,letterSpacing:5,color:palette.accent,marginBottom:25,opacity:motion(f,[3,18],[0,1])}}>{kicker}</div>}
  <div style={{fontSize:91,fontWeight:600,lineHeight:1.35,letterSpacing:2,opacity:motion(f,[5,22],[0,1]),translate:`0 ${motion(f,[5,25],[28,0])}px`}}>{title}</div>
  {sub&&<div style={{fontSize:47,lineHeight:1.5,letterSpacing:2,marginTop:22,color:palette.muted,opacity:motion(f,[16,34],[0,1])}}>{sub}</div>}
 </div>;
};
export const Product:React.FC<{file?:string;top?:number;width?:number;left?:number;zoom?:number}>=({file='sock-hero.png',top=590,width=1010,left=35,zoom=1})=><Img src={staticFile(file)} style={{position:'absolute',width,height:width,objectFit:'contain',top,left,scale:zoom}}/>;
export const Floor:React.FC<{top?:number}>=({top=1530})=><div style={{position:'absolute',top,left:100,width:880,height:90,borderRadius:'50%',background:'radial-gradient(ellipse,rgba(61,51,35,.19),transparent 70%)',filter:'blur(11px)'}}/>;
export const FullPhoto:React.FC<{file:string;zoom?:number;dx?:number}>=({file,zoom=1,dx=0})=><Img src={staticFile(file)} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'cover',scale:zoom,translate:`${dx}px 0`}}/>;
