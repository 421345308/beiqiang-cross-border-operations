import React from 'react';
import {AbsoluteFill,useCurrentFrame} from 'remotion';
import {Frame,FullPhoto,Heading,Identity,motion} from './common';
export const Comfort:React.FC=()=>{
 const f=useCurrentFrame();
 return <Frame>
  <FullPhoto file="sock-comfort.png" zoom={motion(f,[0,177],[1.035,1])}/>
  <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(242,237,227,.6),transparent 47%)'}}/>
  <Identity/><Heading kicker="03 / EVERYDAY COMFORT" title="袜套鞋口" sub="把舒适，穿进日常"/>
 </Frame>;
};
