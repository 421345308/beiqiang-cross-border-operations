import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Floor,Frame,Identity,Product,motion,palette} from './common';
export const ProductScene:React.FC=()=>{
 const f=useCurrentFrame();
 return <Frame><Identity/>
  <div style={{position:'absolute',left:86,top:290,color:palette.ink,opacity:motion(f,[3,24],[0,1])}}>
   <div style={{fontSize:110,fontWeight:600,letterSpacing:5}}>贝强</div>
   <div style={{fontSize:85,fontWeight:500,letterSpacing:3,marginTop:10}}>针织袜子鞋</div>
  </div>
  <div style={{position:'absolute',left:88,top:600,height:3,width:motion(f,[20,60],[0,150]),background:palette.accent}}/>
  <Floor top={1510}/><Product top={585} zoom={motion(f,[0,117],[.96,1])}/>
  <div style={{position:'absolute',left:86,top:1620,width:900,display:'flex',justifyContent:'space-between',fontSize:41,color:palette.ink,opacity:motion(f,[35,55],[0,1])}}>{['针织鞋面','袜套鞋口','套脚设计'].map((text,i)=><div key={text}><span style={{color:palette.accent,fontFamily:'Arial',fontSize:25,marginRight:12}}>0{i+1}</span>{text}</div>)}</div>
 </Frame>;
};
