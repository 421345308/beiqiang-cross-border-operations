import React from 'react';
import {AbsoluteFill, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=Easing.bezier(.22,1,.36,1);
const font='"Microsoft YaHei", "PingFang SC", sans-serif';
export const OPENING_SHOT_BOUNDARIES=[0,144,240,384] as const;
const Product:React.FC=()=>{
 const f=useCurrentFrame();
 return <AbsoluteFill style={{background:'radial-gradient(ellipse at 55% 30%,#fffdf7,#efe8dc 65%,#e2d7c5)',overflow:'hidden',color:'#282520',fontFamily:font}}>
  <div style={{position:'absolute',left:88,top:132,fontSize:43,letterSpacing:5,fontWeight:600}}>贝强 BEIQIANG</div>
  <div style={{position:'absolute',left:88,top:296,fontSize:94,lineHeight:1.2,fontWeight:500,letterSpacing:2}}>针织袜子鞋</div>
  <div style={{position:'absolute',left:120,top:1465,width:835,height:90,background:'radial-gradient(ellipse,rgba(78,59,37,.22),transparent 70%)',filter:'blur(14px)'}}/>
  <Img src={staticFile('sock-hero.png')} style={{position:'absolute',left:18,top:465,width:1038,height:1038,objectFit:'contain',transform:`translateY(${interpolate(f,[0,144],[24,-12],clamp)}px) scale(${interpolate(f,[0,144],[.94,1.015],clamp)})`,filter:'drop-shadow(0 24px 28px rgba(74,53,33,.11))'}}/>
 </AbsoluteFill>;
};
const Detail:React.FC<{src:string;title:string;sub:string;dark?:boolean;duration:number}>=({src,title,sub,dark=false,duration})=>{
 const f=useCurrentFrame();const a=interpolate(f,[5,24],[0,1],{...clamp,easing:ease});
 return <AbsoluteFill style={{background:dark?'#1c1915':'#eee7db',overflow:'hidden',fontFamily:font,color:dark?'#fff8ed':'#282520'}}>
  <Img src={staticFile(src)} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${interpolate(f,[0,duration],dark?[1.08,1.025]:[1,1.025],clamp)})`,transformOrigin:dark?'55% 58%':'52% 62%'}}/>
  {dark&&<AbsoluteFill style={{background:'linear-gradient(180deg,transparent 55%,rgba(10,8,6,.65))'}}/>}
  <div style={{position:'absolute',left:88,right:85,top:dark?1458:146,fontSize:84,lineHeight:1.2,letterSpacing:3,fontWeight:500,opacity:a,transform:`translateY(${18*(1-a)}px)`}}>{title}</div>
  <div style={{position:'absolute',left:91,top:dark?1588:266,fontSize:42,letterSpacing:2,opacity:interpolate(f,[18,36],[0,1],clamp)}}>{sub}</div>
 </AbsoluteFill>;
};
/** Product on frame zero; subsequent views identify visible black-shoe details. */
export const Opening:React.FC=()=> <AbsoluteFill>
 <Sequence from={0} durationInFrames={144}><Product/></Sequence>
 <Sequence from={144} durationInFrames={96}><Detail src="sock-knit.png" title="针织鞋面" sub="细密织纹，清晰可见" dark duration={96}/></Sequence>
 <Sequence from={240} durationInFrames={144}><Detail src="campaign-collar.png" title="袜式鞋口" sub="从鞋口，看套脚结构" duration={144}/></Sequence>
</AbsoluteFill>;
