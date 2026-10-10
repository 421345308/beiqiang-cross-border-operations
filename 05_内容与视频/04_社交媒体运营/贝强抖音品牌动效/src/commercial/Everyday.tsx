import React from 'react';
import {AbsoluteFill,useCurrentFrame} from 'remotion';
import {Frame,FullPhoto,Identity,motion,palette} from './common';
export const Everyday:React.FC=()=>{
 const f=useCurrentFrame();const selected=f<68?0:f<140?1:2;
 return <Frame>
  <FullPhoto file="sock-city.png" zoom={motion(f,[0,207],[1,1.07])}/>
  <div style={{position:'absolute',inset:0,opacity:motion(f,[64,80],[0,1])}}><FullPhoto file="sock-park.png" zoom={motion(f,[64,207],[1.06,1])}/></div>
  <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(242,237,227,.8),transparent 60%)'}}/>
  <Identity/>
  <div style={{position:'absolute',left:86,top:300,color:palette.ink,fontSize:92,fontWeight:600,lineHeight:1.5}}>穿进<br/>你的每一天。</div>
  <div style={{position:'absolute',left:86,top:680,display:'flex',gap:27,fontSize:43,letterSpacing:1}}>{['通勤','散步','日常穿搭'].map((label,i)=><div key={label} style={{color:selected===i?palette.accent:palette.ink,opacity:selected===i?1:.55,borderBottom:`${selected===i?3:0}px solid ${palette.accent}`,paddingBottom:12}}>{label}</div>)}</div>
 </Frame>;
};
