import React from 'react';
import {useCurrentFrame} from 'remotion';
import {Floor,Frame,Heading,Identity,Product,motion,palette} from './common';
export const SlipOn:React.FC=()=>{
 const f=useCurrentFrame();
 const stage=f<58?0:f<128?1:2;
 return <Frame><Identity/><Heading kicker="02 / SLIP ON" title="套脚设计" sub="少一步系带"/>
  <div style={{position:'absolute',left:0,top:620,width:1080,height:945,overflow:'hidden',background:'#eae4d9'}}>
   <Floor top={850}/>
   <div style={{position:'absolute',inset:0,opacity:motion(f,[48,60],[1,0])}}><Product top={-85} width={1020} left={30}/></div>
   <div style={{position:'absolute',inset:0,opacity:motion(f,[48,60,120,132],[0,1,1,0])}}><Product file="sock-entry.png" top={-85} width={1020} left={30}/></div>
   <div style={{position:'absolute',inset:0,opacity:motion(f,[120,132],[0,1])}}><Product file="sock-worn.png" top={-85} width={1020} left={30}/></div>
  </div>
  <div style={{position:'absolute',left:112,top:1660,display:'flex',width:856,justifyContent:'space-between'}}>{['准备','穿上','出发'].map((label,i)=><div key={label} style={{display:'flex',alignItems:'center',gap:18,color:stage===i?palette.ink:'#929186',fontSize:47,opacity:motion(f,[15+i*8,34+i*8],[0,1])}}><span style={{width:52,height:52,borderRadius:40,border:`2px solid ${stage===i?palette.accent:'#c5bdb0'}`,background:stage===i?palette.accent:'transparent',color:stage===i?palette.paper:'#929186',fontFamily:'Arial',fontSize:30,display:'flex',alignItems:'center',justifyContent:'center'}}>{i+1}</span>{label}</div>)}</div>
 </Frame>;
};
